"use client";
import React, { useEffect, useState } from "react";
import { Loader2, BarChart3 } from "lucide-react";
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
      <div className="py-8 flex items-center gap-2 text-[#a8a29e] font-mono text-xs">
        <Loader2 className="h-4 w-4 animate-spin text-[#f26625]" /> Loading distribution telemetry…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="py-6 text-[#a8a29e] font-mono text-xs">
        No verified quality distribution available — live metrics could not be loaded.
      </div>
    );
  }

  const { distribution, mean, histogram, is_reference } = data;
  const maxBucket = Math.max(...histogram, 1);
  const bucketLabels = [
    "0-10%", "10-20%", "20-30%", "30-40%", "40-50%",
    "50-60%", "60-70%", "70-80%", "80-90%", "90-100%"
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-[#f26625]" />
            Quality Score Distribution
          </h4>
          <p className="text-xs text-[#a8a29e] mt-0.5">
            Decile frequency breakdown across verified instruction &amp; response adherence
          </p>
        </div>
        <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded border border-white/10 text-zinc-300">
          Sample Mean: <strong className="text-emerald-400">{(mean * 100).toFixed(1)}%</strong>
        </span>
      </div>

      {/* Histogram */}
      <div className="space-y-1 pt-1">
        <div className="flex items-end h-28 gap-2 p-2 bg-white/[0.02] rounded-xl border border-white/[0.06] relative">
          {histogram.map((val, i) => {
            const heightPct = Math.max((val / maxBucket) * 100, 4);
            const isHighTier = i >= 7;
            return (
              <div
                key={i}
                className="flex-1 h-full flex flex-col justify-end items-center group relative cursor-pointer"
              >
                {/* Tooltip on hover */}
                <div className="absolute -top-8 bg-zinc-900 text-white text-[11px] font-mono py-1 px-2 rounded border border-white/20 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-20 shadow-xl">
                  {bucketLabels[i]}: <span className="font-bold text-[#f26625]">{val}</span> samples
                </div>
                <div
                  className={`w-full rounded-t transition-all ${
                    isHighTier ? "bg-emerald-400 group-hover:bg-emerald-300" : "bg-[#f26625] group-hover:bg-[#ea580c]"
                  }`}
                  style={{ height: `${heightPct}%` }}
                />
              </div>
            );
          })}
        </div>

        {/* X-axis labels */}
        <div className="flex justify-between items-center text-[10px] font-mono text-[#a8a29e] px-1">
          <span>0% (Poor)</span>
          <span>50% (Acceptable)</span>
          <span>100% (Gold Standard)</span>
        </div>
      </div>

      {/* Category breakdown (Border-free stat strip) */}
      <div className="grid grid-cols-4 gap-2 pt-2 text-xs font-mono">
        {[
          { label: "Excellent (≥85%)", value: distribution.excellent, color: "text-emerald-400" },
          { label: "Good (70-84%)",   value: distribution.good,      color: "text-[#f26625]" },
          { label: "Fair (50-69%)",   value: distribution.fair,      color: "text-amber-400" },
          { label: "Poor (<50%)",     value: distribution.poor,      color: "text-rose-400"  },
        ].map(({ label, value, color }) => (
          <div key={label} className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
            <p className={`text-base font-bold ${color}`}>{value}</p>
            <p className="text-[#a8a29e] text-[10px] uppercase truncate">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
