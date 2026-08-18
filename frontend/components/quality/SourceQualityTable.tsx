"use client";
import React, { useEffect, useState } from "react";
import { Loader2, Database } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    fetch(`${API_BASE}/api/quality/sources`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-6 text-muted-foreground text-sm bg-surface/40 rounded-lg border border-border">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading source breakdown…
      </div>
    );
  }

  if (!data || data.sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-10 text-muted-foreground bg-surface/40 rounded-lg border border-border gap-3">
        <Database className="h-8 w-8 opacity-30" />
        <p className="text-sm">No source data yet — run a dataset orchestration job to begin.</p>
      </div>
    );
  }

  return (
    <div className="bg-surface/40 rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border/50 flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{data.total_unique_sources} unique sources</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-xs uppercase text-muted-foreground border-b border-border/50">
            <tr>
              <th className="px-4 py-3 font-medium">Source Domain / Category</th>
              <th className="px-4 py-3 font-medium">Avg Quality</th>
              <th className="px-4 py-3 font-medium">Samples</th>
              <th className="px-4 py-3 font-medium">Tier</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/30">
            {data.sources.map((item) => {
              const pct = (item.avg_quality * 100).toFixed(1);
              const tier =
                item.avg_quality >= 0.8 ? { label: "Excellent", cls: "bg-green-500/15 text-green-300 border-green-500/30" }
              : item.avg_quality >= 0.6 ? { label: "Good",      cls: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30" }
              :                           { label: "Needs Review", cls: "bg-red-500/15 text-red-300 border-red-500/30" };

              return (
                <tr key={item.source} className="hover:bg-surface/70 transition-colors">
                  <td className="px-4 py-3 font-medium capitalize">{item.source}</td>
                  <td className="px-4 py-3 font-mono text-blue-400">{pct}%</td>
                  <td className="px-4 py-3 font-mono text-muted-foreground">{item.samples_count.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs border font-medium ${tier.cls}`}>
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
