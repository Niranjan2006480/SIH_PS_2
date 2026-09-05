"""
Report Composer Service
Assembles Module 1 (market/AI) + Module 2 (financial) into a unified report
and persists it to the feasibility_reports table.
"""

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.report_cache import ReportCache, make_input_hash, make_report_cache_key
from app.models.report import FeasibilityReport
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    CompetitorData,
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
from app.ai.ai_orchestrator import AIOrchestrator
from app.models.business import CategoryConfig
from sqlalchemy import select

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
        cat_result = await db.execute(
            select(CategoryConfig).where(
                CategoryConfig.category_code == request.business_category
            )
        )
        cat = cat_result.scalar_one_or_none()
        category_display = cat.display_name if cat else request.business_category.title()

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
        )

        # Step 7: Persist to DB
        input_hash = make_input_hash(
            request.village_lgd_code,
            request.business_category,
            request.margin_capital,
            request.radius_km,
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

        # Step 8: Cache the result
        await self.cache.set(cache_key, response.model_dump(mode="json"))

        return response

    def _assemble_response(
        self,
        report_id: str,
        request: AnalysisRequest,
        category_display: str,
        ai_analysis: dict[str, Any],
        financial: FinancialCalculationResponse,
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
            # Module 1 — AI analysis
            viability_score=safe_get(ai_analysis, "viability_score", 65),
            scores=[ScoreBreakdown(**s) for s in ai_scores],
            market=MarketData(
                population_5km=safe_get(ai_market, "population_5km", 0),
                population_10km=safe_get(ai_market, "population_10km", 0),
                potential_segment=safe_get(ai_market, "potential_segment", 0),
                estimated_customers=safe_get(ai_market, "estimated_customers", 0),
                distribution_channels=safe_get(ai_market, "distribution_channels", []),
            ),
            opportunity=OpportunityData(
                score=safe_get(ai_opp, "score", 70),
                title=safe_get(ai_opp, "title", ""),
                detail=safe_get(ai_opp, "detail", ""),
                signals=safe_get(ai_opp, "signals", []),
            ),
            swot=[SwotItem(**s) for s in ai_swot],
            risks=[RiskItem(**r) for r in ai_risks],
            competitors=CompetitorData(
                count=safe_get(ai_comp, "count", 0),
                density=safe_get(ai_comp, "density", "Moderate"),
                categories=safe_get(ai_comp, "categories", []),
                differentiators=safe_get(ai_comp, "differentiators", []),
            ),
            pricing=PricingData(
                low=safe_get(ai_pricing, "low", 0),
                base=safe_get(ai_pricing, "base", 0),
                premium=safe_get(ai_pricing, "premium", 0),
                margin_pct=safe_get(ai_pricing, "margin_pct", 30),
                unit=safe_get(ai_pricing, "unit", "per unit"),
                rationale=safe_get(ai_pricing, "rationale", ""),
            ),
            working_capital=WorkingCapitalData(
                setup=safe_get(ai_wc, "setup", 0),
                raw_materials=safe_get(ai_wc, "raw_materials", 0),
                inventory=safe_get(ai_wc, "inventory", 0),
                transport=safe_get(ai_wc, "transport", 0),
                utilities=safe_get(ai_wc, "utilities", 0),
                staff=safe_get(ai_wc, "staff", 0),
                marketing=safe_get(ai_wc, "marketing", 0),
                reserve=safe_get(ai_wc, "reserve", 0),
            ),
            recommendation=RecommendationData(
                label=safe_get(ai_rec, "label", "Validate further before proceeding"),
                title=safe_get(ai_rec, "title", ""),
                detail=safe_get(ai_rec, "detail", ""),
                reserve=safe_get(ai_rec, "reserve", 0),
                checklist=safe_get(ai_rec, "checklist", []),
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
            data_sources=safe_get(ai_analysis, "data_sources", ["Census 2011", "SECC 2011", "HCES 2023-24"]),
            confidence_score=safe_get(ai_analysis, "confidence_score", 0.70),
            is_cached=False,
        )
