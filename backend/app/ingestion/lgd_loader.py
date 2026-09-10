"""
LGD Hierarchy & Location Ingestion Loader

Parses LGD Excel files across Maharashtra districts to populate:
- states
- districts
- subdistricts
- villages
- locations (coordinates)
"""

import glob
import logging
import os
import re
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


from psycopg2.extras import execute_values

def safe_upsert(
    df: pd.DataFrame,
    table_name: str,
    engine: Engine,
    unique_keys: list[str],
    chunk_size: int = 2000,
) -> None:
    """Safely and rapidly upserts DataFrame rows into PostgreSQL using execute_values."""
    if df.empty:
        return

    # Replace NaN with None so psycopg2 sends NULL
    df_clean = df.where(pd.notnull(df), None)

    columns = list(df_clean.columns)
    col_str = ", ".join(columns)
    conflict_keys = ", ".join(unique_keys)
    non_key_cols = [c for c in columns if c not in unique_keys]

    if non_key_cols:
        update_str = ", ".join([f"{col} = EXCLUDED.{col}" for col in non_key_cols])
        sql = f"""
        INSERT INTO {table_name} ({col_str})
        VALUES %s
        ON CONFLICT ({conflict_keys}) DO UPDATE SET {update_str};
        """
    else:
        sql = f"""
        INSERT INTO {table_name} ({col_str})
        VALUES %s
        ON CONFLICT ({conflict_keys}) DO NOTHING;
        """

    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        records = [tuple(x) for x in df_clean.to_numpy()]
        execute_values(cur, sql, records, page_size=chunk_size)
        raw_conn.commit()
        cur.close()
    finally:
        raw_conn.close()

    logger.info("Fast upserted %d rows into %s", len(df), table_name)


