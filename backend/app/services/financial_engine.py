"""
Financial Engine Service
Handles: scheme selection, EMI calculation, full amortization schedule generation.
All logic reads from the database scheme_rules table (not hardcoded).
"""

import math
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheme import FinancialCalculation, RepaymentScheduleEntry, SchemeRule
from app.schemas.financial import (
    FinancialCalculationResponse,
    RepaymentPeriod,
    SchemeResponse,
)


def _round_inr(value: float, nearest: int = 100) -> float:
    """Round to nearest rupee unit (default: nearest ₹100)."""
    return round(round(value / nearest) * nearest, 2)


def calculate_emi(
    principal: float,
    annual_rate_pct: float,
    tenure_months: int,
    moratorium_months: int = 0,
) -> float:
    """
    Standard reducing-balance EMI with moratorium capitalization.
    During moratorium, interest accrues and is capitalized into the principal.
    EMI is then computed on the inflated principal for the remaining tenure.
    """
    if principal <= 0 or annual_rate_pct <= 0 or tenure_months <= 0:
        return 0.0

    monthly_rate = annual_rate_pct / 1200
    # Capitalize interest during moratorium
    capitalized_principal = principal * ((1 + monthly_rate) ** moratorium_months)
    # Standard EMI formula
    emi = (
        capitalized_principal
        * monthly_rate
        * ((1 + monthly_rate) ** tenure_months)
    ) / (((1 + monthly_rate) ** tenure_months) - 1)
    return round(emi, 2)


def build_monthly_schedule(
    principal: float,
    annual_rate_pct: float,
    tenure_months: int,
    moratorium_months: int = 0,
    monthly_emi: Optional[float] = None,
) -> list[RepaymentPeriod]:
    """Generate a full month-by-month amortization schedule."""
    if monthly_emi is None:
        monthly_emi = calculate_emi(principal, annual_rate_pct, tenure_months, moratorium_months)

    monthly_rate = annual_rate_pct / 1200
    schedule: list[RepaymentPeriod] = []
    balance = principal
    total_periods = moratorium_months + tenure_months

    for i in range(total_periods):
        is_moratorium = i < moratorium_months
        opening = balance
        interest = round(balance * monthly_rate, 2)

        if is_moratorium:
            # Interest accrues, no principal payment
            payment = 0.0
            principal_paid = 0.0
            balance = opening + interest
        else:
            payment = monthly_emi
            principal_paid = round(min(balance, max(0.0, payment - interest)), 2)
            balance = round(max(0.0, balance - principal_paid), 2)
            # Last period adjustment to clear rounding residue
            if i == total_periods - 1 and balance > 0:
                principal_paid += balance
                payment = principal_paid + interest
                balance = 0.0

        period_num = i + 1
        period_label = (
            f"Moratorium Month {period_num}"
            if is_moratorium
            else f"Month {i + 1 - moratorium_months}"
        )
        schedule.append(
            RepaymentPeriod(
                period_number=period_num,
                period_label=period_label,
                is_moratorium=is_moratorium,
                opening_balance=round(opening, 2),
                principal=principal_paid,
                interest=interest,
                payment=round(payment, 2),
                closing_balance=round(balance, 2),
            )
        )
    return schedule


def build_quarterly_schedule(
    monthly_schedule: list[RepaymentPeriod],
) -> list[RepaymentPeriod]:
    """Convert monthly schedule to quarterly view by aggregating every 3 months."""
    quarterly: list[RepaymentPeriod] = []
    for i in range(0, len(monthly_schedule), 3):
        chunk = monthly_schedule[i : i + 3]
        if not chunk:
            break
        q_num = i // 3 + 1
        is_moro = all(p.is_moratorium for p in chunk)
        quarterly.append(
            RepaymentPeriod(
                period_number=q_num,
                period_label=(
                    f"Moratorium Q{q_num}" if is_moro else f"Quarter {q_num}"
                ),
                is_moratorium=is_moro,
                opening_balance=chunk[0].opening_balance,
                principal=round(sum(p.principal for p in chunk), 2),
                interest=round(sum(p.interest for p in chunk), 2),
                payment=round(sum(p.payment for p in chunk), 2),
                closing_balance=chunk[-1].closing_balance,
            )
        )
    return quarterly


