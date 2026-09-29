import pytest
from unittest.mock import MagicMock, AsyncMock

from app.config import get_settings
from app.ai.ai_orchestrator import AIOrchestrator
from app.services.market_analyzer import MarketContext


def test_gemini_model_configuration():
    """Verify that only gemini-3.8-flash is configured as the active Gemini model."""
    settings = get_settings()
    assert settings.gemini_model == "gemini-3.8-flash"


@pytest.mark.asyncio
async def test_gemini_immediate_fallback_on_429():
    """Verify that when Gemini raises 429 Quota Exceeded, fallback engine is invoked immediately."""
    orchestrator = AIOrchestrator()
    # Mock RAG retriever so no network / DB call is needed
    orchestrator._rag.retrieve = AsyncMock(return_value="Sample RAG context")

    # Mock Gemini model to simulate 429 quota error
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("429 Resource has been exhausted (e.g. check quota)")
    orchestrator._model = mock_model

    market_ctx = MarketContext(
        village_lgd_code="555000",
        village_name="Test Village",
        district_lgd_code="100",
        state_code="MH",
        latitude=19.0,
        longitude=74.0,
        population_5km=5000,
        population_10km=15000,
        avg_monthly_expenditure=2500.0,
        deprived_households_pct=30.0,
        literacy_rate_pct=75.0,
        competitor_count_5km=2,
        competitor_count_10km=5,
        district_total_businesses=120,
        market_within_10km_count=1,
        road_access_quality="Good",
        commodity_prices=[],
        inflation_rate=5.5,
        category_config={"benchmark_operating_margin": 0.2},
    )

    request_data = {
        "village_lgd_code": "555000",
        "business_category": "dairy",
        "business_idea": "Dairy Farm",
        "total_capital": 500000.0,
        "margin_capital": 50000.0,
    }

    result = await orchestrator.generate_analysis(
        request_data=request_data,
        market_ctx=market_ctx,
        category_display_name="Dairy Farm",
    )

    # Verify generate_content was called exactly once (no retry loop across obsolete models)
    assert mock_model.generate_content.call_count == 1

    # Verify fallback structure returned successfully
    assert "viability_score" in result
    assert "scores" in result
    assert "opportunity" in result
    assert "market" in result
    assert result["market"]["population_5km"] == 5000
    assert result["market"]["population_10km"] == 15000
