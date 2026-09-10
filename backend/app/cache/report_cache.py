"""
Redis Cache Service
Caches feasibility reports and location data to minimize DB + AI calls.
"""

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Get or create Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


def make_report_cache_key(
    village_lgd_code: str,
    business_category: str,
    margin_capital: float,
    radius_km: int,
    business_idea: str = "",
) -> str:
    """Deterministic cache key from analysis inputs including specific business idea."""
    cleaned_idea = (business_idea or "").strip().lower()
    raw = f"{village_lgd_code}:{business_category}:{int(margin_capital)}:{radius_km}:{cleaned_idea}"
    return f"report:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def make_input_hash(
    village_lgd_code: str,
    business_category: str,
    margin_capital: float,
    radius_km: int,
    business_idea: str = "",
) -> str:
    """SHA-256 hash stored in DB for deduplication."""
    cleaned_idea = (business_idea or "").strip().lower()
    raw = f"{village_lgd_code}:{business_category}:{int(margin_capital)}:{radius_km}:{cleaned_idea}"
    return hashlib.sha256(raw.encode()).hexdigest()


class ReportCache:
    """Report caching layer backed by Redis."""

    async def get(self, cache_key: str) -> dict[str, Any] | None:
        try:
            redis = await get_redis()
            data = await redis.get(cache_key)
            if data:
                logger.info("Cache HIT: %s", cache_key)
                return json.loads(data)
        except Exception as e:
            logger.warning("Cache GET failed: %s", e)
        return None

    async def set(
        self,
        cache_key: str,
        data: dict[str, Any],
        ttl: int = settings.redis_report_ttl_seconds,
    ) -> None:
        try:
            redis = await get_redis()
            await redis.setex(cache_key, ttl, json.dumps(data, default=str))
            logger.info("Cache SET: %s (TTL=%ds)", cache_key, ttl)
        except Exception as e:
            logger.warning("Cache SET failed: %s", e)

    async def invalidate(self, cache_key: str) -> None:
        try:
            redis = await get_redis()
            await redis.delete(cache_key)
        except Exception as e:
            logger.warning("Cache invalidation failed: %s", e)
