# SIH26091 Database Setup & Data Ingestion

This repository contains the complete PostgreSQL + PostGIS database schema, data transformation scripts, and validation routines for the UdyamSaathi Rural Business Feasibility Engine.

## 1. How to create the Supabase project
1. Log in to [Supabase](https://supabase.com/).
2. Create a new project. Choose a region close to your users (e.g., Mumbai, India).
3. Set a strong database password and save it securely.
4. Once the project is provisioned, go to **Project Settings -> Database** to find your connection string (`DATABASE_URL`).

## 2. How to enable PostGIS
The schema script automatically enables PostGIS, but to do it manually:
1. Open the Supabase SQL Editor.
2. Run the following command:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```
3. Alternatively, you can enable it via the Supabase Dashboard under **Database -> Extensions**.

## 3. How to execute the schema
The database definition is split into extensions, schema, indexes, and seed data.
1. Install `psql` (PostgreSQL client) on your machine.
2. Run the scripts in the following order:
   ```bash
   export DATABASE_URL="postgresql://postgres.[YOUR_PROJECT_ID]:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"
   
   psql $DATABASE_URL -f database/extensions.sql
   psql $DATABASE_URL -f database/schema.sql
   psql $DATABASE_URL -f database/indexes.sql
   psql $DATABASE_URL -f database/seed.sql
   ```
3. Alternatively, you can copy-paste the contents of each file sequentially into the Supabase SQL Editor.

## 4. How to prepare datasets
1. Place all your raw datasets into the `datasets/` directory.
2. Ensure you have the LGD village files, Census PCA files, PMGSY shapefiles (`.shp`, `.dbf`, `.shx`), MSME counts, AGMARKNET CSVs, and MoSPI/HCES files organized.
3. Run the dataset inspection tool to verify all files are present and correctly formatted:
   ```bash
   python scripts/inspect_datasets.py
   python scripts/generate_inventory_md.py
   ```
   This will generate a `Dataset_Inventory.md` report.

## 5. How to run ingestion
Set up your python environment:
```bash
pip install pandas geopandas sqlalchemy psycopg2-binary
```
Execute the data ingestion pipeline:
```bash
export DATABASE_URL="your-supabase-connection-string"
python scripts/load_supabase.py
```
This orchestrates the safe UPSERT-based loading of LGD, Census, Locations, PMGSY, MSME, and pricing data without creating duplicates.

## 6. How to validate the database
Run the validation script to check geographic integrity, spatial integrity, duplicate integrity, and referential integrity:
```bash
python scripts/validate_database.py
```
This script will output a report showing the number of orphan records, foreign-key violations, and total rows loaded per table.

## 7. How to test PostGIS
You can test the geospatial radius search using the SQL Editor or `psql`:
```sql
-- Find all facilities within 10 km of a specific village location
SELECT 
    v.village_name, 
    a.asset_name, 
    a.asset_type,
    ST_Distance(v.geom::geography, a.geom::geography) / 1000 AS distance_km
FROM locations v
CROSS JOIN rural_assets a
WHERE v.village_lgd_code = '123456'  -- Replace with a valid village code
AND ST_DWithin(v.geom::geography, a.geom::geography, 10000)
ORDER BY distance_km;
```

## 8. How to rerun ingestion safely
The data ingestion scripts are designed to be **idempotent**. 
1. They use `ON CONFLICT DO UPDATE` (upsert) logic keyed by unique IDs (like `village_lgd_code`).
2. They do not drop tables or truncate existing data unless explicitly requested.
3. You can safely run `python scripts/load_supabase.py` multiple times as new dataset files are added; it will only insert new records or update existing ones without causing duplication.
