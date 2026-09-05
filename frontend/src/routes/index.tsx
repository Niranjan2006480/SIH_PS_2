/**
 * UdyamAI — Main Application Page
 *
 * Refactored from monolithic 55KB into a clean orchestrator that:
 * 1. Manages the multi-step intake form state
 * 2. Calls the backend API for real analysis
 * 3. Renders the report using extracted components
 *
 * The visual design is preserved exactly from the original.
 */

import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight, Check, FileDown, Loader2, BarChart3, Lightbulb, ShieldCheck, DollarSign } from "lucide-react";

import type { AnalysisResponse, LocationResult } from "@/lib/api-client";
import { api } from "@/lib/api-client";
import { formatINR, selectSchemePreview, calculateEmiPreview } from "@/lib/format";
import { LocationSearch } from "@/components/form/LocationSearch";
import { ReportOverview } from "@/components/report/ReportOverview";
import { SwotGrid, RiskRadar } from "@/components/report/SwotRisk";
import { FinancePlan } from "@/components/report/financial/FinancePlan";
import { CompetitorSection, PricingSection } from "@/components/report/CompetitorPricing";
import { WorkingCapitalPlanner, RecommendationCard } from "@/components/report/WorkingCapitalRec";
import { SectionKicker, Metric } from "@/components/shared/primitives";
import { Button } from "@/components/ui/button";

// ─── Route ────────────────────────────────────────────────────────────────────

export const Route = createFileRoute("/")({
  component: App,
});

// ─── Business categories ──────────────────────────────────────────────────────

const CATEGORIES = [
  { code: "dairy", name: "Dairy", icon: "🐄" },
  { code: "agriculture", name: "Agriculture", icon: "🌾" },
  { code: "food_processing", name: "Food Processing", icon: "🍱" },
  { code: "retail", name: "Retail", icon: "🏪" },
  { code: "textiles", name: "Textiles", icon: "🧵" },
  { code: "tailoring", name: "Tailoring", icon: "✂️" },
  { code: "manufacturing", name: "Manufacturing", icon: "🏭" },
  { code: "handicrafts", name: "Handicrafts", icon: "🎨" },
  { code: "transportation", name: "Transportation", icon: "🚛" },
  { code: "repair_services", name: "Repair Services", icon: "🔧" },
  { code: "beauty_care", name: "Beauty & Care", icon: "💄" },
  { code: "digital_services", name: "Digital Services", icon: "💻" },
  { code: "livestock", name: "Livestock", icon: "🐑" },
  { code: "other", name: "Other", icon: "💡" },
] as const;

const ANALYSIS_STAGES = [
  "Understanding your location",
  "Estimating local customer reach",
  "Studying business opportunity",
  "Assessing competition",
  "Identifying local risks",
  "Estimating pricing potential",
  "Calculating financing structure",
  "Selecting suitable scheme",
  "Preparing your business blueprint",
];

// ─── Types ────────────────────────────────────────────────────────────────────

type Step = "landing" | "form" | "loading" | "report";
type FormStep = 1 | 2 | 3;

interface FormState {
  location: LocationResult | null;
  capital: number;
  category: string;
  idea: string;
  radius: 5 | 10;
}

// ─── App ──────────────────────────────────────────────────────────────────────

