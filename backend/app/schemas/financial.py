"""
Financial Schemas — Request/Response for Module 2 calculations.
"""


from pydantic import BaseModel, Field


class FinancialCalculationRequest(BaseModel):
    margin_capital: float = Field(..., gt=0, description="Available margin capital in INR")
    village_lgd_code: str | None = Field(None)
    user_id: str | None = Field(None)


class RepaymentPeriod(BaseModel):
    period_number: int
    period_label: str
    is_moratorium: bool
    opening_balance: float
    principal: float
    interest: float
    payment: float
    closing_balance: float


class SchemeResponse(BaseModel):
    scheme_id: str
    scheme_code: str
    scheme_name: str
    category: str
    loan_percentage: float
    max_loan_amount: float
    annual_interest_rate: float
    tenure_months: int
    tenure_years: float
    moratorium_months: int
    repayment_frequency: str

    model_config = {"from_attributes": True}


class FinancialCalculationResponse(BaseModel):
    calculation_id: str
    available_margin: float
    project_cost: float
    theoretical_loan: float
    eligible_loan: float
    funding_gap: float
    scheme: SchemeResponse
    monthly_emi: float
    quarterly_payment: float
    total_repayment: float
    total_interest: float
    moratorium_interest_total: float
    repayment_schedule_monthly: list[RepaymentPeriod]
    repayment_schedule_quarterly: list[RepaymentPeriod]


class SchemesListResponse(BaseModel):
    schemes: list[SchemeResponse]
    total: int
