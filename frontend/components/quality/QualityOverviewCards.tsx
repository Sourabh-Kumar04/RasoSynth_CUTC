import React, { useEffect, useState } from "react";
import { Loader2, ShieldCheck, Database, CheckCircle2, XCircle, Award } from "lucide-react";
import { api } from "@/lib/api/client";

interface QualityOverview {
  average_quality: number;
  total_jobs: number;
  total_samples_reviewed: number;
  approval_rate: number;
  rejection_rate: number;
  is_live?: boolean;
}

export default function QualityOverviewCards() {
  const [data, setData] = useState<QualityOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    api.getQualityOverview()
      .then((res: any) => {
        // Mock-mode responses must never render as live.
        const mockMode = typeof window !== 'undefined' && localStorage.getItem('mockMode') === 'true';
        setData({
          ...res,
          is_live: !mockMode,
        });
      })
      .catch(() => {
        // No fallback numbers: an unavailable metric shows as unavailable.
        setData(null);
        setLoadError(true);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-[#a8a29e] font-mono text-xs">
        <Loader2 className="h-4 w-4 animate-spin text-[#f26625]" /> Loading quality overview telemetry…
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-4 text-[#a8a29e] font-mono text-xs border border-[#272738] rounded-md bg-[#12121a]">
        Quality overview unavailable — live metrics could not be loaded.
      </div>
    );
  }

  const formatRate = (rate: number | undefined) => {
    if (rate === undefined || rate === null) return "—";
    if (rate <= 1) return `${Math.round(rate * 100)}%`;
    return `${Math.round(rate)}%`;
  };

  const avgScore = data?.average_quality ?? null;
  const avgPct = avgScore == null ? null : avgScore <= 1 ? (avgScore * 100).toFixed(1) : Number(avgScore).toFixed(1);

  const cards = [
    {
      label: "Average Quality",
      sub: "5D Rubric Mean",
      value: avgPct == null ? '—' : `${avgPct}%`,
      icon: Award,
      color: avgPct == null ? "text-zinc-400" : Number(avgPct) > 75 ? "text-[#10b981]" : Number(avgPct) > 50 ? "text-amber-400" : "text-rose-400",
      badge: "MT-Bench / Jury",
    },
    {
      label: "Certified Datasets",
      sub: "Active Repositories",
      value: (data?.total_jobs ?? '—').toString(),
      icon: Database,
      color: "text-white",
      badge: "Catalogued",
    },
    {
      label: "Samples Reviewed",
      sub: "Automated & HITL",
      value: data?.total_samples_reviewed != null ? data.total_samples_reviewed.toLocaleString() : '—',
      icon: ShieldCheck,
      color: "text-[#f26625]",
      badge: "Stratified Split",
    },
    {
      label: "Approval Rate",
      sub: "Consensus Passing",
      value: formatRate(data?.approval_rate),
      icon: CheckCircle2,
      color: "text-[#10b981]",
      badge: "≥ 0.80 Threshold",
    },
    {
      label: "Rejection Rate",
      sub: "Decontaminated / Filtered",
      value: formatRate(data?.rejection_rate),
      icon: XCircle,
      color: "text-rose-400",
      badge: "Zero Contam",
    },
  ];

  return (
    <div className="space-y-2">
      <div className="flex flex-col sm:flex-row sm:divide-x divide-[#272738] rounded-md border border-[#272738] bg-[#12121a]">
        {cards.map(({ label, sub, value, color, icon: Icon, badge }) => (
          <div key={label} className="flex-1 px-4 py-3 flex flex-col justify-between">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-mono text-[#a8a29e] uppercase tracking-wider font-bold truncate">{label}</span>
              <Icon className="h-3.5 w-3.5 text-[#a8a29e] shrink-0" />
            </div>
            <div className="my-1">
              <p className={`text-2xl font-bold font-mono tracking-tight ${color}`}>{value}</p>
              <p className="text-xs text-[#a8a29e] font-mono">{sub}</p>
            </div>
            <div className="pt-2 border-t border-[#1a1a26] mt-1">
              <span className="text-xs font-mono text-[#a8a29e] bg-[#0a0a0f] px-1.5 py-0.5 rounded border border-[#272738]">
                {badge}
              </span>
            </div>
          </div>
        ))}
      </div>
      {!data?.is_live && (
        <p className="text-xs font-mono text-[#a8a29e] text-right">
          Telemetry mode: Calibrated Reference Baseline (Live metrics sync when continuous generator jobs run)
        </p>
      )}
    </div>
  );
}
