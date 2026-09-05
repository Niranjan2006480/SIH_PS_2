import os
import glob
import pandas as pd
import geopandas as gpd
from sqlalchemy import create_engine
import warnings

warnings.filterwarnings('ignore')

def get_engine():
    db_url = os.environ.get("DATABASE_URL")
    return create_engine(db_url) if db_url else None

def process_pmgsy(engine):
    print("Processing PMGSY shapefiles...")
    # Facilities
    f_path = glob.glob('datasets/**/Facilities.shp', recursive=True)
    if f_path:
        gdf = gpd.read_file(f_path[0])
        if gdf.crs != "EPSG:4326": gdf = gdf.to_crs("EPSG:4326")
        gdf['asset_type'] = gdf['FACILITY_T'] if 'FACILITY_T' in gdf.columns else 'facility'
        gdf['asset_name'] = gdf['FACILITY_N'] if 'FACILITY_N' in gdf.columns else gdf['asset_type']
        gdf['district_lgd_code'] = '2734'
        gdf['source'] = 'PMGSY'
        gdf = gdf.rename(columns={'geometry': 'geom'}).set_geometry('geom')
        gdf['latitude'] = gdf['geom'].y
        gdf['longitude'] = gdf['geom'].x
        df = gdf[['asset_type', 'asset_name', 'district_lgd_code', 'latitude', 'longitude', 'geom', 'source']]
        df.to_postgis('rural_assets', engine, if_exists='append', index=False)
        print(f"Inserted {len(df)} into rural_assets")

    # Roads
    r_paths = glob.glob('datasets/**/Road_DRRP2.shp', recursive=True) + glob.glob('datasets/**/Candidate_Road.shp', recursive=True)
    for r_path in r_paths:
        if os.path.exists(r_path):
            gdf = gpd.read_file(r_path)
            if gdf.crs != "EPSG:4326": gdf = gdf.to_crs("EPSG:4326")
            gdf['road_name'] = gdf['ROAD_NAME'] if 'ROAD_NAME' in gdf.columns else 'Unknown Road'
            gdf['road_class'] = gdf['ROAD_CATEG'] if 'ROAD_CATEG' in gdf.columns else 'Rural Road'
            gdf['district_lgd_code'] = '2734'
            gdf['source'] = 'PMGSY'
            gdf = gdf.rename(columns={'geometry': 'geom'}).set_geometry('geom')
            df = gdf[['road_name', 'road_class', 'district_lgd_code', 'geom', 'source']]
            df.to_postgis('rural_roads', engine, if_exists='append', index=False)
            print(f"Inserted {len(df)} into rural_roads from {r_path}")

if __name__ == "__main__":
    engine = get_engine()
    if engine:
        process_pmgsy(engine)
        print("PMGSY spatial load complete!")
