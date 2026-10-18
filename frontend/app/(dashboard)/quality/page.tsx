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
      <div className="border-b border-[#272738] pb-4">
        <div className="flex items-center gap-2.5 mb-1">
          <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#161622] border border-[#3b3b52] text-[#6366f1] font-bold uppercase tracking-wider">
            Quality Intelligence
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display flex items-center gap-2">
            <BarChart2 className="h-5 w-5 text-[#6366f1]" />
            Dataset Quality Studio
          </h1>
        </div>
        <p className="text-xs text-[#94a3b8] font-sans">
          Grounding verifications, perplexity scores, deduplication metrics, and source-level quality breakdowns
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
          <h3 className="text-sm font-bold text-white mb-4 font-mono uppercase tracking-wider">Metrics &amp; Grounding Controls</h3>
          <ul className="space-y-3 text-sm">
            {[
              ["Duplicate Detection",   "4 levels (exact, fuzzy, embedding, MinHash LSH)"],
              ["Hallucination Detection","Source grounding + context citation matching"],
              ["Diversity Analysis",     "5 dimensions (topic, source, instruction, response, domain)"],
              ["Semantic Scoring",       "LLM Judge + heuristic fallback (perplexity & length)"],
              ["Human Review Gate",      "Stratified sampling, approve, reject, edit in HITL queue"],
            ].map(([label, detail]) => (
              <li key={label} className="flex items-start justify-between gap-4 p-2.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                <span className="text-white font-bold text-xs">{label}</span>
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
