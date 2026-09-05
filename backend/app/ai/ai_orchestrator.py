"""
AI Orchestrator Service
Orchestrates Gemini calls with market context + RAG retrieval
to generate structured feasibility analysis JSON.
"""

import json
import logging
import re
from string import Template
from typing import Any

import google.generativeai as genai

from app.ai.prompts import MARKET_ANALYSIS_PROMPT
from app.ai.rag_retriever import RAGRetriever
from app.config import get_settings
from app.services.market_analyzer import MarketContext

logger = logging.getLogger(__name__)
settings = get_settings()


class AIOrchestrator:
    """
    Orchestrates Gemini LLM calls to generate structured feasibility analysis.
    Combines real market data (from DB) + RAG context (from Qdrant) into prompts.
    """

    def __init__(self) -> None:
        genai.configure(api_key=settings.google_gemini_api_key)
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config=genai.GenerationConfig(
                temperature=settings.gemini_temperature,
                max_output_tokens=settings.gemini_max_output_tokens,
                response_mime_type="application/json",
            ),
        )
        self._rag = RAGRetriever()

    async def generate_analysis(
        self,
        request_data: dict[str, Any],
        market_ctx: MarketContext,
        category_display_name: str,
    ) -> dict[str, Any]:
        """
        Full pipeline:
        1. Retrieve RAG context
        2. Build structured prompt with real data
        3. Call Gemini with JSON mode
        4. Parse + validate response
        5. Return structured dict
        """
        # Step 1: RAG retrieval
        rag_query = (
            f"{category_display_name} business in rural {market_ctx.district_lgd_code} "
            f"India, margin capital ₹{request_data['margin_capital']}"
        )
        rag_context = await self._rag.retrieve(
            query=rag_query,
            business_category=request_data["business_category"],
            state_code=market_ctx.state_code,
        )

        # Step 2: Build prompt with real data
        prompt = self._build_prompt(
            request_data=request_data,
            market_ctx=market_ctx,
            category_display_name=category_display_name,
            rag_context=rag_context,
        )

        # Step 3: Call Gemini
        logger.info(
            "Calling Gemini %s for village=%s category=%s",
            settings.gemini_model,
            market_ctx.village_lgd_code,
            request_data["business_category"],
        )
        response = self._model.generate_content(prompt)

        # Step 4: Parse JSON response
        raw_text = response.text
        analysis = self._parse_json_response(raw_text)

        # Step 5: Override population values with our DB values (Gemini may hallucinate)
        analysis["market"]["population_5km"] = market_ctx.population_5km
        analysis["market"]["population_10km"] = market_ctx.population_10km

        return analysis

    def _build_prompt(
        self,
        request_data: dict[str, Any],
        market_ctx: MarketContext,
        category_display_name: str,
        rag_context: str,
    ) -> str:
        """Build the market analysis prompt with real data interpolated."""
        commodity_prices_str = (
            json.dumps(market_ctx.commodity_prices[:5], ensure_ascii=False)
            if market_ctx.commodity_prices
            else "No recent price data available for this district"
        )

        risk_factors = []
        cat_cfg = market_ctx.category_config or {}
        if cat_cfg.get("risk_factors"):
            risk_factors = cat_cfg["risk_factors"]

        target_segments = []
        if cat_cfg.get("target_segments"):
            target_segments = cat_cfg["target_segments"]

        prompt = MARKET_ANALYSIS_PROMPT.replace(
            "$village_name", market_ctx.village_name
        ).replace(
            "$village_lgd_code", market_ctx.village_lgd_code
        ).replace(
            "$district_name", request_data.get("district_name", "")
        ).replace(
            "$state_name", request_data.get("state_name", "")
        ).replace(
            "$business_category_display", category_display_name
        ).replace(
            "$business_idea", request_data.get("business_idea", "Not specified")
        ).replace(
            "$margin_capital", f"{request_data['margin_capital']:,.0f}"
        ).replace(
            "$radius_km", str(request_data.get("radius_km", 10))
        ).replace(
            "$population_5km", str(market_ctx.population_5km)
        ).replace(
            "$population_10km", str(market_ctx.population_10km)
        ).replace(
            "$avg_monthly_expenditure", str(market_ctx.avg_monthly_expenditure or "N/A")
        ).replace(
            "$deprived_pct", str(market_ctx.deprived_households_pct or "N/A")
        ).replace(
            "$literacy_rate", str(market_ctx.literacy_rate_pct or "N/A")
        ).replace(
            "$competitor_count", str(market_ctx.competitor_count_10km)
        ).replace(
            "$district_businesses", str(market_ctx.district_total_businesses)
        ).replace(
            "$inflation_rate", str(market_ctx.inflation_rate or "N/A")
        ).replace(
            "$commodity_prices", commodity_prices_str
        ).replace(
            "$risk_factors", json.dumps(risk_factors, ensure_ascii=False)
        ).replace(
            "$target_segments", json.dumps(target_segments, ensure_ascii=False)
        ).replace(
            "$rag_context", rag_context
        )

        return prompt

    def _parse_json_response(self, raw_text: str) -> dict[str, Any]:
        """Parse and validate Gemini JSON response."""
        # Try direct parse first (Gemini JSON mode usually returns clean JSON)
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Fallback: extract JSON from markdown code blocks
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Last resort: find first { ... } block
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.error("Failed to parse Gemini response: %s", raw_text[:500])
        raise ValueError("Gemini returned non-parseable response. Please retry.")
