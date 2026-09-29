"""
Tests for Census 2011 PCA Population Data Ingestion Loader.

Verifies:
- Census code matching against villages.village_census_2011_code
- Accurate demographic field mapping (total, male, female, households, sex_ratio)
- Idempotent upsert (running twice produces no duplicates)
- Unmatched village handling (unmatched records are skipped and counted)
- Aggregate and non-village row skipping
- Dry-run validation
"""

import os
import tempfile
import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from app.ingestion.census_loader import (
    clean_code,
    find_column,
    ingest_census_pca,
    to_int,
)


@pytest.fixture
def sqlite_test_engine():
    """In-memory SQLite engine with schema matching geography & population_stats."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE villages (
                    village_lgd_code VARCHAR(15) PRIMARY KEY,
                    village_census_2011_code VARCHAR(15),
                    district_lgd_code VARCHAR(10),
                    village_name TEXT
                );
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE population_stats (
                    id VARCHAR(36) PRIMARY KEY,
                    village_lgd_code VARCHAR(15),
                    district_lgd_code VARCHAR(10),
                    geographic_level TEXT,
                    source TEXT,
                    source_year INT,
                    total_population INT,
                    male_population INT,
                    female_population INT,
                    total_households INT,
                    sex_ratio NUMERIC,
                    data_quality TEXT,
                    created_at TIMESTAMP
                );
                """
            )
        )
        # Prepopulate test villages: Mulher and Tirhe
        conn.execute(
            text(
                """
                INSERT INTO villages (village_lgd_code, village_census_2011_code, district_lgd_code, village_name)
                VALUES
                    ('550001', '550001', '487', 'Mulher'),
                    ('562164', '562164', '504', 'Tirhe');
                """
            )
        )
    return engine


def test_clean_code_and_to_int_helpers():
    """Verify code cleaning and numeric parsing edge cases."""
    assert clean_code("550001") == "550001"
    assert clean_code(550001) == "550001"
    assert clean_code(550001.0) == "550001"
    assert clean_code(" 550001 ") == "550001"
    assert clean_code(0) is None
    assert clean_code("0") is None
    assert clean_code("000000") is None
    assert clean_code(None) is None
    assert clean_code(float("nan")) is None

    assert to_int("3,959") == 3959
    assert to_int(3959.0) == 3959
    assert to_int(3959) == 3959
    assert to_int(" 4762 ") == 4762
    assert to_int(0) == 0
    assert to_int("-") is None
    assert to_int("NA") is None
    assert to_int(None) is None
    assert to_int(float("nan")) is None


def test_find_column():
    """Verify case-insensitive column finder."""
    cols = ["State", "District", "Town/Village", "Level", "TOT_P", "No_HH"]
    assert find_column(cols, ["Town/Village", "Village_Code"]) == "Town/Village"
    assert find_column(cols, ["tot_p", "Total Population"]) == "TOT_P"
    assert find_column(cols, ["NonExistent"]) is None


