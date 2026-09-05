import os
import glob
import geopandas as gpd
from sqlalchemy import create_engine, text

db_url = os.environ.get('DATABASE_URL')
engine = create_engine(db_url)

print("Truncating rural_assets...")
with engine.begin() as conn:
    conn.execute(text("TRUNCATE TABLE rural_assets RESTART IDENTITY CASCADE;"))

print("Searching for facility shapefiles...")
shapefiles = glob.glob('datasets/**/*Facilities*.shp', recursive=True) + glob.glob('datasets/**/*facilities*.shp', recursive=True)
shapefiles = list(set(shapefiles))

for shp in shapefiles:
    print(f"Processing {shp}...")
    try:
        gdf = gpd.read_file(shp)
        if gdf.crs is None or gdf.crs.to_string() != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
            
        gdf['asset_type'] = gdf['FAC_DESC'] if 'FAC_DESC' in gdf.columns else 'facility'
        gdf['facility_category'] = gdf['FAC_CATEGO'] if 'FAC_CATEGO' in gdf.columns else None
        gdf['asset_name'] = gdf['FAC_DESC'] if 'FAC_DESC' in gdf.columns else 'facility'
        
        gdf['district_lgd_code'] = None
        gdf['source'] = 'PMGSY'
        
        gdf = gdf.rename(columns={'geometry': 'geom'}).set_geometry('geom')
        gdf['latitude'] = gdf['geom'].y
        gdf['longitude'] = gdf['geom'].x
        
        allowed_cols = ['asset_type', 'facility_category', 'asset_name', 'district_lgd_code', 'latitude', 'longitude', 'source', 'geom']
        cols_to_keep = [c for c in gdf.columns if c in allowed_cols]
        gdf = gdf[cols_to_keep]
        
        chunk_size = 5000
        total = 0
        for i in range(0, len(gdf), chunk_size):
            chunk = gdf.iloc[i:i+chunk_size]
            chunk.to_postgis('rural_assets', engine, if_exists='append', index=False)
            total += len(chunk)
            print(f"  Inserted chunk {i//chunk_size + 1} ({len(chunk)} records)")
            
        print(f"Total inserted for {shp}: {total}")
        
    except Exception as e:
        print(f"Error processing {shp}: {e}")
