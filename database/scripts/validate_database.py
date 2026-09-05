import os
from sqlalchemy import create_engine, text

def validate_database():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set. Skipping validation.")
        return
        
    engine = create_engine(db_url)
    
    queries = {
        "Total Villages": "SELECT COUNT(*) FROM villages;",
        "Total Locations": "SELECT COUNT(*) FROM locations;",
        "Orphan Locations (No Village)": """
            SELECT COUNT(*) FROM locations l 
            LEFT JOIN villages v ON l.village_lgd_code = v.village_lgd_code 
            WHERE v.village_lgd_code IS NULL;
        """,
        "Locations without Geometry": "SELECT COUNT(*) FROM locations WHERE geom IS NULL;",
        "Total Rural Assets": "SELECT COUNT(*) FROM rural_assets;",
        "Total Rural Roads": "SELECT COUNT(*) FROM rural_roads;",
        "Orphan Population Stats (No Village)": """
            SELECT COUNT(*) FROM population_stats p
            LEFT JOIN villages v ON p.village_lgd_code = v.village_lgd_code 
            WHERE p.geographic_level = 'village' AND v.village_lgd_code IS NULL;
        """
    }
    
    print("--- Database Validation Report ---")
    with engine.connect() as conn:
        for name, sql in queries.items():
            try:
                result = conn.execute(text(sql)).scalar()
                print(f"{name}: {result}")
            except Exception as e:
                print(f"{name}: ERROR - {e}")
    print("----------------------------------")

if __name__ == "__main__":
    validate_database()
