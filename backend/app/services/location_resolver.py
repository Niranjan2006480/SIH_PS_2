"""
Location Resolver Service
Provides fuzzy village search using pg_trgm and exact LGD code lookups.
Also handles location hierarchy (State → District → Subdistrict → Village).
"""

from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geography import District, Location, State, Subdistrict, Village
from app.schemas.location import (
    LocationSearchResponse,
    VillageDetail,
    VillageResult,
)


class LocationResolver:
    """
    Resolves geographic inputs to LGD-coded locations.

    Search strategy (cascade):
    1. Exact LGD code match
    2. pg_trgm trigram similarity (SIMILARITY > 0.3)
    3. ILIKE prefix match (fallback)
    """

    async def search(
        self,
        query: str,
        db: AsyncSession,
        state_code: Optional[str] = None,
        limit: int = 10,
    ) -> LocationSearchResponse:
        """Fuzzy search across village names using pg_trgm."""
        q = query.strip().lower()

        # Build similarity search using pg_trgm
        similarity_expr = func.similarity(Village.village_name_normalized, q)
        stmt = (
            select(
                Village,
                Subdistrict.subdistrict_name,
                District.district_name,
                State.state_name,
                Location.latitude,
                Location.longitude,
            )
            .join(Subdistrict, Village.subdistrict_lgd_code == Subdistrict.subdistrict_lgd_code)
            .join(District, Village.district_lgd_code == District.district_lgd_code)
            .join(State, Village.state_code == State.state_code)
            .outerjoin(Location, Village.village_lgd_code == Location.village_lgd_code)
            .where(similarity_expr > 0.15)
        )

        if state_code:
            stmt = stmt.where(Village.state_code == state_code)

        stmt = stmt.order_by(similarity_expr.desc()).limit(limit)

        result = await db.execute(stmt)
        rows = result.all()

        villages = [
            VillageResult(
                village_lgd_code=row.Village.village_lgd_code,
                village_name=row.Village.village_name,
                subdistrict_name=row.subdistrict_name,
                district_name=row.district_name,
                state_name=row.state_name,
                state_code=row.Village.state_code,
                latitude=row.latitude,
                longitude=row.longitude,
                has_coordinates=row.latitude is not None,
            )
            for row in rows
        ]

        return LocationSearchResponse(
            results=villages,
            total=len(villages),
            query=query,
        )

    async def get_village_detail(
        self,
        village_lgd_code: str,
        db: AsyncSession,
    ) -> Optional[VillageDetail]:
        """Get full village details including coordinates."""
        stmt = (
            select(
                Village,
                Subdistrict.subdistrict_name,
                District.district_lgd_code,
                District.district_name,
                State.state_name,
                Location.latitude,
                Location.longitude,
                Location.coordinate_source,
            )
            .join(Subdistrict, Village.subdistrict_lgd_code == Subdistrict.subdistrict_lgd_code)
            .join(District, Village.district_lgd_code == District.district_lgd_code)
            .join(State, Village.state_code == State.state_code)
            .outerjoin(Location, Village.village_lgd_code == Location.village_lgd_code)
            .where(Village.village_lgd_code == village_lgd_code)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()

        if not row:
            return None

        return VillageDetail(
            village_lgd_code=row.Village.village_lgd_code,
            village_name=row.Village.village_name,
            subdistrict_lgd_code=row.Village.subdistrict_lgd_code,
            subdistrict_name=row.subdistrict_name,
            district_lgd_code=row.district_lgd_code,
            district_name=row.district_name,
            state_code=row.Village.state_code,
            state_name=row.state_name,
            latitude=row.latitude,
            longitude=row.longitude,
            coordinate_source=row.coordinate_source,
            has_coordinates=row.latitude is not None,
        )

    async def get_districts_by_state(
        self,
        state_code: str,
        db: AsyncSession,
    ) -> list[dict]:
        """Return districts for a given state."""
        result = await db.execute(
            select(District)
            .where(District.state_code == state_code)
            .order_by(District.district_name)
        )
        districts = result.scalars().all()
        return [
            {
                "code": d.district_lgd_code,
                "name": d.district_name,
            }
            for d in districts
        ]

    async def get_villages_by_district(
        self,
        district_lgd_code: str,
        db: AsyncSession,
        limit: int = 200,
    ) -> list[dict]:
        """Return villages for a given district."""
        result = await db.execute(
            select(Village)
            .where(Village.district_lgd_code == district_lgd_code)
            .order_by(Village.village_name)
            .limit(limit)
        )
        villages = result.scalars().all()
        return [
            {
                "code": v.village_lgd_code,
                "name": v.village_name,
                "subdistrict_code": v.subdistrict_lgd_code,
            }
            for v in villages
        ]

    async def get_all_states(self, db: AsyncSession) -> list[dict]:
        """Return all states."""
        result = await db.execute(
            select(State).order_by(State.state_name)
        )
        states = result.scalars().all()
        return [
            {"code": s.state_code, "name": s.state_name}
            for s in states
        ]
