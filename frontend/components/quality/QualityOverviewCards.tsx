import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api/client";

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
    api.getQualityOverview()
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-[#94a3b8] font-mono text-xs">
        <Loader2 className="h-4 w-4 animate-spin text-[#6366f1]" /> Loading quality overview…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4 text-xs font-mono text-amber-400 bg-amber-950/20 border border-amber-500/30 rounded-xl">
        Quality API not available — run a dataset job first.
      </div>
    );
  }

  const cards = [
    {
      label: "Average Quality",
      value: (data.average_quality * 100).toFixed(1) + "%",
      color: data.average_quality > 0.7 ? "text-[#10b981]"
           : data.average_quality > 0.4 ? "text-amber-400" : "text-rose-400",
    },
    { label: "Total Datasets", value: data.total_jobs.toString(), color: "text-white" },
    { label: "Samples Reviewed", value: data.total_samples_reviewed.toLocaleString(), color: "text-[#818cf8]" },
    {
      label: "Approval Rate",
      value: data.approval_rate + "%",
      color: data.approval_rate > 70 ? "text-[#10b981]" : "text-amber-400",
    },
    {
      label: "Rejection Rate",
      value: data.rejection_rate + "%",
      color: data.rejection_rate < 30 ? "text-[#10b981]" : "text-rose-400",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {cards.map(({ label, value, color }) => (
        <div key={label} className="bg-[#12121a] rounded-2xl border border-[#272738] p-4 card-shadow">
          <p className="text-xs font-mono text-[#94a3b8] uppercase mb-1">{label}</p>
          <p className={`text-2xl font-bold font-mono ${color}`}>{value}</p>
        </div>
      ))}
    </div>
  );
}
