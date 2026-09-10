"""
Master Ingestion CLI Runner
Runs all data ingestion pipelines (LGD, Census, SECC, RAG indexing).
"""

import argparse
import asyncio
import logging
import sys
from sqlalchemy import create_engine

from app.config import get_settings
from app.ingestion.census_loader import ingest_census_pca
from app.ingestion.lgd_loader import ingest_lgd
from app.ingestion.rag_indexer import index_domain_knowledge
from app.ingestion.secc_loader import ingest_secc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingestion")


def run_all(datasets_dir: str = "datasets") -> None:
    settings = get_settings()
    logger.info("Starting ingestion pipeline...")
    logger.info("Target Database: %s", settings.database_url)

    engine = create_engine(settings.database_url)

    logger.info("--- Step 1: Ingesting LGD Locations ---")
    ingest_lgd(engine, datasets_dir)

    logger.info("--- Step 2: Ingesting SECC Economic Profile ---")
    ingest_secc(engine, datasets_dir)

    logger.info("--- Step 3: Ingesting Census PCA Data ---")
    ingest_census_pca(engine, datasets_dir)

    logger.info("--- Step 4: Indexing RAG Knowledge Base ---")
    try:
        asyncio.run(index_domain_knowledge())
    except Exception as e:
        logger.warning("RAG indexing skipped or failed: %s", e)

    logger.info("Ingestion pipeline finished successfully!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UdyamAI Data Ingestion Runner")
    parser.add_argument("--datasets", default="datasets", help="Path to datasets directory")
    args = parser.parse_args()

    try:
        run_all(args.datasets)
    except Exception as ex:
        logger.error("Ingestion failed: %s", ex, exc_info=True)
        sys.exit(1)
