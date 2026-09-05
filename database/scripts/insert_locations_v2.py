import os
import time
import requests
import pandas as pd
from sqlalchemy import create_engine
from rapidfuzz import process, fuzz
import geopandas as gpd

db_url = os.environ.get('DATABASE_URL')
engine = create_engine(db_url)

print("Loading all villages from DB...")
villages_df = pd.read_sql(
    "SELECT village_lgd_code, village_name, village_name_normalized, v.district_lgd_code, "
    "d.district_name, d.district_name_normalized FROM villages v JOIN districts d USING(district_lgd_code)",
    engine
)
print(f"Loaded {len(villages_df)} villages from DB.")

print("Loading IN_clean_Latitude_and_Longitude.csv...")
latlon_df = pd.read_csv("datasets/IN_clean Latitude and Longitude.csv")
latlon_df = latlon_df.dropna(subset=['latitude', 'longitude', 'place_name'])

# Filter to Maharashtra
latlon_df = latlon_df[latlon_df['admin_name1'] == 'Maharashtra']

def normalize(name):
    return str(name).lower().strip().replace('.', '').replace(',', '')

latlon_df['place_normalized'] = latlon_df['place_name'].apply(normalize)
latlon_df['district_normalized'] = latlon_df['admin_name2'].apply(normalize)

matched_rows = []
unmatched = []

print(f"Loaded {len(latlon_df)} coordinate points for Maharashtra.")

for _, village in villages_df.iterrows():
    village_dist_norm = str(village['district_name_normalized'])
    # Map Ahilyanagar to Ahmednagar if needed
    if village_dist_norm == 'ahilyanagar':
        village_dist_norm = 'ahmednagar'
        
    candidates = latlon_df[latlon_df['district_normalized'] == village_dist_norm]
    
    if candidates.empty:
        # Fallback to match across all maharashtra if district spelling differs?
        # Actually safer to stick to district matching if we can.
        unmatched.append(village)
        continue

    match = process.extractOne(
        str(village['village_name_normalized']),
        candidates['place_normalized'].tolist(),
        scorer=fuzz.ratio,
        score_cutoff=85
    )

    if match:
        matched_place = candidates[candidates['place_normalized'] == match[0]].iloc[0]
        matched_rows.append({
            'village_lgd_code': village['village_lgd_code'],
            'latitude': matched_place['latitude'],
            'longitude': matched_place['longitude'],
            'coordinate_source': 'postal_office_proximity',
            'coordinate_accuracy': 'high' if match[1] >= 95 else 'medium'
        })
    else:
        unmatched.append(village)

matched_df = pd.DataFrame(matched_rows)
print(f"Matched: {len(matched_df)} / {len(villages_df)}")
print(f"Unmatched: {len(unmatched)}")

if not matched_df.empty:
    gdf = gpd.GeoDataFrame(matched_df, geometry=gpd.points_from_xy(matched_df.longitude, matched_df.latitude), crs="EPSG:4326")
    gdf = gdf.rename(columns={'geometry': 'geom'}).set_geometry('geom')
    
    # We shouldn't insert duplicates if locations already has rows, so we can use ON CONFLICT DO NOTHING
    # But to_postgis doesn't support ON CONFLICT natively easily, so let's clear the table first for a clean run
    # since this is a new run with a better dataset.
    with engine.begin() as conn:
        from sqlalchemy import text
        conn.execute(text("TRUNCATE TABLE locations;"))
        
    gdf.to_postgis('locations', engine, if_exists='append', index=False)
    print("Matched locations inserted.")

def nominatim_geocode(village_name, district_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': f"{village_name}, {district_name}, Maharashtra, India",
        'format': 'json', 'limit': 1
    }
    headers = {'User-Agent': 'SIH26091-UdyamSaathi/1.0'}
    r = requests.get(url, params=params, headers=headers)
    time.sleep(1.1)
    results = r.json()
    if results:
        return float(results[0]['lat']), float(results[0]['lon'])
    return None, None

fallback_rows = []
print("Running Nominatim fallback for a sample of 25 unmatched villages...")
for village in unmatched[:25]:
    lat, lon = nominatim_geocode(village['village_name'], village['district_name'])
    if lat and lon:
        fallback_rows.append({
            'village_lgd_code': village['village_lgd_code'],
            'latitude': lat,
            'longitude': lon,
            'coordinate_source': 'nominatim_fallback',
            'coordinate_accuracy': 'low'
        })
        print(f"Found {village['village_name']} via Nominatim: {lat}, {lon}")
    else:
        print(f"Could not find {village['village_name']}")

if fallback_rows:
    fb_df = pd.DataFrame(fallback_rows)
    gdf_fb = gpd.GeoDataFrame(fb_df, geometry=gpd.points_from_xy(fb_df.longitude, fb_df.latitude), crs="EPSG:4326")
    gdf_fb = gdf_fb.rename(columns={'geometry': 'geom'}).set_geometry('geom')
    gdf_fb.to_postgis('locations', engine, if_exists='append', index=False)
    print("Fallback locations inserted.")
