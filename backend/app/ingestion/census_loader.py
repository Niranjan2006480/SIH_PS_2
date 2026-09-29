"""
Census 2011 PCA Population Data Loader
Loads population statistics from PCA_CDB Excel sheets into population_stats table.
"""

import glob
import logging
import os
import uuid
from typing import Any

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Column candidates for dynamic matching across Census PCA formats
CANDIDATE_VILLAGE_CODE = [
    "Town/Village",
    "Town/Village_Code",
    "Town/Village Code",
    "Village_Code",
    "Village Code",
    "village_census_2011_code",
]

CANDIDATE_LEVEL = [
    "Level",
    "LEVEL",
]

CANDIDATE_TRU = [
    "TRU",
    "Total/Rural/Urban",
    "Total / Rural / Urban",
    "TRU_Code",
]

CANDIDATE_HOUSEHOLDS = [
    "No_HH",
    "No of Households",
    "No. of Households",
    "No_of_Households",
    "HOUSEHOLDS",
    "total_households",
]

CANDIDATE_TOTAL_POP = [
    "TOT_P",
    "Total Population Person",
    "Total Population Persons",
    "TOT_POP",
    "TOTAL_POP",
    "total_population",
]

CANDIDATE_MALE_POP = [
    "TOT_M",
    "Total Population Male",
    "MALE_POP",
    "male_population",
]

CANDIDATE_FEMALE_POP = [
    "TOT_F",
    "Total Population Female",
    "FEMALE_POP",
    "female_population",
]

CANDIDATE_SC_POP = [
    "P_SC",
    "Scheduled Castes population Person",
    "Scheduled Castes Population Person",
    "SC_POP",
    "sc_population",
]

CANDIDATE_ST_POP = [
    "P_ST",
    "Scheduled Tribes population Person",
    "Scheduled Tribes Population Person",
    "ST_POP",
    "st_population",
]

CANDIDATE_LIT_POP = [
    "P_LIT",
    "Literates Population Person",
    "Literate Population Person",
    "LIT_POP",
    "literate_population",
]


def clean_code(val: Any) -> str | None:
    """Clean numeric or string census/LGD codes."""
    if val is None or pd.isna(val):
        return None
    s = str(val).split(".")[0].strip()
    if not s or s.lower() in ("nan", "none", "null", "0", "000000"):
        return None
    return s


def to_int(val: Any) -> int | None:
    """Safely cast string/float/int numeric values to integer."""
    if val is None or pd.isna(val):
        return None
    try:
        s = str(val).replace(",", "").strip()
        if not s or s.lower() in ("nan", "none", "-", "na", "null"):
            return None
        return int(float(s))
    except (ValueError, TypeError):
        return None


def find_column(columns: Any, candidates: list[str]) -> str | None:
    """Case-insensitive column lookup."""
    col_map = {str(c).strip().lower(): str(c) for c in columns}
    for cand in candidates:
        if cand.strip().lower() in col_map:
            return col_map[cand.strip().lower()]
    return None


def get_table_columns(engine: Engine, table_name: str) -> set[str]:
    """Inspect columns present in database table."""
    try:
        insp = inspect(engine)
        if insp.has_table(table_name):
            return {col["name"] for col in insp.get_columns(table_name)}
    except Exception as e:
        logger.debug("Could not inspect columns for %s: %s", table_name, e)
    # Default fallback matching schema.sql
    return {
        "id",
        "village_lgd_code",
        "district_lgd_code",
        "geographic_level",
        "source",
        "source_year",
        "total_population",
        "male_population",
        "female_population",
        "total_households",
        "sex_ratio",
        "data_quality",
        "created_at",
    }


