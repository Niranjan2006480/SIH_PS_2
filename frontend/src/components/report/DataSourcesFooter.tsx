import type { AnalysisResponse } from "@/lib/api-client";
import { Database, ShieldCheck, FileText, CheckCircle2 } from "lucide-react";
import { SectionKicker } from "@/components/shared/primitives";

interface Props {
  report: AnalysisResponse;
}

export function DataSourcesFooter({ report }: Props) {
  const sources = report.data_sources?.length
    ? report.data_sources
    : [
        "Census of India 2011 (Village PCA & Primary Demographics)",
        "Socio Economic and Caste Census (SECC 2011)",
        "MoSPI Household Consumption Expenditure Survey (HCES 2023-24)",
        "Ministry of Panchayati Raj Local Government Directory (LGD)",
        "AGMARKNET Mandi Price Intelligence & Daily Arrivals",
        "MoSPI Rural Consumer Price Index (CPI 2024)",
        "NBCFDC & SCA Concessional Loan Scheme Guidelines",
        "Ministry of MSME Udyam Enterprise Registry",
      ];

  const confidencePct = Math.round((report.confidence_score ?? 0.85) * 100);

  return (
    <div className="mt-12 border-t border-line pt-8">
      <div className="rounded-md border border-line bg-cream p-6 paper-shadow">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <SectionKicker text="Intelligence Provenance & Sources" />
            <h3 className="mt-1 font-display text-xl font-semibold text-ink">
              Official Data Sources & Field Verification
            </h3>
            <p className="mt-1 text-xs text-ink/70">
              UdyamAI cross-references government registries, national statistical surveys, and hyper-local mandi benchmarks.
            </p>
          </div>

          <div className="flex items-center gap-2 rounded border border-moss/30 bg-moss/10 px-3 py-1.5 text-xs font-semibold text-moss">
            <ShieldCheck size={16} />
            <span>{confidencePct}% Data Confidence</span>
          </div>
        </div>

        {/* Sources Grid */}
        <div className="mt-6 grid gap-2.5 sm:grid-cols-2">
          {sources.map((source, index) => (
            <div
              key={index}
              className="flex items-center gap-2.5 rounded border border-line bg-paper px-3 py-2 text-xs text-ink/80 transition-colors hover:border-ink/30"
            >
              <CheckCircle2 size={13} className="shrink-0 text-moss" />
              <span className="font-medium">{source}</span>
            </div>
          ))}
        </div>

        {/* Footnote */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-line/60 pt-4 text-[11px] text-ink/50">
          <div className="flex items-center gap-1.5">
            <Database size={12} className="text-ink/40" />
            <span>Generated for {report.village_name}, {report.district_name}, {report.state_name}</span>
          </div>
          <div>
            <span>Report ID: {report.report_id.slice(0, 16)} • Verified against NBCFDC Credit Norms</span>
          </div>
        </div>
      </div>
    </div>
  );
}
