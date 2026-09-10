"""
Analysis Schemas — Request/Response for the core AI feasibility analysis.
"""

from typing import Literal

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


class CompetitorItem(BaseModel):
    name: str
    category: str
    distance_km: float
    latitude: float | None = None
    longitude: float | None = None
    strength: Literal["High", "Moderate", "Emerging"] = "Moderate"
    offering: str = ""


class CompetitorData(BaseModel):
    count: int
    density: str
    categories: list[str]
    differentiators: list[str]
    items: list[CompetitorItem] = []


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
    latitude: float | None = None
    longitude: float | None = None

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
    scheme_code: str | None = None
    scheme_name: str | None = None
    interest_rate: float | None = None
    tenure_years: float | None = None
    moratorium_months: int | None = None
    monthly_emi: float | None = None
    total_repayment: float | None = None

    # Data source metadata
    data_sources: list[str] = []
    confidence_score: float
    is_cached: bool = False

    model_config = {"from_attributes": True}