def ingest_census_pca(
    engine: Engine,
    datasets_dir: str = "datasets",
    dry_run: bool = False,
    chunk_size: int = 1000,
) -> dict[str, int]:
    """
    Ingests Census 2011 Primary Census Abstract (PCA) population data into population_stats.

    Matches each Census village using:
        Census Town/Village Code -> villages.village_census_2011_code

    Idempotent upsert:
        Updates existing population_stats records or inserts new ones.
        Running twice does not duplicate rows.

    Returns:
        dict with ingestion statistics.
    """
    stats = {
        "total_census_records_read": 0,
        "skipped_aggregate_rows": 0,
        "total_village_records_read": 0,
        "matched_villages": 0,
        "unmatched_villages": 0,
        "inserted_rows": 0,
        "updated_rows": 0,
        "files_processed": 0,
    }

    # Discover PCA files (both .xlsx and .xls, in datasets_dir or datasets_dir/*/)
    patterns = [
        os.path.join(datasets_dir, "*", "PCA*.xls*"),
        os.path.join(datasets_dir, "PCA*.xls*"),
    ]
    if not os.path.isabs(datasets_dir):
        patterns.extend([
            os.path.join("..", datasets_dir, "*", "PCA*.xls*"),
            os.path.join("..", datasets_dir, "PCA*.xls*"),
        ])

    files: list[str] = []
    for p in patterns:
        for f in glob.glob(p):
            if f not in files:
                files.append(f)

    logger.info("Found %d Census PCA files for processing", len(files))
    if not files:
        logger.warning("No Census PCA files found matching patterns in %s", datasets_dir)
        return stats

    # 1. Inspect target table columns to ensure strict adherence to existing schema
    target_cols = get_table_columns(engine, "population_stats")
    code_col = "village_lgd_code" if "village_lgd_code" in target_cols else "village_id"

    # 2. Build village lookup mapping: census_2011_code -> {village_lgd_code, district_lgd_code}
    village_map: dict[str, dict[str, str | None]] = {}
    try:
        with engine.connect() as conn:
            # Check which columns exist in villages table
            v_cols = get_table_columns(engine, "villages")
            select_cols = ["village_census_2011_code", "village_lgd_code"]
            if "district_lgd_code" in v_cols:
                select_cols.append("district_lgd_code")

            q = f"SELECT {', '.join(select_cols)} FROM villages WHERE village_census_2011_code IS NOT NULL"
            rows = conn.execute(text(q)).fetchall()
            for r in rows:
                c_code = clean_code(r[0])
                if c_code and c_code not in village_map:
                    village_map[c_code] = {
                        "village_lgd_code": str(r[1]),
                        "district_lgd_code": str(r[2]) if len(r) > 2 and r[2] is not None else None,
                    }
        logger.info("Loaded %d village mappings from database", len(village_map))
    except Exception as e:
        logger.error("Failed to query villages table for Census mapping: %s", e)
        return stats

    # 3. Pre-fetch existing population_stats records to support idempotent upsert without duplicates
    existing_pop_stats: dict[str, str] = {}  # village_lgd_code -> id
    try:
        with engine.connect() as conn:
            q = f"SELECT id, {code_col} FROM population_stats WHERE geographic_level = 'village'"
            rows = conn.execute(text(q)).fetchall()
            for r in rows:
                if r[1] is not None:
                    existing_pop_stats[str(r[1])] = str(r[0])
        logger.info("Found %d existing population_stats records", len(existing_pop_stats))
    except Exception as e:
        logger.debug("Could not pre-fetch existing population_stats: %s", e)

    # 4. Process each Census file
    records_to_insert: list[dict[str, Any]] = []
    records_to_update: list[dict[str, Any]] = []

    for file_path in files:
        try:
            logger.info("Processing Census PCA file: %s", file_path)
            try:
                df = pd.read_excel(file_path, engine="openpyxl")
            except Exception:
                try:
                    df = pd.read_excel(file_path, engine="xlrd")
                except Exception:
                    df = pd.read_excel(file_path)

            file_records = len(df)
            stats["total_census_records_read"] += file_records
            stats["files_processed"] += 1
            logger.info("Read %d raw records from %s", file_records, os.path.basename(file_path))

            cols = list(df.columns)
            c_code = find_column(cols, CANDIDATE_VILLAGE_CODE)
            c_lvl = find_column(cols, CANDIDATE_LEVEL)
            c_hh = find_column(cols, CANDIDATE_HOUSEHOLDS)
            c_tot = find_column(cols, CANDIDATE_TOTAL_POP)
            c_m = find_column(cols, CANDIDATE_MALE_POP)
            c_f = find_column(cols, CANDIDATE_FEMALE_POP)
            c_sc = find_column(cols, CANDIDATE_SC_POP)
            c_st = find_column(cols, CANDIDATE_ST_POP)
            c_lit = find_column(cols, CANDIDATE_LIT_POP)

            if not c_code:
                logger.warning("Could not identify village code column in %s; skipping", file_path)
                continue

            for _, row in df.iterrows():
                # Check Level column to ignore aggregate rows (DISTRICT, CD BLOCK, TOWN, etc.)
                if c_lvl and pd.notnull(row[c_lvl]):
                    lvl = str(row[c_lvl]).strip().upper()
                    if lvl != "VILLAGE":
                        stats["skipped_aggregate_rows"] += 1
                        continue

                v_code = clean_code(row[c_code])
                if not v_code:
                    stats["skipped_aggregate_rows"] += 1
                    continue

                stats["total_village_records_read"] += 1

                # Match against known villages in database
                if v_code not in village_map:
                    stats["unmatched_villages"] += 1
                    continue

                stats["matched_villages"] += 1
                v_info = village_map[v_code]
                v_lgd = v_info["village_lgd_code"]
                d_lgd = v_info["district_lgd_code"]

                # Extract and parse demographics
                tot_p = to_int(row[c_tot]) if c_tot else None
                tot_m = to_int(row[c_m]) if c_m else None
                tot_f = to_int(row[c_f]) if c_f else None
                no_hh = to_int(row[c_hh]) if c_hh else None
                sc_p = to_int(row[c_sc]) if c_sc else None
                st_p = to_int(row[c_st]) if c_st else None
                lit_p = to_int(row[c_lit]) if c_lit else None

                sex_ratio = None
                if tot_m and tot_m > 0 and tot_f is not None:
                    sex_ratio = round((float(tot_f) / float(tot_m)) * 1000.0, 2)

                # Assemble database record matching available columns in population_stats
                record: dict[str, Any] = {}
                if "village_lgd_code" in target_cols:
                    record["village_lgd_code"] = v_lgd
                if "village_id" in target_cols:
                    record["village_id"] = v_lgd
                if "district_lgd_code" in target_cols:
                    record["district_lgd_code"] = d_lgd
                if "geographic_level" in target_cols:
                    record["geographic_level"] = "village"
                if "source" in target_cols:
                    record["source"] = "Census 2011 PCA"
                if "source_year" in target_cols:
                    record["source_year"] = 2011
                if "census_year" in target_cols:
                    record["census_year"] = 2011
                if "total_population" in target_cols:
                    record["total_population"] = tot_p
                if "male_population" in target_cols:
                    record["male_population"] = tot_m
                if "female_population" in target_cols:
                    record["female_population"] = tot_f
                if "total_households" in target_cols:
                    record["total_households"] = no_hh
                if "sex_ratio" in target_cols:
                    record["sex_ratio"] = sex_ratio
                if "data_quality" in target_cols:
                    record["data_quality"] = "high"
                if "sc_population" in target_cols:
                    record["sc_population"] = sc_p
                if "st_population" in target_cols:
                    record["st_population"] = st_p
                if "literate_population" in target_cols:
                    record["literate_population"] = lit_p

                # Idempotent routing: update if exists, insert if new
                if v_lgd in existing_pop_stats:
                    rec_id = existing_pop_stats[v_lgd]
                    if "id" in target_cols:
                        record["id"] = rec_id
                    records_to_update.append(record)
                else:
                    rec_id = str(uuid.uuid4())
                    if "id" in target_cols:
                        record["id"] = rec_id
                    existing_pop_stats[v_lgd] = rec_id
                    records_to_insert.append(record)

        except Exception as e:
            logger.warning("Could not ingest Census file %s: %s", file_path, e)

    logger.info(
        "Census parsing summary: read=%d, villages=%d, matched=%d, unmatched=%d, skipped_agg=%d",
        stats["total_census_records_read"],
        stats["total_village_records_read"],
        stats["matched_villages"],
        stats["unmatched_villages"],
        stats["skipped_aggregate_rows"],
    )

    # 5. Database write execution (if not dry_run)
    if dry_run:
        stats["inserted_rows"] = len(records_to_insert)
        stats["updated_rows"] = len(records_to_update)
        logger.info(
            "Dry run complete: %d records would be inserted, %d updated",
            stats["inserted_rows"],
            stats["updated_rows"],
        )
        return stats

    if not records_to_insert and not records_to_update:
        logger.info("No records to insert or update in population_stats")
        return stats

    try:
        with engine.begin() as conn:
            if records_to_insert:
                cols = list(records_to_insert[0].keys())
                col_str = ", ".join(cols)
                val_str = ", ".join([f":{c}" for c in cols])
                insert_sql = text(f"INSERT INTO population_stats ({col_str}) VALUES ({val_str})")
                for i in range(0, len(records_to_insert), chunk_size):
                    chunk = records_to_insert[i:i + chunk_size]
                    conn.execute(insert_sql, chunk)
                stats["inserted_rows"] = len(records_to_insert)
                logger.info("Successfully inserted %d rows into population_stats", stats["inserted_rows"])

            if records_to_update:
                update_cols = [c for c in records_to_update[0].keys() if c != "id"]
                set_str = ", ".join([f"{c} = :{c}" for c in update_cols])
                update_sql = text(f"UPDATE population_stats SET {set_str} WHERE id = :id")
                for i in range(0, len(records_to_update), chunk_size):
                    chunk = records_to_update[i:i + chunk_size]
                    conn.execute(update_sql, chunk)
                stats["updated_rows"] = len(records_to_update)
                logger.info("Successfully updated %d rows in population_stats", stats["updated_rows"])

    except Exception as e:
        logger.error("Failed to commit population_stats to database: %s", e)
        raise

    return stats
