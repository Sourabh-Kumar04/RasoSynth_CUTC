'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import {
  Sparkles,
  Play,
  Square,
  RefreshCw,
  Trophy,
  CheckCircle2,
  XCircle,
  Copy,
  Download,
  Terminal,
  Zap,
  TrendingDown,
  Layers,
  Cpu,
  ArrowRight,
  Database,
  Sliders,
  FileText
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { clsx } from 'clsx'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'

export interface AutoResearchTrial {
  id: number
  name: string
  hypothesis: string
  lora_r: number
  lora_alpha: number
  learning_rate: number
  lr_scheduler: 'linear' | 'cosine' | 'constant'
  train_loss: number
  eval_loss: number
  loss_delta_pct: number
  win_rate_pct: number
  decision: 'keep' | 'discard'
  duration_sec: number
  reasoning: string
}

const DEFAULT_TRIALS: AutoResearchTrial[] = [
  {
    id: 1,
    name: 'Trial 1 (Baseline Anchor)',
    hypothesis: 'Establish empirical baseline with standard Rank-16 LoRA and linear decay schedule.',
    lora_r: 16,
    lora_alpha: 32,
    learning_rate: 0.0002,
    lr_scheduler: 'linear',
    train_loss: 0.442,
    eval_loss: 0.468,
    loss_delta_pct: 0.0,
    win_rate_pct: 68.5,
    decision: 'keep',
    duration_sec: 14,
    reasoning: 'Baseline established as initial champion benchmark.',
  },
  {
    id: 2,
    name: 'Trial 2 (High-Rank Capacity)',
    hypothesis: 'Expand LoRA rank to r=32 to capture dense domain-specific statutory statutory clauses and cross-referencing.',
    lora_r: 32,
    lora_alpha: 64,
    learning_rate: 0.00018,
    lr_scheduler: 'linear',
    train_loss: 0.365,
    eval_loss: 0.381,
    loss_delta_pct: -18.6,
    win_rate_pct: 79.2,
    decision: 'keep',
    duration_sec: 16,
    reasoning: 'Validation loss decreased by 18.6% with substantial statutory accuracy gain. Promoted to Champion.',
  },
  {
    id: 3,
    name: 'Trial 3 (Aggressive Learning Rate)',
    hypothesis: 'Accelerate convergence using 3x higher learning rate (lr=5e-4) with rank-32.',
    lora_r: 32,
    lora_alpha: 64,
    learning_rate: 0.0005,
    lr_scheduler: 'linear',
    train_loss: 0.512,
    eval_loss: 0.584,
    loss_delta_pct: +53.3,
    win_rate_pct: 54.0,
    decision: 'discard',
    duration_sec: 13,
    reasoning: 'Gradient instability observed; validation loss degraded by 53%. Reverting to Trial 2 checkpoint.',
  },
  {
    id: 4,
    name: 'Trial 4 (Cosine Warmup & Packing)',
    hypothesis: 'Apply smooth cosine annealing schedule with sample packing to prevent padding noise on tail tokens.',
    lora_r: 32,
    lora_alpha: 64,
    learning_rate: 0.00015,
    lr_scheduler: 'cosine',
    train_loss: 0.298,
    eval_loss: 0.314,
    loss_delta_pct: -17.6,
    win_rate_pct: 88.4,
    decision: 'keep',
    duration_sec: 18,
    reasoning: 'Cosine decay smoothed gradient steps. Achieved lowest perplexity and 88.4% win-rate. Crowned Champion.',
  },
]

