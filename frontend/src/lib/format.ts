/**
 * Shared formatting utilities.
 */

export function formatINR(value: number): string {
  if (value >= 10_000_000) return `₹${(value / 10_000_000).toFixed(1)}Cr`;
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(1)}L`;
  if (value >= 1_000) return `₹${(value / 1_000).toFixed(1)}K`;
  return `₹${value.toFixed(0)}`;
}

export function formatINRFull(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN").format(value);
}

/** Client-side EMI computation for live preview (before backend call). */
export function calculateEmiPreview(
  principal: number,
  annualRatePct: number,
  tenureMonths: number,
  moratoriumMonths: number,
): number {
  if (!principal || !annualRatePct || !tenureMonths) return 0;
  const r = annualRatePct / 1200;
  const P = principal * Math.pow(1 + r, moratoriumMonths);
  const n = tenureMonths;
  return Math.round((P * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1));
}

/** Scheme selection for client-side preview only. Real selection is by backend. */
export function selectSchemePreview(projectCost: number) {
  if (projectCost <= 140_000) {
    return { name: "Micro Finance Scheme", interest: 6.5, tenure: 3, moratorium: 3, maxFunding: 125_000 };
  }
  if (projectCost <= 5_000_000) {
    return { name: "Term Loan Scheme", interest: 8, tenure: 7, moratorium: 6, maxFunding: 4_500_000 };
  }
  return null;
}
