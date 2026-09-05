"""
Market Analyzer Service
Uses PostGIS ST_DWithin to query population, competitors, and facilities
within a specified radius of a village centroid.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import (
    Business,
    CategoryConfig,
    DistrictBusinessSummary,
    MarketPrice,
    PriceIndex,
    PurchasingPowerBand,
)
from app.models.geography import Location, Village
from app.models.population import PopulationStats, StateEconomicProfile


@dataclass
class MarketContext:
    """Structured market context data for a given village + category + radius."""
    village_lgd_code: str
    village_name: str
    district_lgd_code: str
    state_code: str
    latitude: Optional[float]
    longitude: Optional[float]

    # Population within radius
    population_5km: int
    population_10km: int

    # Economic profile
    avg_monthly_expenditure: Optional[float]
    deprived_households_pct: Optional[float]
    literacy_rate_pct: Optional[float]

    # Competition
    competitor_count_5km: int
    competitor_count_10km: int
    district_total_businesses: int

    # Infrastructure
    market_within_10km_count: int
    road_access_quality: str  # good | moderate | limited

    # Pricing
    commodity_prices: list[dict]
    inflation_rate: Optional[float]

    # Category config
    category_config: Optional[dict]


class MarketAnalyzer:
    """
    Queries the PostgreSQL + PostGIS database to build a rich market context
    for the AI orchestrator to reason over.
    """

    async def build_context(
        self,
        village_lgd_code: str,
        business_category: str,
        radius_km: int,
        db: AsyncSession,
    ) -> MarketContext:
        """Build full market context for a village + category."""

        # 1. Fetch village + location
        loc_result = await db.execute(
            select(Village, Location)
            .outerjoin(Location, Village.village_lgd_code == Location.village_lgd_code)
            .where(Village.village_lgd_code == village_lgd_code)
        )
        row = loc_result.one_or_none()
        if row is None:
            raise ValueError(f"Village {village_lgd_code} not found in database.")

        village, location = row.Village, row.Location
        lat = float(location.latitude) if location else None
        lon = float(location.longitude) if location else None

        # 2. Population within radius (if we have coordinates)
        pop_5km, pop_10km = await self._get_radius_population(
            village_lgd_code, village.district_lgd_code, lat, lon, db
        )

        # 3. Economic profile from SECC
        econ = await self._get_economic_profile(village.state_code, village.district_lgd_code, db)

        # 4. Purchasing power from HCES
        pp = await self._get_purchasing_power(village.state_code, db)

        # 5. Competitor count
        comp_5, comp_10 = await self._count_competitors(
            business_category, lat, lon, village.district_lgd_code, db
        )

        # 6. District total businesses (Udyam)
        district_biz = await self._get_district_business_count(village.district_lgd_code, db)

        # 7. Market prices
        prices = await self._get_commodity_prices(
            business_category, village.state_code, village.district_lgd_code, db
        )

        # 8. CPI inflation
        inflation = await self._get_inflation_rate(village.state_code, db)

        # 9. Category config
        cat_config = await self._get_category_config(business_category, db)

        return MarketContext(
            village_lgd_code=village_lgd_code,
            village_name=village.village_name,
            district_lgd_code=village.district_lgd_code,
            state_code=village.state_code,
            latitude=lat,
            longitude=lon,
            population_5km=pop_5km,
            population_10km=pop_10km,
            avg_monthly_expenditure=float(pp.monthly_pcc_expenditure) if pp else None,
            deprived_households_pct=float(econ.deprived_households_pct) if econ and econ.deprived_households_pct else None,
            literacy_rate_pct=float(econ.literacy_rate_pct) if econ and econ.literacy_rate_pct else None,
            competitor_count_5km=comp_5,
            competitor_count_10km=comp_10,
            district_total_businesses=district_biz,
            market_within_10km_count=0,  # populated from rural_assets if available
            road_access_quality="moderate",  # default; enriched by PMGSY data
            commodity_prices=prices,
            inflation_rate=float(inflation) if inflation else None,
            category_config=cat_config,
        )

    async def _get_radius_population(
        self,
        village_lgd_code: str,
        district_lgd_code: str,
        lat: Optional[float],
        lon: Optional[float],
        db: AsyncSession,
    ) -> tuple[int, int]:
        """Estimate population within 5 and 10 km radius."""

        # Strategy 1: PostGIS radius if we have coordinates
        if lat is not None and lon is not None:
            try:
                stmt = text("""
                    SELECT
                        SUM(CASE WHEN ST_DWithin(l.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 5000) THEN ps.total_population ELSE 0 END) AS pop_5km,
                        SUM(CASE WHEN ST_DWithin(l.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 10000) THEN ps.total_population ELSE 0 END) AS pop_10km
                    FROM population_stats ps
                    JOIN locations l ON ps.village_lgd_code = l.village_lgd_code
                    WHERE ps.geographic_level = 'village'
                """)
                result = await db.execute(stmt, {"lat": lat, "lon": lon})
                row = result.one_or_none()
                if row and row.pop_10km:
                    return (int(row.pop_5km or 0), int(row.pop_10km or 0))
            except Exception:
                pass  # Fall through to district-level estimate

        # Strategy 2: District-level fallback (sum all village populations in district)
        stmt = select(func.sum(PopulationStats.total_population)).where(
            PopulationStats.district_lgd_code == district_lgd_code,
            PopulationStats.geographic_level == "village",
        )
        result = await db.execute(stmt)
        district_pop = result.scalar() or 0

        # Rough estimate: 5km ≈ 25% of district, 10km ≈ 50%
        pop_5 = int(float(district_pop) * 0.10)
        pop_10 = int(float(district_pop) * 0.25)
        return (max(pop_5, 1000), max(pop_10, 3000))

    async def _get_economic_profile(
        self, state_code: str, district_lgd_code: str, db: AsyncSession
    ) -> Optional[StateEconomicProfile]:
        result = await db.execute(
            select(StateEconomicProfile)
            .where(
                StateEconomicProfile.state_code == state_code,
                StateEconomicProfile.district_lgd_code == district_lgd_code,
            )
            .limit(1)
        )
        profile = result.scalar_one_or_none()
        if profile:
            return profile
        # Fallback to state level
        result = await db.execute(
            select(StateEconomicProfile)
            .where(StateEconomicProfile.state_code == state_code)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_purchasing_power(
        self, state_code: str, db: AsyncSession
    ) -> Optional[PurchasingPowerBand]:
        result = await db.execute(
            select(PurchasingPowerBand)
            .where(
                PurchasingPowerBand.state_code == state_code,
                PurchasingPowerBand.rural_urban == "rural",
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _count_competitors(
        self,
        category: str,
        lat: Optional[float],
        lon: Optional[float],
        district_lgd_code: str,
        db: AsyncSession,
    ) -> tuple[int, int]:
        """Count competitor businesses within 5 and 10 km."""
        if lat is not None and lon is not None:
            try:
                stmt = text("""
                    SELECT
                        COUNT(CASE WHEN ST_DWithin(b.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 5000) THEN 1 END) AS count_5km,
                        COUNT(CASE WHEN ST_DWithin(b.geom::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, 10000) THEN 1 END) AS count_10km
                    FROM businesses b
                    WHERE b.category = :category AND b.geom IS NOT NULL
                """)
                result = await db.execute(stmt, {"lat": lat, "lon": lon, "category": category})
                row = result.one_or_none()
                if row:
                    return (int(row.count_5km or 0), int(row.count_10km or 0))
            except Exception:
                pass

        # District-level fallback using district_business_summary
        result = await db.execute(
            select(DistrictBusinessSummary)
            .where(DistrictBusinessSummary.district_lgd_code == district_lgd_code)
            .limit(1)
        )
        summary = result.scalar_one_or_none()
        if summary:
            # Estimate based on total and typical rural density
            total = summary.total_registered or 0
            estimated_10km = max(5, int(total * 0.05))
            return (max(2, estimated_10km // 2), estimated_10km)

        return (5, 12)  # Default estimates

    async def _get_district_business_count(
        self, district_lgd_code: str, db: AsyncSession
    ) -> int:
        result = await db.execute(
            select(func.sum(DistrictBusinessSummary.total_registered))
            .where(DistrictBusinessSummary.district_lgd_code == district_lgd_code)
        )
        return int(result.scalar() or 0)

    async def _get_commodity_prices(
        self,
        category: str,
        state_code: str,
        district_lgd_code: str,
        db: AsyncSession,
    ) -> list[dict]:
        """Get recent commodity prices relevant to the business category."""
        # Category-to-commodity mapping
        CATEGORY_COMMODITIES = {
            "dairy": ["Milk", "Curd", "Ghee", "Butter"],
            "agriculture": ["Rice", "Wheat", "Paddy", "Maize"],
            "food_processing": ["Rice", "Wheat", "Sugar", "Maize"],
            "retail": ["Rice", "Wheat", "Sugar", "Pulses"],
            "textiles": ["Cotton", "Silk"],
            "livestock": ["Cattle", "Poultry"],
        }
        commodities = CATEGORY_COMMODITIES.get(category.lower(), ["Rice", "Wheat"])

        result = await db.execute(
            select(MarketPrice)
            .where(
                MarketPrice.district_lgd_code == district_lgd_code,
                MarketPrice.commodity.in_(commodities),
            )
            .order_by(MarketPrice.price_date.desc())
            .limit(10)
        )
        prices = result.scalars().all()
        return [
            {
                "commodity": p.commodity,
                "market": p.market_name,
                "modal_price": float(p.modal_price) if p.modal_price else None,
                "price_date": str(p.price_date),
            }
            for p in prices
        ]

    async def _get_inflation_rate(
        self, state_code: str, db: AsyncSession
    ) -> Optional[float]:
        result = await db.execute(
            select(PriceIndex.inflation_rate_pct)
            .where(PriceIndex.state_code == state_code)
            .order_by(PriceIndex.month_year.desc())
            .limit(1)
        )
        val = result.scalar_one_or_none()
        return float(val) if val else None

    async def _get_category_config(
        self, category: str, db: AsyncSession
    ) -> Optional[dict]:
        result = await db.execute(
            select(CategoryConfig).where(CategoryConfig.category_code == category)
        )
        cfg = result.scalar_one_or_none()
        if not cfg:
            return None
        return {
            "display_name": cfg.display_name,
            "target_segments": cfg.target_segments,
            "relevant_commodities": cfg.relevant_commodities,
            "required_facilities": cfg.required_facilities,
            "risk_factors": cfg.risk_factors,
            "competitor_categories": cfg.competitor_categories,
            "pricing_method": cfg.pricing_method,
        }
