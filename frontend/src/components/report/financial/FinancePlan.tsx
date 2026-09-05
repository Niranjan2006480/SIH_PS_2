/**
 * Financial Plan section — scheme card, EMI calculator, repayment schedule.
 */

import { useState, useMemo } from "react";
import type { AnalysisResponse } from "@/lib/api-client";
import { formatINR } from "@/lib/format";
import { calculateEmiPreview } from "@/lib/format";
import { SectionKicker, FinanceValue } from "@/components/shared/primitives";
import { Gauge } from "lucide-react";

interface Props {
  report: AnalysisResponse;
}

function makeSchedule(
  principal: number,
  annualRate: number,
  years: number,
  frequency: "monthly" | "quarterly",
  moratoriumMonths = 0,
) {
  const monthlyRate = annualRate / 1200;
  const tenureMonths = years * 12;
  const emi = calculateEmiPreview(principal, annualRate, tenureMonths, moratoriumMonths);
  const totalPeriods = moratoriumMonths + tenureMonths;
  const periodsToShow = frequency === "monthly" ? totalPeriods : Math.ceil(totalPeriods / 3);
  const rows: {
    period: string;
    principal: number;
    interest: number;
    payment: number;
    balance: number;
  }[] = [];

  let balance = principal;
  for (let i = 0; i < Math.min(periodsToShow, frequency === "monthly" ? 36 : 12); i++) {
    const startMonth = frequency === "monthly" ? i : i * 3;
    const months = frequency === "monthly" ? 1 : 3;
    const isMoratorium = startMonth < moratoriumMonths;
    const interest = Math.round(balance * monthlyRate * months);
    const payment = isMoratorium ? 0 : frequency === "monthly" ? emi : emi * 3;
    const principalPaid = isMoratorium ? 0 : Math.min(balance, Math.max(0, payment - interest));
    balance = isMoratorium ? balance + interest : Math.max(0, balance - principalPaid);

    const label = isMoratorium
      ? `Moratorium ${frequency === "monthly" ? "Month" : "Q"} ${i + 1}`
      : `${frequency === "monthly" ? "Month" : "Q"} ${
          frequency === "monthly" ? i + 1 - moratoriumMonths : i + 1 - Math.ceil(moratoriumMonths / 3)
        }`;

    rows.push({ period: label, principal: principalPaid, interest, payment: principalPaid + interest, balance });
  }
  return rows;
}

