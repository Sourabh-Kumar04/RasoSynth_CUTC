"use client";
import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api/client";

interface Distribution {
  total_scores: number;
  mean: number;
  distribution: { excellent: number; good: number; fair: number; poor: number };
  histogram: number[];
}

export default function QualityScoreChart() {
  const [data, setData] = useState<Distribution | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getQualityDistributions()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-[#0c0d14] rounded-2xl border border-[#1e2235] p-4 flex items-center gap-2 text-[#94a3b8] font-mono text-xs">
        <Loader2 className="h-4 w-4 animate-spin text-[#008ecc]" /> Loading distribution…
      </div>
    );
  }

  if (!data || data.total_scores === 0) {
    return (
      <div className="bg-[#0c0d14] rounded-2xl border border-[#1e2235] p-8 flex items-center justify-center text-xs font-mono text-[#94a3b8]">
        No distribution data yet — run a dataset job first.
      </div>
    );
  }

  const { distribution, mean, histogram } = data;
  const maxBucket = Math.max(...histogram, 1);

  return (
    <div className="bg-[#0c0d14] rounded-2xl border border-[#1e2235] p-6 card-shadow">
      <h3 className="text-sm font-bold text-white mb-4 font-mono uppercase tracking-wider">Quality Score Distribution</h3>

      {/* Histogram */}
      <div className="flex items-end h-28 gap-1 mb-2">
        {histogram.map((val, i) => (
          <div
            key={i}
            className="flex-1 bg-[#008ecc] rounded-t transition-all hover:bg-[#008ecc]"
            style={{ height: `${(val / maxBucket) * 100}%`, minHeight: val > 0 ? "3px" : "0" }}
            title={`${i * 10}–${(i + 1) * 10}%: ${val} samples`}
          />
        ))}
      </div>
      <p className="text-[11px] font-mono text-[#94a3b8] text-center mb-3">Score range (0–100%)</p>
      <p className="text-xs font-mono text-[#94a3b8] mb-4">
        Mean: <span className="font-bold text-[#10b981]">{(mean * 100).toFixed(1)}%</span>
        <span className="ml-3">Total: <span className="font-bold text-white">{data.total_scores.toLocaleString()}</span></span>
      </p>

      {/* Category breakdown */}
      <div className="grid grid-cols-4 gap-2 text-center text-xs font-mono">
        {[
          { label: "Excellent", value: distribution.excellent, color: "text-[#10b981]" },
          { label: "Good",      value: distribution.good,      color: "text-[#008ecc]" },
          { label: "Fair",      value: distribution.fair,      color: "text-amber-400" },
          { label: "Poor",      value: distribution.poor,      color: "text-rose-400"  },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[#050508] rounded-xl p-2.5 border border-[#1e2235]">
            <p className={`text-base font-bold ${color}`}>{value}</p>
            <p className="text-[#94a3b8] text-[10px] uppercase mt-0.5">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
