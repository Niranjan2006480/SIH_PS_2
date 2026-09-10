from app.services.financial_engine import _round_inr, build_monthly_schedule, calculate_emi


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


def test_build_monthly_schedule():
    schedule = build_monthly_schedule(
        principal=100000,
        annual_rate_pct=10.0,
        tenure_months=12,
        moratorium_months=0,
    )
    assert len(schedule) == 12
    assert schedule[0].period_number == 1
    # Check that final balance approaches 0
    assert schedule[-1].closing_balance < 10.0
