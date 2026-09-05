import os
import glob
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine, text
from geoalchemy2 import Geometry, WKTElement
import warnings

warnings.filterwarnings('ignore')

def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    return create_engine(db_url) if db_url else None

def safe_upsert(df, table_name, engine, unique_keys):
    if df.empty:
        return
    temp_table = f"temp_{table_name}"
    
    if 'geom' in df.columns:
        df['geom'] = df['geom'].apply(lambda x: WKTElement(x.wkt, srid=4326) if pd.notnull(x) else None)
        dtype = {'geom': Geometry(geometry_type='GEOMETRY', srid=4326)}
        df.to_sql(temp_table, engine, if_exists='replace', index=False, dtype=dtype)
    else:
        df.to_sql(temp_table, engine, if_exists='replace', index=False)
    
    with engine.begin() as conn:
        columns = ", ".join(df.columns)
        updates = ", ".join([f"{col} = EXCLUDED.{col}" for col in df.columns if col not in unique_keys])
        conflict_keys = ", ".join(unique_keys)
        
        sql = f"""
        INSERT INTO {table_name} ({columns})
        SELECT * FROM {temp_table}
        ON CONFLICT ({conflict_keys}) DO UPDATE SET {updates};
        """
        if updates:
            conn.execute(text(sql))
        else:
            sql = f"""
            INSERT INTO {table_name} ({columns})
            SELECT * FROM {temp_table}
            ON CONFLICT ({conflict_keys}) DO NOTHING;
            """
            conn.execute(text(sql))
        conn.execute(text(f"DROP TABLE {temp_table};"))
    print(f"Upserted {len(df)} rows into {table_name}")

def transform_locations(engine):
    print("Transforming Village Locations...")
    try:
        df = pd.read_excel("datasets/Village Latitude & Longitude.xlsx")
        cols = list(df.columns)
        vc = next((c for c in cols if 'Village LGD Code' in str(c)), None)
        lat = next((c for c in cols if 'Latitude' in str(c)), None)
        lon = next((c for c in cols if 'Longitude' in str(c)), None)
        
        if all([vc, lat, lon]):
            df = df.dropna(subset=[vc, lat, lon])
            df = df.rename(columns={vc: 'village_lgd_code', lat: 'latitude', lon: 'longitude'})
            # Clean non-numeric or float representations
            df['village_lgd_code'] = df['village_lgd_code'].apply(lambda x: str(int(float(x))) if pd.notnull(x) and str(x).replace('.','',1).isdigit() else str(x))
            
            df = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
            df = df.rename(columns={'geometry': 'geom'})
            df['coordinate_source'] = 'LGD Portal'
            
            with engine.connect() as conn:
                existing_villages = pd.read_sql("SELECT village_lgd_code FROM villages", conn)
            
            # Keep only villages that exist in the DB
            df = df[df['village_lgd_code'].isin(existing_villages['village_lgd_code'])]
            
            # Drop duplicates if any
            df = df.drop_duplicates(subset=['village_lgd_code'])
            
            if not df.empty:
                safe_upsert(df[['village_lgd_code', 'latitude', 'longitude', 'geom', 'coordinate_source']], 'locations', engine, ['village_lgd_code'])
            else:
                print("No matching village codes found for locations!")
    except Exception as e:
        print(f"Locations error: {e}")

def transform_pmgsy(engine):
    print("Transforming PMGSY spatial data...")
    # Facilities
    try:
        f_path = glob.glob("datasets/*/Facilities.shp")
        if f_path:
            gdf = gpd.read_file(f_path[0])
            if gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            # Usually columns like 'FACILITY_N', 'FACILITY_T', etc.
            # We'll map generic columns to the schema
            gdf['asset_type'] = gdf['FACILITY_T'] if 'FACILITY_T' in gdf.columns else 'facility'
            gdf['asset_name'] = gdf['FACILITY_N'] if 'FACILITY_N' in gdf.columns else gdf['asset_type']
            gdf['district_lgd_code'] = '2734' # Hardcoding Kolhapur district code based on where it was found, normally we parse this from the layer or file path.
            gdf['source'] = 'PMGSY'
            gdf = gdf.rename(columns={'geometry': 'geom'})
            gdf['latitude'] = gdf['geom'].y
            gdf['longitude'] = gdf['geom'].x
            # PMGSY tables have uuid as PK, no easy upsert without a unique key, but let's insert them using to_sql since it's initial load
            temp_df = gdf[['asset_type', 'asset_name', 'district_lgd_code', 'latitude', 'longitude', 'geom', 'source']].copy()
            
            # Because asset_id is UUID default gen_random_uuid(), we can just append
            temp_df['geom'] = temp_df['geom'].apply(lambda x: WKTElement(x.wkt, srid=4326) if pd.notnull(x) else None)
            temp_df.to_sql('rural_assets', engine, if_exists='append', index=False, dtype={'geom': Geometry(geometry_type='GEOMETRY', srid=4326)})
            print(f"Inserted {len(temp_df)} facilities into rural_assets")
    except Exception as e:
        print(f"PMGSY Facilities error: {e}")

    # Roads
    try:
        r_path = glob.glob("datasets/*/Road_DRRP2.shp") + glob.glob("datasets/*/Candidate_Road.shp")
        for rp in r_path:
            gdf = gpd.read_file(rp)
            if gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            gdf['road_name'] = gdf['ROAD_NAME'] if 'ROAD_NAME' in gdf.columns else 'Unknown Road'
            gdf['road_class'] = gdf['ROAD_CATEG'] if 'ROAD_CATEG' in gdf.columns else 'Rural Road'
            gdf['district_lgd_code'] = '2734'
            gdf['source'] = 'PMGSY'
            gdf = gdf.rename(columns={'geometry': 'geom'})
            temp_df = gdf[['road_name', 'road_class', 'district_lgd_code', 'geom', 'source']].copy()
            temp_df['geom'] = temp_df['geom'].apply(lambda x: WKTElement(x.wkt, srid=4326) if pd.notnull(x) else None)
            temp_df.to_sql('rural_roads', engine, if_exists='append', index=False, dtype={'geom': Geometry(geometry_type='GEOMETRY', srid=4326)})
            print(f"Inserted {len(temp_df)} roads from {rp} into rural_roads")
    except Exception as e:
        print(f"PMGSY Roads error: {e}")

if __name__ == "__main__":
    engine = get_engine()
    if engine:
        transform_locations(engine)
        transform_pmgsy(engine)
        print("Data Ingestion Complete!")
