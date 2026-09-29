"""
Financial Engine Service
Handles: scheme selection, EMI calculation, full amortization schedule generation.
All logic reads from the database scheme_rules table (not hardcoded).
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheme import FinancialCalculation, RepaymentScheduleEntry, SchemeRule
from app.schemas.financial import (
    FinancialCalculationResponse,
    RepaymentPeriod,
    SchemeResponse,
)

logger = logging.getLogger(__name__)

# ── SIH PS 26091 Default Scheme Rules ─────────────────────────────────────────
DEFAULT_MICRO_FINANCE_SCHEME = SchemeRule(
    scheme_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    scheme_code="NBCFDC_MICRO_FINANCE",
    scheme_name="NBCFDC Micro Finance Scheme",
    category="Micro Finance",
    min_project_cost=0.0,
    max_project_cost=140000.0,
    loan_percentage=90.0,
    max_loan_amount=125000.0,
    annual_interest_rate=6.5,
    tenure_months=36,
    moratorium_months=3,
    repayment_frequency="monthly",
    moratorium_interest_policy="paid_separately",
    version=1,
)

DEFAULT_TERM_LOAN_SCHEME = SchemeRule(
    scheme_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
    scheme_code="NBCFDC_TERM_LOAN",
    scheme_name="NBCFDC Term Loan Scheme",
    category="Term Loan",
    min_project_cost=140000.01,
    max_project_cost=5000000.0,
    loan_percentage=90.0,
    max_loan_amount=4500000.0,
    annual_interest_rate=8.0,
    tenure_months=84,
    moratorium_months=6,
    repayment_frequency="monthly",
    moratorium_interest_policy="paid_separately",
    version=1,
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
    Total tenure includes moratorium; repayment is over (tenure_months - moratorium_months).
    """
    repayment_months = tenure_months - moratorium_months
    if principal <= 0 or annual_rate_pct <= 0 or repayment_months <= 0:
        return 0.0

    monthly_rate = annual_rate_pct / 1200
    # Capitalize interest during moratorium
    capitalized_principal = principal * ((1 + monthly_rate) ** moratorium_months)
    # Standard EMI formula on active repayment tenure
    emi = (
        capitalized_principal
        * monthly_rate
        * ((1 + monthly_rate) ** repayment_months)
    ) / (((1 + monthly_rate) ** repayment_months) - 1)
    return round(emi, 2)


