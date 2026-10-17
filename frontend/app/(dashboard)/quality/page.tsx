"use client";
import React from "react";
import QualityOverviewCards from "@/components/quality/QualityOverviewCards";
import QualityScoreChart from "@/components/quality/QualityScoreChart";
import SourceQualityTable from "@/components/quality/SourceQualityTable";
import { BarChart2 } from "lucide-react";

export default function QualityDashboardPage() {
  return (
    <div className="space-y-6 animate-fade-in pb-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-serif font-bold text-[#6366f1] flex items-center gap-2.5">
          <BarChart2 className="h-6 w-6 text-[#6366f1]" />
          Dataset Quality Dashboard
        </h1>
        <p className="text-xs sm:text-sm text-[#94a3b8] mt-1 font-sans">
          Quality scores, distributions, and source breakdowns across all generated synthetic datasets
        </p>
      </div>

      {/* Overview Cards */}
      <section>
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#94a3b8] mb-3">
          Overview Telemetry
        </h2>
        <QualityOverviewCards />
      </section>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <QualityScoreChart />
        <div className="bg-[#12121a] rounded-2xl border border-[#272738] p-6 card-shadow">
          <h3 className="text-base font-bold text-[#6366f1] mb-4">Metrics & Grounding Controls</h3>
          <ul className="space-y-3 text-sm">
            {[
              ["Duplicate Detection",   "4 levels (exact, fuzzy, embedding, cluster)"],
              ["Hallucination Detection","Source grounding + citation matching"],
              ["Diversity Analysis",     "5 dimensions (topic, source, instruction, response, domain)"],
              ["Semantic Scoring",       "Provider-based + heuristic fallback"],
              ["Human Review",          "Approve, reject, edit, bulk operations"],
            ].map(([label, detail]) => (
              <li key={label} className="flex items-start justify-between gap-4 p-2 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                <span className="text-[#6366f1] font-medium text-xs">{label}</span>
                <span className="text-[#94a3b8] text-xs font-mono text-right">{detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Source Quality Table */}
      <section>
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#94a3b8] mb-3">
          Source Quality Breakdown — Strategic Segmentation
        </h2>
        <SourceQualityTable />
      </section>
    </div>
  );
}
