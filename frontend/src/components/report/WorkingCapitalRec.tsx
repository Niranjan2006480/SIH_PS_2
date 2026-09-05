/**
 * Working Capital Planner + AI Business Recommendation card.
 */

import type { AnalysisResponse } from "@/lib/api-client";
import { formatINR } from "@/lib/format";
import { SectionKicker } from "@/components/shared/primitives";
import { CheckCircle2, AlertTriangle, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  report: AnalysisResponse;
}

// ── Working Capital Planner ──────────────────────────────────────────────────

export function WorkingCapitalPlanner({ report }: Props) {
  const wc = report.working_capital;

  const items: { label: string; value: number; color: string }[] = [
    { label: "Setup / Fixed assets", value: wc.setup, color: "bg-ink" },
    { label: "Raw materials (monthly)", value: wc.raw_materials, color: "bg-moss" },
    { label: "Inventory", value: wc.inventory, color: "bg-moss/70" },
    { label: "Transport", value: wc.transport, color: "bg-ochre" },
    { label: "Utilities", value: wc.utilities, color: "bg-ochre/70" },
    { label: "Staff", value: wc.staff, color: "bg-clay/60" },
    { label: "Marketing", value: wc.marketing, color: "bg-clay/40" },
    { label: "Emergency reserve", value: wc.reserve, color: "bg-line" },
  ];

  const total = items.reduce((sum, i) => sum + i.value, 0);

  return (
    <div className="border border-line bg-cream p-5 paper-shadow sm:p-7">
      <SectionKicker text="Working capital planner" />
      <h2 className="mt-2 font-display text-2xl font-semibold">
        How much cash will your business need?
      </h2>
      <p className="mt-2 text-sm text-ink/60">
        AI-estimated monthly working capital requirements based on your business category and project
        size.
      </p>

      <div className="mt-6 space-y-2.5">
        {items.map((item) => {
          const pct = total > 0 ? (item.value / total) * 100 : 0;
          return (
            <div key={item.label} className="flex items-center gap-3">
              <div className="w-36 shrink-0 font-mono text-[10px] uppercase tracking-wider text-ink/55">
                {item.label}
              </div>
              <div className="relative flex-1 h-6 overflow-hidden rounded bg-note">
                <div
                  className={cn("h-full rounded transition-all duration-700", item.color)}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="w-20 shrink-0 text-right font-mono text-xs text-ink/70">
                {formatINR(item.value)}
              </div>
            </div>
          );
        })}
      </div>

      {/* Total */}
      <div className="mt-5 border-t-2 border-ink pt-4 flex items-center justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-ink/50">
            Estimated total funding requirement
          </div>
          <div className="mt-1 font-display text-3xl font-bold text-moss">
            {formatINR(total)}
          </div>
        </div>
        <div className="rounded border border-ochre/30 bg-ochre/8 px-3 py-2 text-center">
          <div className="font-mono text-[10px] uppercase tracking-wider text-ochre">Reserve</div>
          <div className="mt-0.5 font-display text-lg font-bold text-ochre">
            {formatINR(wc.reserve)}
          </div>
        </div>
      </div>

      <p className="mt-4 font-mono text-[10px] text-ink/40">
        AI estimate · Indicative only · Verify before applying
      </p>
    </div>
  );
}

// ── AI Recommendation Card ────────────────────────────────────────────────────

export function RecommendationCard({ report }: Props) {
  const rec = report.recommendation;
  const isProceed = rec.label.toLowerCase().includes("proceed");

  const DISCLAIMER =
    "GramBiz AI provides informational and analytical assistance. Scheme eligibility, loan approval, market conditions and repayment obligations are subject to verification by the relevant authority/financial institution.";

  return (
    <div className="space-y-4">
      {/* Main recommendation */}
      <div className="border-2 border-ink bg-ink p-6 text-cream sm:p-8 ledger-rise">
        <SectionKicker text="AI Recommendation" />
        <div className="mt-4 flex items-center gap-3">
          {isProceed ? (
            <TrendingUp className="shrink-0 text-moss" size={28} />
          ) : (
            <AlertTriangle className="shrink-0 text-ochre" size={28} />
          )}
          <h2 className="font-display text-2xl font-bold text-cream sm:text-3xl">{rec.label}</h2>
        </div>
        <p className="mt-4 font-display text-lg font-medium leading-relaxed text-cream/85">
          {rec.title}
        </p>
        <p className="mt-3 text-sm leading-relaxed text-cream/65">{rec.detail}</p>
        {rec.reserve > 0 && (
          <div className="mt-5 inline-block rounded border border-moss/30 bg-moss/15 px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-wider text-moss/70">
              Recommended reserve ·{" "}
            </span>
            <span className="font-display font-bold text-moss">{formatINR(rec.reserve)}</span>
          </div>
        )}
      </div>

      {/* Before you apply checklist */}
      {rec.checklist.length > 0 && (
        <div className="border border-line bg-paper p-5 paper-shadow sm:p-7">
          <SectionKicker text="Before you apply" />
          <h2 className="mt-2 font-display text-xl font-semibold">Validate these first.</h2>
          <ul className="mt-4 space-y-3">
            {rec.checklist.map((item) => (
              <li key={item} className="flex items-start gap-3">
                <CheckCircle2
                  size={15}
                  className="mt-0.5 shrink-0 text-moss"
                />
                <span className="text-sm text-ink/75">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Business Plan Summary */}
      <div className="border border-line bg-note p-5 paper-shadow sm:p-7">
        <SectionKicker text="Business plan summary" />
        <h2 className="mt-2 font-display text-xl font-semibold">One-page overview.</h2>
        <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
          {[
            { label: "Business", value: report.business_category_display },
            { label: "Location", value: `${report.village_name} · ${report.district_name}` },
            { label: "Viability score", value: `${report.viability_score}/100` },
            { label: "Competition", value: report.competitors.density },
            { label: "Recommended price", value: `${formatINR(report.pricing.base)} ${report.pricing.unit}` },
            { label: "Project cost", value: formatINR(report.project_cost) },
            { label: "Your contribution", value: formatINR(report.margin_capital) },
            { label: "Loan amount", value: formatINR(report.loan_amount) },
            { label: "Scheme", value: report.scheme_name ?? "—" },
            { label: "Interest rate", value: report.interest_rate != null ? `${report.interest_rate}% p.a.` : "—" },
            { label: "Tenure", value: report.tenure_years != null ? `${report.tenure_years} years` : "—" },
            { label: "Monthly EMI", value: report.monthly_emi != null ? formatINR(report.monthly_emi) : "—" },
          ].map(({ label, value }) => (
            <div key={label}>
              <div className="font-mono text-[9px] uppercase tracking-wider text-ink/45">
                {label}
              </div>
              <div className="mt-0.5 text-sm font-medium text-ink">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Disclaimer */}
      <p className="rounded border border-line bg-cream p-4 font-mono text-[10px] leading-relaxed text-ink/45">
        ⚠️ {DISCLAIMER}
      </p>
    </div>
  );
}
