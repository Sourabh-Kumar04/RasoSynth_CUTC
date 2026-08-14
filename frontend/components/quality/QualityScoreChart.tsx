"use client";
import React, { useEffect, useState } from "react";

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
    fetch("/api/quality/distributions")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-4 text-gray-400">Loading quality distribution...</div>;
  if (!data || data.total_scores === 0)
    return <div className="p-4 text-gray-500">No distribution data available yet.</div>;

  const { distribution, mean, histogram } = data;
  const maxBucket = Math.max(...histogram, 1);

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
      <h3 className="text-lg font-semibold text-white mb-3">Quality Score Distribution</h3>

      {/* Histogram */}
      <div className="mb-4">
        <div className="flex items-end h-32 gap-1 mb-2">
          {histogram.map((val, i) => (
            <div
              key={i}
              className="flex-1 bg-blue-500 rounded-t"
              style={{ height: `${(val / maxBucket) * 100}%`, minHeight: val > 0 ? "4px" : "0" }}
              title={`${i * 10}-${(i + 1) * 10}%: ${val} samples`}
            />
          ))}
        </div>
        <div className="text-xs text-gray-400 text-center">Score Range (0-100%)</div>
      </div>

      {/* Mean */}
      <div className="text-sm text-gray-300 mb-3">Mean Score: {(mean * 100).toFixed(1)}%</div>

      {/* Category breakdown */}
      <div className="grid grid-cols-4 gap-2 text-center text-sm">
        <div>
          <div className="text-green-400 font-bold">{distribution.excellent}</div>
          <div className="text-gray-400">Excellent</div>
        </div>
        <div>
          <div className="text-blue-400 font-bold">{distribution.good}</div>
          <div className="text-gray-400">Good</div>
        </div>
        <div>
          <div className="text-yellow-400 font-bold">{distribution.fair}</div>
          <div className="text-gray-400">Fair</div>
        </div>
        <div>
          <div className="text-red-400 font-bold">{distribution.poor}</div>
          <div className="text-gray-400">Poor</div>
        </div>
      </div>
    </div>
  );
}