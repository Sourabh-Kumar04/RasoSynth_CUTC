"use client";
import React from "react";
import QualityOverviewCards from "@/components/quality/QualityOverviewCards";
import QualityScoreChart from "@/components/quality/QualityScoreChart";
import SourceQualityTable from "@/components/quality/SourceQualityTable";
import { BarChart2 } from "lucide-react";

export default function QualityDashboardPage() {
  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
          <BarChart2 className="h-5 w-5 text-orange-400" />
          Dataset Quality Dashboard
        </h1>
        <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
          Quality scores, distributions, and source breakdowns across all generated datasets
        </p>
      </div>

      {/* Overview Cards */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">Overview</h2>
        <QualityOverviewCards />
      </section>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <QualityScoreChart />
        <div className="bg-surface/40 rounded-lg border border-border p-4">
          <h3 className="text-sm font-semibold mb-3">Metrics at a Glance</h3>
          <ul className="space-y-2.5 text-sm">
            {[
              ["Duplicate Detection",   "4 levels (exact, fuzzy, embedding, cluster)"],
              ["Hallucination Detection","Source grounding + citation matching"],
              ["Diversity Analysis",     "5 dimensions (topic, source, instruction, response, domain)"],
              ["Semantic Scoring",       "Provider-based + heuristic fallback"],
              ["Human Review",          "Approve, reject, edit, bulk operations"],
            ].map(([label, detail]) => (
              <li key={label} className="flex items-start justify-between gap-4">
                <span className="text-foreground">{label}</span>
                <span className="text-muted-foreground text-xs text-right">{detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Source Quality Table */}
      <section>
        <h2 className="text-sm font-medium text-muted-foreground mb-3">
          Source Quality Breakdown — Strategic Segmentation
        </h2>
        <SourceQualityTable />
      </section>
    </div>
  );
}
