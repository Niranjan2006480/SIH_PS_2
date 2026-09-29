from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.financial_engine import (
    FinancialEngine,
    _round_inr,
    build_monthly_schedule,
    calculate_emi,
)


def _make_db_mock():
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.execute.side_effect = Exception("DB offline in test")
    return db


def test_round_inr():
    assert _round_inr(1234.56, 100) == 1200.0
    assert _round_inr(1260.00, 100) == 1300.0


def test_calculate_emi():
    # Standard loan: 100,000 INR at 12% for 12 months, no moratorium
    emi = calculate_emi(100000, 12.0, 12, 0)
    assert 8800 <= emi <= 8950

    # Edge cases
    assert calculate_emi(0, 10.0, 12) == 0.0
    assert calculate_emi(10000, 0, 12) == 0.0
    assert calculate_emi(10000, 10.0, 0) == 0.0


def test_build_monthly_schedule_moratorium_included():
    # Micro finance schedule: 36 months total (3 moratorium + 33 repayment)
    schedule = build_monthly_schedule(
        principal=100000,
        annual_rate_pct=6.5,
        tenure_months=36,
        moratorium_months=3,
    )
    assert len(schedule) == 36
    assert schedule[0].is_moratorium is True
    assert schedule[2].is_moratorium is True
    assert schedule[3].is_moratorium is False
    assert schedule[-1].closing_balance == 0.0


@pytest.mark.asyncio
async def test_sih_micro_finance_calculation():
    engine = FinancialEngine()
    db_mock = _make_db_mock()

    # Margin 10,000 -> Project Cost 100,000 (<= 1.40L)
    res = await engine.calculate(margin_capital=10000, db=db_mock)
    assert res.project_cost == 100000.0
    assert res.eligible_loan == 90000.0
    assert res.scheme.scheme_code == "NBCFDC_MICRO_FINANCE"
    assert res.scheme.annual_interest_rate == 6.5
    assert res.scheme.tenure_months == 36
    assert res.scheme.moratorium_months == 3
    assert len(res.repayment_schedule_monthly) == 36
    # Total interest = Total repayment - Loan amount (no double counting)
    assert round(res.total_repayment - res.eligible_loan, 2) == res.total_interest


# ============================================================================
# SIH PS 26091 MANDATORY BOUNDARY TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_sih_boundary_test_1_micro_finance():
    """
    TEST 1: Margin = ₹14,000
    Expected:
    - Project Cost = ₹1,40,000
    - Scheme = Micro Finance
    - Loan = ₹1,25,000 (90% is ₹1,26,000, capped at max ₹1,25,000)
    - Interest = 6.5%
    - Tenure = 36 months
    - Moratorium = 3 months
    - Repayment months = 33
    """
    engine = FinancialEngine()
    db_mock = _make_db_mock()

    res = await engine.calculate(margin_capital=14000.0, db=db_mock)
    assert res.project_cost == 140000.0
    assert res.scheme.category == "Micro Finance"
    assert res.scheme.scheme_code == "NBCFDC_MICRO_FINANCE"
    assert res.eligible_loan == 125000.0
    assert res.eligible_loan <= 125000.0
    assert res.scheme.annual_interest_rate == 6.5
    assert res.scheme.tenure_months == 36
    assert res.scheme.moratorium_months == 3
    repayment_months = res.scheme.tenure_months - res.scheme.moratorium_months
    assert repayment_months == 33
    active_repayment_periods = [p for p in res.repayment_schedule_monthly if not p.is_moratorium]
    assert len(active_repayment_periods) == 33
    assert len(res.repayment_schedule_monthly) == 36


@pytest.mark.asyncio
async def test_sih_boundary_test_2_term_loan_lower():
    """
    TEST 2: Margin = ₹14,001
    Expected:
    - Project Cost = ₹1,40,010
    - Scheme = Term Loan
    - Interest = 8%
    - Tenure = 84 months
    - Moratorium = 6 months
    - Repayment months = 78
    """
    engine = FinancialEngine()
    db_mock = _make_db_mock()

    res = await engine.calculate(margin_capital=14001.0, db=db_mock)
    assert res.project_cost == 140010.0
    assert res.scheme.category == "Term Loan"
    assert res.scheme.scheme_code == "NBCFDC_TERM_LOAN"
    assert res.scheme.annual_interest_rate == 8.0
    assert res.scheme.tenure_months == 84
    assert res.scheme.moratorium_months == 6
    repayment_months = res.scheme.tenure_months - res.scheme.moratorium_months
    assert repayment_months == 78
    active_repayment_periods = [p for p in res.repayment_schedule_monthly if not p.is_moratorium]
    assert len(active_repayment_periods) == 78
    assert len(res.repayment_schedule_monthly) == 84


@pytest.mark.asyncio
async def test_sih_boundary_test_3_term_loan_upper():
    """
    TEST 3: Margin = ₹5,00,000
    Expected:
    - Project Cost = ₹50,00,000
    - Scheme = Term Loan
    - Loan = ₹45,00,000 (90% is ₹45,00,000, max ₹45,00,000)
    - Interest = 8%
    - Tenure = 84 months
    - Moratorium = 6 months
    - Repayment months = 78
    """
    engine = FinancialEngine()
    db_mock = _make_db_mock()

    res = await engine.calculate(margin_capital=500000.0, db=db_mock)
    assert res.project_cost == 5000000.0
    assert res.scheme.category == "Term Loan"
    assert res.scheme.scheme_code == "NBCFDC_TERM_LOAN"
    assert res.eligible_loan == 4500000.0
    assert res.eligible_loan <= 4500000.0
    assert res.scheme.annual_interest_rate == 8.0
    assert res.scheme.tenure_months == 84
    assert res.scheme.moratorium_months == 6
    repayment_months = res.scheme.tenure_months - res.scheme.moratorium_months
    assert repayment_months == 78
    active_repayment_periods = [p for p in res.repayment_schedule_monthly if not p.is_moratorium]
    assert len(active_repayment_periods) == 78
    assert len(res.repayment_schedule_monthly) == 84


@pytest.mark.asyncio
async def test_sih_boundary_test_4_ineligible_exceeds_50_lakh():
    """
    TEST 4: Margin = ₹5,00,001
    Expected:
    - Project Cost = ₹50,00,010
    - Calculation is rejected (raises ValueError)
    - Error indicates the project is not eligible because it exceeds ₹50 lakh
    """
    engine = FinancialEngine()
    db_mock = _make_db_mock()

    derived_cost = round(500001.0 / 0.10, 2)
    assert derived_cost == 5000010.0

    with pytest.raises(ValueError) as exc_info:
        await engine.calculate(margin_capital=500001.0, db=db_mock)

    err_msg = str(exc_info.value)
    assert "exceeds the maximum eligible limit of ₹50.00 Lakh" in err_msg
    assert "Not eligible" in err_msg
