"use client";
import React, { useEffect, useState } from "react";
import { Loader2, Database } from "lucide-react";
import { api } from "@/lib/api/client";

interface SourceQuality {
  source: string;
  avg_quality: number;
  samples_count: number;
}

interface SourceQualityResponse {
  total_unique_sources: number;
  sources: SourceQuality[];
}

export default function SourceQualityTable() {
  const [data, setData] = useState<SourceQualityResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getQualitySources()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-8 text-[#a8a29e] font-mono text-xs">
        <Loader2 className="h-4 w-4 animate-spin text-[#f26625]" /> Loading source breakdown…
      </div>
    );
  }

  if (!data || data.sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-[#a8a29e] font-mono text-xs gap-2">
        <Database className="h-7 w-7 text-zinc-600" />
        <p>No source data yet — run a dataset orchestration run to begin ingestion.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-bold text-white flex items-center gap-2">
            <Database className="h-4 w-4 text-[#f26625]" />
            Source Ingestion Fidelity Breakdown
          </h4>
          <p className="text-xs text-[#a8a29e] mt-0.5">
            Average accuracy and sample yield per discovered authority domain
          </p>
        </div>
        <span className="text-[11px] font-mono text-[#a8a29e]">
          {data.total_unique_sources} unique authority sources
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono text-left">
          <thead className="text-[11px] uppercase text-[#a8a29e] border-b border-white/[0.08]">
            <tr>
              <th className="py-2.5 px-3 font-semibold">Source Domain / Authority</th>
              <th className="py-2.5 px-3 font-semibold">Avg Quality</th>
              <th className="py-2.5 px-3 font-semibold">Samples Yielded</th>
              <th className="py-2.5 px-3 font-semibold text-right">Integrity Tier</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {data.sources.map((src) => {
              const scorePct = Math.round(src.avg_quality * 100);
              const tier = scorePct >= 85 ? "Authoritative Gold" : scorePct >= 70 ? "Verified Silver" : "Needs Review";
              const color = scorePct >= 85 ? "text-emerald-400" : scorePct >= 70 ? "text-[#f26625]" : "text-amber-400";

              return (
                <tr key={src.source} className="hover:bg-white/[0.02] transition-colors">
                  <td className="py-3 px-3 font-bold text-white max-w-xs truncate">
                    {src.source}
                  </td>
                  <td className={`py-3 px-3 font-bold ${color}`}>
                    {scorePct}%
                  </td>
                  <td className="py-3 px-3 text-zinc-300">
                    {src.samples_count.toLocaleString()}
                  </td>
                  <td className="py-3 px-3 text-right">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${color} bg-white/[0.02]`}>
                      {tier}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