def ingest_lgd(engine: Engine, datasets_dir: str = "datasets") -> None:
    """Ingests LGD village hierarchy from datasets folder."""
    patterns = [
        os.path.join(datasets_dir, "*", "LGD*.xlsx"),
        os.path.join("..", datasets_dir, "*", "LGD*.xlsx"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))
    files = sorted(list(set(files)))

    logger.info("Found %d LGD files for processing: %s", len(files), [os.path.basename(f) for f in files])

    if not files:
        logger.warning("No LGD Excel files found in %s", datasets_dir)
        return

    # 1. Ensure State (Maharashtra: 27)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO states (state_code, state_name, state_name_normalized)
                VALUES ('27', 'Maharashtra', 'maharashtra')
                ON CONFLICT (state_code) DO NOTHING;
                """
            )
        )
    logger.info("State 'Maharashtra' (27) ensured.")

    for file_path in files:
        file_name = os.path.basename(file_path)
        try:
            logger.info("Reading LGD file with calamine: %s", file_name)
            try:
                df = pd.read_excel(file_path, engine="calamine")
            except Exception as e:
                logger.info("Calamine failed (%s), falling back to openpyxl", e)
                df = pd.read_excel(file_path, engine="openpyxl")

            if df.empty:
                logger.warning("File is empty: %s", file_name)
                continue

            cols = [str(c).strip() for c in df.columns]
            df.columns = cols

            # Locate columns
            vc_col = next((c for c in cols if "village lgd code" in c.lower()), None)
            vn_col = next((c for c in cols if "village name (in english)" in c.lower() or "village name" in c.lower()), None)
            hier_col = next((c for c in cols if "hierarchy" in c.lower()), None)
            c11_col = next((c for c in cols if "census2011" in c.lower() or "census 2011" in c.lower()), None)

            if not vc_col or not vn_col:
                logger.warning("Missing vital columns in %s: %s", file_name, cols)
                continue

            # Drop invalid village codes
            df = df.dropna(subset=[vc_col])
            df["village_lgd_code"] = df[vc_col].astype(str).str.split(".").str[0].str.strip()
            df = df[df["village_lgd_code"].str.isnumeric()]
            if df.empty:
                continue

            parent_dir = os.path.basename(os.path.dirname(file_path))
            default_dist = parent_dir if parent_dir and parent_dir != "datasets" else "Maharashtra District"

            if hier_col and hier_col in df.columns:
                df["state_name"] = df[hier_col].astype(str).str.extract(r"/\s*([^\/]+)\(State\)")[0].str.strip().fillna("Maharashtra")
                df["district_name"] = df[hier_col].astype(str).str.extract(r"/\s*([^\/]+)\(District\)")[0].str.strip().fillna(default_dist)
                df["subdistrict_name"] = df[hier_col].astype(str).str.extract(r"^([^\/]+)\(Sub-District\)")[0].str.strip().fillna("General Block")
            else:
                df["state_name"] = "Maharashtra"
                df["district_name"] = default_dist
                df["subdistrict_name"] = "General Block"

            df["state_code"] = "27"

            # Stable unique numeric codes
            df["district_lgd_code"] = df["district_name"].apply(lambda x: str(abs(hash(x)) % 9000 + 1000)[:10])
            df["subdistrict_lgd_code"] = df.apply(
                lambda r: str(abs(hash(f"{r['district_name']}_{r['subdistrict_name']}")) % 90000 + 10000)[:10],
                axis=1,
            )

            # 2. Upsert Districts
            dist_df = df[["district_lgd_code", "state_code", "district_name"]].drop_duplicates(subset=["district_lgd_code"])
            dist_df["district_name_normalized"] = dist_df["district_name"].str.lower().str.strip()
            dist_df["is_pilot_active"] = True
            safe_upsert(dist_df, "districts", engine, ["district_lgd_code"])

            # 3. Upsert Subdistricts
            sub_df = df[["subdistrict_lgd_code", "district_lgd_code", "subdistrict_name"]].drop_duplicates(subset=["subdistrict_lgd_code"])
            sub_df["subdistrict_name_normalized"] = sub_df["subdistrict_name"].str.lower().str.strip()
            safe_upsert(sub_df, "subdistricts", engine, ["subdistrict_lgd_code"])

            # 4. Upsert Villages
            v_cols = ["village_lgd_code", "subdistrict_lgd_code", "district_lgd_code", "state_code"]
            v_df = df[v_cols].copy()
            v_df["village_name"] = df[vn_col].astype(str).str.strip()
            v_df["village_name_normalized"] = v_df["village_name"].str.lower().str.strip()
            v_df["village_census_2011_code"] = (
                df[c11_col].astype(str).str.split(".").str[0].str.strip() if c11_col else None
            )
            v_df["is_pilot_active"] = True
            v_df = v_df.drop_duplicates(subset=["village_lgd_code"])

            safe_upsert(v_df, "villages", engine, ["village_lgd_code"])
            logger.info("Successfully ingested %d villages from %s", len(v_df), file_name)

        except Exception as e:
            logger.exception("Error ingesting %s: %s", file_name, e)

    # Ingest Locations / Coordinates
    ingest_locations(engine, datasets_dir)


def ingest_locations(engine: Engine, datasets_dir: str = "datasets") -> None:
    """Ingests Village coordinates using Village Latitude & Longitude.xlsx."""
    candidates = [
        os.path.join(datasets_dir, "Village Latitude & Longitude.xlsx"),
        os.path.join("..", datasets_dir, "Village Latitude & Longitude.xlsx"),
    ]
    file_path = next((c for c in candidates if os.path.exists(c)), None)

    if not file_path:
        logger.warning("Coordinates file not found")
        return

    try:
        logger.info("Reading coordinates from %s with calamine", file_path)
        try:
            latlon_df = pd.read_excel(file_path, engine="calamine")
        except Exception:
            latlon_df = pd.read_excel(file_path)

        cols = [str(c).strip().lower() for c in latlon_df.columns]
        latlon_df.columns = cols

        if "latitude" not in cols or "longitude" not in cols or "officename" not in cols:
            logger.warning("Unexpected columns in coordinates file: %s", cols)
            return

        latlon_df = latlon_df.dropna(subset=["latitude", "longitude", "officename"])
        latlon_df["place_normalized"] = latlon_df["officename"].astype(str).str.lower().str.strip().str.replace(r"[.,]", "", regex=True)

        with engine.connect() as conn:
            villages_db = pd.read_sql("SELECT village_lgd_code, village_name_normalized FROM villages", conn)

        if villages_db.empty:
            logger.warning("Villages table is empty, cannot map coordinates")
            return

        # Direct name match
        merged = pd.merge(
            villages_db,
            latlon_df[["place_normalized", "latitude", "longitude"]].drop_duplicates(subset=["place_normalized"]),
            left_on="village_name_normalized",
            right_on="place_normalized",
            how="inner",
        )

        if not merged.empty:
            loc_df = pd.DataFrame({
                "village_lgd_code": merged["village_lgd_code"],
                "latitude": merged["latitude"].astype(float),
                "longitude": merged["longitude"].astype(float),
                "coordinate_source": "postal_office_proximity",
            }).drop_duplicates(subset=["village_lgd_code"])

            safe_upsert(loc_df, "locations", engine, ["village_lgd_code"])
            logger.info("Ingested %d village coordinates into locations table", len(loc_df))

    except Exception as e:
        logger.exception("Error ingesting coordinates: %s", e)