export function FinancePlan({ report }: Props) {
  const [frequency, setFrequency] = useState<"monthly" | "quarterly">("monthly");
  const [principal, setPrincipal] = useState(report.loan_amount ?? 0);

  const tenureYears = report.tenure_years ?? 7;
  const interest = report.interest_rate ?? 8;
  const moratorium = report.moratorium_months ?? 0;
  const tenureMonths = Math.round(tenureYears * 12);

  const emi = calculateEmiPreview(principal, interest, tenureMonths, moratorium);
  const schedule = useMemo(
    () => makeSchedule(principal, interest, tenureYears, frequency, moratorium),
    [principal, interest, tenureYears, frequency, moratorium],
  );

  return (
    <div className="mt-7 space-y-5">
      {/* Structure overview */}
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="border border-ink bg-ink p-5 text-cream sm:p-7">
          <SectionKicker text="Financial roadmap" />
          <h2 className="mt-3 font-display text-3xl font-semibold">Structure the money clearly.</h2>
          <div className="mt-7 grid gap-5">
            <FinanceValue label="Your contribution" value={formatINR(report.margin_capital)} />
            <FinanceValue label="Total project cost" value={formatINR(report.project_cost)} />
            <FinanceValue label="Eligible loan" value={formatINR(report.loan_amount ?? 0)} />
          </div>
          <div className="mt-7 flex h-9 overflow-hidden rounded bg-cream/15">
            <div
              className="grid place-items-center bg-ochre font-mono text-[10px]"
              style={{ width: "10%" }}
            >
              10%
            </div>
            <div
              className="grid place-items-center bg-moss font-mono text-[10px]"
              style={{ width: "90%" }}
            >
              90% institutional loan
            </div>
          </div>
          <p className="mt-3 font-mono text-[10px] text-cream/65">
            Project cost = available margin / 10%. Loan = project cost × 90%.
          </p>
        </div>

        {/* Scheme card */}
        <div className="border border-line bg-cream p-5 paper-shadow sm:p-7">
          <div className="flex items-center justify-between">
            <SectionKicker text="Scheme auto-selection" />
            <span className="rounded bg-moss/10 px-2 py-1 font-mono text-[10px] text-moss">
              Matched by project cost
            </span>
          </div>
          {report.scheme_name ? (
            <>
              <h2 className="mt-3 font-display text-3xl font-semibold text-moss">
                {report.scheme_name}
              </h2>
              <p className="mt-2 text-sm text-ink/65">
                Up to 90% financing · Maximum{" "}
                {report.scheme_code === "MICRO_FINANCE" ? "₹1.25L" : "₹45L"}
              </p>
              <div className="mt-6 grid grid-cols-2 gap-4">
                <FinanceValue label="Interest" value={`${interest}% p.a.`} />
                <FinanceValue label="Tenure" value={`${tenureYears} years`} />
                <FinanceValue label="Moratorium" value={`${moratorium} months`} />
                <FinanceValue label="Monthly EMI" value={formatINR(report.monthly_emi ?? 0)} tone="moss" />
              </div>
            </>
          ) : (
            <div className="mt-4">
              <p className="text-sm text-clay leading-relaxed">
                Your estimated project exceeds the supported limit. Reduce scope or explore additional financing.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Repayment Schedule */}
      <div className="border border-line bg-cream p-5 paper-shadow sm:p-7">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <SectionKicker text="Repayment schedule" />
            <h2 className="mt-1 font-display text-2xl font-semibold">Your declining balance plan</h2>
            <p className="mt-1 text-sm text-ink/60">
              Moratorium: {moratorium} months · Interest accrues during moratorium.
            </p>
          </div>
          <div className="flex border border-line bg-note p-1">
            {(["monthly", "quarterly"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFrequency(f)}
                className={`px-3 py-2 font-mono text-[10px] uppercase ${
                  frequency === f ? "bg-ink text-cream" : "text-ink/55"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[480px] border-collapse text-left font-mono text-xs">
            <thead>
              <tr className="border-b-2 border-ink text-[10px] uppercase tracking-wider text-ink/55">
                <th className="pb-3">Period</th>
                <th className="pb-3">Principal</th>
                <th className="pb-3">Interest</th>
                <th className="pb-3">Payment</th>
                <th className="pb-3">Balance</th>
              </tr>
            </thead>
            <tbody>
              {schedule.map((row) => (
                <tr key={row.period} className="border-b border-line">
                  <td className="py-3">{row.period}</td>
                  <td>{formatINR(row.principal)}</td>
                  <td>{formatINR(row.interest)}</td>
                  <td>{formatINR(row.payment)}</td>
                  <td>{formatINR(row.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Interactive EMI Calculator */}
      <div className="border border-line bg-paper p-5 paper-shadow sm:p-7">
        <div className="flex items-center justify-between">
          <div>
            <SectionKicker text="Interactive EMI calculator" />
            <h2 className="mt-1 font-display text-2xl font-semibold">Stress-test the loan amount.</h2>
          </div>
          <Gauge className="text-moss" />
        </div>
        <div className="mt-5 grid gap-5 md:grid-cols-2">
          <label className="block">
            <span className="font-mono text-[10px] uppercase tracking-wider text-ink/55">
              Loan amount · {formatINR(principal)}
            </span>
            <input
              type="range"
              min={Math.max(10_000, report.margin_capital)}
              max={Math.max(100_000, report.loan_amount ?? 900_000)}
              step={10_000}
              value={principal}
              onChange={(e) => setPrincipal(Number(e.target.value))}
              className="mt-4 w-full accent-moss"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <FinanceValue label="Monthly EMI" value={formatINR(emi)} tone="moss" />
            <FinanceValue
              label="Total repayment"
              value={formatINR(emi * tenureMonths)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
