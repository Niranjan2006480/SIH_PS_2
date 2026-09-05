export type BusinessCategory =
  | "Dairy"
  | "Agriculture"
  | "Food Processing"
  | "Retail"
  | "Textiles"
  | "Tailoring"
  | "Manufacturing"
  | "Handicrafts"
  | "Transportation"
  | "Repair Services"
  | "Beauty & Personal Care"
  | "Digital Services"
  | "Livestock"
  | "Other";

export interface LocationInput {
  state: string;
  district: string;
  block: string;
  village: string;
  radius: 5 | 10;
}

export interface BusinessInput extends LocationInput {
  capital: number;
  category: BusinessCategory;
  idea: string;
}

export interface Scheme {
  name: string;
  funding: string;
  interest: number;
  tenure: number;
  moratorium: number;
  maxFunding: number;
  minimumCapital: number;
}

export interface AnalysisReport {
  business: BusinessCategory;
  location: LocationInput;
  projectCost: number;
  loan: number;
  scheme: Scheme | null;
  emi: number;
  totalRepayment: number;
  totalInterest: number;
  viabilityScore: number;
  scores: { label: string; value: number }[];
  market: { within5: number; within10: number; segment: number; customers: number; channels: string[] };
  opportunity: { score: number; title: string; detail: string; signals: string[] };
  swot: { title: string; items: string[] }[];
  risks: { name: string; level: "Low" | "Medium" | "High"; detail: string; action: string }[];
  competitors: { count: number; density: string; categories: string[]; differentiators: string[] };
  pricing: { low: number; base: number; premium: number; margin: number; unit: string };
  workingCapital: { setup: number; rawMaterials: number; inventory: number; transport: number; utilities: number; staff: number; marketing: number; reserve: number };
  recommendation: { label: string; title: string; detail: string; reserve: number; checklist: string[] };
}

export const categories: { name: BusinessCategory; icon: string }[] = [
  { name: "Dairy", icon: "◒" },
  { name: "Agriculture", icon: "⌁" },
  { name: "Food Processing", icon: "◉" },
  { name: "Retail", icon: "▥" },
  { name: "Textiles", icon: "▤" },
  { name: "Tailoring", icon: "⌘" },
  { name: "Manufacturing", icon: "⚙" },
  { name: "Handicrafts", icon: "✦" },
  { name: "Transportation", icon: "↗" },
  { name: "Repair Services", icon: "⌁" },
  { name: "Beauty & Personal Care", icon: "✽" },
  { name: "Digital Services", icon: "⌘" },
  { name: "Livestock", icon: "◌" },
  { name: "Other", icon: "＋" },
];

export const demoInput: BusinessInput = {
  state: "Karnataka",
  district: "Belagavi",
  block: "Belagavi",
  village: "Kadri",
  radius: 10,
  capital: 100000,
  category: "Dairy",
  idea: "A small dairy unit supplying fresh milk and packaged curd to nearby households and shops.",
};

const roundRupee = (value: number) => Math.round(value / 100) * 100;

export function selectScheme(projectCost: number): Scheme | null {
  if (projectCost <= 0) return null;
  if (projectCost <= 140000) {
    return { name: "Micro Finance Scheme", funding: "Up to 90%", interest: 6.5, tenure: 3, moratorium: 3, maxFunding: 125000, minimumCapital: 15556 };
  }
  if (projectCost <= 5000000) {
    return { name: "Term Loan Scheme", funding: "Up to 90%", interest: 8, tenure: 7, moratorium: 6, maxFunding: 4500000, minimumCapital: 15556 };
  }
  return null;
}

export function calculateEmi(principal: number, annualRate: number, years: number, moratoriumMonths = 0): number {
  if (!principal || !annualRate || !years) return 0;
  const months = years * 12;
  const monthlyRate = annualRate / 1200;
  const capitalizedPrincipal = principal * (1 + monthlyRate) ** Math.max(0, moratoriumMonths);
  return Math.round((capitalizedPrincipal * monthlyRate * (1 + monthlyRate) ** months) / ((1 + monthlyRate) ** months - 1));
}

