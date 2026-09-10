/**
 * Competitor Map + Pricing Intelligence components.
 */

import type { AnalysisResponse } from "@/lib/api-client";
import { formatINR } from "@/lib/format";
import { SectionKicker, RiskBadge } from "@/components/shared/primitives";
import { Target, TrendingUp, Map } from "lucide-react";
import { cn } from "@/lib/utils";
import { CompetitorMap } from "./CompetitorMap";

interface Props {
  report: AnalysisResponse;
}

// ── Competitor Section ────────────────────────────────────────────────────────

export function CompetitorSection({ report }: Props) {
  const { competitors } = report;
  const densityColor: Record<string, string> = {
    Low: "text-moss",
    Moderate: "text-ochre",
    High: "text-clay",
  };

  return (
    <div className="space-y-6">
      {/* Interactive Map */}
      <div className="border border-line bg-cream p-5 paper-shadow sm:p-7">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <SectionKicker text="Geospatial Competitor Mapping" />
            <h2 className="mt-2 font-display text-2xl font-semibold">Field Radar & Catchment Map</h2>
            <p className="mt-1 text-xs text-ink/70">
              Interactive map of {report.village_name} with {report.radius_km} km catchment boundary and competing units.
            </p>
          </div>
          <Map className="shrink-0 text-moss" size={26} />
        </div>

        <CompetitorMap report={report} />
      </div>

      {/* Intelligence Cards */}
      <div className="border border-line bg-cream p-5 paper-shadow sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <SectionKicker text="Competitor intelligence" />
            <h2 className="mt-2 font-display text-2xl font-semibold">Know the field.</h2>
          </div>
          <Target className="shrink-0 text-ochre" size={26} />
        </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {/* Count card */}
        <div className="rounded border border-line bg-note p-4 text-center">
          <div className="font-display text-5xl font-bold text-ink">{competitors.count}</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-ink/50">
            Similar businesses
          </div>
          <div className="mt-1 text-xs text-ink/60">within selected radius</div>
        </div>

        {/* Density */}
        <div className="rounded border border-line bg-note p-4 text-center">
          <div
            className={cn(
              "font-display text-4xl font-bold",
              densityColor[competitors.density] ?? "text-ink",
            )}
          >
            {competitors.density}
          </div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-wider text-ink/50">
            Competition density
          </div>
        </div>

        {/* Categories */}
        <div className="rounded border border-line bg-note p-4">
          <div className="font-mono text-[10px] uppercase tracking-wider text-ink/50">
            Competitor types
          </div>
          <ul className="mt-2 space-y-1.5">
            {competitors.categories.map((cat) => (
              <li key={cat} className="flex items-center gap-2 text-sm text-ink/75">
                <span className="shrink-0 text-[8px] text-ink/30">●</span>
                {cat}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Differentiators */}
      {competitors.differentiators.length > 0 && (
        <div className="mt-6 border-t border-line pt-5">
          <div className="font-mono text-[10px] uppercase tracking-wider text-ink/50">
            How you can differentiate
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {competitors.differentiators.map((d) => (
              <span
                key={d}
                className="rounded border border-moss/20 bg-moss/5 px-3 py-1.5 text-sm font-medium text-moss"
              >
                {d}
              </span>
            ))}
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

// ── Pricing Intelligence ──────────────────────────────────────────────────────

export function PricingSection({ report }: Props) {
  const { pricing } = report;

  const scenarios = [
    { label: "Low-price scenario", value: pricing.low, note: "Penetration pricing" },
    { label: "Base scenario", value: pricing.base, note: "Recommended" },
    { label: "Premium scenario", value: pricing.premium, note: "Quality differentiation" },
  ];

  return (
    <div className="border border-line bg-paper p-5 paper-shadow sm:p-7">
      <div className="flex items-start justify-between gap-4">
        <div>
          <SectionKicker text="Pricing intelligence" />
          <h2 className="mt-2 font-display text-2xl font-semibold">Set the right price.</h2>
        </div>
        <TrendingUp className="shrink-0 text-moss" size={26} />
      </div>

      {/* Price scenarios */}
      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {scenarios.map((s, i) => (
          <div
            key={s.label}
            className={cn(
              "rounded border p-4 text-center transition-all",
              i === 1
                ? "border-moss/30 bg-moss/8 ring-1 ring-moss/20"
                : "border-line bg-cream",
            )}
          >
            {i === 1 && (
              <div className="mb-2 font-mono text-[9px] uppercase tracking-wider text-moss">
                ★ Recommended
              </div>
            )}
            <div
              className={cn(
                "font-display text-3xl font-bold",
                i === 1 ? "text-moss" : "text-ink",
              )}
            >
              {formatINR(s.value)}
            </div>
            <div className="mt-1 font-mono text-[10px] text-ink/50">{pricing.unit}</div>
            <div className="mt-1 text-xs text-ink/45">{s.note}</div>
          </div>
        ))}
      </div>

      {/* Gross margin */}
      <div className="mt-5 flex items-center gap-5">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-ink/50">
            Estimated gross margin
          </div>
          <div className="mt-1 font-display text-2xl font-bold text-moss">
            {pricing.margin_pct}%
          </div>
        </div>
        <div className="flex-1 text-sm leading-relaxed text-ink/60">
          <span className="font-mono text-[10px] uppercase tracking-wider text-ink/40 block mb-1">
            Rationale
          </span>
          {pricing.rationale}
        </div>
      </div>

      {/* Margin bar */}
      <div className="mt-5 flex h-8 overflow-hidden rounded border border-line bg-cream/50">
        <div
          className="flex items-center justify-center bg-moss font-mono text-[10px] text-cream"
          style={{ width: `${pricing.margin_pct}%` }}
        >
          {pricing.margin_pct}% margin
        </div>
        <div className="flex items-center justify-center px-3 font-mono text-[10px] text-ink/45">
          {100 - pricing.margin_pct}% cost
        </div>
      </div>
    </div>
  );
}
