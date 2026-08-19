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
        <h1 className="text-2xl sm:text-3xl font-serif font-bold text-[#1B3B2B] flex items-center gap-2.5">
          <BarChart2 className="h-6 w-6 text-[#1B3B2B]" />
          Dataset Quality Dashboard
        </h1>
        <p className="text-xs sm:text-sm text-[#55635B] mt-1 font-sans">
          Quality scores, distributions, and source breakdowns across all generated synthetic datasets
        </p>
      </div>

      {/* Overview Cards */}
      <section>
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#55635B] mb-3">
          Overview Telemetry
        </h2>
        <QualityOverviewCards />
      </section>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <QualityScoreChart />
        <div className="bg-white rounded-2xl border border-[#E2E6E0] p-6 card-shadow">
          <h3 className="text-base font-bold text-[#1B3B2B] mb-4">Metrics & Grounding Controls</h3>
          <ul className="space-y-3 text-sm">
            {[
              ["Duplicate Detection",   "4 levels (exact, fuzzy, embedding, cluster)"],
              ["Hallucination Detection","Source grounding + citation matching"],
              ["Diversity Analysis",     "5 dimensions (topic, source, instruction, response, domain)"],
              ["Semantic Scoring",       "Provider-based + heuristic fallback"],
              ["Human Review",          "Approve, reject, edit, bulk operations"],
            ].map(([label, detail]) => (
              <li key={label} className="flex items-start justify-between gap-4 p-2 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0]">
                <span className="text-[#1B3B2B] font-medium text-xs">{label}</span>
                <span className="text-[#55635B] text-xs font-mono text-right">{detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Source Quality Table */}
      <section>
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#55635B] mb-3">
          Source Quality Breakdown — Strategic Segmentation
        </h2>
        <SourceQualityTable />
      </section>
    </div>
  );
}
