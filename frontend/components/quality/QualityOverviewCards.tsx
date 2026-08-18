"use client";
import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface QualityOverview {
  average_quality: number;
  total_jobs: number;
  total_samples_reviewed: number;
  approval_rate: number;
  rejection_rate: number;
}

export default function QualityOverviewCards() {
  const [data, setData] = useState<QualityOverview | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/quality/overview`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-muted-foreground text-sm">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading quality overview…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4 text-sm text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
        Quality API not available — run a dataset job first.
      </div>
    );
  }

  const cards = [
    {
      label: "Average Quality",
      value: (data.average_quality * 100).toFixed(1) + "%",
      color: data.average_quality > 0.7 ? "text-green-400"
           : data.average_quality > 0.4 ? "text-yellow-400" : "text-red-400",
    },
    { label: "Total Datasets", value: data.total_jobs.toString(), color: "text-blue-400" },
    { label: "Samples Reviewed", value: data.total_samples_reviewed.toLocaleString(), color: "text-purple-400" },
    {
      label: "Approval Rate",
      value: data.approval_rate + "%",
      color: data.approval_rate > 70 ? "text-green-400" : "text-yellow-400",
    },
    {
      label: "Rejection Rate",
      value: data.rejection_rate + "%",
      color: data.rejection_rate < 30 ? "text-green-400" : "text-red-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {cards.map(({ label, value, color }) => (
        <div key={label} className="bg-surface/40 rounded-lg border border-border p-4">
          <p className="text-xs text-muted-foreground mb-1">{label}</p>
          <p className={`text-2xl font-bold ${color}`}>{value}</p>
        </div>
      ))}
    </div>
  );
}
