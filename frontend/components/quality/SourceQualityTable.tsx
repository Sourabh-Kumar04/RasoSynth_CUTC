"use client";
import React, { useEffect, useState } from "react";

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
    fetch("/api/quality/sources")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8 text-center text-gray-400 bg-gray-800 rounded-lg border border-gray-700">
        <div className="animate-pulse flex space-x-4 justify-center items-center">
          <div className="rounded-full bg-slate-700 h-10 w-10"></div>
          <div className="h-4 bg-slate-700 rounded w-28"></div>
        </div>
      </div>
    );
  }

  if (!data || data.sources.length === 0) {
    return (
      <div className="p-8 text-center text-gray-500 bg-gray-800 rounded-lg border border-gray-700">
        No source quality data available yet. Run a dataset orchestration job to begin.
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden shadow-xl">
      <table className="w-full text-left text-sm text-gray-300">
        <thead className="bg-gray-700/50 text-xs uppercase text-gray-400 border-b border-gray-700">
          <tr>
            <th className="px-6 py-3 font-semibold">Source Domain / Category</th>
            <th className="px-6 py-3 font-semibold">Avg Quality Score</th>
            <th className="px-6 py-3 font-semibold">Samples Evaluated</th>
            <th className="px-6 py-3 font-semibold">Status / Tier</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-700">
          {data.sources.map((item) => {
            const pct = (item.avg_quality * 100).toFixed(1);
            let badgeColor = "bg-red-500/10 text-red-400 border border-red-500/20";
            if (item.avg_quality >= 0.8) {
              badgeColor = "bg-green-500/10 text-green-400 border border-green-500/20";
            } else if (item.avg_quality >= 0.6) {
              badgeColor = "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20";
            }

            return (
              <tr key={item.source} className="hover:bg-gray-750 transition-colors">
                <td className="px-6 py-4 font-medium text-white capitalize">{item.source}</td>
                <td className="px-6 py-4 font-mono text-blue-400">{pct}%</td>
                <td className="px-6 py-4 font-mono">{item.samples_count}</td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-0.5 rounded text-xs border font-medium ${badgeColor}`}>
                    {item.avg_quality >= 0.8 ? "Excellent" : item.avg_quality >= 0.6 ? "Good" : "Needs Review"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
