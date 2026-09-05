import os
from sqlalchemy import create_engine, text

db_url = os.environ.get('DATABASE_URL')
engine = create_engine(db_url)

sql = text("""
UPDATE rural_assets 
SET facility_category = CASE 
    WHEN asset_type ILIKE '%health%' OR asset_type ILIKE '%hospital%' OR asset_type ILIKE '%clinic%' THEN 'Healthcare' 
    WHEN asset_type ILIKE '%school%' OR asset_type ILIKE '%college%' OR asset_type ILIKE '%education%' THEN 'Education' 
    WHEN asset_type ILIKE '%bank%' OR asset_type ILIKE '%atm%' THEN 'Financial' 
    WHEN asset_type ILIKE '%market%' OR asset_type ILIKE '%shop%' THEN 'Commercial' 
    WHEN asset_type ILIKE '%post%' OR asset_type ILIKE '%police%' THEN 'Government' 
    ELSE 'Other' 
END 
WHERE facility_category IS NULL;
""")

with engine.begin() as conn:
    conn.execute(sql)
print("Updated facility_category!")
