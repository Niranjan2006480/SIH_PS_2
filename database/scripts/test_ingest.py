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
    
    # Check if geometry column exists
    if 'geom' in df.columns:
        # Convert shapely geometries to WKTElement for PostGIS
        # GeoPandas might not directly work with pandas to_sql for geometries, we use WKT
        df['geom'] = df['geom'].apply(lambda x: WKTElement(x.wkt, srid=4326) if x is not None else None)
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

def transform_lgd(engine):
    print("Transforming LGD data...")
    files = glob.glob("datasets/*/LGD*.xlsx")
    for file in files:
        if "Nashik" in file:
            continue
        print(f"Processing {file}")
        try:
            df = pd.read_excel(file, engine='calamine', skiprows=2)  # Typically government LGD has header rows
            # Based on standard LGD format: State Code, State Name, District Code, District Name, Sub District Code, Sub District Name, Village Code, Village Name
            # Find matching columns via partial match
            cols = df.columns
            state_code_col = next((c for c in cols if 'State Code' in str(c)), None)
            state_name_col = next((c for c in cols if 'State Name' in str(c)), None)
            dist_code_col = next((c for c in cols if 'District Code' in str(c)), None)
            dist_name_col = next((c for c in cols if 'District Name' in str(c)), None)
            sub_code_col = next((c for c in cols if 'Sub District Code' in str(c) or 'Block Code' in str(c)), None)
            sub_name_col = next((c for c in cols if 'Sub District Name' in str(c) or 'Block Name' in str(c)), None)
            vill_code_col = next((c for c in cols if 'Village Code' in str(c)), None)
            vill_name_col = next((c for c in cols if 'Village Name' in str(c)), None)
            
            if not all([state_code_col, dist_code_col, sub_code_col, vill_code_col]):
                print(f"Skipping {file}: Column mismatch")
                continue
                
            df = df.dropna(subset=[vill_code_col])
            
            # States
            states = df[[state_code_col, state_name_col]].drop_duplicates().rename(columns={
                state_code_col: 'state_code', state_name_col: 'state_name'
            })
            states['state_code'] = states['state_code'].astype(int).astype(str).str.zfill(2)
            states['state_name_normalized'] = states['state_name'].str.lower().str.strip()
            safe_upsert(states, 'states', engine, ['state_code'])
            
            # Districts
            districts = df[[dist_code_col, state_code_col, dist_name_col]].drop_duplicates().rename(columns={
                dist_code_col: 'district_lgd_code', state_code_col: 'state_code', dist_name_col: 'district_name'
            })
            districts['district_lgd_code'] = districts['district_lgd_code'].astype(int).astype(str)
            districts['state_code'] = districts['state_code'].astype(int).astype(str).str.zfill(2)
            districts['district_name_normalized'] = districts['district_name'].str.lower().str.strip()
            districts['is_pilot_active'] = True
            safe_upsert(districts, 'districts', engine, ['district_lgd_code'])
            
            # Subdistricts
            subds = df[[sub_code_col, dist_code_col, sub_name_col]].drop_duplicates().rename(columns={
                sub_code_col: 'subdistrict_lgd_code', dist_code_col: 'district_lgd_code', sub_name_col: 'subdistrict_name'
            })
            subds['subdistrict_lgd_code'] = subds['subdistrict_lgd_code'].astype(int).astype(str)
            subds['district_lgd_code'] = subds['district_lgd_code'].astype(int).astype(str)
            subds['subdistrict_name_normalized'] = subds['subdistrict_name'].str.lower().str.strip()
            safe_upsert(subds, 'subdistricts', engine, ['subdistrict_lgd_code'])
            
            # Villages
            villages = df[[vill_code_col, sub_code_col, dist_code_col, state_code_col, vill_name_col]].drop_duplicates().rename(columns={
                vill_code_col: 'village_lgd_code', sub_code_col: 'subdistrict_lgd_code',
                dist_code_col: 'district_lgd_code', state_code_col: 'state_code', vill_name_col: 'village_name'
            })
            villages['village_lgd_code'] = villages['village_lgd_code'].astype(int).astype(str)
            villages['subdistrict_lgd_code'] = villages['subdistrict_lgd_code'].astype(int).astype(str)
            villages['district_lgd_code'] = villages['district_lgd_code'].astype(int).astype(str)
            villages['state_code'] = villages['state_code'].astype(int).astype(str).str.zfill(2)
            villages['village_name_normalized'] = villages['village_name'].str.lower().str.strip()
            safe_upsert(villages, 'villages', engine, ['village_lgd_code'])
            
        except Exception as e:
            print(f"Error parsing LGD {file}: {e}")

if __name__ == "__main__":
    engine = get_engine()
    print("Starting LGD ingestion...")
    transform_lgd(engine)