export function buildAnalysis(input: BusinessInput): AnalysisReport {
  const projectCost = roundRupee(input.capital * 10);
  const loan = roundRupee(projectCost * 0.9);
  const scheme = selectScheme(projectCost);
  const annualRate = scheme?.interest ?? 8;
  const tenure = scheme?.tenure ?? 7;
  const financedPrincipal = Math.min(loan, scheme?.maxFunding ?? loan);
  const emi = calculateEmi(financedPrincipal, annualRate, tenure, scheme?.moratorium ?? 0);
  const totalRepayment = emi * tenure * 12;
  const categoryBoost = input.category === "Dairy" || input.category === "Food Processing" ? 3 : 0;
  const viabilityScore = Math.min(96, Math.max(48, 79 + categoryBoost + (input.capital >= 100000 ? 0 : -8) + (input.radius === 10 ? 1 : -1)));
  const base = input.category === "Dairy" ? 52 : input.category === "Tailoring" ? 850 : input.category === "Digital Services" ? 450 : 120;
  const market10 = input.radius === 10 ? 11600 : 4200;
  const reserve = roundRupee(Math.max(60000, projectCost * 0.12));
  return {
    business: input.category,
    location: input,
    projectCost,
    loan,
    scheme,
    emi,
    totalRepayment,
    totalInterest: Math.max(0, totalRepayment - financedPrincipal),
    viabilityScore,
    scores: [{ label: "Demand", value: 88 }, { label: "Competition", value: 72 }, { label: "Capital Fit", value: 91 }, { label: "Risk", value: 68 }, { label: "Pricing Potential", value: 84 }],
    market: { within5: 4200, within10: market10, segment: 2900, customers: 860, channels: ["Local retail stores", "Weekly markets", "Direct-to-consumer", "WhatsApp ordering", "Nearby towns"] },
    opportunity: { score: 86, title: `Strong ${input.category.toLowerCase()} demand with room for a local-first offer`, detail: `Local demand appears stronger for accessible, reliable products than premium specialty products. A consistent service model can win trust in ${input.village || "your locality"}.`, signals: ["Repeat household demand", "Underserved nearby hamlets", "Short distribution distance"] },
    swot: [
      { title: "Strengths", items: ["Direct customer access", "Low transport distance", "Existing local demand"] },
      { title: "Weaknesses", items: ["Limited first capital", "Supplier dependency", "Early brand awareness"] },
      { title: "Opportunities", items: ["Nearby town expansion", "WhatsApp ordering", "Packaged local line"] },
      { title: "Threats", items: ["Seasonal demand dips", "Raw material price swings", "Established competitors"] },
    ],
    risks: [
      { name: "Supply Chain Risk", level: "Low", detail: "Nearby sourcing reduces average replenishment distance.", action: "Identify two suppliers before launch." },
      { name: "Seasonality Risk", level: "Medium", detail: "Demand may soften during harvest and festival cycles.", action: "Keep a 3-month operating reserve." },
      { name: "Competition Risk", level: "Medium", detail: "Customers already have familiar local options.", action: "Differentiate with delivery and reliability." },
      { name: "Working Capital Risk", level: input.capital < 50000 ? "High" : "Low", detail: "Early cash cycles can be tighter than expected.", action: "Ring-fence cash for supplies and utilities." },
    ],
    competitors: { count: input.radius === 10 ? 18 : 8, density: "Moderate", categories: ["Local independent units", "Weekly market sellers", "Regional distributors"], differentiators: ["Lower delivery time", "Subscription model", "Better packaging", "Transparent pricing"] },
    pricing: { low: Math.round(base * 0.86), base, premium: Math.round(base * 1.15), margin: 38, unit: input.category === "Dairy" ? "per litre / unit" : "per sale" },
    workingCapital: { setup: roundRupee(projectCost * 0.62), rawMaterials: roundRupee(projectCost * 0.08), inventory: roundRupee(projectCost * 0.05), transport: roundRupee(projectCost * 0.025), utilities: roundRupee(projectCost * 0.02), staff: roundRupee(projectCost * 0.035), marketing: roundRupee(projectCost * 0.015), reserve },
    recommendation: { label: viabilityScore >= 75 ? "Proceed — with modifications" : "Validate further before proceeding", title: `Your ${input.category.toLowerCase()} idea has a workable local opportunity.`, detail: `Start with a focused ${input.category.toLowerCase()} offer, validate demand with local customers and protect your first working-capital cycle. Maintain at least ${formatINR(reserve)} as a reserve.`, reserve, checklist: ["Validate demand with 20–30 local customers", "Confirm supplier pricing", "Identify at least 2 suppliers", "Track monthly operating costs", "Keep emergency working capital", "Compare local competitor pricing"] },
  };
}

export function formatINR(value: number): string {
  return `₹${Math.round(value).toLocaleString("en-IN")}`;
}

export function formatLakh(value: number): string {
  if (value >= 100000) return `₹${(value / 100000).toFixed(value % 100000 === 0 ? 0 : 1)}L`;
  return formatINR(value);
}