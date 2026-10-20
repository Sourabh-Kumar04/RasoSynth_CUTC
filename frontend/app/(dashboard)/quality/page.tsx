"use client";
import React, { useState } from "react";
import QualityOverviewCards from "@/components/quality/QualityOverviewCards";
import QualityScoreChart from "@/components/quality/QualityScoreChart";
import SourceQualityTable from "@/components/quality/SourceQualityTable";
import { BarChart2, Sparkles, Loader2, ShieldCheck, CheckCircle2 } from "lucide-react";
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
          <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#161622] border border-[#3b3b52] text-[#6366f1] font-bold uppercase tracking-wider">
            Quality Intelligence
          </span>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display flex items-center gap-2">
            <BarChart2 className="h-5 w-5 text-[#6366f1]" />
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
        <div className="bg-[#12121a] rounded-2xl border border-[#272738] p-6 card-shadow">
          <h3 className="text-sm font-bold text-white mb-4 font-mono uppercase tracking-wider">Metrics &amp; Grounding Controls</h3>
          <ul className="space-y-3 text-sm">
            {[
              ["Duplicate Detection",   "4 levels (exact, fuzzy, embedding, MinHash LSH)"],
              ["Hallucination Detection","Source grounding + context citation matching"],
              ["Diversity Analysis",     "5 dimensions (topic, source, instruction, response, domain)"],
              ["Semantic Scoring",       "LLM Judge + heuristic fallback (perplexity & length)"],
              ["Human Review Gate",      "Stratified sampling, approve, reject, edit in HITL queue"],
            ].map(([label, detail]) => (
              <li key={label} className="flex items-start justify-between gap-4 p-2.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
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
          <Badge variant="outline" className="text-[10px] border-[#272738] text-cyan-300 font-mono">
            5-Dimension MT-Bench Rubric
          </Badge>
        </div>

        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow overflow-hidden">
          <CardHeader className="pb-3 border-b border-[#272738] bg-[#0e0e14]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#818cf8]" />
                <CardTitle className="text-sm font-bold text-white font-mono">Sample Quality Jury</CardTitle>
              </div>
              <Button
                size="sm"
                onClick={handleRunJudge}
                disabled={judgeLoading}
                className="h-8 gap-1.5 text-xs font-mono rounded-full bg-[#6366f1] hover:bg-indigo-600 text-white"
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
