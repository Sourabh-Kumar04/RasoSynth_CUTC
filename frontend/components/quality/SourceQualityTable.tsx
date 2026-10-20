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
      <div className="flex items-center gap-2 p-6 text-[#94a3b8] font-mono text-xs bg-[#12121a] rounded-2xl border border-[#272738]">
        <Loader2 className="h-4 w-4 animate-spin text-[#f26625]" /> Loading source breakdown…
      </div>
    );
  }

  if (!data || data.sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-10 text-[#94a3b8] font-mono text-xs bg-[#12121a] rounded-2xl border border-[#272738] gap-3">
        <Database className="h-8 w-8 text-[#64748b]" />
        <p>No source data yet — run a dataset orchestration job to begin.</p>
      </div>
    );
  }

  return (
    <div className="bg-[#12121a] rounded-2xl border border-[#272738] overflow-hidden card-shadow">
      <div className="px-4 py-3 border-b border-[#272738] flex items-center justify-between">
        <span className="text-xs font-mono text-[#94a3b8]">{data.total_unique_sources} unique source domains</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono text-left">
          <thead className="text-[10px] uppercase text-[#94a3b8] border-b border-[#272738] bg-[#0a0a0f]">
            <tr>
              <th className="px-4 py-3 font-medium">Source Domain / Category</th>
              <th className="px-4 py-3 font-medium">Avg Quality</th>
              <th className="px-4 py-3 font-medium">Samples</th>
              <th className="px-4 py-3 font-medium">Tier</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#272738]">
            {data.sources.map((item) => {
              const pct = (item.avg_quality * 100).toFixed(1);
              const tier =
                item.avg_quality >= 0.8 ? { label: "Excellent", cls: "bg-emerald-950/40 text-emerald-400 border-emerald-500/30" }
              : item.avg_quality >= 0.6 ? { label: "Good",      cls: "bg-indigo-950/40 text-[#f26625] border-indigo-500/30" }
              :                           { label: "Needs Review", cls: "bg-rose-950/40 text-rose-400 border-rose-500/30" };

              return (
                <tr key={item.source} className="hover:bg-[#161622]/50 transition-colors">
                  <td className="px-4 py-3 font-bold text-white capitalize">{item.source}</td>
                  <td className="px-4 py-3 text-[#10b981] font-bold">{pct}%</td>
                  <td className="px-4 py-3 text-[#94a3b8]">{item.samples_count.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] border font-bold uppercase ${tier.cls}`}>
                      {tier.label}
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
