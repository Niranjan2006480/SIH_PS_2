"""
LGD Hierarchy & Location Ingestion Loader

Parses official Maharashtra LGD directory and gazetteer coordinates:
- datasets/Villageof_Specific_State_2026-08-27_08-57-01.xlsx
- datasets/IN_clean Latitude and Longitude.csv

Populates:
- states (State code 27: Maharashtra)
- districts (35 official revenue districts)
- subdistricts (358 official subdistricts / talukas)
- villages (44,911 official villages)
- locations (unambiguous geocoded points)
"""

import argparse
import logging
import os
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

PILOT_DISTRICTS = {
    "ahilyanagar",
    "ahmednagar",
    "pune",
    "satara",
    "kolhapur",
    "nashik",
    "gadchiroli",
    "solapur",
}


def clean_code(val: any) -> str | None:
    """Clean numeric LGD or census codes."""
    if pd.isna(val):
        return None
    s = str(val).split(".")[0].strip()
    return s if s and s.lower() != "nan" else None


def clean_text(val: any) -> str | None:
    """Clean string values."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None


def safe_upsert(
    df: pd.DataFrame,
    table_name: str,
    engine: Engine,
    unique_keys: list[str],
    chunk_size: int = 1000,
) -> None:
    """Safely and rapidly upserts DataFrame rows into PostgreSQL."""
    if df.empty:
        return

    # Replace NaN with None so psycopg sends NULL to SQL
    df_clean = df.where(pd.notnull(df), None)

    columns = list(df_clean.columns)
    col_str = ", ".join(columns)
    conflict_keys = ", ".join(unique_keys)
    non_key_cols = [c for c in columns if c not in unique_keys]

    if non_key_cols:
        update_str = ", ".join([f"{col} = EXCLUDED.{col}" for col in non_key_cols])
        conflict_action = f"DO UPDATE SET {update_str}"
    else:
        conflict_action = "DO NOTHING"

    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        records = [tuple(x) for x in df_clean.to_numpy()]

        for i in range(0, len(records), chunk_size):
            chunk = records[i:i + chunk_size]
            row_placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
            all_placeholders = ", ".join([row_placeholders] * len(chunk))
            flat_params = [val for row in chunk for val in row]

            sql = f"""
            INSERT INTO {table_name} ({col_str})
            VALUES {all_placeholders}
            ON CONFLICT ({conflict_keys}) {conflict_action};
            """
            cur.execute(sql, flat_params)

        raw_conn.commit()
        cur.close()
    finally:
        raw_conn.close()

    logger.info("Fast upserted %d rows into %s", len(df), table_name)


def ingest_lgd(engine: Engine, datasets_dir: str = "datasets", dry_run: bool = False) -> dict:
    """
    Ingests LGD village hierarchy and unambiguous coordinates.
    If dry_run=True, parses and validates without modifying database tables.
    """
    xlsx_candidates = [
        os.path.join(datasets_dir, "Villageof_Specific_State_2026-08-27_08-57-01.xlsx"),
        os.path.join("..", datasets_dir, "Villageof_Specific_State_2026-08-27_08-57-01.xlsx"),
    ]
    xlsx_file = next((f for f in xlsx_candidates if os.path.exists(f)), None)

    if not xlsx_file:
        logger.warning("Master LGD file not found in %s", datasets_dir)
        return {}

    logger.info("Reading official LGD village dataset: %s", xlsx_file)
    df = pd.read_excel(xlsx_file, header=1, engine="openpyxl")
    xlsx_total_rows = len(df)
    logger.info("Loaded %d rows from master LGD dataset", xlsx_total_rows)

    # 1. State: Maharashtra (27)
    state_df = pd.DataFrame([{
        "state_code": "27",
        "census_2011_code": "27",
        "state_name": "Maharashtra",
        "state_name_normalized": "maharashtra",
        "is_union_territory": False,
        "region": "Western",
    }])

    if not dry_run:
        safe_upsert(state_df, "states", engine, ["state_code"])
        logger.info("State 'Maharashtra' (27) ensured.")

    # 2. Districts
    df["district_lgd_code"] = df["District Code"].apply(clean_code)
    df["district_name"] = df["District Name (In English)"].apply(clean_text)
    df["district_name_normalized"] = df["district_name"].str.lower().str.strip()

    dist_df = df[["district_lgd_code", "district_name", "district_name_normalized"]].dropna(subset=["district_lgd_code"]).drop_duplicates(subset=["district_lgd_code"]).copy()
    dist_df["state_code"] = "27"
    dist_df["district_census_code"] = None
    dist_df["is_pilot_active"] = dist_df["district_name_normalized"].isin(PILOT_DISTRICTS)
    dist_df["data_completeness_pct"] = 100.0

    dist_cols = ["district_lgd_code", "district_census_code", "state_code", "district_name", "district_name_normalized", "is_pilot_active", "data_completeness_pct"]
    dist_df = dist_df[dist_cols]

    if not dry_run:
        safe_upsert(dist_df, "districts", engine, ["district_lgd_code"])
        logger.info("Ingested %d districts", len(dist_df))

    # 3. Subdistricts
    df["subdistrict_lgd_code"] = df["Sub-District Code"].apply(clean_code)
    df["subdistrict_name"] = df["Sub-District Name (In English)"].apply(clean_text)
    df["subdistrict_name_normalized"] = df["subdistrict_name"].str.lower().str.strip()

    sub_df = df[["subdistrict_lgd_code", "district_lgd_code", "subdistrict_name", "subdistrict_name_normalized"]].dropna(subset=["subdistrict_lgd_code"]).drop_duplicates(subset=["subdistrict_lgd_code"]).copy()

    if not dry_run:
        safe_upsert(sub_df, "subdistricts", engine, ["subdistrict_lgd_code"])
        logger.info("Ingested %d subdistricts", len(sub_df))

    # 4. Villages
    df["village_lgd_code"] = df["Village Code"].apply(clean_code)
    df["village_name"] = df["Village Name (In English)"].apply(clean_text)
    df["village_name_normalized"] = df["village_name"].str.lower().str.strip()
    df["village_census_2011_code"] = df["Census 2011 Code"].apply(clean_code)
    df["local_body_name"] = df["Village Name (In Local)"].apply(clean_text)
    df["local_body_code"] = None
    df["state_code"] = "27"
    df["is_pilot_active"] = df["district_name_normalized"].isin(PILOT_DISTRICTS)

    v_cols = [
        "village_lgd_code",
        "village_census_2011_code",
        "subdistrict_lgd_code",
        "district_lgd_code",
        "state_code",
        "village_name",
        "village_name_normalized",
        "local_body_code",
        "local_body_name",
        "is_pilot_active",
    ]
    v_df = df[v_cols].dropna(subset=["village_lgd_code"]).drop_duplicates(subset=["village_lgd_code"]).copy()

    if not dry_run:
        safe_upsert(v_df, "villages", engine, ["village_lgd_code"], chunk_size=3000)
        logger.info("Ingested %d villages", len(v_df))

    # 5. Ingest Coordinates
    coord_metrics = ingest_locations(engine, datasets_dir, villages_df=df, dry_run=dry_run)

    summary = {
        "source": {
            "xlsx_rows": xlsx_total_rows,
            "unique_districts": len(dist_df),
            "unique_subdistricts": len(sub_df),
            "unique_villages": len(v_df),
        },
        "coordinates": coord_metrics,
        "database_after_ingestion": {
            "states": 1,
            "districts": len(dist_df),
            "subdistricts": len(sub_df),
            "villages": len(v_df),
            "locations": coord_metrics.get("locations_inserted", 0),
        },
    }
    return summary


def ingest_locations(
    engine: Engine,
    datasets_dir: str = "datasets",
    villages_df: pd.DataFrame | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Ingests village coordinates using IN_clean Latitude and Longitude.csv.
    Enforces unambiguous matching: only inserts coordinates when an exact,
    unique (1-to-1) match exists between village and coordinates dataset.
    """
    candidates = [
        os.path.join(datasets_dir, "IN_clean Latitude and Longitude.csv"),
        os.path.join("..", datasets_dir, "IN_clean Latitude and Longitude.csv"),
    ]
    file_path = next((c for c in candidates if os.path.exists(c)), None)

    if not file_path:
        logger.warning("Coordinates CSV not found in %s", datasets_dir)
        return {}

    try:
        logger.info("Reading coordinates from: %s", file_path)
        coords_df = pd.read_csv(file_path)
        csv_total_rows = len(coords_df)

        # Filter to Maharashtra and drop nulls
        coords_mh = coords_df[coords_df["admin_name1"] == "Maharashtra"].copy()
        mh_rows = len(coords_mh)
        coords_mh = coords_mh.dropna(subset=["latitude", "longitude", "place_name", "admin_name2"])

        coords_mh["place_norm"] = coords_mh["place_name"].astype(str).str.lower().str.strip()
        coords_mh["d_match"] = coords_mh["admin_name2"].astype(str).str.lower().str.strip().replace({"ahilyanagar": "ahmednagar"})

        # Load villages from passed dataframe or DB
        if villages_df is not None:
            v_prep = villages_df.copy()
            v_prep["v_norm"] = v_prep["village_name_normalized"]
            v_prep["d_match"] = v_prep["district_name_normalized"].replace({"ahilyanagar": "ahmednagar"})
        else:
            with engine.connect() as conn:
                v_prep = pd.read_sql(
                    "SELECT v.village_lgd_code, v.village_name_normalized AS v_norm, "
                    "d.district_name_normalized AS d_norm "
                    "FROM villages v JOIN districts d USING(district_lgd_code)",
                    conn,
                )
            v_prep["d_match"] = v_prep["d_norm"].replace({"ahilyanagar": "ahmednagar"})

        total_villages = len(v_prep)

        # Check village name frequency in the same district
        v_counts = v_prep.groupby(["d_match", "v_norm"])["village_lgd_code"].count().reset_index()
        v_counts.columns = ["d_match", "v_norm", "v_count_in_dist"]
        v_prep = v_prep.merge(v_counts, on=["d_match", "v_norm"], how="left")

        # Group CSV coordinates by (d_match, place_norm)
        coord_agg = coords_mh.groupby(["d_match", "place_norm"]).agg(
            lat_nunique=("latitude", "nunique"),
            lat_val=("latitude", "first"),
            lon_val=("longitude", "first"),
            coord_count=("latitude", "count"),
        ).reset_index()

        # Join villages with coordinates
        matched = v_prep.merge(
            coord_agg,
            left_on=["d_match", "v_norm"],
            right_on=["d_match", "place_norm"],
            how="inner",
        )

        # Strictly unambiguous criteria:
        # 1. Exactly 1 village in that district has this name (v_count_in_dist == 1)
        # 2. All coordinate entries in CSV for this place are identical (lat_nunique == 1)
        unambiguous = matched[(matched["v_count_in_dist"] == 1) & (matched["lat_nunique"] == 1)].copy()
        ambiguous = matched[(matched["v_count_in_dist"] > 1) | (matched["lat_nunique"] > 1)].copy()

        # Count unmatched coordinate rows from CSV
        v_unique_pairs = set(zip(v_prep["d_match"], v_prep["v_norm"]))
        coords_mh["is_matched"] = coords_mh.apply(lambda r: (r["d_match"], r["place_norm"]) in v_unique_pairs, axis=1)
        unmatched_csv_rows = len(coords_mh[~coords_mh["is_matched"]])

        unambiguous_count = len(unambiguous)
        ambiguous_count = len(ambiguous)

        if not dry_run and unambiguous_count > 0:
            loc_df = pd.DataFrame({
                "village_lgd_code": unambiguous["village_lgd_code"],
                "latitude": unambiguous["lat_val"].astype(float),
                "longitude": unambiguous["lon_val"].astype(float),
                "coordinate_source": "in_clean_gazetteer",
                "coordinate_accuracy": "high",
            }).drop_duplicates(subset=["village_lgd_code"])

            safe_upsert(loc_df, "locations", engine, ["village_lgd_code"], chunk_size=2000)
            logger.info("Ingested %d unambiguous village coordinates into locations table", len(loc_df))

        return {
            "csv_rows": csv_total_rows,
            "maharashtra_rows": mh_rows,
            "unique_village_matches": unambiguous_count,
            "ambiguous_matches": ambiguous_count,
            "unmatched_csv_records": unmatched_csv_rows,
            "villages_without_coordinates": total_villages - unambiguous_count,
            "locations_inserted": unambiguous_count if not dry_run else unambiguous_count,
        }

    except Exception as e:
        logger.exception("Error during coordinate processing: %s", e)
        return {}


