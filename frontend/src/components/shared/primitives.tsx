/**
 * Shared UI primitives used across report sections.
 */

import { cn } from "@/lib/utils";

export function SectionKicker({ text }: { text: string }) {
  return (
    <div className="font-mono text-[10px] uppercase tracking-[0.15em] text-ink/50">
      {text}
    </div>
  );
}

export function ScoreBar({ value, max = 100, tone = "moss" }: { value: number; max?: number; tone?: string }) {
  const pct = Math.min(100, (value / max) * 100);
  const colorMap: Record<string, string> = {
    moss: "bg-moss",
    ochre: "bg-ochre",
    clay: "bg-clay",
  };
  return (
    <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-ink/10">
      <div
        className={cn("h-full rounded-full transition-all duration-700", colorMap[tone] ?? "bg-moss")}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "moss" | "ochre" | "clay";
}) {
  const colorMap = { moss: "text-moss", ochre: "text-ochre", clay: "text-clay" };
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-ink/50">{label}</div>
      <div className={cn("mt-1 font-display text-lg font-semibold", tone ? colorMap[tone] : "")}>
        {value}
      </div>
    </div>
  );
}

export function RiskBadge({ level }: { level: "Low" | "Medium" | "High" }) {
  const styles = {
    Low: "bg-moss/10 text-moss border-moss/20",
    Medium: "bg-ochre/10 text-ochre border-ochre/20",
    High: "bg-clay/10 text-clay border-clay/20",
  };
  return (
    <span className={cn("rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider", styles[level])}>
      {level}
    </span>
  );
}

export function FinanceValue({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div>
      <div className="font-mono text-[10px] uppercase tracking-wider opacity-60">{label}</div>
      <div className={cn("mt-1 font-display text-xl font-semibold", tone === "moss" ? "text-moss" : "")}>
        {value}
      </div>
    </div>
  );
}
