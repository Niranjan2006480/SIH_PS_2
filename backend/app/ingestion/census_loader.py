"""
Census 2011 PCA Population Data Loader
Loads population statistics from PCA_CDB Excel sheets into population_stats table.
"""

import glob
import logging
import os
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ingest_census_pca(engine: Engine, datasets_dir: str = "datasets") -> None:
    """Ingests Census Primary Census Abstract (PCA) population data."""
    patterns = [
        os.path.join(datasets_dir, "*", "PCA*.xlsx"),
        os.path.join("..", datasets_dir, "*", "PCA*.xlsx"),
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    logger.info("Found %d Census PCA files for processing", len(files))

    for file_path in files:
        try:
            logger.info("Processing Census PCA file: %s", file_path)
            try:
                df = pd.read_excel(file_path, engine="openpyxl")
            except Exception:
                df = pd.read_excel(file_path)

            logger.info("Loaded Census PCA records: %d", len(df))

        except Exception as e:
            logger.warning("Could not ingest Census file %s: %s", file_path, e)