def test_census_ingestion_and_field_mapping(sqlite_test_engine):
    """
    Test end-to-end ingestion from synthetic Census Excel file:
    - skips aggregate rows (DISTRICT, CD BLOCK)
    - matches existing villages (Mulher, Tirhe)
    - skips and records unmatched village (999999)
    - maps demographic fields accurately
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock Census PCA Excel file in standard format
        mock_data = pd.DataFrame([
            {
                "Level": "DISTRICT",
                "Town/Village": 0,
                "Name": "Nashik",
                "TRU": "Total",
                "No_HH": 1200000,
                "TOT_P": 6107187,
                "TOT_M": 3157186,
                "TOT_F": 2950001,
            },
            {
                "Level": "CD BLOCK",
                "Town/Village": 0,
                "Name": "Baglan",
                "TRU": "Total",
                "No_HH": 75000,
                "TOT_P": 374000,
                "TOT_M": 192000,
                "TOT_F": 182000,
            },
            {
                "Level": "VILLAGE",
                "Town/Village": 550001,
                "Name": "Mulher",
                "TRU": "Total",
                "No_HH": 836,
                "TOT_P": 3959,
                "TOT_M": 2019,
                "TOT_F": 1940,
            },
            {
                "Level": "VILLAGE",
                "Town/Village": 562164,
                "Name": "Tirhe",
                "TRU": "Total",
                "No_HH": 968,
                "TOT_P": 4762,
                "TOT_M": 2463,
                "TOT_F": 2299,
            },
            {
                "Level": "VILLAGE",
                "Town/Village": 999999,
                "Name": "Unmatched Village",
                "TRU": "Total",
                "No_HH": 100,
                "TOT_P": 500,
                "TOT_M": 260,
                "TOT_F": 240,
            },
        ])

        excel_path = os.path.join(temp_dir, "PCA_CDB-Test.xlsx")
        mock_data.to_excel(excel_path, index=False)

        stats = ingest_census_pca(sqlite_test_engine, datasets_dir=temp_dir)

        assert stats["files_processed"] == 1
        assert stats["total_census_records_read"] == 5
        assert stats["skipped_aggregate_rows"] == 2
        assert stats["total_village_records_read"] == 3
        assert stats["matched_villages"] == 2
        assert stats["unmatched_villages"] == 1
        assert stats["inserted_rows"] == 2
        assert stats["updated_rows"] == 0

        # Verify database contents
        with sqlite_test_engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM population_stats ORDER BY total_population")
            ).mappings().fetchall()

            assert len(rows) == 2

            # Mulher record check
            mulher = rows[0]
            assert mulher["village_lgd_code"] == "550001"
            assert mulher["district_lgd_code"] == "487"
            assert mulher["geographic_level"] == "village"
            assert mulher["source"] == "Census 2011 PCA"
            assert mulher["source_year"] == 2011
            assert mulher["total_population"] == 3959
            assert mulher["male_population"] == 2019
            assert mulher["female_population"] == 1940
            assert mulher["total_households"] == 836
            # 1940 / 2019 * 1000 = 960.87
            assert pytest.approx(float(mulher["sex_ratio"]), 0.01) == 960.87

            # Tirhe record check
            tirhe = rows[1]
            assert tirhe["village_lgd_code"] == "562164"
            assert tirhe["district_lgd_code"] == "504"
            assert tirhe["total_population"] == 4762
            assert tirhe["male_population"] == 2463
            assert tirhe["female_population"] == 2299
            assert tirhe["total_households"] == 968
            # 2299 / 2463 * 1000 = 933.41
            assert pytest.approx(float(tirhe["sex_ratio"]), 0.01) == 933.41


def test_idempotent_upsert(sqlite_test_engine):
    """Verify that running ingestion twice does NOT duplicate rows."""
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_data = pd.DataFrame([
            {
                "Level": "VILLAGE",
                "Town/Village": 550001,
                "Name": "Mulher",
                "TRU": "Total",
                "No_HH": 836,
                "TOT_P": 3959,
                "TOT_M": 2019,
                "TOT_F": 1940,
            }
        ])
        excel_path = os.path.join(temp_dir, "PCA_CDB-Test.xlsx")
        mock_data.to_excel(excel_path, index=False)

        # Run 1: First insert
        stats1 = ingest_census_pca(sqlite_test_engine, datasets_dir=temp_dir)
        assert stats1["inserted_rows"] == 1
        assert stats1["updated_rows"] == 0

        with sqlite_test_engine.connect() as conn:
            count1 = conn.execute(text("SELECT COUNT(*) FROM population_stats")).scalar()
            assert count1 == 1

        # Run 2: Second run with slightly updated population
        updated_data = pd.DataFrame([
            {
                "Level": "VILLAGE",
                "Town/Village": 550001,
                "Name": "Mulher",
                "TRU": "Total",
                "No_HH": 850,
                "TOT_P": 4000,
                "TOT_M": 2050,
                "TOT_F": 1950,
            }
        ])
        updated_data.to_excel(excel_path, index=False)

        stats2 = ingest_census_pca(sqlite_test_engine, datasets_dir=temp_dir)
        assert stats2["inserted_rows"] == 0
        assert stats2["updated_rows"] == 1

        with sqlite_test_engine.connect() as conn:
            count2 = conn.execute(text("SELECT COUNT(*) FROM population_stats")).scalar()
            # Must still have exactly 1 row, not 2
            assert count2 == 1

            row = conn.execute(text("SELECT total_population, total_households FROM population_stats")).mappings().one()
            assert row["total_population"] == 4000
            assert row["total_households"] == 850


def test_dry_run_does_not_modify_database(sqlite_test_engine):
    """Verify dry_run=True computes statistics without inserting rows."""
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_data = pd.DataFrame([
            {
                "Level": "VILLAGE",
                "Town/Village": 550001,
                "Name": "Mulher",
                "TRU": "Total",
                "No_HH": 836,
                "TOT_P": 3959,
                "TOT_M": 2019,
                "TOT_F": 1940,
            }
        ])
        excel_path = os.path.join(temp_dir, "PCA_CDB-Test.xlsx")
        mock_data.to_excel(excel_path, index=False)

        stats = ingest_census_pca(sqlite_test_engine, datasets_dir=temp_dir, dry_run=True)
        assert stats["matched_villages"] == 1
        assert stats["inserted_rows"] == 1

        with sqlite_test_engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM population_stats")).scalar()
            assert count == 0


def test_nashik_alternate_column_format(sqlite_test_engine):
    """Verify handling of alternate Census PCA column names (like Nashik dataset)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_data = pd.DataFrame([
            {
                "Level": "VILLAGE",
                "Town/Village_Code": 550001,
                "Name": "Mulher",
                "Total/Rural/Urban": "Total",
                "No of Households": 836,
                "Total Population Person": 3959,
                "Total Population Male": 2019,
                "Total Population Female": 1940,
            }
        ])
        excel_path = os.path.join(temp_dir, "PCA_CDB-Nashik_style.xlsx")
        mock_data.to_excel(excel_path, index=False)

        stats = ingest_census_pca(sqlite_test_engine, datasets_dir=temp_dir)
        assert stats["matched_villages"] == 1
        assert stats["inserted_rows"] == 1

        with sqlite_test_engine.connect() as conn:
            row = conn.execute(
                text("SELECT total_population, male_population, female_population, total_households FROM population_stats")
            ).mappings().one()
            assert row["total_population"] == 3959
            assert row["male_population"] == 2019
            assert row["female_population"] == 1940
            assert row["total_households"] == 836
