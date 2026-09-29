"""
API integration tests for Financial Calculation Endpoint
Endpoint: POST /api/v1/financial/calculate
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_api_calculate_boundary_test_1_micro_finance(client: TestClient):
    """
    TEST 1: Margin = ₹14,000
    - Verify successful HTTP 200
    - Verify scheme: NBCFDC_MICRO_FINANCE / Micro Finance
    - Verify project_cost = ₹1,40,000
    - Verify eligible_loan = ₹1,25,000 (capped at ₹1,25,000)
    - Verify interest = 6.5%
    - Verify tenure = 36 months, moratorium = 3 months
    - Verify active repayment periods = 33
    """
    payload = {"margin_capital": 14000.0}
    response = client.post("/api/v1/financial/calculate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["available_margin"] == 14000.0
    assert data["project_cost"] == 140000.0
    assert data["eligible_loan"] == 125000.0
    assert data["eligible_loan"] <= 125000.0

    scheme = data["scheme"]
    assert scheme["scheme_code"] == "NBCFDC_MICRO_FINANCE"
    assert scheme["category"] == "Micro Finance"
    assert scheme["annual_interest_rate"] == 6.5
    assert scheme["tenure_months"] == 36
    assert scheme["moratorium_months"] == 3
    assert scheme["tenure_months"] - scheme["moratorium_months"] == 33

    monthly_schedule = data["repayment_schedule_monthly"]
    assert len(monthly_schedule) == 36
    active_periods = [p for p in monthly_schedule if not p["is_moratorium"]]
    assert len(active_periods) == 33


def test_api_calculate_boundary_test_2_term_loan_lower(client: TestClient):
    """
    TEST 2: Margin = ₹14,001
    - Verify successful HTTP 200
    - Verify scheme: NBCFDC_TERM_LOAN / Term Loan
    - Verify project_cost = ₹1,40,010
    - Verify interest = 8%
    - Verify tenure = 84 months, moratorium = 6 months
    - Verify active repayment periods = 78
    """
    payload = {"margin_capital": 14001.0}
    response = client.post("/api/v1/financial/calculate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["available_margin"] == 14001.0
    assert data["project_cost"] == 140010.0

    scheme = data["scheme"]
    assert scheme["scheme_code"] == "NBCFDC_TERM_LOAN"
    assert scheme["category"] == "Term Loan"
    assert scheme["annual_interest_rate"] == 8.0
    assert scheme["tenure_months"] == 84
    assert scheme["moratorium_months"] == 6
    assert scheme["tenure_months"] - scheme["moratorium_months"] == 78

    monthly_schedule = data["repayment_schedule_monthly"]
    assert len(monthly_schedule) == 84
    active_periods = [p for p in monthly_schedule if not p["is_moratorium"]]
    assert len(active_periods) == 78


def test_api_calculate_boundary_test_3_term_loan_upper(client: TestClient):
    """
    TEST 3: Margin = ₹5,00,000
    - Verify successful HTTP 200
    - Verify scheme: NBCFDC_TERM_LOAN / Term Loan
    - Verify project_cost = ₹50,00,000
    - Verify eligible_loan = ₹45,00,000 (capped at ₹45,00,000)
    - Verify interest = 8%
    - Verify tenure = 84 months, moratorium = 6 months
    - Verify active repayment periods = 78
    """
    payload = {"margin_capital": 500000.0}
    response = client.post("/api/v1/financial/calculate", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["available_margin"] == 500000.0
    assert data["project_cost"] == 5000000.0
    assert data["eligible_loan"] == 4500000.0
    assert data["eligible_loan"] <= 4500000.0

    scheme = data["scheme"]
    assert scheme["scheme_code"] == "NBCFDC_TERM_LOAN"
    assert scheme["category"] == "Term Loan"
    assert scheme["annual_interest_rate"] == 8.0
    assert scheme["tenure_months"] == 84
    assert scheme["moratorium_months"] == 6
    assert scheme["tenure_months"] - scheme["moratorium_months"] == 78

    monthly_schedule = data["repayment_schedule_monthly"]
    assert len(monthly_schedule) == 84
    active_periods = [p for p in monthly_schedule if not p["is_moratorium"]]
    assert len(active_periods) == 78


def test_api_calculate_boundary_test_4_ineligible_exceeds_50_lakh(client: TestClient):
    """
    TEST 4: Margin = ₹5,00,001
    - Derived project_cost = ₹50,00,010 (> ₹50 Lakh)
    - Verify HTTP 422 Unprocessable Entity
    - Verify response detail communicates that the project is not eligible because it exceeds ₹50 lakh
    """
    payload = {"margin_capital": 500001.0}
    response = client.post("/api/v1/financial/calculate", json=payload)
    assert response.status_code == 422

    data = response.json()
    detail = data.get("detail", "")
    assert "exceeds the maximum eligible limit of ₹50.00 Lakh" in detail
    assert "Not eligible" in detail
