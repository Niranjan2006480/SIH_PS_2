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

def process_roads(engine):
    print("Processing PMGSY roads with chunks...")
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
            
            # Using chunksize to prevent statement timeout in Supabase
            df.to_postgis('rural_roads', engine, if_exists='append', index=False, chunksize=5000)
            print(f"Inserted {len(df)} into rural_roads from {r_path}")

if __name__ == "__main__":
    engine = get_engine()
    if engine:
        process_roads(engine)
        print("Roads load complete!")
