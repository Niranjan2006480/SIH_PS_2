/**
 * Report Overview — viability score, score breakdown, and market reach header.
 */

import { formatNumber } from "@/lib/format";
import type { AnalysisResponse } from "@/lib/api-client";
import { SectionKicker, ScoreBar, Metric } from "@/components/shared/primitives";
import { TrendingUp } from "lucide-react";

interface Props {
  report: AnalysisResponse;
}

export function ReportOverview({ report }: Props) {
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
      {/* Viability Score */}
      <div className="border-2 border-ink bg-ink p-6 text-cream paper-shadow sm:p-8 ledger-rise">
        <SectionKicker text="Business Viability Score" />
        <div className="mt-4 flex items-end gap-3">
          <span className="font-display text-7xl font-bold tabular-nums leading-none text-moss">
            {report.viability_score}
          </span>
          <span className="mb-2 font-display text-2xl text-cream/40">/ 100</span>
        </div>
        <p className="mt-3 text-sm text-cream/60">{report.recommendation.label}</p>

        {/* Score breakdown */}
        <div className="mt-6 space-y-3">
          {report.scores.map((s) => (
            <div key={s.label} className="flex items-center gap-3">
              <div className="w-28 font-mono text-[10px] uppercase text-cream/50">{s.label}</div>
              <div className="flex-1">
                <ScoreBar value={s.value} tone="moss" />
              </div>
              <div className="w-7 font-mono text-[10px] text-cream/70">{s.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Market Reach */}
      <div className="space-y-4">
        <div className="border border-line bg-cream p-5 paper-shadow sm:p-6 ledger-rise">
          <SectionKicker text="Market reach" />
          <div className="mt-3 grid grid-cols-2 gap-4">
            <Metric label="Population · 5 km" value={formatNumber(report.market.population_5km)} />
            <Metric label="Population · 10 km" value={formatNumber(report.market.population_10km)} />
            <Metric label="Potential segment" value={formatNumber(report.market.potential_segment)} />
            <Metric
              label="Est. customers"
              value={formatNumber(report.market.estimated_customers)}
              tone="moss"
            />
          </div>
        </div>

        {/* Opportunity */}
        <div className="border border-line bg-paper p-5 paper-shadow sm:p-6 ledger-rise">
          <div className="flex items-center justify-between">
            <SectionKicker text="Opportunity signal" />
            <div className="flex items-center gap-1.5">
              <TrendingUp size={13} className="text-moss" />
              <span className="font-mono text-[10px] text-moss">{report.opportunity.score}/100</span>
            </div>
          </div>
          <p className="mt-2 font-display text-lg font-semibold leading-snug">
            {report.opportunity.title}
          </p>
          <p className="mt-2 text-sm leading-relaxed text-ink/65">{report.opportunity.detail}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {report.opportunity.signals.map((sig) => (
              <span
                key={sig}
                className="rounded bg-moss/8 px-2 py-0.5 font-mono text-[9px] text-moss"
              >
                {sig}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
