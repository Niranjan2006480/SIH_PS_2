/**
 * SWOT Analysis + Risk Radar components.
 */

import type { AnalysisResponse, SwotItem, RiskItem } from "@/lib/api-client";
import { SectionKicker } from "@/components/shared/primitives";
import { RiskBadge } from "@/components/shared/primitives";
import { Shield } from "lucide-react";
import { cn } from "@/lib/utils";

const SWOT_STYLES: Record<string, string> = {
  Strengths: "border-moss/30 bg-moss/5",
  Weaknesses: "border-clay/30 bg-clay/5",
  Opportunities: "border-ochre/30 bg-ochre/5",
  Threats: "border-line bg-paper",
};

const SWOT_LABEL_STYLES: Record<string, string> = {
  Strengths: "text-moss",
  Weaknesses: "text-clay",
  Opportunities: "text-ochre",
  Threats: "text-ink/70",
};

export function SwotGrid({ swot }: { swot: SwotItem[] }) {
  return (
    <div className="border border-line bg-cream p-5 paper-shadow sm:p-7">
      <SectionKicker text="SWOT analysis" />
      <h2 className="mt-2 font-display text-2xl font-semibold">Know your position.</h2>
      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {swot.map((quad) => (
          <div
            key={quad.title}
            className={cn("rounded border p-4", SWOT_STYLES[quad.title] ?? "border-line bg-paper")}
          >
            <div
              className={cn(
                "font-mono text-[10px] uppercase tracking-wider font-semibold",
                SWOT_LABEL_STYLES[quad.title] ?? "text-ink/70",
              )}
            >
              {quad.title}
            </div>
            <ul className="mt-3 space-y-1.5">
              {quad.items.map((item) => (
                <li key={item} className="flex gap-2 text-sm text-ink/75">
                  <span className="mt-1 shrink-0 text-[8px] text-ink/30">●</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RiskRadar({ risks }: { risks: RiskItem[] }) {
  return (
    <div className="border border-line bg-paper p-5 paper-shadow sm:p-7">
      <div className="flex items-center justify-between">
        <div>
          <SectionKicker text="Risk radar" />
          <h2 className="mt-1 font-display text-2xl font-semibold">Know before you invest.</h2>
        </div>
        <Shield className="text-ochre" size={28} />
      </div>
      <div className="mt-5 space-y-4">
        {risks.map((risk) => (
          <div key={risk.name} className="border-b border-line pb-4 last:border-0 last:pb-0">
            <div className="flex items-start justify-between gap-3">
              <span className="font-semibold text-sm">{risk.name}</span>
              <RiskBadge level={risk.level} />
            </div>
            <p className="mt-1.5 text-sm text-ink/65 leading-relaxed">{risk.detail}</p>
            <p className="mt-1 text-xs text-moss font-medium">→ {risk.action}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