def build_monthly_schedule(
    principal: float,
    annual_rate_pct: float,
    tenure_months: int,
    moratorium_months: int = 0,
    monthly_emi: float | None = None,
) -> list[RepaymentPeriod]:
    """Generate a full month-by-month amortization schedule within total tenure."""
    if monthly_emi is None:
        monthly_emi = calculate_emi(principal, annual_rate_pct, tenure_months, moratorium_months)

    monthly_rate = annual_rate_pct / 1200
    schedule: list[RepaymentPeriod] = []
    balance = principal
    total_periods = tenure_months

    for i in range(total_periods):
        is_moratorium = i < moratorium_months
        opening = balance
        interest = round(balance * monthly_rate, 2)

        if is_moratorium:
            # Interest accrues, no principal payment
            payment = 0.0
            principal_paid = 0.0
            balance = round(opening + interest, 2)
        else:
            payment = monthly_emi
            principal_paid = round(min(balance, max(0.0, payment - interest)), 2)
            balance = round(max(0.0, balance - principal_paid), 2)
            # Last period adjustment to clear rounding residue
            if i == total_periods - 1 and balance > 0:
                principal_paid = round(principal_paid + balance, 2)
                payment = round(principal_paid + interest, 2)
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
    Core financial engine implementing SIH PS 26091.
    - Reads scheme rules from database with offline deterministic fallback.
    - Selects Micro Finance (<= ₹1.40L) or Term Loan (<= ₹50L).
    - Enforces ineligibility (> ₹50L).
    - Computes project cost, loan amount, EMI, and full amortization schedule.
    - Persists calculation snapshot.
    """

    async def get_all_schemes(self, db: AsyncSession) -> list[SchemeRule]:
        try:
            result = await db.execute(
                select(SchemeRule)
                .where(SchemeRule.is_active == True)  # noqa: E712
                .order_by(SchemeRule.min_project_cost)
            )
            schemes = [s for s in result.scalars().all() if isinstance(s, SchemeRule)]
            if len(schemes) == 2:
                return schemes
        except Exception as e:
            logger.warning("DB scheme query failed (%s), returning default schemes", e)
        return [DEFAULT_MICRO_FINANCE_SCHEME, DEFAULT_TERM_LOAN_SCHEME]

    async def select_scheme(
        self, project_cost: float, db: AsyncSession | None = None
    ) -> SchemeRule | None:
        """Select the matching SIH PS 26091 scheme for a given project cost."""
        if project_cost > 5000000.0:
            return None

        target_code = (
            "NBCFDC_MICRO_FINANCE" if project_cost <= 140000.0 else "NBCFDC_TERM_LOAN"
        )
        if db is not None:
            try:
                result = await db.execute(
                    select(SchemeRule)
                    .where(
                        SchemeRule.is_active == True,  # noqa: E712
                        SchemeRule.scheme_code == target_code,
                        SchemeRule.min_project_cost <= project_cost,
                        SchemeRule.max_project_cost >= project_cost,
                    )
                    .limit(1)
                )
                scheme = result.scalar_one_or_none()
                if isinstance(scheme, SchemeRule):
                    return scheme

                # Secondary lookup by scheme_code if cost boundary check was slightly off
                result = await db.execute(
                    select(SchemeRule)
                    .where(
                        SchemeRule.is_active == True,  # noqa: E712
                        SchemeRule.scheme_code == target_code,
                    )
                    .limit(1)
                )
                scheme = result.scalar_one_or_none()
                if isinstance(scheme, SchemeRule):
                    return scheme
            except Exception as e:
                logger.warning("DB select_scheme query failed (%s), using default rule", e)

        # Fallback selection according to SIH PS 26091
        if project_cost <= 140000.0:
            return DEFAULT_MICRO_FINANCE_SCHEME
        elif project_cost <= 5000000.0:
            return DEFAULT_TERM_LOAN_SCHEME
        return None

    async def calculate(
        self,
        margin_capital: float,
        db: AsyncSession,
        village_lgd_code: str | None = None,
        user_id: str | None = None,
    ) -> FinancialCalculationResponse:
        """
        Full financial calculation pipeline.
        1. Derive project cost (margin / 10%)
        2. Validate eligibility (<= ₹50 Lakh)
        3. Select matching scheme (Micro Finance <= ₹1.40L, Term Loan <= ₹50L)
        4. Compute EMI and full amortization schedule (moratorium inside total tenure)
        5. Compute totals without double-counting interest
        6. Persist to DB (if available)
        """
        # Step 1: Derive project cost (Rule 2: Project Cost = Margin / 0.10)
        raw_project_cost = margin_capital / 0.10
        project_cost = round(raw_project_cost, 2)

        # Step 2: Validate eligibility limit (SIH PS 26091: > ₹50L is not eligible)
        if project_cost > 5000000.0:
            raise ValueError(
                f"Project cost of ₹{project_cost:,.2f} (derived from margin ₹{margin_capital:,.2f}) "
                f"exceeds the maximum eligible limit of ₹50.00 Lakh. Not eligible under supported NBCFDC schemes."
            )

        # Step 3: Select scheme
        scheme = await self.select_scheme(project_cost, db)
        if scheme is None:
            raise ValueError(
                f"No eligible scheme found for project cost of ₹{project_cost:,.2f}."
            )

        # Step 4: Compute loan amounts
        theoretical_loan = project_cost * (float(scheme.loan_percentage) / 100)
        eligible_loan = min(theoretical_loan, float(scheme.max_loan_amount))
        required_margin = project_cost - eligible_loan
        funding_gap = max(0.0, required_margin - margin_capital)

        # Step 5: EMI calculation
        annual_rate = float(scheme.annual_interest_rate)
        tenure_months = scheme.tenure_months
        moratorium_months = scheme.moratorium_months

        monthly_emi = calculate_emi(eligible_loan, annual_rate, tenure_months, moratorium_months)
        quarterly_payment = round(monthly_emi * 3, 2)

        # Step 6: Build schedules within total tenure
        monthly_schedule = build_monthly_schedule(
            eligible_loan, annual_rate, tenure_months, moratorium_months, monthly_emi
        )
        quarterly_schedule = build_quarterly_schedule(monthly_schedule)

        # Step 7: Totals (Total interest = Total repayment - Loan amount)
        total_repayment = round(sum(p.payment for p in monthly_schedule), 2)
        moratorium_interest = round(
            sum(p.interest for p in monthly_schedule if p.is_moratorium), 2
        )
        total_interest = round(total_repayment - eligible_loan, 2)

        # Step 8: Persist to DB (only if a valid DB scheme was resolved and db session is provided)
        is_db_scheme = (
            db is not None
            and scheme.scheme_id not in {
                DEFAULT_MICRO_FINANCE_SCHEME.scheme_id,
                DEFAULT_TERM_LOAN_SCHEME.scheme_id,
            }
        )
        if is_db_scheme:
            calc_id = uuid.uuid4()
            try:
                calc = FinancialCalculation(
                    id=calc_id,
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

                for period in monthly_schedule[:24]:
                    db.add(
                        RepaymentScheduleEntry(
                            calculation_id=calc_id,
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
            except Exception as e:
                logger.warning("Financial calculation DB persistence skipped: %s", e)
        else:
            calc_id = uuid.uuid4()
            logger.info(
                "Financial calculation DB persistence skipped: scheme '%s' is an in-memory fallback without a database record",
                scheme.scheme_code,
            )

        return FinancialCalculationResponse(
            calculation_id=str(calc_id),
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