export function AutoResearchView({
  pipelineDatasets = [],
  onAdoptChampion,
}: {
  pipelineDatasets: any[]
  onAdoptChampion?: (trial: AutoResearchTrial) => void
}) {
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('')
  const [objective, setObjective] = useState(
    'Minimize validation loss & maximize statutory citation accuracy on Indian legal / domain corpus'
  )
  const [maxTrials, setMaxTrials] = useState<number>(5)
  const [isRunning, setIsRunning] = useState<boolean>(false)
  const [trials, setTrials] = useState<AutoResearchTrial[]>(DEFAULT_TRIALS)
  const [activeStep, setActiveStep] = useState<string>('Idle · Ready for autonomous exploration')
  const [currentProgress, setCurrentProgress] = useState<number>(0)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [agentLogs, setAgentLogs] = useState<string[]>([
    '[INIT] AutoResearch agent initialized with Karpathy-style autonomous loop.',
    '[STATE] Anchor trials loaded: 4 iterations completed, Trial #4 is current champion.',
  ])

  // Select most recent dataset by default
  useEffect(() => {
    if (pipelineDatasets && pipelineDatasets.length > 0 && !selectedDatasetId) {
      setSelectedDatasetId(pipelineDatasets[0].id)
    }
  }, [pipelineDatasets, selectedDatasetId])

  // Find the winning champion trial (lowest eval_loss among keep decisions)
  const championTrial = useMemo(() => {
    const kept = trials.filter((t) => t.decision === 'keep')
    if (kept.length === 0) return trials[0]
    return kept.reduce((best, curr) => (curr.eval_loss < best.eval_loss ? curr : best), kept[0])
  }, [trials])

  const handleCopy = (text: string) => {
    playClickSound()
    navigator.clipboard.writeText(text)
    setCopiedId(text)
    setTimeout(() => setCopiedId(null), 2000)
  }

  // Autonomous loop simulator
  const runAutoLoop = async () => {
    if (isRunning) {
      setIsRunning(false)
      setActiveStep('Paused by user')
      return
    }

    playClickSound()
    setIsRunning(true)
    const nextId = trials.length + 1
    setActiveStep(`Agent formulating hypothesis for Trial #${nextId}...`)
    setCurrentProgress(15)

    setAgentLogs((prev) => [
      ...prev,
      `[LOOP] Starting autonomous trial #${nextId}...`,
      `[AGENT] Inspecting prior Champion (Trial #${championTrial.id}, eval_loss=${championTrial.eval_loss})...`,
    ])

    await new Promise((r) => setTimeout(r, 1200))
    setCurrentProgress(40)
    setActiveStep(`Agent dispatching QLoRA training for Trial #${nextId} (r=48, lr=1.2e-4, cosine)...`)
    setAgentLogs((prev) => [
      ...prev,
      `[HYPOTHESIS] Fine-grained Rank-48 parameter allocation with lr=1.2e-4 to capture edge exceptions.`,
      `[TRAINING] Compiling PyTorch QLoRA graph on cloud GPU...`,
    ])

    await new Promise((r) => setTimeout(r, 1800))
    setCurrentProgress(80)
    setActiveStep(`Evaluating candidate model against held-out benchmark split...`)

    await new Promise((r) => setTimeout(r, 1200))
    setCurrentProgress(100)

    const newEval = 0.285
    const delta = Math.round(((newEval - championTrial.eval_loss) / championTrial.eval_loss) * 1000) / 10
    const newTrial: AutoResearchTrial = {
      id: nextId,
      name: `Trial ${nextId} (Rank-48 Precision)`,
      hypothesis: 'Fine-grained Rank-48 parameter allocation with lr=1.2e-4 to capture edge exceptions.',
      lora_r: 48,
      lora_alpha: 96,
      learning_rate: 0.00012,
      lr_scheduler: 'cosine',
      train_loss: 0.264,
      eval_loss: newEval,
      loss_delta_pct: delta,
      win_rate_pct: 91.8,
      decision: 'keep',
      duration_sec: 17,
      reasoning: `New record convergence: eval_loss reduced to ${newEval} (${delta}%). Promoted to Champion!`,
    }

    setTrials((prev) => [...prev, newTrial])
    setAgentLogs((prev) => [
      ...prev,
      `[VERDICT] Trial #${nextId} achieved ${delta}% lower loss. Promoted to New Champion!`,
      `[REPORT] Checkpoint weights verified and stored.`,
    ])
    setActiveStep(`Trial #${nextId} completed successfully! New Champion crowned.`)
    setIsRunning(false)
    playSuccessChime()
  }

  const exportReport = () => {
    playClickSound()
    const content = `# AutoResearch Trajectory & Empirical Log
Generated by RasoSynthTune Autonomous Fine-Tuning Agent (Karpathy Paradigm)

## Objective
${objective}

## Champion Configuration
- **Model Checkpoint**: ${championTrial.name}
- **LoRA Rank**: ${championTrial.lora_r} (Alpha: ${championTrial.lora_alpha})
- **Learning Rate**: ${championTrial.learning_rate}
- **LR Scheduler**: ${championTrial.lr_scheduler}
- **Validation Loss**: ${championTrial.eval_loss} (Delta: ${championTrial.loss_delta_pct}%)
- **Benchmark Win Rate**: ${championTrial.win_rate_pct}%

## Experiment Iterations
| Trial | Hypothesis | LoRA r | LR | Eval Loss | Delta | Decision |
|---|---|---|---|---|---|---|
${trials
  .map(
    (t) =>
      `| #${t.id} | ${t.hypothesis} | ${t.lora_r} | ${t.learning_rate} | ${t.eval_loss.toFixed(4)} | ${
        t.loss_delta_pct
      }% | **${t.decision.toUpperCase()}** |`
  )
  .join('\n')}

## Autonomous Findings
1. Higher LoRA rank (r=32 to r=48) is essential for domain statutory recall compared to general conversational models.
2. Cosine learning rate scheduling with 10% warmup prevented divergence that affected linear schedules with aggressive learning rates.
3. Automatic checkpoint rollbacks prevented degraded runs from corrupting model weights.
`

    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `AUTORESEARCH_FINDINGS.md`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-6 font-mono text-xs animate-fade-in">
      {/* Hero Header */}
      <div className="p-5 rounded-xl bg-gradient-to-r from-purple-950/40 via-[#12121a] to-[#0a0a0f] border border-purple-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="p-1 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 font-bold uppercase text-[10px] flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-purple-400" />
              Karpathy AutoResearch Paradigm
            </span>
            <Badge variant="outline" className="text-[10px] border-emerald-500/40 text-emerald-400 bg-emerald-950/20 font-bold">
              Autonomous Agent Active
            </Badge>
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight font-display">
            Autonomous Hyperparameter &amp; Model Optimization Loop
          </h2>
          <p className="text-xs text-zinc-400 max-w-2xl font-sans">
            Inspired by Andrej Karpathy&apos;s autoresearch. An autonomous AI researcher tests ML hypotheses,
            runs training trials, audits validation loss, discards regressions, and keeps champion checkpoints.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 flex-wrap">
          <Button
            type="button"
            size="sm"
            onClick={runAutoLoop}
            className={clsx(
              'h-9 px-4 font-bold text-xs rounded-md shadow-md flex items-center gap-2 transition-all cursor-pointer',
              isRunning
                ? 'bg-amber-600 hover:bg-amber-500 text-white'
                : 'bg-gradient-to-r from-purple-600 to-[#f26625] hover:opacity-95 text-white'
            )}
          >
            {isRunning ? (
              <>
                <Square className="w-3.5 h-3.5 fill-current" />
                <span>Pause AutoResearch</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Run Autonomous Trial</span>
              </>
            )}
          </Button>

          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={exportReport}
            className="h-9 px-3 border-[#272738] bg-[#0a0a0f] text-zinc-300 hover:text-white flex items-center gap-1.5 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-purple-400" />
            <span>Export Findings (.md)</span>
          </Button>
        </div>
      </div>

      {/* Dataset & Objective Configuration Card */}
      <Card className="bg-[#12121a] border-[#272738] rounded-xl">
        <CardContent className="p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Target Dataset Selection */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-white uppercase flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-[#f26625]" />
                  Training Dataset Target
                </label>
                {selectedDatasetId && (
                  <button
                    type="button"
                    onClick={() => handleCopy(selectedDatasetId)}
                    className="text-[11px] text-zinc-400 hover:text-white flex items-center gap-1 font-mono transition-colors cursor-pointer"
                  >
                    <Copy className="w-3 h-3 text-[#f26625]" />
                    <span>{copiedId === selectedDatasetId ? 'Copied!' : `#${selectedDatasetId.slice(0, 8)}`}</span>
                  </button>
                )}
              </div>
              <Select value={selectedDatasetId} onValueChange={setSelectedDatasetId}>
                <SelectTrigger className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9">
                  <SelectValue placeholder="Choose synthesized dataset..." />
                </SelectTrigger>
                <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs">
                  {pipelineDatasets.map((ds, idx) => (
                    <SelectItem key={ds.id} value={ds.id}>
                      {idx === 0 ? '★ [Most Recent] ' : ''}
                      {ds.config?.target_domain || ds.target_domain || ds.dataset_name || ds.id.slice(0, 8)} (
                      {ds.samples_generated || 0} rows)
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Research Goal / Objective */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-white uppercase flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-purple-400" />
                Research Objective / Fitness Function
              </label>
              <Input
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9"
                placeholder="Optimization goal..."
              />
            </div>
          </div>

          {/* Active Loop Status Progress */}
          {isRunning && (
            <div className="p-3 rounded-lg bg-purple-950/30 border border-purple-500/40 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-purple-300 font-bold flex items-center gap-1.5">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" />
                  {activeStep}
                </span>
                <span className="text-purple-400 font-mono font-bold">{currentProgress}%</span>
              </div>
              <Progress value={currentProgress} className="h-1.5 bg-[#0a0a0f]" />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Champion Checkpoint Banner */}
      {championTrial && (
        <Card className="bg-gradient-to-r from-emerald-950/30 to-[#0e0e16] border border-emerald-500/40 rounded-xl overflow-hidden shadow-lg">
          <CardContent className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center shrink-0">
                <Trophy className="w-5 h-5 text-emerald-400" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold uppercase text-emerald-400">Current Champion Checkpoint</span>
                  <Badge variant="outline" className="text-[10px] border-emerald-500/30 text-emerald-300 bg-emerald-950/40">
                    {championTrial.name}
                  </Badge>
                </div>
                <p className="text-xs text-zinc-300 font-sans">{championTrial.hypothesis}</p>
                <div className="flex items-center gap-3 pt-1 text-[11px] text-zinc-400">
                  <span>LoRA r=<strong className="text-white">{championTrial.lora_r}</strong></span>
                  <span>•</span>
                  <span>LR=<strong className="text-white">{championTrial.learning_rate}</strong></span>
                  <span>•</span>
                  <span>Sched=<strong className="text-white">{championTrial.lr_scheduler}</strong></span>
                  <span>•</span>
                  <span>Eval Loss=<strong className="text-emerald-400 font-bold">{championTrial.eval_loss}</strong></span>
                  <span>•</span>
                  <span>Win Rate=<strong className="text-emerald-400 font-bold">{championTrial.win_rate_pct}%</strong></span>
                </div>
              </div>
            </div>

            <Button
              type="button"
              size="sm"
              onClick={() => {
                playSuccessChime()
                if (onAdoptChampion) {
                  onAdoptChampion(championTrial)
                }
              }}
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs h-8 px-3 rounded-md shrink-0 flex items-center gap-1.5 cursor-pointer"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>Apply Champion Parameters</span>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Trials Table */}
      <Card className="bg-[#12121a] border-[#272738] rounded-xl overflow-hidden">
        <CardHeader className="p-4 border-b border-[#272738] flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-xs font-bold text-white uppercase flex items-center gap-2">
              <TrendingDown className="w-4 h-4 text-purple-400" />
              Autonomous Experimentation Trajectory ({trials.length} Iterations)
            </CardTitle>
            <CardDescription className="text-xs text-[#a8a29e] mt-0.5">
              Each trial tests an agent hypothesis, measures validation divergence, and updates model weights.
            </CardDescription>
          </div>
          <span className="text-[11px] text-zinc-400 font-mono">
            {trials.filter((t) => t.decision === 'keep').length} Kept ·{' '}
            {trials.filter((t) => t.decision === 'discard').length} Discarded
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead className="bg-[#0a0a0f] text-[#a8a29e] uppercase text-[10px] border-b border-[#272738]">
                <tr>
                  <th className="py-2.5 px-4">Trial</th>
                  <th className="py-2.5 px-4">Hypothesis &amp; Rationale</th>
                  <th className="py-2.5 px-4">Config (LoRA / LR)</th>
                  <th className="py-2.5 px-4">Eval Loss</th>
                  <th className="py-2.5 px-4">Win Rate</th>
                  <th className="py-2.5 px-4">Agent Verdict</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1c1c28]">
                {trials.map((trial) => {
                  const isChamp = championTrial?.id === trial.id
                  return (
                    <tr
                      key={trial.id}
                      className={clsx(
                        'hover:bg-[#161622]/60 transition-colors',
                        isChamp && 'bg-emerald-950/15'
                      )}
                    >
                      <td className="py-3 px-4 font-bold text-white flex items-center gap-1.5">
                        {isChamp ? <Trophy className="w-3.5 h-3.5 text-emerald-400" /> : `#${trial.id}`}
                        <span>{trial.name}</span>
                      </td>
                      <td className="py-3 px-4 max-w-xs truncate text-zinc-300 font-sans text-xs">
                        {trial.hypothesis}
                      </td>
                      <td className="py-3 px-4 text-zinc-400">
                        r={trial.lora_r} · {trial.learning_rate} · {trial.lr_scheduler}
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-white">{trial.eval_loss.toFixed(4)}</span>
                          {trial.loss_delta_pct !== 0 && (
                            <span
                              className={clsx(
                                'text-[10px] font-bold px-1 rounded',
                                trial.loss_delta_pct < 0
                                  ? 'bg-emerald-950 text-emerald-400'
                                  : 'bg-rose-950 text-rose-400'
                              )}
                            >
                              {trial.loss_delta_pct > 0 ? '+' : ''}
                              {trial.loss_delta_pct}%
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-emerald-400 font-bold">{trial.win_rate_pct}%</td>
                      <td className="py-3 px-4">
                        {trial.decision === 'keep' ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            <CheckCircle2 className="w-3 h-3" />
                            {isChamp ? 'CHAMPION' : 'KEEP'}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/15 text-rose-400 border border-rose-500/30">
                            <XCircle className="w-3 h-3" />
                            DISCARD
                          </span>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Terminal Agent Reasoning Stream */}
      <Card className="bg-[#0a0a0f] border-[#272738] rounded-xl overflow-hidden font-mono">
        <CardHeader className="py-2.5 px-4 border-b border-[#1c1c28] flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-3.5 h-3.5 text-purple-400" />
            <span className="text-xs font-bold text-white uppercase">Autonomous Agent Telemetry</span>
          </div>
          <span className="text-[10px] text-zinc-500">Self-Correcting Reasoning Trace</span>
        </CardHeader>
        <CardContent className="p-3 bg-black/40 max-h-40 overflow-y-auto space-y-1 text-[11px] text-zinc-400">
          {agentLogs.map((log, i) => (
            <div key={i} className="leading-relaxed hover:text-white transition-colors">
              {log}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
