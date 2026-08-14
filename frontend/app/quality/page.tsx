"use client";
import React from "react";
import QualityOverviewCards from "@/components/quality/QualityOverviewCards";
import QualityScoreChart from "@/components/quality/QualityScoreChart";
import SourceQualityTable from "@/components/quality/SourceQualityTable";

export default function QualityDashboardPage() {
  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">Dataset Quality Dashboard</h1>

        {/* Overview Cards */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-300 mb-3">Overview</h2>
          <QualityOverviewCards />
        </section>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <QualityScoreChart />
          <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-3">Metrics at a Glance</h3>
            <ul className="space-y-2 text-sm text-gray-300">
              <li className="flex justify-between">
                <span> Duplicate Detection</span>
                <span className="text-gray-400">4 levels (exact, fuzzy, embedding, cluster)</span>
              </li>
              <li className="flex justify-between">
                <span> Hallucination Detection</span>
                <span className="text-gray-400">Source grounding + citation matching</span>
              </li>
              <li className="flex justify-between">
                <span> Diversity Analysis</span>
                <span className="text-gray-400">5 dimensions (topic, source, instruction, response, domain)</span>
              </li>
              <li className="flex justify-between">
                <span> Semantic Scoring</span>
                <span className="text-gray-400">Provider-based + heuristic fallback</span>
              </li>
              <li className="flex justify-between">
                <span> Human Review</span>
                <span className="text-gray-400">Approve, reject, edit, bulk operations</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Source Quality Table (Dynamic) */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-300 mb-3">Source Quality Breakdown (Strategic Segmentation)</h2>
          <SourceQualityTable />
        </section>
      </div>
    </div>
  );
}