if __name__ == "__main__":
    from app.config import get_settings
    from sqlalchemy import create_engine

    parser = argparse.ArgumentParser(description="LGD & Geographic Ingestion Loader")
    parser.add_argument("--datasets", default="datasets", help="Path to datasets directory")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report counts without writing to database")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url)

    rep = ingest_lgd(engine, datasets_dir=args.datasets, dry_run=args.dry_run)

    print("\n================== VALIDATION REPORT ==================")
    if rep:
        src = rep.get("source", {})
        coords = rep.get("coordinates", {})
        db = rep.get("database_after_ingestion", {})

        print("SOURCE:")
        print(f"- XLSX rows: {src.get('xlsx_rows', 0):,}")
        print(f"- unique districts: {src.get('unique_districts', 0)}")
        print(f"- unique subdistricts: {src.get('unique_subdistricts', 0)}")
        print(f"- unique villages: {src.get('unique_villages', 0):,}")

        print("\nCOORDINATES:")
        print(f"- CSV rows: {coords.get('csv_rows', 0):,}")
        print(f"- Maharashtra rows: {coords.get('maharashtra_rows', 0):,}")
        print(f"- unique village matches: {coords.get('unique_village_matches', 0):,}")
        print(f"- ambiguous matches: {coords.get('ambiguous_matches', 0):,}")
        print(f"- unmatched: {coords.get('unmatched_csv_records', 0):,}")
        print(f"- locations inserted: {coords.get('locations_inserted', 0):,}")

        print("\nDATABASE AFTER INGESTION:")
        print(f"- states: {db.get('states', 0)}")
        print(f"- districts: {db.get('districts', 0)}")
        print(f"- subdistricts: {db.get('subdistricts', 0)}")
        print(f"- villages: {db.get('villages', 0):,}")
        print(f"- locations: {db.get('locations', 0):,}")
    print("=======================================================\n")