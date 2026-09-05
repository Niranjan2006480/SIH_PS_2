import os
import glob
import geopandas as gpd
from sqlalchemy import create_engine

db_url = os.environ.get('DATABASE_URL')
engine = create_engine(db_url)

print("Searching for road shapefiles...")
shapefiles = glob.glob('datasets/**/*Road*.shp', recursive=True) + glob.glob('datasets/**/*road*.shp', recursive=True)
shapefiles = list(set(shapefiles))

print(f"Found {len(shapefiles)} road shapefiles to process.")

for shp in shapefiles:
    print(f"Processing {shp}...")
    try:
        gdf = gpd.read_file(shp)
        
        # Ensure CRS is set before transforming
        if gdf.crs is None:
            gdf.set_crs('EPSG:4326', inplace=True)
        elif gdf.crs.to_string() != 'EPSG:4326':
            gdf = gdf.to_crs('EPSG:4326')
            
        source = 'PMGSY_CANDIDATE' if 'Candidate' in shp else 'PMGSY_DRRP'
        
        # Schema columns: road_name, road_class, district_lgd_code, geom, source
        rename_dict = {}
        for col in gdf.columns:
            if col.upper() == 'ROAD_NAME':
                rename_dict[col] = 'road_name'
            elif col.upper() == 'ROAD_CATE' or col.upper() == 'ROAD_CAT' or col.upper() == 'ROAD_CLASS':
                rename_dict[col] = 'road_class'
                
        gdf = gdf.rename(columns=rename_dict)
        gdf['source'] = source
        
        # If geometry column is named something else
        if gdf.active_geometry_name != 'geom':
            gdf = gdf.rename_geometry('geom')
            
        # Add district_lgd_code (Pune = 536, Nashik = 515, Ahmednagar = 522)
        # Using a dummy value if needed, or extract from district name
        if 'district_lgd_code' not in gdf.columns:
            gdf['district_lgd_code'] = None # Allow null if schema allows, or set a default.
            
        allowed_cols = ['road_name', 'road_class', 'source', 'district_lgd_code', 'geom']
        cols_to_keep = [c for c in gdf.columns if c in allowed_cols]
        gdf = gdf[cols_to_keep]
        
        # Check if geom type is MultiLineString, cast to LineString if needed? The schema is LineString, 4326
        # Let's see if to_postgis can handle it natively or if we need to explode/cast.
        gdf = gdf.explode(index_parts=False) # Convert MultiLineString to LineString
        gdf = gdf[gdf.geometry.type == 'LineString'] # Filter out non-linestrings
        
        chunk_size = 1000
        total_inserted = 0
        for i in range(0, len(gdf), chunk_size):
            chunk = gdf.iloc[i:i+chunk_size]
            chunk.to_postgis('rural_roads', engine, if_exists='append', index=False)
            total_inserted += len(chunk)
            print(f"  Inserted chunk {i//chunk_size + 1} ({len(chunk)} records)")
            
        print(f"Total inserted for {shp}: {total_inserted}")
    except Exception as e:
        print(f"Error processing {shp}: {e}")

print("Done processing roads!")
