/**
 * UdyamAI API Client
 * Typed fetch wrapper for all backend endpoints.
 */

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = (await res.json()) as { detail?: string };
      detail = err.detail ?? detail;
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

// ── Types (mirrors backend Pydantic schemas) ──────────────────────────────────

export interface LocationResult {
  village_lgd_code: string;
  village_name: string;
  subdistrict_name: string;
  district_name: string;
  state_name: string;
  state_code: string;
  latitude: number | null;
  longitude: number | null;
  has_coordinates: boolean;
}

export interface LocationSearchResponse {
  results: LocationResult[];
  total: number;
  query: string;
}

export interface AnalysisRequest {
  village_lgd_code: string;
  village_name: string;
  district_name: string;
  state_name: string;
  business_category: string;
  business_idea: string;
  margin_capital: number;
  radius_km: 5 | 10;
  language: string;
}

export interface ScoreBreakdown {
  label: string;
  value: number;
}

export interface MarketData {
  population_5km: number;
  population_10km: number;
  potential_segment: number;
  estimated_customers: number;
  distribution_channels: string[];
}

export interface OpportunityData {
  score: number;
  title: string;
  detail: string;
  signals: string[];
}

export interface SwotItem {
  title: "Strengths" | "Weaknesses" | "Opportunities" | "Threats";
  items: string[];
}

export interface RiskItem {
  name: string;
  level: "Low" | "Medium" | "High";
  detail: string;
  action: string;
}

export interface CompetitorData {
  count: number;
  density: string;
  categories: string[];
  differentiators: string[];
}

export interface PricingData {
  low: number;
  base: number;
  premium: number;
  margin_pct: number;
  unit: string;
  rationale: string;
}

export interface WorkingCapitalData {
  setup: number;
  raw_materials: number;
  inventory: number;
  transport: number;
  utilities: number;
  staff: number;
  marketing: number;
  reserve: number;
}

export interface RecommendationData {
  label: string;
  title: string;
  detail: string;
  reserve: number;
  checklist: string[];
}

export interface AnalysisResponse {
  report_id: string;
  village_lgd_code: string;
  village_name: string;
  district_name: string;
  state_name: string;
  business_category: string;
  business_category_display: string;
  margin_capital: number;
  radius_km: number;
  viability_score: number;
  scores: ScoreBreakdown[];
  market: MarketData;
  opportunity: OpportunityData;
  swot: SwotItem[];
  risks: RiskItem[];
  competitors: CompetitorData;
  pricing: PricingData;
  working_capital: WorkingCapitalData;
  recommendation: RecommendationData;
  project_cost: number;
  loan_amount: number;
  scheme_code: string | null;
  scheme_name: string | null;
  interest_rate: number | null;
  tenure_years: number | null;
  moratorium_months: number | null;
  monthly_emi: number | null;
  total_repayment: number | null;
  data_sources: string[];
  confidence_score: number;
  is_cached: boolean;
}

export interface SchemeInfo {
  scheme_id: string;
  scheme_code: string;
  scheme_name: string;
  category: string;
  loan_percentage: number;
  max_loan_amount: number;
  annual_interest_rate: number;
  tenure_months: number;
  tenure_years: number;
  moratorium_months: number;
  repayment_frequency: string;
}

export interface FinancialCalcRequest {
  margin_capital: number;
  village_lgd_code?: string;
}

export interface RepaymentPeriod {
  period_number: number;
  period_label: string;
  is_moratorium: boolean;
  opening_balance: number;
  principal: number;
  interest: number;
  payment: number;
  closing_balance: number;
}

export interface FinancialCalcResponse {
  calculation_id: string;
  available_margin: number;
  project_cost: number;
  theoretical_loan: number;
  eligible_loan: number;
  funding_gap: number;
  scheme: SchemeInfo;
  monthly_emi: number;
  quarterly_payment: number;
  total_repayment: number;
  total_interest: number;
  moratorium_interest_total: number;
  repayment_schedule_monthly: RepaymentPeriod[];
  repayment_schedule_quarterly: RepaymentPeriod[];
}

export interface CategoryInfo {
  code: string;
  name: string;
  target_segments: string[] | null;
}

// ── API Functions ─────────────────────────────────────────────────────────────

export const api = {
  health: () => request<{ status: string; services: Record<string, string> }>("/api/v1/health"),

  locations: {
    search: (q: string, stateCode?: string) =>
      request<LocationSearchResponse>(
        `/api/v1/locations/search?q=${encodeURIComponent(q)}${stateCode ? `&state_code=${stateCode}` : ""}&limit=10`,
      ),
    get: (lgdCode: string) => request<LocationResult>(`/api/v1/locations/${lgdCode}`),
    states: () => request<{ code: string; name: string }[]>("/api/v1/locations/states"),
    districts: (stateCode: string) =>
      request<{ state_code: string; districts: { code: string; name: string }[] }>(
        `/api/v1/locations/districts?state_code=${stateCode}`,
      ),
    villages: (districtCode: string) =>
      request<{ villages: { code: string; name: string; subdistrict_code: string }[] }>(
        `/api/v1/locations/villages?district_lgd_code=${districtCode}`,
      ),
  },

  analysis: {
    generate: (req: AnalysisRequest) =>
      request<AnalysisResponse>("/api/v1/analysis/generate", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    get: (reportId: string) => request<AnalysisResponse>(`/api/v1/analysis/${reportId}`),
    pdfUrl: (reportId: string) => `${API_BASE}/api/v1/analysis/${reportId}/pdf`,
  },

  financial: {
    schemes: () => request<{ schemes: SchemeInfo[]; total: number }>("/api/v1/financial/schemes"),
    calculate: (req: FinancialCalcRequest) =>
      request<FinancialCalcResponse>("/api/v1/financial/calculate", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    categories: () =>
      request<{ categories: CategoryInfo[]; total: number }>("/api/v1/financial/categories"),
  },
};
