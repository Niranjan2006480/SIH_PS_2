import os
from sqlalchemy import create_engine, text

def apply_schema(db_url):
    engine = create_engine(db_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for script in ["extensions.sql", "schema.sql", "indexes.sql", "seed.sql"]:
            path = os.path.join("database", script)
            if not os.path.exists(path):
                continue
            print(f"Executing {script}...")
            with open(path, "r", encoding="utf-8") as f:
                sql = f.read()
            # Split by statements isn't perfectly reliable with text().execute(),
            # but SQLAlchemy text() handles multi-statement if driver supports it.
            # Using psycopg2 driver allows multiple statements.
            try:
                conn.execute(text(sql))
                print(f"{script} executed successfully.")
            except Exception as e:
                print(f"Error executing {script}: {e}")

if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set.")
    else:
        apply_schema(db_url)
