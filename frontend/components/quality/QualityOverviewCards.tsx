"use client";
import React, { useEffect, useState } from "react";

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
    fetch("/api/quality/overview")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-4 text-gray-400">Loading quality overview...</div>;
  if (!data) return <div className="p-4 text-yellow-400">Quality API not available</div>;

  const cards = [
    { label: "Average Quality", value: (data.average_quality * 100).toFixed(1) + "%", color: data.average_quality > 0.7 ? "text-green-400" : data.average_quality > 0.4 ? "text-yellow-400" : "text-red-400" },
    { label: "Total Jobs", value: data.total_jobs.toString(), color: "text-blue-400" },
    { label: "Samples Reviewed", value: data.total_samples_reviewed.toString(), color: "text-purple-400" },
    { label: "Approval Rate", value: data.approval_rate + "%", color: data.approval_rate > 70 ? "text-green-400" : "text-yellow-400" },
    { label: "Rejection Rate", value: data.rejection_rate + "%", color: data.rejection_rate < 30 ? "text-green-400" : "text-red-400" },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 p-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">{card.label}</div>
          <div className={`text-2xl font-bold ${card.color}`}>{card.value}</div>
        </div>
      ))}
    </div>
  );
}