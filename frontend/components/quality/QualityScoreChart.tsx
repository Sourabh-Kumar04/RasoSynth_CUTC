"use client";
import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
    fetch(`${API_BASE}/api/quality/distributions`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="bg-surface/40 rounded-lg border border-border p-4 flex items-center gap-2 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading distribution…
      </div>
    );
  }

  if (!data || data.total_scores === 0) {
    return (
      <div className="bg-surface/40 rounded-lg border border-border p-8 flex items-center justify-center text-sm text-muted-foreground">
        No distribution data yet — run a dataset job first.
      </div>
    );
  }

  const { distribution, mean, histogram } = data;
  const maxBucket = Math.max(...histogram, 1);

  return (
    <div className="bg-surface/40 rounded-lg border border-border p-4">
      <h3 className="text-sm font-semibold mb-4">Quality Score Distribution</h3>

      {/* Histogram */}
      <div className="flex items-end h-28 gap-1 mb-2">
        {histogram.map((val, i) => (
          <div
            key={i}
            className="flex-1 bg-accent/70 rounded-t transition-all hover:bg-accent"
            style={{ height: `${(val / maxBucket) * 100}%`, minHeight: val > 0 ? "3px" : "0" }}
            title={`${i * 10}–${(i + 1) * 10}%: ${val} samples`}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground text-center mb-3">Score range (0–100%)</p>
      <p className="text-xs text-muted-foreground mb-4">
        Mean: <span className="font-mono text-foreground">{(mean * 100).toFixed(1)}%</span>
        <span className="ml-3">Total: <span className="font-mono text-foreground">{data.total_scores.toLocaleString()}</span></span>
      </p>

      {/* Category breakdown */}
      <div className="grid grid-cols-4 gap-2 text-center text-xs">
        {[
          { label: "Excellent", value: distribution.excellent, color: "text-green-400" },
          { label: "Good",      value: distribution.good,      color: "text-blue-400"  },
          { label: "Fair",      value: distribution.fair,      color: "text-yellow-400"},
          { label: "Poor",      value: distribution.poor,      color: "text-red-400"   },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-background/50 rounded-lg p-2 border border-border/40">
            <p className={`text-base font-bold ${color}`}>{value}</p>
            <p className="text-muted-foreground mt-0.5">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
