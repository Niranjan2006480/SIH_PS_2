import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Load environment variables from .env if present
env_paths = [
    Path.cwd() / ".env",
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path(__file__).resolve().parent.parent / ".env",
]
for p in env_paths:
    if p.exists():
        load_dotenv(p)
        break

def apply_schema(db_url: str):
    # Normalize postgres:// to postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # Use isolation_level AUTOCOMMIT for DDL and CREATE EXTENSION
    engine = create_engine(db_url, isolation_level="AUTOCOMMIT")
    base_dir = Path(__file__).resolve().parent.parent

    sql_files = [
        "extensions.sql",
        "schema.sql",
        "indexes.sql",
        "seed.sql",
        "seed_schemes.sql",
    ]

    print(f"Connecting to database...")
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cursor:
            for script_name in sql_files:
                script_path = base_dir / script_name
                if not script_path.exists():
                    print(f"[-] Warning: {script_name} not found at {script_path}, skipping.")
                    continue
                
                print(f"[+] Executing {script_name}...")
                with open(script_path, "r", encoding="utf-8") as f:
                    sql_content = f.read()

                try:
                    cursor.execute(sql_content)
                    print(f"[✓] {script_name} executed successfully.")
                except Exception as e:
                    print(f"[✗] Error executing {script_name}: {e}")
                    raise
        print("\nAll schema files and seeds applied successfully!")
    finally:
        raw_conn.close()

if __name__ == "__main__":
    db_url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not set in environment or passed as argument.")
        print("Usage: python apply_schema.py [optional_database_url]")
        sys.exit(1)
    apply_schema(db_url)