function App() {
  const [step, setStep] = useState<Step>("landing");
  const [formStep, setFormStep] = useState<FormStep>(1);
  const [form, setForm] = useState<FormState>({
    location: null,
    capital: 0,
    category: "",
    idea: "",
    radius: 10,
  });
  const [report, setReport] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadStage, setLoadStage] = useState(0);

  // ── Live financial preview ────────────────────────────────────────────────
  const projectCost = form.capital > 0 ? form.capital / 0.1 : 0;
  const loanAmount = projectCost * 0.9;
  const previewScheme = form.capital > 0 ? selectSchemePreview(projectCost) : null;
  const previewEmi = previewScheme
    ? calculateEmiPreview(loanAmount, previewScheme.interest, previewScheme.tenure * 12, previewScheme.moratorium)
    : 0;

  // ── Generate analysis ────────────────────────────────────────────────────
  async function handleGenerate() {
    if (!form.location || !form.category || form.capital <= 0) return;
    setStep("loading");
    setLoadStage(0);

    // Animate through stages
    const timer = setInterval(() => {
      setLoadStage((s) => (s < ANALYSIS_STAGES.length - 1 ? s + 1 : s));
    }, 900);

    try {
      const result = await api.analysis.generate({
        village_lgd_code: form.location.village_lgd_code,
        village_name: form.location.village_name,
        district_name: form.location.district_name,
        state_name: form.location.state_name,
        business_category: form.category,
        business_idea: form.idea,
        margin_capital: form.capital,
        radius_km: form.radius,
        language: "en",
      });
      clearInterval(timer);
      setReport(result);
      setStep("report");
    } catch (err) {
      clearInterval(timer);
      setError(err instanceof Error ? err.message : "Analysis failed. Please check your inputs and retry.");
      setStep("form");
    }
  }

  function handleReset() {
    setReport(null);
    setError(null);
    setForm({ location: null, capital: 0, category: "", idea: "", radius: 10 });
    setFormStep(1);
    setStep("landing");
  }

  // ── Render ────────────────────────────────────────────────────────────────
  if (step === "landing") return <Landing onStart={() => setStep("form")} />;
  if (step === "loading") return <Loader stages={ANALYSIS_STAGES} currentStage={loadStage} />;
  if (step === "report" && report) return <Report report={report} onNew={handleReset} />;

  return (
    <IntakeForm
      form={form}
      formStep={formStep}
      error={error}
      projectCost={projectCost}
      loanAmount={loanAmount}
      previewScheme={previewScheme}
      previewEmi={previewEmi}
      onChange={(partial) => setForm((prev) => ({ ...prev, ...partial }))}
      onNext={() => setFormStep((s) => Math.min(s + 1, 3) as FormStep)}
      onBack={() => setFormStep((s) => Math.max(s - 1, 1) as FormStep)}
      onGenerate={handleGenerate}
    />
  );
}

// ─── Landing Page ─────────────────────────────────────────────────────────────

