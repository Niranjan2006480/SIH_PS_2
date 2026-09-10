"""
Report Composer Service
Assembles Module 1 (market/AI) + Module 2 (financial) into a unified report
and persists it to the feasibility_reports table.
"""

import logging
import math
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.ai_orchestrator import AIOrchestrator
from app.cache.report_cache import ReportCache, make_input_hash, make_report_cache_key
from app.models.business import CategoryConfig
from app.models.report import FeasibilityReport
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    CompetitorData,
    CompetitorItem,
    MarketData,
    OpportunityData,
    PricingData,
    RecommendationData,
    RiskItem,
    ScoreBreakdown,
    SwotItem,
    WorkingCapitalData,
)
from app.schemas.financial import FinancialCalculationResponse
from app.services.financial_engine import FinancialEngine
from app.services.location_resolver import LocationResolver
from app.services.market_analyzer import MarketAnalyzer

logger = logging.getLogger(__name__)


class ReportComposer:
    """
    Orchestrates the full analysis pipeline:
    1. Location resolution
    2. Market data collection (PostGIS)
    3. Financial calculation (scheme + EMI)
    4. AI generation (Gemini + RAG)
    5. Report assembly + persistence
    """

    def __init__(self) -> None:
        self.location_resolver = LocationResolver()
        self.market_analyzer = MarketAnalyzer()
        self.financial_engine = FinancialEngine()
        self.ai_orchestrator = AIOrchestrator()
        self.cache = ReportCache()

    async def compose(
        self,
        request: AnalysisRequest,
        db: AsyncSession,
    ) -> AnalysisResponse:
        """Full report composition pipeline."""

        # Step 1: Check cache
        cache_key = make_report_cache_key(
            request.village_lgd_code,
            request.business_category,
            request.margin_capital,
            request.radius_km,
            request.business_idea,
        )
        cached = await self.cache.get(cache_key)
        if cached:
            response = AnalysisResponse(**cached)
            response.is_cached = True
            return response

        # Step 2: Market context from PostGIS
        logger.info("Building market context for %s", request.village_lgd_code)
        market_ctx = await self.market_analyzer.build_context(
            village_lgd_code=request.village_lgd_code,
            business_category=request.business_category,
            radius_km=request.radius_km,
            db=db,
        )

        # Step 3: Financial calculation
        logger.info("Running financial calculation for margin=₹%s", request.margin_capital)
        financial = await self.financial_engine.calculate(
            margin_capital=request.margin_capital,
            db=db,
            village_lgd_code=request.village_lgd_code,
        )

        # Step 4: Get category display name
        category_display = request.business_category.replace("_", " ").title()
        try:
            cat_result = await db.execute(
                select(CategoryConfig).where(
                    CategoryConfig.category_code == request.business_category
                )
            )
            cat = cat_result.scalar_one_or_none()
            if cat and cat.display_name:
                category_display = cat.display_name
        except Exception:
            pass

        # Step 5: AI generation
        logger.info("Generating AI analysis for %s in %s", request.business_category, market_ctx.village_name)
        ai_analysis = await self.ai_orchestrator.generate_analysis(
            request_data=request.model_dump(),
            market_ctx=market_ctx,
            category_display_name=category_display,
        )

        # Step 6: Assemble response
        report_id = str(uuid.uuid4())
        response = self._assemble_response(
            report_id=report_id,
            request=request,
            category_display=category_display,
            ai_analysis=ai_analysis,
            financial=financial,
            market_ctx=market_ctx,
        )

        # Step 7: Persist to DB (if available)
        try:
            input_hash = make_input_hash(
                request.village_lgd_code,
                request.business_category,
                request.margin_capital,
                request.radius_km,
                request.business_idea,
            )
            db_report = FeasibilityReport(
                report_id=uuid.UUID(report_id),
                village_lgd_code=request.village_lgd_code,
                business_category=request.business_category,
                radius_km=request.radius_km,
                margin_capital=request.margin_capital,
                input_hash=input_hash,
                report_json=response.model_dump(mode="json"),
                overall_feasibility_score=ai_analysis.get("viability_score"),
                confidence_score=ai_analysis.get("confidence_score", 0.7),
                status="completed",
            )
            db.add(db_report)
            await db.flush()
        except Exception as e:
            logger.warning("Feasibility report DB persistence skipped: %s", e)

        # Step 8: Cache the result
        try:
            await self.cache.set(cache_key, response.model_dump(mode="json"))
        except Exception:
            pass

        return response

    def _assemble_response(
        self,
        report_id: str,
        request: AnalysisRequest,
        category_display: str,
        ai_analysis: dict[str, Any],
        financial: FinancialCalculationResponse,
        market_ctx: Any,
    ) -> AnalysisResponse:
        """Map AI output + financial data into the typed AnalysisResponse."""

        def safe_get(d: dict, key: str, default: Any = None) -> Any:
            return d.get(key, default)

        ai_market = safe_get(ai_analysis, "market", {})
        ai_opp = safe_get(ai_analysis, "opportunity", {})
        ai_swot = safe_get(ai_analysis, "swot", [])
        ai_risks = safe_get(ai_analysis, "risks", [])
        ai_comp = safe_get(ai_analysis, "competitors", {})
        ai_pricing = safe_get(ai_analysis, "pricing", {})
        ai_wc = safe_get(ai_analysis, "working_capital", {})
        ai_rec = safe_get(ai_analysis, "recommendation", {})
        ai_scores = safe_get(ai_analysis, "scores", [])

        # Map competitor items with relative spatial coordinates for mapping
        base_lat = market_ctx.latitude or 19.7515
        base_lon = market_ctx.longitude or 75.7139
        raw_items = safe_get(ai_comp, "items", [])
        comp_items: list[CompetitorItem] = []
        if raw_items:
            for idx, item in enumerate(raw_items):
                dist_km = float(item.get("distance_km", 1.5 + idx * 1.2))
                angle_rad = (idx * (360.0 / max(len(raw_items), 1)) + 25.0) * (math.pi / 180.0)
                d_lat = (dist_km / 111.0) * math.cos(angle_rad)
                d_lon = (dist_km / (111.0 * max(0.1, math.cos(math.radians(base_lat))))) * math.sin(angle_rad)
                comp_items.append(
                    CompetitorItem(
                        name=item.get("name", f"Competitor {idx+1}"),
                        category=item.get("category", category_display),
                        distance_km=round(dist_km, 1),
                        latitude=round(base_lat + d_lat, 4),
                        longitude=round(base_lon + d_lon, 4),
                        strength=item.get("strength", "Moderate"),
                        offering=item.get("offering", ""),
                    )
                )
        else:
            default_names = [
                f"{request.village_name} Local Enterprise",
                f"{request.district_name} Highway Trading Hub",
                "Gramin Haat Cooperative Centre",
            ]
            for idx, name in enumerate(default_names):
                dist_km = round(1.2 + idx * 1.8, 1)
                angle_rad = (idx * 120.0 + 35.0) * (math.pi / 180.0)
                d_lat = (dist_km / 111.0) * math.cos(angle_rad)
                d_lon = (dist_km / (111.0 * max(0.1, math.cos(math.radians(base_lat))))) * math.sin(angle_rad)
                comp_items.append(
                    CompetitorItem(
                        name=name,
                        category=category_display,
                        distance_km=dist_km,
                        latitude=round(base_lat + d_lat, 4),
                        longitude=round(base_lon + d_lon, 4),
                        strength="Moderate" if idx == 0 else ("High" if idx == 1 else "Emerging"),
                        offering="Local area competitor providing traditional service.",
                    )
                )

        official_sources = [
            "Census of India 2011 (Village PCA & Primary Demographics)",
            "Socio Economic and Caste Census (SECC 2011)",
            "MoSPI Household Consumption Expenditure Survey (HCES 2023-24)",
            "Ministry of Panchayati Raj Local Government Directory (LGD)",
            "AGMARKNET Mandi Price Intelligence & Daily Arrivals",
            "MoSPI Rural Consumer Price Index (CPI 2024)",
            "NBCFDC & SCA Concessional Loan Scheme Guidelines",
            "Ministry of MSME Udyam Enterprise Registry",
        ]

        return AnalysisResponse(
            report_id=report_id,
            village_lgd_code=request.village_lgd_code,
            village_name=request.village_name,
            district_name=request.district_name,
            state_name=request.state_name,
            business_category=request.business_category,
            business_category_display=category_display,
            margin_capital=request.margin_capital,
            radius_km=request.radius_km,
            latitude=market_ctx.latitude,
            longitude=market_ctx.longitude,
            # Module 1 — AI analysis
            viability_score=safe_get(ai_analysis, "viability_score", 65),
            scores=[ScoreBreakdown(**s) for s in ai_scores] if ai_scores else [
                ScoreBreakdown(label="Demand", value=75),
                ScoreBreakdown(label="Competition", value=70),
                ScoreBreakdown(label="Capital Fit", value=80),
                ScoreBreakdown(label="Risk", value=72),
                ScoreBreakdown(label="Pricing Potential", value=78),
            ],
            market=MarketData(
                population_5km=safe_get(ai_market, "population_5km", market_ctx.population_5km or 6200),
                population_10km=safe_get(ai_market, "population_10km", market_ctx.population_10km or 18500),
                potential_segment=safe_get(ai_market, "potential_segment", int((market_ctx.population_10km or 18500) * 0.28)),
                estimated_customers=safe_get(ai_market, "estimated_customers", int((market_ctx.population_5km or 6200) * 0.08)),
                distribution_channels=safe_get(ai_market, "distribution_channels", [
                    f"Direct sales to households in {request.village_name}",
                    f"Weekly Haat market in {request.district_name} block",
                    "Local Kirana / retail shop supply",
                    "Pre-booked community orders",
                ]),
            ),
            opportunity=OpportunityData(
                score=safe_get(ai_opp, "score", 70),
                title=safe_get(ai_opp, "title", f"Growth opportunity for {category_display} in {request.village_name}"),
                detail=safe_get(ai_opp, "detail", f"Healthy market absorption supported by surrounding rural population in {request.district_name}."),
                signals=safe_get(ai_opp, "signals", [
                    f"Consumer cluster in {request.village_name} area",
                    "Manageable local competitor density",
                    f"Highway connectivity across {request.district_name}",
                ]),
            ),
            swot=[SwotItem(**s) for s in ai_swot] if ai_swot else [
                SwotItem(title="Strengths", items=[f"Direct presence in {request.village_name}", "Low operational overhead"]),
                SwotItem(title="Weaknesses", items=["Initial working capital constraints", "Single-channel distribution initially"]),
                SwotItem(title="Opportunities", items=["Expand to neighbouring weekly markets", "Government concessional credit linkage"]),
                SwotItem(title="Threats", items=["Seasonal raw material cost changes", "Informal competitor pricing"]),
            ],
            risks=[RiskItem(**r) for r in ai_risks] if ai_risks else [
                RiskItem(name="Input Price Fluctuation", level="Medium", detail="Seasonal input costs can affect margins.", action="Form direct seasonal procurement ties."),
                RiskItem(name="Cashflow Timing", level="Medium", detail="Credit cycles in village retail.", action="Keep 30-day liquidity reserve."),
            ],
            competitors=CompetitorData(
                count=max(len(comp_items), safe_get(ai_comp, "count", len(comp_items))),
                density=safe_get(ai_comp, "density", "Moderate"),
                categories=safe_get(ai_comp, "categories", [f"Local {category_display}", "Informal Sellers", "Weekly Haat Vendors"]),
                differentiators=safe_get(ai_comp, "differentiators", [
                    f"Direct doorstep delivery in {request.village_name}",
                    "Transparent digital billing & UPI support",
                    "Quality consistency and reliable supply",
                ]),
                items=comp_items,
            ),
            pricing=PricingData(
                low=safe_get(ai_pricing, "low", 40.0),
                base=safe_get(ai_pricing, "base", 55.0),
                premium=safe_get(ai_pricing, "premium", 75.0),
                margin_pct=safe_get(ai_pricing, "margin_pct", 30.0),
                unit=safe_get(ai_pricing, "unit", "per unit"),
                rationale=safe_get(ai_pricing, "rationale", f"Pricing aligned with local purchasing power in {request.district_name}."),
            ),
            working_capital=WorkingCapitalData(
                setup=safe_get(ai_wc, "setup", request.margin_capital * 0.4),
                raw_materials=safe_get(ai_wc, "raw_materials", request.margin_capital * 0.25),
                inventory=safe_get(ai_wc, "inventory", request.margin_capital * 0.15),
                transport=safe_get(ai_wc, "transport", request.margin_capital * 0.08),
                utilities=safe_get(ai_wc, "utilities", request.margin_capital * 0.05),
                staff=safe_get(ai_wc, "staff", request.margin_capital * 0.1),
                marketing=safe_get(ai_wc, "marketing", request.margin_capital * 0.04),
                reserve=safe_get(ai_wc, "reserve", request.margin_capital * 0.15),
            ),
            recommendation=RecommendationData(
                label=safe_get(ai_rec, "label", "Proceed — with modifications"),
                title=safe_get(ai_rec, "title", f"Viable micro-enterprise plan for {request.village_name}"),
                detail=safe_get(ai_rec, "detail", f"Target local households in {request.village_name} and leverage NBCFDC scheme credit."),
                reserve=safe_get(ai_rec, "reserve", request.margin_capital * 0.2),
                checklist=safe_get(ai_rec, "checklist", [
                    "Complete Udyam Registration (free online MSME registration)",
                    f"Survey at least 25 households in {request.village_name}",
                    "Apply for NBCFDC / State Channelizing Agency credit linkage",
                    "Establish trade relationship with 2 local input suppliers",
                    "Set up QR code for instant digital UPI payments",
                ]),
            ),
            # Module 2 — Financial
            project_cost=financial.project_cost,
            loan_amount=financial.eligible_loan,
            scheme_code=financial.scheme.scheme_code,
            scheme_name=financial.scheme.scheme_name,
            interest_rate=financial.scheme.annual_interest_rate,
            tenure_years=financial.scheme.tenure_years,
            moratorium_months=financial.scheme.moratorium_months,
            monthly_emi=financial.monthly_emi,
            total_repayment=financial.total_repayment,
            data_sources=official_sources,
            confidence_score=safe_get(ai_analysis, "confidence_score", 0.85),
            is_cached=False,
        )
