"""GET /api/v1/health — System health check."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.cache.report_cache import get_redis
from qdrant_client import AsyncQdrantClient
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/health", tags=["System"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Returns health status of all backend services:
    - PostgreSQL (Supabase)
    - Redis
    - Qdrant
    """
    status: dict = {"status": "ok", "services": {}}

    # PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        status["services"]["postgres"] = "ok"
    except Exception as e:
        status["services"]["postgres"] = f"error: {e}"
        status["status"] = "degraded"

    # Redis
    try:
        redis = await get_redis()
        await redis.ping()
        status["services"]["redis"] = "ok"
    except Exception as e:
        status["services"]["redis"] = f"error: {e}"
        status["status"] = "degraded"

    # Qdrant
    try:
        qclient = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        collections = await qclient.get_collections()
        status["services"]["qdrant"] = f"ok ({len(collections.collections)} collections)"
    except Exception as e:
        status["services"]["qdrant"] = f"error: {e}"
        status["status"] = "degraded"

    return status