function Landing({ onStart }: { onStart: () => void }) {
  return (
    <div className="min-h-screen bg-background">
      {/* Hero */}
      <section className="ledger-grid relative overflow-hidden border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-20 lg:py-28">
          <div className="max-w-3xl ledger-rise">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink/50">
              UdyamAI · AI-Powered Business Advisory
            </p>
            <h1 className="mt-6 font-display text-5xl font-bold leading-tight text-ink sm:text-6xl lg:text-7xl">
              Build the Right Business.{" "}
              <span className="text-moss">In the Right Place.</span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink/65">
              UdyamAI analyzes your local market, business opportunity and financing
              eligibility before you invest your money.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Button
                onClick={onStart}
                className="bg-moss text-cream hover:bg-moss/90 h-12 px-8 text-base"
              >
                Analyze My Business <ArrowRight size={16} className="ml-2" />
              </Button>
              <Button
                variant="outline"
                onClick={onStart}
                className="h-12 px-8 text-base border-line"
              >
                Try Demo
              </Button>
            </div>
            <div className="mt-8 flex gap-6 font-mono text-[10px] uppercase tracking-wider text-ink/40">
              <span>AI-powered</span>
              <span>·</span>
              <span>Local-first</span>
              <span>·</span>
              <span>Financially Transparent</span>
            </div>
          </div>
        </div>
      </section>

      {/* Problem section */}
      <section className="border-b border-line bg-ink">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cream/40">The problem</p>
          <h2 className="mt-3 font-display text-3xl font-bold text-cream">
            A Good Business Idea Isn't Enough.
          </h2>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                icon: <Lightbulb size={20} />,
                title: "Guesswork",
                desc: "Entrepreneurs choose businesses based on anecdotal success instead of actual local demand.",
              },
              {
                icon: <DollarSign size={20} />,
                title: "Financial Confusion",
                desc: "Many first-time entrepreneurs don't understand margin contribution, loan amounts, or repayment schedules.",
              },
              {
                icon: <BarChart3 size={20} />,
                title: "Local Blind Spots",
                desc: "A business that works in one village may fail in another because of competition, demand, or supply constraints.",
              },
              {
                icon: <ShieldCheck size={20} />,
                title: "No Guidance",
                desc: "Traditional business advice is often generic instead of being tailored to a specific village or block.",
              },
            ].map((item) => (
              <div key={item.title} className="border border-cream/10 bg-cream/5 p-5">
                <div className="text-moss">{item.icon}</div>
                <h3 className="mt-3 font-display text-lg font-semibold text-cream">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-cream/55">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink/50">How it works</p>
          <h2 className="mt-3 font-display text-3xl font-bold">Four steps to your business plan.</h2>
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { step: "01", title: "Tell Us About You", desc: "Enter your village, district, and available capital." },
              { step: "02", title: "AI Studies Your Market", desc: "We analyze local demand, competition, pricing, and infrastructure." },
              { step: "03", title: "Calculate Your Financing", desc: "Get scheme eligibility, loan amount, EMI, and repayment schedule." },
              { step: "04", title: "Get Your Blueprint", desc: "Receive a clear feasibility report you can act on immediately." },
            ].map((item) => (
              <div key={item.step} className="border border-line bg-paper p-5 paper-shadow">
                <div className="font-display text-4xl font-bold text-moss/30">{item.step}</div>
                <h3 className="mt-3 font-display text-lg font-semibold">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink/60">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Product Modules */}
      <section className="border-b border-line bg-paper">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink/50">What you get</p>
          <h2 className="mt-3 font-display text-3xl font-bold">Two powerful modules, one platform.</h2>
          <div className="mt-10 grid gap-6 lg:grid-cols-2">
            <div className="border border-line bg-cream p-6 paper-shadow">
              <div className="font-mono text-[10px] uppercase tracking-wider text-moss">Module 1</div>
              <h3 className="mt-2 font-display text-2xl font-bold">Hyper-Local Feasibility Report</h3>
              <p className="mt-3 text-sm leading-relaxed text-ink/65">
                AI-powered analysis of your specific location using real population data, competitor mapping, and pricing intelligence.
              </p>
              <ul className="mt-4 space-y-2">
                {["Market reach & population analysis", "Opportunity score & signals", "SWOT analysis", "Risk radar", "Competitor mapping", "Pricing intelligence"].map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-ink/70">
                    <Check size={12} className="text-moss shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
            <div className="border border-line bg-cream p-6 paper-shadow">
              <div className="font-mono text-[10px] uppercase tracking-wider text-ochre">Module 2</div>
              <h3 className="mt-2 font-display text-2xl font-bold">Smart Financial Roadmap</h3>
              <p className="mt-3 text-sm leading-relaxed text-ink/65">
                Automatic scheme selection, EMI calculation, and a full repayment schedule — no manual calculations required.
              </p>
              <ul className="mt-4 space-y-2">
                {["Scheme auto-selection (Micro Finance / Term Loan)", "Project cost derivation", "Interactive EMI calculator", "Monthly & quarterly repayment schedule", "Working capital planner", "Business plan summary PDF"].map((f) => (
                  <li key={f} className="flex items-center gap-2 text-sm text-ink/70">
                    <Check size={12} className="text-ochre shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Impact section */}
      <section className="border-b border-line">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink/50">Impact</p>
          <h2 className="mt-3 font-display text-3xl font-bold">From Capital Access to Business Success.</h2>
          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              { metric: "Better Decisions", detail: "Data-backed business selection instead of guesswork", icon: <BarChart3 size={22} className="text-moss" /> },
              { metric: "Financial Clarity", detail: "Understand your contribution, borrowing, and full repayment", icon: <DollarSign size={22} className="text-ochre" /> },
              { metric: "Local Empowerment", detail: "Enable grassroots entrepreneurs to build sustainable enterprises", icon: <ShieldCheck size={22} className="text-moss" /> },
            ].map((item) => (
              <div key={item.metric} className="border border-line bg-paper p-6 paper-shadow">
                {item.icon}
                <h3 className="mt-3 font-display text-xl font-bold">{item.metric}</h3>
                <p className="mt-2 text-sm leading-relaxed text-ink/60">{item.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="ledger-grid border-b border-line">
        <div className="mx-auto max-w-4xl px-6 py-20 text-center">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-ink/50">Get started</p>
          <h2 className="mt-4 font-display text-4xl font-bold sm:text-5xl">
            Don't Start With a Guess.{" "}
            <span className="text-moss">Start With a Plan.</span>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-ink/65">
            Analyze your local opportunity, understand your financing and make a smarter business decision.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Button
              onClick={onStart}
              className="bg-moss text-cream hover:bg-moss/90 h-12 px-10 text-base"
            >
              Analyze My Business <ArrowRight size={16} className="ml-2" />
            </Button>
          </div>
          <p className="mt-6 font-mono text-[10px] text-ink/35">
            AI Estimate · Based on available local data · Verify before applying
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-line bg-ink">
        <div className="mx-auto max-w-6xl px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="font-display font-bold text-cream">UdyamAI</p>
          <p className="font-mono text-[10px] text-cream/35 text-center">
            AI-powered · Local-first · Financially Transparent · GramBiz AI provides informational assistance only.
          </p>
        </div>
      </footer>
    </div>
  );
}

// ─── Intake Form ──────────────────────────────────────────────────────────────

function IntakeForm({
  form,
  formStep,
  error,
  projectCost,
  loanAmount,
  previewScheme,
  previewEmi,
  onChange,
  onNext,
  onBack,
  onGenerate,
}: {
  form: FormState;
  formStep: FormStep;
  error: string | null;
  projectCost: number;
  loanAmount: number;
  previewScheme: ReturnType<typeof selectSchemePreview>;
  previewEmi: number;
  onChange: (partial: Partial<FormState>) => void;
  onNext: () => void;
  onBack: () => void;
  onGenerate: () => void;
}) {
  const steps = ["Location", "Capital", "Business"];
  const canNext1 = !!form.location;
  const canNext2 = form.capital > 0;
  const canGenerate = !!form.location && form.capital > 0 && !!form.category;

  return (
    <div className="min-h-screen bg-background">
      {/* Progress rail */}
      <div className="sticky top-0 z-20 border-b border-line bg-cream/95 backdrop-blur">
        <div className="mx-auto max-w-3xl px-6 py-3">
          <div className="flex gap-0">
            {steps.map((s, i) => {
              const idx = i + 1;
              const active = formStep === idx;
              const done = formStep > idx;
              return (
                <div key={s} className="flex flex-1 items-center">
                  <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-mono font-bold ${done ? "bg-moss text-cream" : active ? "bg-ink text-cream" : "border border-line text-ink/30"}`}>
                    {done ? "✓" : idx}
                  </div>
                  <span className={`ml-2 font-mono text-[10px] uppercase tracking-wider ${active ? "text-ink" : "text-ink/40"}`}>{s}</span>
                  {i < 2 && <div className="mx-3 h-px flex-1 bg-line" />}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-6 py-10">
        {error && (
          <div className="mb-6 rounded border border-clay/30 bg-clay/5 p-4 text-sm text-clay">
            ⚠️ {error}
          </div>
        )}

        {/* Step 1 — Location */}
        {formStep === 1 && (
          <div className="ledger-rise space-y-6">
            <div>
              <SectionKicker text="Step 1 of 3" />
              <h2 className="mt-2 font-display text-3xl font-bold">Where is your business?</h2>
              <p className="mt-2 text-sm text-ink/60">
                Enter your village name. We'll find it in the LGD database.
              </p>
            </div>
            <LocationSearch
              value={form.location}
              onChange={(loc) => onChange({ location: loc })}
              placeholder="Type your village or town name..."
            />
            {form.location && (
              <div className="rounded border border-moss/20 bg-moss/5 p-4 text-sm">
                <div className="font-semibold text-moss">{form.location.village_name}</div>
                <div className="mt-1 text-ink/60">
                  {form.location.subdistrict_name} · {form.location.district_name} · {form.location.state_name}
                </div>
                {form.location.has_coordinates && (
                  <div className="mt-1 font-mono text-[10px] text-ink/40">
                    📍 {form.location.latitude?.toFixed(4)}, {form.location.longitude?.toFixed(4)}
                  </div>
                )}
              </div>
            )}
            <div className="flex justify-end">
              <Button onClick={onNext} disabled={!canNext1} className="bg-moss text-cream hover:bg-moss/90">
                Next: Capital <ArrowRight size={15} className="ml-1" />
              </Button>
            </div>
          </div>
        )}

        {/* Step 2 — Capital */}
        {formStep === 2 && (
          <div className="ledger-rise space-y-6">
            <div>
              <SectionKicker text="Step 2 of 3" />
              <h2 className="mt-2 font-display text-3xl font-bold">How much can you contribute?</h2>
              <p className="mt-2 text-sm text-ink/60">
                This is your margin capital — the amount you'll invest from your own savings.
              </p>
            </div>
            <div>
              <label className="block">
                <span className="font-mono text-[10px] uppercase tracking-wider text-ink/50">
                  Your margin capital (₹)
                </span>
                <div className="mt-2 flex items-center border border-line bg-cream focus-within:border-moss transition-colors">
                  <span className="border-r border-line px-4 py-3 font-mono text-ink/50">₹</span>
                  <input
                    type="number"
                    min={1000}
                    step={1000}
                    placeholder="e.g. 100000"
                    value={form.capital || ""}
                    onChange={(e) => onChange({ capital: Number(e.target.value) })}
                    className="w-full bg-transparent px-4 py-3 text-lg outline-none"
                  />
                </div>
              </label>
            </div>
            {form.capital > 0 && (
              <div className="rounded border border-line bg-note p-5 ledger-rise">
                <div className="grid grid-cols-3 gap-4">
                  <Metric label="Your capital" value={formatINR(form.capital)} />
                  <Metric label="Project cost" value={formatINR(projectCost)} />
                  <Metric label="Potential loan" value={formatINR(loanAmount)} tone="moss" />
                </div>
                {previewScheme && (
                  <div className="mt-4 border-t border-line pt-4 grid grid-cols-2 gap-3">
                    <Metric label="Scheme" value={previewScheme.name} />
                    <Metric label="Monthly EMI" value={formatINR(previewEmi)} tone="moss" />
                  </div>
                )}
              </div>
            )}
            <div className="flex justify-between">
              <Button variant="ghost" onClick={onBack}>← Back</Button>
              <Button onClick={onNext} disabled={!canNext2} className="bg-moss text-cream hover:bg-moss/90">
                Next: Business <ArrowRight size={15} className="ml-1" />
              </Button>
            </div>
          </div>
        )}

        {/* Step 3 — Business category */}
        {formStep === 3 && (
          <div className="ledger-rise space-y-6">
            <div>
              <SectionKicker text="Step 3 of 3" />
              <h2 className="mt-2 font-display text-3xl font-bold">What business do you want to start?</h2>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.code}
                  type="button"
                  onClick={() => onChange({ category: cat.code })}
                  className={`flex flex-col items-center gap-2 rounded border p-4 text-center transition-all ${
                    form.category === cat.code
                      ? "border-moss bg-moss/10 text-moss"
                      : "border-line bg-cream hover:bg-note text-ink"
                  }`}
                >
                  <span className="text-2xl">{cat.icon}</span>
                  <span className="text-xs font-medium">{cat.name}</span>
                </button>
              ))}
            </div>
            <div>
              <label className="block">
                <span className="font-mono text-[10px] uppercase tracking-wider text-ink/50">
                  Describe your specific idea (optional)
                </span>
                <textarea
                  placeholder="I want to start..."
                  value={form.idea}
                  onChange={(e) => onChange({ idea: e.target.value })}
                  rows={3}
                  className="mt-2 w-full border border-line bg-cream px-4 py-3 text-sm outline-none focus:border-moss transition-colors resize-none"
                />
              </label>
            </div>
            <div className="flex justify-between">
              <Button variant="ghost" onClick={onBack}>← Back</Button>
              <Button
                onClick={onGenerate}
                disabled={!canGenerate}
                className="bg-moss text-cream hover:bg-moss/90 h-12 px-8"
              >
                Generate My Business Plan <ArrowRight size={15} className="ml-1" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Loading Screen ────────────────────────────────────────────────────────────

function Loader({ stages, currentStage }: { stages: string[]; currentStage: number }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-ink px-6">
      <div className="w-full max-w-md ledger-rise">
        <div className="mb-8">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cream/40">
            AI Analysis in Progress
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold text-cream">
            Building your business blueprint.
          </h2>
        </div>
        <div className="space-y-3">
          {stages.map((stage, i) => {
            const done = i < currentStage;
            const active = i === currentStage;
            return (
              <div key={stage} className="flex items-center gap-3">
                <div className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] ${done ? "bg-moss" : active ? "bg-ochre" : "border border-cream/20"}`}>
                  {done ? <Check size={10} className="text-cream" /> : active ? <Loader2 size={10} className="text-cream animate-spin" /> : null}
                </div>
                <span className={`text-sm ${done ? "text-cream/70" : active ? "text-cream font-medium" : "text-cream/25"}`}>
                  {stage}
                </span>
              </div>
            );
          })}
        </div>
        <div className="mt-8 h-px w-full overflow-hidden bg-cream/10">
          <div
            className="h-full bg-moss transition-all duration-700"
            style={{ width: `${((currentStage + 1) / stages.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Report ────────────────────────────────────────────────────────────────────

function Report({ report, onNew }: { report: AnalysisResponse; onNew: () => void }) {
  const [activeTab, setActiveTab] = useState<"overview" | "swot" | "risks" | "financial" | "competitor" | "pricing" | "working_capital" | "recommendation">("overview");

  const tabs: { key: typeof activeTab; label: string }[] = [
    { key: "overview", label: "Overview" },
    { key: "swot", label: "SWOT" },
    { key: "risks", label: "Risk Radar" },
    { key: "competitor", label: "Competitors" },
    { key: "pricing", label: "Pricing" },
    { key: "financial", label: "Financial Plan" },
    { key: "working_capital", label: "Working Capital" },
    { key: "recommendation", label: "Recommendation" },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="sticky top-0 z-20 border-b border-line bg-cream/95 backdrop-blur">
        <div className="mx-auto max-w-6xl px-6 py-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-wider text-ink/50">
                {report.village_name} · {report.business_category_display}
              </p>
              <div className="mt-0.5 flex items-center gap-3">
                <span className="font-display text-lg font-bold text-moss">
                  {report.viability_score}/100
                </span>
                <span className="text-sm text-ink/60">{report.recommendation.label}</span>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => window.open(`/api/v1/analysis/${report.report_id}/pdf`, "_blank")}
                className="border-line"
              >
                <FileDown size={13} /> PDF
              </Button>
              <Button size="sm" variant="ghost" onClick={onNew}>New Analysis</Button>
            </div>
          </div>

          {/* Tabs */}
          <div className="mt-3 flex gap-0 border-t border-line pt-2 overflow-x-auto whitespace-nowrap scrollbar-none">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-1.5 font-mono text-[10px] uppercase tracking-wider transition-colors ${
                  activeTab === tab.key
                    ? "border-b-2 border-ink text-ink"
                    : "text-ink/45 hover:text-ink/70"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tab content */}
      <div className="mx-auto max-w-6xl px-6 py-8">
        {activeTab === "overview" && <ReportOverview report={report} />}
        {activeTab === "swot" && <SwotGrid swot={report.swot} />}
        {activeTab === "risks" && <RiskRadar risks={report.risks} />}
        {activeTab === "competitor" && <CompetitorSection report={report} />}
        {activeTab === "pricing" && <PricingSection report={report} />}
        {activeTab === "financial" && <FinancePlan report={report} />}
        {activeTab === "working_capital" && <WorkingCapitalPlanner report={report} />}
        {activeTab === "recommendation" && <RecommendationCard report={report} />}
      </div>
    </div>
  );
}