"""
Analysis Schemas — Request/Response for the core AI feasibility analysis.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    village_lgd_code: str = Field(..., description="LGD code of the village")
    village_name: str = Field(..., description="Village name (for display)")
    district_name: str = Field(..., description="District name (for display)")
    state_name: str = Field(..., description="State name (for display)")
    business_category: str = Field(..., description="Business category code")
    business_idea: str = Field("", description="Free-text business idea description")
    margin_capital: float = Field(..., gt=0, description="Available margin capital in INR")
    radius_km: Literal[5, 10] = Field(10, description="Analysis radius in km")
    language: str = Field("en", description="Output language code")


# ── Sub-response models ───────────────────────────────────────────────────────

class MarketData(BaseModel):
    population_5km: int
    population_10km: int
    potential_segment: int
    estimated_customers: int
    distribution_channels: list[str]


class OpportunityData(BaseModel):
    score: int
    title: str
    detail: str
    signals: list[str]


class SwotItem(BaseModel):
    title: Literal["Strengths", "Weaknesses", "Opportunities", "Threats"]
    items: list[str]


class RiskItem(BaseModel):
    name: str
    level: Literal["Low", "Medium", "High"]
    detail: str
    action: str


class CompetitorData(BaseModel):
    count: int
    density: str
    categories: list[str]
    differentiators: list[str]


class PricingData(BaseModel):
    low: float
    base: float
    premium: float
    margin_pct: float
    unit: str
    rationale: str


class ScoreBreakdown(BaseModel):
    label: str
    value: int


class WorkingCapitalData(BaseModel):
    setup: float
    raw_materials: float
    inventory: float
    transport: float
    utilities: float
    staff: float
    marketing: float
    reserve: float


class RecommendationData(BaseModel):
    label: str
    title: str
    detail: str
    reserve: float
    checklist: list[str]


# ── Main Response ─────────────────────────────────────────────────────────────

class AnalysisResponse(BaseModel):
    report_id: str
    village_lgd_code: str
    village_name: str
    district_name: str
    state_name: str
    business_category: str
    business_category_display: str
    margin_capital: float
    radius_km: int

    # Module 1 — Business Feasibility
    viability_score: int
    scores: list[ScoreBreakdown]
    market: MarketData
    opportunity: OpportunityData
    swot: list[SwotItem]
    risks: list[RiskItem]
    competitors: CompetitorData
    pricing: PricingData
    working_capital: WorkingCapitalData
    recommendation: RecommendationData

    # Module 2 — Financial (included in main response for efficiency)
    project_cost: float
    loan_amount: float
    scheme_code: Optional[str] = None
    scheme_name: Optional[str] = None
    interest_rate: Optional[float] = None
    tenure_years: Optional[float] = None
    moratorium_months: Optional[int] = None
    monthly_emi: Optional[float] = None
    total_repayment: Optional[float] = None

    # Data source metadata
    data_sources: list[str] = []
    confidence_score: float
    is_cached: bool = False

    model_config = {"from_attributes": True}