class FinancialEngine:
    """
    Core financial engine.
    - Reads scheme rules from database.
    - Computes project cost, loan amount, EMI, and full amortization.
    - Persists calculation snapshot.
    """

    async def get_all_schemes(self, db: AsyncSession) -> list[SchemeRule]:
        result = await db.execute(
            select(SchemeRule)
            .where(SchemeRule.is_active == True)  # noqa: E712
            .order_by(SchemeRule.min_project_cost)
        )
        return list(result.scalars().all())

    async def select_scheme(
        self, project_cost: float, db: AsyncSession
    ) -> Optional[SchemeRule]:
        """Select the best matching scheme for a given project cost."""
        result = await db.execute(
            select(SchemeRule)
            .where(
                SchemeRule.is_active == True,  # noqa: E712
                SchemeRule.min_project_cost <= project_cost,
                SchemeRule.max_project_cost >= project_cost,
            )
            .order_by(SchemeRule.annual_interest_rate)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def calculate(
        self,
        margin_capital: float,
        db: AsyncSession,
        village_lgd_code: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> FinancialCalculationResponse:
        """
        Full financial calculation pipeline.
        1. Derive project cost (margin / 10%)
        2. Select matching scheme
        3. Compute EMI and full amortization schedule
        4. Persist to DB
        """
        # Step 1: Derive project cost
        raw_project_cost = margin_capital / 0.10
        # Round to nearest 100
        project_cost = _round_inr(raw_project_cost, 100)

        # Step 2: Select scheme
        scheme = await self.select_scheme(project_cost, db)
        if scheme is None:
            # Fallback: find highest scheme if over limit
            result = await db.execute(
                select(SchemeRule)
                .where(SchemeRule.is_active == True)  # noqa: E712
                .order_by(SchemeRule.max_project_cost.desc())
                .limit(1)
            )
            scheme = result.scalar_one_or_none()

        if scheme is None:
            raise ValueError("No active scheme rules found in database. Please seed scheme_rules.")

        # Step 3: Compute loan amounts
        theoretical_loan = project_cost * (float(scheme.loan_percentage) / 100)
        eligible_loan = min(theoretical_loan, float(scheme.max_loan_amount))
        required_margin = project_cost - eligible_loan
        funding_gap = max(0.0, required_margin - margin_capital)

        # Step 4: EMI calculation
        annual_rate = float(scheme.annual_interest_rate)
        tenure_months = scheme.tenure_months
        moratorium_months = scheme.moratorium_months

        monthly_emi = calculate_emi(eligible_loan, annual_rate, tenure_months, moratorium_months)
        quarterly_payment = round(monthly_emi * 3, 2)

        # Step 5: Build schedules
        monthly_schedule = build_monthly_schedule(
            eligible_loan, annual_rate, tenure_months, moratorium_months, monthly_emi
        )
        quarterly_schedule = build_quarterly_schedule(monthly_schedule)

        # Step 6: Totals
        total_repayment = round(sum(p.payment for p in monthly_schedule), 2)
        moratorium_interest = round(
            sum(p.interest for p in monthly_schedule if p.is_moratorium), 2
        )
        total_interest = round(total_repayment - eligible_loan + moratorium_interest, 2)

        # Step 7: Persist to DB
        calc = FinancialCalculation(
            id=uuid.uuid4(),
            user_id=user_id,
            location_id=village_lgd_code,
            scheme_id=scheme.scheme_id,
            available_margin=margin_capital,
            raw_project_cost=raw_project_cost,
            project_cost=project_cost,
            theoretical_loan=theoretical_loan,
            eligible_loan=eligible_loan,
            required_margin=required_margin,
            funding_gap=funding_gap,
            annual_interest_rate=annual_rate,
            tenure_months=tenure_months,
            moratorium_months=moratorium_months,
            moratorium_interest_mode=scheme.moratorium_interest_policy,
            monthly_emi=monthly_emi,
            quarterly_payment=quarterly_payment,
            rules_version=scheme.version,
        )
        db.add(calc)

        # Persist first 24 monthly periods to DB for reference
        for period in monthly_schedule[:24]:
            db.add(
                RepaymentScheduleEntry(
                    calculation_id=calc.id,
                    period_number=period.period_number,
                    period_type="month",
                    opening_balance=period.opening_balance,
                    payment=period.payment,
                    principal_component=period.principal,
                    interest_component=period.interest,
                    closing_balance=period.closing_balance,
                )
            )
        await db.flush()

        return FinancialCalculationResponse(
            calculation_id=str(calc.id),
            available_margin=margin_capital,
            project_cost=project_cost,
            theoretical_loan=theoretical_loan,
            eligible_loan=eligible_loan,
            funding_gap=funding_gap,
            scheme=SchemeResponse(
                scheme_id=str(scheme.scheme_id),
                scheme_code=scheme.scheme_code,
                scheme_name=scheme.scheme_name,
                category=scheme.category,
                loan_percentage=float(scheme.loan_percentage),
                max_loan_amount=float(scheme.max_loan_amount),
                annual_interest_rate=annual_rate,
                tenure_months=tenure_months,
                tenure_years=round(tenure_months / 12, 1),
                moratorium_months=moratorium_months,
                repayment_frequency=scheme.repayment_frequency,
            ),
            monthly_emi=monthly_emi,
            quarterly_payment=quarterly_payment,
            total_repayment=total_repayment,
            total_interest=total_interest,
            moratorium_interest_total=moratorium_interest,
            repayment_schedule_monthly=monthly_schedule,
            repayment_schedule_quarterly=quarterly_schedule,
        )
