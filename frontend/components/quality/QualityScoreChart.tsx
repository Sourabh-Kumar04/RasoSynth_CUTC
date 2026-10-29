"use client";
import React, { useEffect, useState } from "react";
import { Loader2, BarChart3, Info } from "lucide-react";
import { api } from "@/lib/api/client";

interface Distribution {
  total_scores: number;
  mean: number;
  distribution: { excellent: number; good: number; fair: number; poor: number };
  histogram: number[];
  is_reference?: boolean;
}

export default function QualityScoreChart() {
  const [data, setData] = useState<Distribution | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getQualityDistributions()
      .then((res: any) => {
        // Empty/error -> no data, never a reference distribution. Mock-mode
        // responses are flagged reference so they never badge as live.
        const mockMode = typeof window !== 'undefined' && localStorage.getItem('mockMode') === 'true';
        if (!res || res.total_scores === 0) {
          setData(null);
        } else {
          setData({ ...res, is_reference: mockMode ? true : (res.is_reference ?? false) });
        }
      })
      .catch(() => {
        setData(null);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-[#12121a] rounded-md border border-[#272738] p-6 flex items-center gap-2 text-[#a8a29e] font-mono text-xs card-shadow">
        <Loader2 className="h-4 w-4 animate-spin text-[#f26625]" /> Loading distribution telemetry…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="bg-[#12121a] rounded-md border border-[#272738] p-6 text-[#a8a29e] font-mono text-xs card-shadow">
        No verified quality distribution available — live metrics could not be loaded.
      </div>
    );
  }

  const chartData = data;

  const { distribution, mean, histogram, is_reference } = chartData;
  const maxBucket = Math.max(...histogram, 1);
  const bucketLabels = [
    "0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
    "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"
  ];

  return (
    <div className="bg-[#12121a] rounded-md border border-[#272738] p-6 card-shadow flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-[#f26625]" />
            <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">
              Quality Score Distribution
            </h3>
          </div>
          {is_reference ? (
            <span className="text-xs font-mono text-amber-400 bg-amber-950/30 border border-amber-600/40 px-2 py-0.5 rounded">
              Reference Benchmark Profile
            </span>
          ) : (
            <span className="text-xs font-mono text-emerald-400 bg-emerald-950/30 border border-emerald-600/40 px-2 py-0.5 rounded">
              Live Verified Split
            </span>
          )}
        </div>

        <p className="text-xs text-[#a8a29e] font-mono mb-4">
          Decile frequency histogram across instruction adherence and MT-bench rubric scores.
        </p>

        {/* Histogram with Y-axis and X-axis */}
        <div className="pt-2 pb-1">
          <div className="flex items-end h-32 gap-1.5 p-2 bg-[#0a0a0f] rounded border border-[#1a1a24] relative">
            {histogram.map((val, i) => {
              const heightPct = Math.max((val / maxBucket) * 100, 3);
              const isHighTier = i >= 7;
              return (
                <div
                  key={i}
                  className="flex-1 h-full flex flex-col justify-end items-center group relative cursor-pointer"
                >
                  {/* Tooltip on hover */}
                  <div className="absolute -top-9 bg-[#1a1a24] text-white text-xs font-mono py-1 px-1.5 rounded border border-[#3b3b52] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20 shadow-lg">
                    {bucketLabels[i]}: <span className="font-bold text-[#f26625]">{val}</span> samples
                  </div>
                  <div
                    className={`w-full rounded-t transition-all ${
                      isHighTier ? "bg-[#10b981] group-hover:bg-[#34d399]" : "bg-[#f26625] group-hover:bg-[#ea580c]"
                    }`}
                    style={{ height: `${heightPct}%` }}
                  />
                </div>
              );
            })}
          </div>

          {/* X-axis labels */}
          <div className="flex justify-between items-center text-xs font-mono text-[#a8a29e] px-1 pt-1.5">
            <span>0% (Poor)</span>
            <span>50% (Acceptable)</span>
            <span>100% (Gold Standard)</span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs font-mono text-[#a8a29e] my-3 p-2 bg-[#0a0a0f] rounded border border-[#1a1a24]">
          <span>
            Sample Mean: <strong className="text-[#10b981]">{(mean * 100).toFixed(1)}%</strong>
          </span>
          <span>
            Audited Batch: <strong className="text-white">{chartData.total_scores.toLocaleString()} records</strong>
          </span>
        </div>
      </div>

      {/* Category breakdown */}
      <div className="grid grid-cols-4 gap-2 text-center text-xs font-mono pt-2">
        {[
          { label: "Excellent (≥85%)", value: distribution.excellent, color: "text-[#10b981]" },
          { label: "Good (70-84%)",   value: distribution.good,      color: "text-[#f26625]" },
          { label: "Fair (50-69%)",   value: distribution.fair,      color: "text-amber-400" },
          { label: "Poor (<50%)",     value: distribution.poor,      color: "text-rose-400"  },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-[#0a0a0f] rounded p-2 border border-[#272738]">
            <p className={`text-sm font-bold ${color}`}>{value}</p>
            <p className="text-[#a8a29e] text-xs uppercase mt-0.5 truncate">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
