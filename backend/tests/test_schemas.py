import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisRequest, RiskItem


def test_analysis_request_valid():
    req = AnalysisRequest(
        village_lgd_code="550001",
        village_name="Baramati Rural",
        district_name="Pune",
        state_name="Maharashtra",
        business_category="dairy_processing",
        margin_capital=50000.0,
        radius_km=10,
        language="en",
    )
    assert req.village_lgd_code == "550001"
    assert req.margin_capital == 50000.0
    assert req.radius_km == 10


def test_analysis_request_invalid_capital():
    with pytest.raises(ValidationError):
        AnalysisRequest(
            village_lgd_code="550001",
            village_name="Baramati Rural",
            district_name="Pune",
            state_name="Maharashtra",
            business_category="dairy_processing",
            margin_capital=-1000.0,
            radius_km=10,
        )


def test_risk_item_validation():
    item = RiskItem(
        name="Market Risk",
        level="High",
        detail="High competition in 5km radius",
        action="Focus on value-added dairy products",
    )
    assert item.level == "High"
