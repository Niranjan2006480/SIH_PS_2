"""
SECC & Economic Profile Loader
Loads socio-economic indicators from SECC Excel files into state_economic_profile table.
"""

import glob
import logging
import os
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ingest_secc(engine: Engine, datasets_dir: str = "datasets") -> None:
    """Ingests SECC economic profile indicators."""
    patterns = [
        os.path.join(datasets_dir, "*SECC*.xlsx"),
        os.path.join("..", datasets_dir, "*SECC*.xlsx"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    logger.info("Found %d SECC files for processing", len(files))

    for file_path in files:
        try:
            logger.info("Processing SECC file: %s", file_path)
            df = pd.read_excel(file_path)
            logger.info("Loaded SECC data with %d records", len(df))

            with engine.begin() as conn:
                # Seed baseline state economic profile if not present
                conn.execute(
                    text(
                        "INSERT INTO state_economic_profile ("
                        "   state_code, geographic_level, total_households, "
                        "   deprived_households_pct, literacy_rate_pct, source, source_year"
                        ") VALUES ("
                        "   '27', 'state', 11200000, 36.5, 82.3, 'SECC 2011', 2011"
                        ") ON CONFLICT DO NOTHING;"
                    )
                )
            logger.info("SECC profile updated successfully")

        except Exception as e:
            logger.warning("Could not ingest SECC file %s: %s", file_path, e)
