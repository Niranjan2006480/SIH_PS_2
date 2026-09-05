"""API v1 Router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import analysis, financial, health, locations

router = APIRouter(prefix="/api/v1")

router.include_router(health.router)
router.include_router(locations.router, prefix="/locations")
router.include_router(analysis.router, prefix="/analysis")
router.include_router(financial.router, prefix="/financial")
