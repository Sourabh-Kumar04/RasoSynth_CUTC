"use client";
import React, { useState } from "react";
import QualityOverviewCards from "@/components/quality/QualityOverviewCards";
import QualityScoreChart from "@/components/quality/QualityScoreChart";
import SourceQualityTable from "@/components/quality/SourceQualityTable";
import { BarChart2, Sparkles, Loader2, ShieldCheck, CheckCircle2, Network, Layers, Compass, AlertCircle, Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api/client";
import { clsx } from "clsx";

export default function QualityDashboardPage() {
  const [judgeInstruction, setJudgeInstruction] = useState("Aap ₹2,50,000 par 18% GST calculate karke bataiye kripya.");
  const [judgeResponse, setJudgeResponse] = useState("<thought>Pehle 2,50,000 * 0.18 calculate karenge = 45,000</thought>Aapka ₹2,50,000 par 18% GST ₹45,000 banta hai. Total payable amount ₹2,95,000 hoga.");
  const [judgeLang, setJudgeLang] = useState("hinglish");
  const [judgeRegister, setJudgeRegister] = useState("formal");
  const [judgeLoading, setJudgeLoading] = useState(false);
  const [judgeResult, setJudgeResult] = useState<any | null>(null);

  // Semantic Density State
  const [densityLoading, setDensityLoading] = useState(false);
  const [selectedPoint, setSelectedPoint] = useState<any | null>(null);
  const [densityResult, setDensityResult] = useState<any | null>({
    total_samples: 12,
    diversity_entropy: 0.942,
    semantic_coverage_pct: 91.7,
    outlier_count: 1,
    redundancy_count: 2,
    clusters: [
      { cluster_id: 0, label: "GST & Tax Calculations", sample_count: 4, percentage: 33.3, centroid: [32.5, 41.2], top_terms: ["gst", "calculate", "tax", "invoices"] },
      { cluster_id: 1, label: "Statutory Deductions & Slabs", sample_count: 3, percentage: 25.0, centroid: [68.0, 31.0], top_terms: ["80c", "deduction", "epf", "ppf"] },
      { cluster_id: 2, label: "Compliance & Dispute Notices", sample_count: 3, percentage: 25.0, centroid: [45.0, 78.5], top_terms: ["notice", "gstr-3b", "penalty", "appeal"] },
      { cluster_id: 3, label: "Enterprise & MSME Registry", sample_count: 2, percentage: 16.7, centroid: [75.0, 72.0], top_terms: ["udyam", "msme", "aadhaar", "portal"] },
    ],
    points: [
      { id: "p1", x: 28.5, y: 39.0, cluster_id: 0, cluster_label: "GST & Tax Calculations", is_outlier: false, is_redundant: true, instruction_snippet: "Calculate 18% GST on ₹2,50,000 for IT consulting services.", domain: "Taxation" },
      { id: "p2", x: 34.0, y: 43.5, cluster_id: 0, cluster_label: "GST & Tax Calculations", is_outlier: false, is_redundant: true, instruction_snippet: "How to compute CGST and SGST split on inter-state taxable supply.", domain: "Taxation" },
      { id: "p3", x: 36.2, y: 38.0, cluster_id: 0, cluster_label: "GST & Tax Calculations", is_outlier: false, is_redundant: false, instruction_snippet: "What are rules for claiming Input Tax Credit under Section 16(2)?", domain: "Taxation" },
      { id: "p4", x: 25.0, y: 46.0, cluster_id: 0, cluster_label: "GST & Tax Calculations", is_outlier: false, is_redundant: false, instruction_snippet: "E-invoicing mandate applicability for businesses exceeding ₹5 Cr turnover.", domain: "Taxation" },
      { id: "p5", x: 65.0, y: 33.0, cluster_id: 1, cluster_label: "Statutory Deductions & Slabs", is_outlier: false, is_redundant: false, instruction_snippet: "Explain Section 80C deductions for EPF and PPF deposits.", domain: "Income Tax" },
      { id: "p6", x: 71.0, y: 29.0, cluster_id: 1, cluster_label: "Statutory Deductions & Slabs", is_outlier: false, is_redundant: false, instruction_snippet: "Section 80D health insurance limits for senior citizen parents.", domain: "Income Tax" },
      { id: "p7", x: 67.5, y: 34.0, cluster_id: 1, cluster_label: "Statutory Deductions & Slabs", is_outlier: false, is_redundant: false, instruction_snippet: "Presumptive taxation scheme Section 44ADA for freelance architects.", domain: "Income Tax" },
      { id: "p8", x: 42.0, y: 76.0, cluster_id: 2, cluster_label: "Compliance & Dispute Notices", is_outlier: false, is_redundant: false, instruction_snippet: "Draft an objection letter against GST notice for reconciliation mismatch.", domain: "Compliance" },
      { id: "p9", x: 48.0, y: 81.0, cluster_id: 2, cluster_label: "Compliance & Dispute Notices", is_outlier: false, is_redundant: false, instruction_snippet: "Late filing fee calculation under Section 47 for GSTR-3B default.", domain: "Compliance" },
      { id: "p10", x: 44.5, y: 79.0, cluster_id: 2, cluster_label: "Compliance & Dispute Notices", is_outlier: false, is_redundant: false, instruction_snippet: "Procedure to file an appeal before the First Appellate Authority.", domain: "Compliance" },
      { id: "p11", x: 73.0, y: 70.0, cluster_id: 3, cluster_label: "Enterprise & MSME Registry", is_outlier: false, is_redundant: false, instruction_snippet: "How to register MSME Udyam portal online with Aadhaar OTP.", domain: "Corporate" },
      { id: "p12", x: 88.0, y: 89.0, cluster_id: 3, cluster_label: "Enterprise & MSME Registry", is_outlier: true, is_redundant: false, instruction_snippet: "Export-import container demurrage charges during customs dock detention.", domain: "Logistics / Edge" },
    ],
  });

  const handleRunSemanticProjection = async () => {
    setDensityLoading(true);
    try {
      const demoSamples = [
        { instruction: "Calculate 18% GST on ₹2,50,000 for IT consulting", response: "₹45,000", domain: "Taxation" },
        { instruction: "Input Tax Credit claiming conditions under Section 16", response: "Tax invoice and payment proof required.", domain: "Taxation" },
        { instruction: "Draft an objection reply for GSTR-2B reconciliation mismatch notice", response: "Respected Officer, Here is the reconciliation...", domain: "Compliance" },
        { instruction: "Explain Section 80C deductions for EPF and PPF deposits", response: "Up to ₹1.5L can be claimed under 80C.", domain: "Income Tax" },
        { instruction: "Health insurance premium deduction limits under Section 80D", response: "₹25,000 for self, ₹50,000 for senior parents.", domain: "Income Tax" },
        { instruction: "Udyam registration online steps for MSME certification", response: "Visit udyamregistration portal with PAN and Aadhaar.", domain: "Corporate" },
        { instruction: "Penalty for delayed submission of annual GSTR-9 filing", response: "Late fee under section 47 applies.", domain: "Compliance" },
        { instruction: "Customs duty bill of entry warehouse bond release clause", response: "Section 68 customs clearance procedure.", domain: "Logistics" },
      ];
      const res = await api.analyzeSemanticDensity({ samples: demoSamples, k_clusters: 4 });
      setDensityResult(res);
      if (res.points?.length) {
        setSelectedPoint(res.points[0]);
      }
    } catch (e: any) {
      console.error("Semantic density analysis failed:", e);
    } finally {
      setDensityLoading(false);
    }
  };

  const handleRunJudge = async () => {
    if (!judgeInstruction.trim() || !judgeResponse.trim()) return;
    setJudgeLoading(true);
    try {
      const res = await api.evaluateRubric({
        instruction: judgeInstruction.trim(),
        response: judgeResponse.trim(),
        language: judgeLang,
        formality_register: judgeRegister,
      });
      setJudgeResult(res);
    } catch (e: any) {
      console.error("Judge evaluation failed:", e);
    } finally {
      setJudgeLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-8">
      {/* Header */}
      <div className="border-b border-[#272738] pb-4">
        <div className="flex items-center gap-2.5 mb-1">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] font-bold uppercase tracking-wider">
            Quality Intelligence
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display flex items-center gap-2">
            <BarChart2 className="h-5 w-5 text-[#f26625]" />
            Dataset Quality Studio
          </h1>
        </div>
        <p className="text-xs text-[#94a3b8] font-sans">
          Grounding verifications, perplexity scores, deduplication metrics, and source-level quality breakdowns
        </p>
      </div>

      {/* Overview Cards */}
      <section>
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#94a3b8] mb-3">
          Overview Telemetry
        </h2>
        <QualityOverviewCards />
      </section>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <QualityScoreChart />
        <div className="bg-[#12121a] rounded-xl border border-[#272738] p-6 card-shadow">
          <h3 className="text-sm font-bold text-white mb-4 font-mono uppercase tracking-wider">Metrics &amp; Grounding Controls</h3>
          <ul className="space-y-3 text-sm">
            {[
              ["Duplicate Detection",   "4 levels (exact, fuzzy, embedding, MinHash LSH)"],
              ["Hallucination Detection","Source grounding + context citation matching"],
              ["Diversity Analysis",     "5 dimensions (topic, source, instruction, response, domain)"],
              ["Semantic Scoring",       "LLM Judge + heuristic fallback (perplexity & length)"],
              ["Human Review Gate",      "Stratified sampling, approve, reject, edit in HITL queue"],
            ].map(([label, detail]) => (
              <li key={label} className="flex items-start justify-between gap-4 p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                <span className="text-white font-bold text-xs">{label}</span>
                <span className="text-[#94a3b8] text-xs font-mono text-right">{detail}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Interactive LLM-as-a-Judge Live Rubric Evaluator */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#94a3b8]">
            Automated LLM-as-a-Judge Multi-Dimensional Rubric
          </h2>
          <Badge variant="outline" className="text-[10px] border-[#272738] text-cyan-300 font-mono rounded-sm">
            5-Dimension MT-Bench Rubric
          </Badge>
        </div>

        <Card className="border-[#272738] bg-[#12121a] rounded-xl card-shadow overflow-hidden">
          <CardHeader className="pb-3 border-b border-[#272738] bg-[#0e0e14]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#f26625]" />
                <CardTitle className="text-sm font-bold text-white font-mono">Sample Quality Jury</CardTitle>
              </div>
              <Button
                size="sm"
                onClick={handleRunJudge}
                disabled={judgeLoading}
                className="h-8 gap-1.5 text-xs font-mono rounded-md bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white font-bold glow-yc"
              >
                {judgeLoading ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Evaluating...
                  </>
                ) : (
                  <>
                    <ShieldCheck className="h-3.5 w-3.5" />
                    Run 5D Evaluation
                  </>
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-5 space-y-4 font-mono text-xs">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] text-[#94a3b8] uppercase font-bold block mb-1">Test Instruction</label>
                <textarea
                  value={judgeInstruction}
                  onChange={(e) => setJudgeInstruction(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-[#0a0a0f] border border-[#272738] text-white focus:outline-none focus:border-[#6366f1] text-xs resize-none"
                />
              </div>
              <div>
                <label className="text-[10px] text-[#94a3b8] uppercase font-bold block mb-1">Synthesized Response / CoT Trace</label>
                <textarea
                  value={judgeResponse}
                  onChange={(e) => setJudgeResponse(e.target.value)}
                  rows={3}
                  className="w-full p-2.5 rounded-xl bg-[#0a0a0f] border border-[#272738] text-white focus:outline-none focus:border-[#6366f1] text-xs resize-none"
                />
              </div>
            </div>

            {/* Rubric Score Breakdown */}
            {judgeResult && (
              <div className="p-4 rounded-xl bg-[#0a0a0f] border border-[#272738] space-y-3 animate-fade-in">
                <div className="flex items-center justify-between pb-2 border-b border-[#1c1c28]">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-[#10b981]" />
                    <span className="font-bold text-white text-xs">Jury Rubric Results</span>
                    <Badge variant="outline" className={clsx("text-[10px] font-bold uppercase", judgeResult.rating === 'excellent' ? 'bg-emerald-950/60 text-emerald-400 border-emerald-700' : 'bg-amber-950/60 text-amber-300 border-amber-700')}>
                      {judgeResult.rating}
                    </Badge>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-[#94a3b8] uppercase mr-2">Overall Quality Index</span>
                    <span className="text-base font-bold text-[#10b981]">
                      {Math.round(judgeResult.overall_score * 100)}%
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                  {[
                    { label: "Groundedness", val: judgeResult.groundedness },
                    { label: "Authenticity", val: judgeResult.authenticity },
                    { label: "Correctness", val: judgeResult.domain_correctness },
                    { label: "Safety & Tone", val: judgeResult.safety_tone },
                    { label: "Conciseness", val: judgeResult.conciseness },
                  ].map((dim, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-[#12121a] border border-[#272738] space-y-1">
                      <span className="text-[10px] text-[#94a3b8] uppercase block truncate">{dim.label}</span>
                      <p className="text-sm font-bold text-white">
                        {Math.round(dim.val * 100)}%
                      </p>
                      <div className="w-full bg-[#1c1c28] h-1 rounded-full overflow-hidden">
                        <div
                          className={clsx("h-full", dim.val >= 0.85 ? "bg-[#10b981]" : dim.val >= 0.65 ? "bg-amber-400" : "bg-rose-500")}
                          style={{ width: `${Math.round(dim.val * 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Semantic Density & 2D Topic Coverage Visualizer */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#94a3b8]">
              Semantic Density &amp; 2D Topic Coverage Visualizer
            </h2>
            <Badge variant="outline" className="text-[10px] border-[#272738] text-purple-300 font-mono">
              TF-IDF + Truncated SVD Projection
            </Badge>
          </div>
          <Button
            size="sm"
            onClick={handleRunSemanticProjection}
            disabled={densityLoading}
            className="h-7 text-xs bg-[#1f1f2e] hover:bg-[#2b2b3d] text-white border border-[#3b3b52] font-mono gap-1.5"
          >
            {densityLoading ? <Loader2 className="h-3 w-3 animate-spin text-purple-400" /> : <Network className="h-3 w-3 text-purple-400" />}
            {densityLoading ? "Projecting..." : "Recompute 2D Clusters"}
          </Button>
        </div>

        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow overflow-hidden">
          <CardHeader className="pb-3 border-b border-[#272738] bg-[#0e0e14]">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center sm:text-left">
              <div className="p-2 rounded-lg bg-[#161622] border border-[#272738]">
                <span className="text-[10px] text-[#94a3b8] uppercase font-mono block">Audited Points</span>
                <span className="text-sm font-bold text-white font-mono">{densityResult?.total_samples || 0} records</span>
              </div>
              <div className="p-2 rounded-lg bg-[#161622] border border-[#272738]">
                <span className="text-[10px] text-[#94a3b8] uppercase font-mono block">Topic Entropy</span>
                <span className="text-sm font-bold text-emerald-400 font-mono">
                  {Math.round((densityResult?.diversity_entropy || 0) * 100)}%
                </span>
              </div>
              <div className="p-2 rounded-lg bg-[#161622] border border-[#272738]">
                <span className="text-[10px] text-[#94a3b8] uppercase font-mono block">Semantic Coverage</span>
                <span className="text-sm font-bold text-cyan-400 font-mono">
                  {densityResult?.semantic_coverage_pct || 0}%
                </span>
              </div>
              <div className="p-2 rounded-lg bg-[#161622] border border-[#272738]">
                <span className="text-[10px] text-[#94a3b8] uppercase font-mono block">Isolated Outliers</span>
                <span className="text-sm font-bold text-rose-400 font-mono">
                  {densityResult?.outlier_count || 0} edge case(s)
                </span>
              </div>
              <div className="p-2 rounded-lg bg-[#161622] border border-[#272738]">
                <span className="text-[10px] text-[#94a3b8] uppercase font-mono block">Dense Redundancies</span>
                <span className="text-sm font-bold text-sky-400 font-mono">
                  {densityResult?.redundancy_count || 0} core duplicates
                </span>
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-5">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* 2D Projection Canvas */}
              <div className="lg:col-span-2 relative bg-[#0a0a0f] border border-[#272738] rounded-xl p-4 flex flex-col items-center justify-center min-h-[340px]">
                <div className="absolute top-2 left-3 flex items-center gap-2 text-[10px] font-mono text-[#64748b]">
                  <Compass className="h-3 w-3 text-purple-400" />
                  <span>Principal Latent Dimension 1 (X) vs. Dimension 2 (Y)</span>
                </div>

                <svg viewBox="0 0 100 100" className="w-full h-72 overflow-visible select-none my-2">
                  {/* Subtle Grid */}
                  <line x1="50" y1="5" x2="50" y2="95" stroke="#1f1f2e" strokeDasharray="1,1" strokeWidth="0.5" />
                  <line x1="5" y1="50" x2="95" y2="50" stroke="#1f1f2e" strokeDasharray="1,1" strokeWidth="0.5" />

                  {/* Centroids */}
                  {densityResult?.clusters?.map((c: any, idx: number) => {
                    const colors = ["#6366f1", "#10b981", "#f59e0b", "#ec4899"];
                    const color = colors[idx % colors.length];
                    return (
                      <g key={`cent-${c.cluster_id}`}>
                        <circle
                          cx={c.centroid[0]}
                          cy={c.centroid[1]}
                          r="6"
                          fill={color}
                          opacity="0.12"
                        />
                        <circle
                          cx={c.centroid[0]}
                          cy={c.centroid[1]}
                          r="1.2"
                          fill={color}
                          opacity="0.8"
                        />
                      </g>
                    );
                  })}

                  {/* Points */}
                  {densityResult?.points?.map((pt: any) => {
                    const colors = ["#6366f1", "#10b981", "#f59e0b", "#ec4899"];
                    const color = colors[pt.cluster_id % colors.length];
                    const isSelected = selectedPoint?.id === pt.id;

                    return (
                      <g
                        key={pt.id}
                        onClick={() => setSelectedPoint(pt)}
                        className="cursor-pointer transition-transform duration-200"
                      >
                        {pt.is_outlier && (
                          <circle
                            cx={pt.x}
                            cy={pt.y}
                            r="3.2"
                            fill="none"
                            stroke="#f43f5e"
                            strokeWidth="0.6"
                            strokeDasharray="1,1"
                          />
                        )}
                        {pt.is_redundant && (
                          <circle
                            cx={pt.x}
                            cy={pt.y}
                            r="3.0"
                            fill="none"
                            stroke="#38bdf8"
                            strokeWidth="0.5"
                          />
                        )}
                        <circle
                          cx={pt.x}
                          cy={pt.y}
                          r={isSelected ? "2.6" : "1.8"}
                          fill={color}
                          stroke={isSelected ? "#ffffff" : color}
                          strokeWidth={isSelected ? "0.8" : "0.3"}
                          opacity={isSelected ? "1.0" : "0.85"}
                        />
                      </g>
                    );
                  })}
                </svg>

                <div className="w-full flex items-center justify-between text-[10px] font-mono text-[#64748b] pt-1 border-t border-[#1a1a24]">
                  <span>Click any coordinate node to inspect sample topic &amp; cluster balance</span>
                  <div className="flex items-center gap-3">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full border border-dashed border-rose-500 inline-block" /> Outlier
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full border border-sky-400 inline-block" /> Redundant Core
                    </span>
                  </div>
                </div>
              </div>

              {/* Cluster Legend & Inspector */}
              <div className="space-y-4 flex flex-col justify-between">
                {/* Cluster Cards */}
                <div>
                  <h4 className="text-xs font-mono font-bold text-[#94a3b8] uppercase mb-2 flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-purple-400" />
                    Topological Clusters ({densityResult?.clusters?.length || 0})
                  </h4>
                  <div className="space-y-2">
                    {densityResult?.clusters?.map((c: any, idx: number) => {
                      const colors = ["#6366f1", "#10b981", "#f59e0b", "#ec4899"];
                      const color = colors[idx % colors.length];
                      return (
                        <div
                          key={c.cluster_id}
                          className="p-2.5 rounded-xl bg-[#0a0a0f] border border-[#272738] flex items-center justify-between"
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className="w-2.5 h-2.5 rounded-full shrink-0"
                              style={{ backgroundColor: color }}
                            />
                            <div>
                              <p className="text-xs font-bold text-white leading-tight">{c.label}</p>
                              <p className="text-[10px] text-[#64748b] font-mono">
                                {c.top_terms?.slice(0, 3).join(", ")}
                              </p>
                            </div>
                          </div>
                          <Badge variant="outline" className="text-[10px] font-mono border-[#272738] text-white">
                            {c.sample_count} ({c.percentage}%)
                          </Badge>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Point Detail Inspector */}
                <div className="p-3.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-mono uppercase text-[#94a3b8] flex items-center gap-1">
                      <Info className="h-3 w-3 text-cyan-400" />
                      Sample Inspector
                    </span>
                    {selectedPoint?.is_outlier && (
                      <Badge className="text-[9px] bg-rose-950/70 text-rose-400 border border-rose-800">
                        Isolated Edge Case
                      </Badge>
                    )}
                    {selectedPoint?.is_redundant && (
                      <Badge className="text-[9px] bg-sky-950/70 text-sky-400 border border-sky-800">
                        Cluster Core Duplicate
                      </Badge>
                    )}
                  </div>
                  {selectedPoint ? (
                    <div className="space-y-1.5 text-xs">
                      <p className="text-white font-medium line-clamp-3">
                        &ldquo;{selectedPoint.instruction_snippet}&rdquo;
                      </p>
                      <div className="flex items-center justify-between pt-1 text-[10px] font-mono text-[#64748b]">
                        <span>Domain: <strong className="text-slate-300">{selectedPoint.domain}</strong></span>
                        <span>Coord: [{selectedPoint.x}, {selectedPoint.y}]</span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-[#64748b] italic">
                      Click any point on the canvas to inspect its instruction snippet and latent spatial coordinates.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Source Quality Table */}
      <section>
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#94a3b8] mb-3">
          Source Quality Breakdown — Strategic Segmentation
        </h2>
        <SourceQualityTable />
      </section>
    </div>
  );
}
