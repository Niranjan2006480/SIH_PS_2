"""Location API endpoints — search, detail, hierarchy."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.location import LocationSearchResponse, VillageDetail
from app.services.location_resolver import LocationResolver

logger = logging.getLogger(__name__)
router = APIRouter()
resolver = LocationResolver()


@router.get("/search", response_model=LocationSearchResponse, tags=["Location"])
async def search_locations(
    q: str = Query(..., min_length=2, description="Village or district name"),
    state_code: str | None = Query(None, description="Filter by 2-digit state code"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Fuzzy search for villages by name using pg_trgm.
    Returns up to `limit` matching villages with coordinates and hierarchy info.
    """
    return await resolver.search(q, db, state_code=state_code, limit=limit)


@router.get("/states", tags=["Location"])
async def get_states(db: AsyncSession = Depends(get_db)):
    """Return all available states."""
    return await resolver.get_all_states(db)


@router.get("/districts", tags=["Location"])
async def get_districts(
    state_code: str = Query(..., description="2-digit state code"),
    db: AsyncSession = Depends(get_db),
):
    """Return all districts for a state."""
    districts = await resolver.get_districts_by_state(state_code, db)
    if not districts:
        raise HTTPException(status_code=404, detail=f"No districts found for state {state_code}")
    return {"state_code": state_code, "districts": districts}


@router.get("/villages", tags=["Location"])
async def get_villages(
    district_lgd_code: str = Query(..., description="District LGD code"),
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Return villages for a given district (for cascade dropdowns)."""
    villages = await resolver.get_villages_by_district(district_lgd_code, db, limit=limit)
    if not villages:
        raise HTTPException(status_code=404, detail=f"No villages found for district {district_lgd_code}")
    return {"district_lgd_code": district_lgd_code, "villages": villages, "total": len(villages)}


@router.get("/{village_lgd_code}", response_model=VillageDetail, tags=["Location"])
async def get_village_detail(
    village_lgd_code: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full village detail including coordinates and administrative hierarchy."""
    detail = await resolver.get_village_detail(village_lgd_code, db)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Village {village_lgd_code} not found")
    return detail
