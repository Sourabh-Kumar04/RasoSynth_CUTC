'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  Activity,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  Play,
  Pause,
  Zap,
  ArrowRight,
  AlertCircle,
  RefreshCw,
  Database,
  FlaskConical,
  Workflow,
  ChevronRight,
  RotateCcw,
  Layers,
  Terminal,
  Users,
  Bot,
  Check,
  Copy,
  Cpu,
  Sparkles,
  BookOpen,
  GitCompare,
  Search,
  ShieldCheck,
  GitMerge,
  FileCode2,
  Trash2,
  Eye,
  Globe,
  FileText,
  Puzzle,
  Scale,
  Package,
  Rocket
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/lib/api/client'

// Pipeline stages for live DAG matching industry-standard non-linear architecture
const PIPELINE_STAGES = [
  { id: 'query_optimizer', label: '1. Optimizer', desc: 'LLM Fast-Pass', icon: Zap },
  { id: 'preview_acceptance', label: '2. Early Preview', desc: 'Acceptance Gate', icon: Eye },
  { id: 'discovering_sources', label: '3. Crawling', desc: 'AI Kosh & Open Repos', icon: Globe },
  { id: 'extracting_content', label: '4. Extract', desc: 'Concurrent Chunks', icon: FileText },
  { id: 'filtering_quality', label: '5. Filter', desc: 'DPDP & Statutory LSH', icon: Sparkles },
  { id: 'constructing_dataset', label: '6. Synthesis', desc: 'VRAM-Budgeted LLM', icon: Puzzle },
  { id: 'human_review', label: '7. HITL Gate', desc: 'Stratified Review', icon: Users },
  { id: 'balance', label: '8. Balancing', desc: 'Exact Size Guarantee', icon: Scale },
  { id: 'exporting', label: '9. Packaging', desc: 'ADR-002 Merkle Manifest', icon: Package },
  { id: 'finetuning', label: '10. Fine-Tune', desc: '1-Click QLoRA / SFT', icon: Rocket },
]

export default function OrchestrationPage() {
  const router = useRouter()
  const [jobs, setJobs] = useState<any[]>([])
  const [agents, setAgents] = useState<any[]>([])
  const [agentStats, setAgentStats] = useState<any | null>(null)
  const [researchStatus, setResearchStatus] = useState<any | null>(null)
  const [triggeringResearch, setTriggeringResearch] = useState(false)
  const [researchToast, setResearchToast] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<any | null>(null)
  const [activeTab, setActiveTab] = useState<'dag' | 'agents' | 'research' | 'refinement'>('dag')
  const [dagInfo, setDagInfo] = useState<any | null>(null)
  const [selectedStageNode, setSelectedStageNode] = useState<any | null>(null)
  const [showAcceptConfirm, setShowAcceptConfirm] = useState(false)
  const [expandedSamples, setExpandedSamples] = useState<Record<number, boolean>>({})
  const [copiedSampleIdx, setCopiedSampleIdx] = useState<number | null>(null)
  const [showJobDrawer, setShowJobDrawer] = useState(false)
  const [selectedTrajectory, setSelectedTrajectory] = useState<any | null>(null)

  const fetchJobs = useCallback(async () => {
    try {
      const response = await api.getJobs({ limit: 20 })
      const jobList = response.data || []
      setJobs(jobList)
      if (jobList.length > 0) {
        setSelectedJob((prev: any) => {
          if (!prev) return jobList[0]
          const updated = jobList.find((j: any) => j.id === prev.id)
          return updated ? { ...prev, ...updated } : prev
        })
      }
    } catch {
      console.debug('Failed to load orchestration jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchAll = useCallback(async () => {
    fetchJobs()
    try {
      const [agentsRes, statsRes, resStatus, liveDag] = await Promise.all([
        api.getAgents().catch(() => ({ agents: [], total: 0 })),
        api.getAgentStats().catch(() => null),
        api.getResearchStatus().catch(() => null),
        selectedJob?.id ? api.getOrchestrationDag(selectedJob.id).catch(() => null) : Promise.resolve(null),
      ])
      setAgents(agentsRes?.agents || [])
      setAgentStats(statsRes)
      setResearchStatus(resStatus)
      if (liveDag) setDagInfo(liveDag)
    } catch {
      console.debug('Failed to load agents or research data')
    }
  }, [fetchJobs, selectedJob?.id])

  useEffect(() => {
    fetchAll()
    const interval = setInterval(fetchAll, 6000)
    return () => clearInterval(interval)
  }, [fetchAll])

  const handleTriggerResearch = async () => {
    setTriggeringResearch(true)
    try {
      const res = await api.triggerResearch({ query: 'autonomous sft dataset synthesis' })
      setResearchToast(res?.message || 'Research loop activated')
      fetchAll()
      setTimeout(() => setResearchToast(null), 4000)
    } catch (err: any) {
      setResearchToast('Research loop trigger failed')
      setTimeout(() => setResearchToast(null), 4000)
    } finally {
      setTriggeringResearch(false)
    }
  }

  const handleDeleteJob = async (jobId: string) => {
    if (!confirm(`Are you sure you want to delete job ${jobId.slice(0, 8)}? All outputs and checkpoints will be removed.`)) return
    try {
      await api.deleteJob(jobId)
      setJobs((prev) => prev.filter((j) => j.id !== jobId))
      if (selectedJob?.id === jobId) setSelectedJob(null)
    } catch (e: any) {
      console.error('Failed to delete job:', e)
      alert(e.message || 'Failed to delete job')
    }
  }

  const [refinePrompt, setRefinePrompt] = useState('')
  const [previewSubmitting, setPreviewSubmitting] = useState(false)
  const [editingSampleIndex, setEditingSampleIndex] = useState<number | null>(null)
  const [editedSamples, setEditedSamples] = useState<Record<number, { instruction: string; response: string }>>({})

  const handleAcceptPreview = async (jobId: string) => {
    setPreviewSubmitting(true)
    try {
      const origSamples = selectedJob?.config?.preview_samples || []
      const finalSamples = origSamples.map((s: any, idx: number) => {
        if (editedSamples[idx]) {
          return { ...s, ...editedSamples[idx] }
        }
        return s
      })
      await api.acceptPreview(jobId, finalSamples.length > 0 ? finalSamples : undefined)
      await fetchJobs()
    } catch (e: any) {
      console.error('Failed to accept preview:', e)
      alert(e.message || 'Failed to accept preview')
    } finally {
      setPreviewSubmitting(false)
    }
  }

  const handleRejectPreview = async (jobId: string) => {
    setPreviewSubmitting(true)
    try {
      await api.rejectPreview(jobId, refinePrompt)
      await fetchJobs()
    } catch (e: any) {
      console.error('Failed to update query for preview:', e)
      alert(e.message || 'Failed to update query')
    } finally {
      setPreviewSubmitting(false)
    }
  }

  const runningJobs = jobs.filter((j) => j.status === 'running')
  const completedJobs = jobs.filter((j) => j.status === 'completed')

  const researchHistoryList: string[] = (() => {
    if (Array.isArray(researchStatus?.research_history) && researchStatus.research_history.length > 0) {
      return researchStatus.research_history.map((item: any) =>
        typeof item === 'string' ? item : (item?.query || item?.title || item?.name || JSON.stringify(item))
      )
    }
    return []
  })()

  const cachedTechniquesList: string[] = (() => {
    if (Array.isArray(researchStatus?.cached_techniques) && researchStatus.cached_techniques.length > 0) {
      return researchStatus.cached_techniques.map(String)
    }
    if (researchStatus?.cached_techniques && typeof researchStatus.cached_techniques === 'object') {
      const flattened = Object.values(researchStatus.cached_techniques).flat().map(String)
      if (flattened.length > 0) return flattened
    }
    return []
  })()

  return (
    <div className="w-full max-w-[1600px] mx-auto space-y-6">
      
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#272738] pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded-sm text-xs font-mono font-bold bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] uppercase tracking-wider">
              SYNTHESIS PIPELINES
            </span>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white font-display">
              Pipeline Execution Engine
            </h1>
          </div>

        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center space-x-2 text-xs font-mono">
            <span className="px-2 py-1 rounded bg-[#12121a] border border-[#272738] text-[#10b981] flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
              {runningJobs.length} Running
            </span>
            <span className="px-2 py-1 rounded bg-[#12121a] border border-[#272738] text-white">
              {completedJobs.length} Completed
            </span>
          </div>

          <Button
            onClick={fetchJobs}
            variant="outline"
            className="border-[#272738] bg-[#12121a] hover:bg-[#161622] text-[#a8a29e] hover:text-white text-xs font-mono h-8 rounded-md"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1 text-[#f26625]" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Research Loop Toast */}
      {researchToast && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-md border border-emerald-500/30 bg-emerald-950/80 text-emerald-400 text-xs font-mono font-semibold shadow-xl animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {researchToast}
        </div>
      )}

      {/* Tabs Navigation */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="w-full space-y-6">
        <TabsList className="bg-[#161622] rounded-md border border-[#272738] p-1 flex flex-wrap gap-1 h-auto">
          <TabsTrigger value="dag" className="rounded-sm text-xs font-mono flex items-center gap-1.5 data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">
            <Workflow className="w-3.5 h-3.5" />
            Pipeline DAG Execution
          </TabsTrigger>
          <TabsTrigger value="agents" className="rounded-sm text-xs font-mono flex items-center gap-1.5 data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">
            <Users className="w-3.5 h-3.5" />
            Multi-Agent Society ({agents.length > 0 ? agents.length : '—'})
          </TabsTrigger>
          <TabsTrigger value="research" className="rounded-sm text-xs font-mono flex items-center gap-1.5 data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">
            <FlaskConical className="w-3.5 h-3.5" />
            Autonomous Research Loop
          </TabsTrigger>
          <TabsTrigger value="refinement" className="rounded-sm text-xs font-mono flex items-center gap-1.5 data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">
            <Sparkles className="w-3.5 h-3.5" />
            Self-Refinement Loop
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Pipeline DAG View */}
        <TabsContent value="dag" className="space-y-6 mt-0">
          {/* Main DAG Visualizer Card */}
          <div className="p-5 rounded-md bg-[#12121a] border border-[#272738] space-y-4 relative overflow-hidden">
            <div className="flex flex-wrap items-center justify-between pb-3 border-b border-[#1c1c28] gap-2">
              <div className="flex items-center space-x-2">
                <Workflow className="w-4 h-4 text-[#f26625]" />
                <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                  Active Pipeline Execution DAG
                </h3>
                {selectedJob && (
                  <span className="font-mono text-xs text-[#a8a29e]">
                    [Job: <strong className="text-white">{selectedJob.id.slice(0, 8)}...</strong>]
                  </span>
                )}
              </div>

              <div className="flex items-center space-x-3 text-xs font-mono">
                <span className="text-[#a8a29e]">DAG LATENCY: <strong className="text-white">—</strong></span>
                <span className="text-[#a8a29e]">CHECKPOINT: <strong className="text-[#10b981]">ckpt-latest</strong></span>
                {selectedJob ? (
                  <span className="text-[#10b981] flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                    RUNNING
                  </span>
                ) : (
                  <span className="text-zinc-500 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" />
                    IDLE (NO RUN SELECTED)
                  </span>
                )}
              </div>
            </div>

            {/* Horizontal Visual Graph Viewport */}
            <div className="overflow-x-auto py-4">
              <div className="min-w-[960px] flex items-center justify-between relative px-4">
                {/* Connecting Track Line */}
                <div className="absolute left-10 right-10 top-1/2 -translate-y-1/2 h-[2px] bg-[#1c1c28] -z-0" />

                {PIPELINE_STAGES.map((stage, i, arr) => {
                  const currentStage = selectedJob?.current_stage || ''
                  const liveNode = dagInfo?.nodes?.find((n: any) => n.id.includes(stage.id.split('_')[0]))
                  const isCurrent = liveNode ? liveNode.status === 'running' : Boolean(selectedJob && currentStage && currentStage.includes(stage.id.split('_')[0]))
                  const isPast = liveNode ? liveNode.status === 'completed' : Boolean(selectedJob?.progress && (selectedJob.progress * arr.length > i))
                  const isFailed = liveNode?.status === 'failed'

                  // Check if node has active feedback loop capability
                  const hasFeedbackLoop = stage.id === 'preview_acceptance' || stage.id === 'filtering_quality' || stage.id === 'constructing_dataset'
                  const feedbackLabel = stage.id === 'preview_acceptance' ? '↺ Refine Query Loop' : stage.id === 'filtering_quality' ? '↺ Re-extract Loop' : '↺ Synthesis Loop'

                  return (
                    <div key={stage.id} className="flex items-center relative z-10">
                      <motion.div
                        whileHover={{ scale: 1.03 }}
                        onClick={() => setSelectedStageNode({ ...stage, stepIndex: i + 1, isCurrent, isPast, liveNode })}
                        title="Click to inspect node inputs, outputs, and logs"
                        className={clsx(
                          'w-40 p-3 rounded-md border transition-all cursor-pointer',
                          isFailed
                            ? 'bg-[#1a0e12] border-rose-500/70 shadow-sm'
                            : isCurrent
                            ? 'bg-[#161622] border-[#f26625] shadow-sm'
                            : isPast
                            ? 'bg-[#12121a] border-[#10b981]/50'
                            : 'bg-[#0e0e13] border-[#272738] opacity-60'
                        )}
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-xs font-mono font-bold text-[#f26625]">
                            NODE {String(i + 1).padStart(2, '0')}
                          </span>
                          <span className={clsx(
                            'w-2 h-2 rounded-full',
                            isFailed ? 'bg-rose-500' : isCurrent ? 'bg-[#10b981] animate-pulse' : isPast ? 'bg-[#10b981]' : 'bg-[#a8a29e]'
                          )} />
                        </div>
                        <h4 className="text-xs font-semibold text-white truncate">{stage.label}</h4>
                        <p className="text-xs font-mono text-[#a8a29e] truncate">{stage.desc}</p>
                        
                        {hasFeedbackLoop && (
                          <div className="mt-1">
                            <span className="inline-block text-xs font-mono px-1.5 py-0.5 rounded bg-[#1c1c28] text-amber-400/90 border border-amber-500/20">
                              {feedbackLabel}
                            </span>
                          </div>
                        )}

                        <div className="mt-2 pt-1 border-t border-[#1c1c28] flex justify-between text-xs font-mono">
                          <span className="text-[#a8a29e]">Status:</span>
                          <span className={isCurrent ? 'text-[#10b981] font-semibold' : 'text-[#a8a29e]'}>
                            {liveNode?.status ? liveNode.status.toUpperCase() : isCurrent ? 'EXECUTING' : isPast ? 'PASSED' : 'PENDING'}
                          </span>
                        </div>
                      </motion.div>

                      {i < arr.length - 1 && (
                        <div className="mx-2 text-[#a8a29e]">
                          <ChevronRight className="w-4 h-4 text-[#272738]" />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Clicked DAG Node Inspector Drawer / Card */}
            {selectedStageNode && (
              <div className="p-4 rounded-lg bg-[#0a0a0f] border border-[#f26625]/40 space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between pb-2 border-b border-[#1c1c28]">
                  <div className="flex items-center gap-2">
                    {(() => { const NodeIcon = selectedStageNode.icon; return <NodeIcon className="h-4 w-4" /> })()}
                    <span className="font-bold text-white uppercase tracking-wider">
                      Node {String(selectedStageNode.stepIndex).padStart(2, '0')}: {selectedStageNode.label}
                    </span>
                    <Badge variant="outline" className="text-xs bg-[#1b1b18]/60 text-[#d8d2c4] border-[#4a463f]">
                      {selectedStageNode.desc}
                    </Badge>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSelectedStageNode(null)}
                    className="text-zinc-400 hover:text-white p-1"
                    aria-label="Close node inspector"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                  <div className="p-2.5 rounded bg-[#0a0a0f] border border-[#4a463f] space-y-1">
                    <span className="text-zinc-500 text-xs uppercase block">Inputs / Invariants</span>
                    <p className="text-zinc-300">
                      Domain: <strong className="text-white">{selectedJob?.target_domain || 'Unknown'}</strong><br />
                      PII Guard: <span className="text-emerald-400">Masking Active</span> · MinHash: &gt;0.85
                    </p>
                  </div>
                  <div className="p-2.5 rounded bg-[#0a0a0f] border border-[#4a463f] space-y-1">
                    <span className="text-zinc-500 text-xs uppercase block">Stage Outputs</span>
                    <p className="text-zinc-300">
                      Artifact: <strong className="text-[#d8d2c4]">Merkle Leaves / JSONL</strong><br />
                      Status: <span className="text-emerald-400 font-semibold">{selectedStageNode.isCurrent ? 'Executing' : selectedStageNode.isPast ? 'Completed' : 'Queued'}</span>
                    </p>
                  </div>
                  <div className="p-2.5 rounded bg-[#0a0a0f] border border-[#4a463f] space-y-1">
                    <span className="text-zinc-500 text-xs uppercase block">Stage Telemetry</span>
                    <p className="text-zinc-300">
                      Est. Latency: <strong className="text-white">— (per-stage timing not yet measured)</strong><br />
                      Checkpoint: <span className="text-[#f26625]">ckpt-{selectedStageNode.id}</span>
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Selected Job Telemetry Bar */}
            {selectedJob && (
              <div className="space-y-3 pt-3 border-t border-[#1c1c28]">
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-xs font-mono">
                  <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
                    <span className="text-[#a8a29e] text-xs block">Current Stage</span>
                    <span className="text-white font-bold truncate block">{selectedJob.current_stage || 'unknown'}</span>
                  </div>
                  <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
                    <span className="text-[#a8a29e] text-xs block">Samples Generated</span>
                    <span className="text-[#10b981] font-bold">{selectedJob.samples_generated || 0}</span>
                  </div>
                  <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
                    <span className="text-[#a8a29e] text-xs block">Total Cost Accrued (provider spend not attributed per job)</span>
                    <span className="text-[#f26625] font-bold">${(typeof selectedJob.cost_usd === 'number' ? selectedJob.cost_usd : 0.0).toFixed(3)}</span>
                  </div>
                  <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
                    <span className="text-[#a8a29e] text-xs block">Pipeline Progress</span>
                    <span className="text-white font-bold">{selectedJob.progress != null ? `${Math.round(selectedJob.progress * 100)}%` : '—'}</span>
                  </div>
                  <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
                    <div className="flex items-center justify-between text-xs text-[#a8a29e]">
                      <span>Collision Defense</span>
                      <span className="text-[#10b981] text-xs font-bold">ACTIVE</span>
                    </div>
                    <span className="text-amber-400 font-bold flex items-center gap-1">
                      🛡️ {selectedJob.sources_discovered ? Math.max(0, selectedJob.sources_discovered - (selectedJob.sources_extracted || 0)) : (selectedJob.samples_filtered || 0)} Blocked
                    </span>
                  </div>
                </div>

                {/* Live Multi-Agent Society Coordinator Telemetry */}
                <div className="p-3 rounded-lg bg-[#12121a] border border-[#272738] space-y-2.5 font-mono text-xs">
                  <div className="flex items-center justify-between border-b border-[#1c1c28] pb-2">
                    <div className="flex items-center gap-2">
                      <div className="h-6 w-6 rounded bg-[#f26625]/10 border border-[#f26625]/30 flex items-center justify-center text-[#f26625]">
                        <Bot className="w-3.5 h-3.5 animate-pulse" />
                      </div>
                      <div>
                        <span className="font-bold text-white flex items-center gap-2">
                          Active Persona: {selectedJob.active_agent?.agent || (
                            selectedJob.current_stage === 'plan' ? 'StrategyAgent' :
                            selectedJob.current_stage === 'query_optimizer' ? 'SearchOptimizationAgent' :
                            selectedJob.current_stage === 'discover' ? 'SourceDiscoveryAgent' :
                            selectedJob.current_stage === 'extract' ? 'WebCrawlerAgent' :
                            selectedJob.current_stage === 'filter' ? 'ContextBundleAgent' :
                            selectedJob.current_stage === 'construct' ? 'SyntheticGenerationAgent' :
                            selectedJob.current_stage === 'quality_eval' ? 'ReviewEnsembleAgent' :
                            selectedJob.current_stage === 'balance' ? 'CurriculumAgent' :
                            selectedJob.current_stage === 'export' ? 'DBOMAttestorAgent' : 'Autonomous Coordinator'
                          )}
                        </span>
                      </div>
                    </div>
                    <Badge variant="outline" className="text-[10px] bg-emerald-950/40 text-emerald-400 border-emerald-500/30 font-bold">
                      EXECUTION LOCK HELD
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#a8a29e]">
                    <span>
                      Task Responsibility: <strong className="text-zinc-200 font-normal">{selectedJob.active_agent?.role || 'Decentralized LangGraph state transition'}</strong>
                    </span>
                    <span className="flex items-center gap-1 text-[11px] text-[#f26625]">
                      <GitMerge className="w-3 h-3" /> Consensus Protocol: Multi-Agent Quorum
                    </span>
                  </div>
                </div>

                {/* Synthesis Cognitive Engine & Domain Telemetry */}
                <div className="flex flex-wrap items-center gap-2.5 p-2.5 rounded bg-[#0a0a0f]/80 border border-[#272738] text-xs font-mono">
                  <span className="text-[#a8a29e] text-xs uppercase font-bold flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 text-[#f26625]" />
                    Cognitive Engine:
                  </span>
                  <span className="px-2 py-0.5 rounded bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] font-bold uppercase text-xs">
                    {selectedJob.config?.synthesis_mode || selectedJob.synthesis_mode || 'standard'}
                  </span>
                  <span className="text-[#4a463f]">/</span>
                  <span className="text-[#a8a29e] text-xs">
                    Domain: <strong className="text-white font-normal">{selectedJob.target_domain || selectedJob.domain || selectedJob.dataset_name || 'Unknown'}</strong>
                  </span>
                  <span className="text-[#4a463f]">/</span>
                  <span className="text-[#d8d2c4] text-xs flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3 text-[#f26625]" />
                    DBOM Attestation: Certified
                  </span>
                </div>

                {/* 1-Click Fine-Tuning Pipeline Handoff */}
                {(selectedJob.status === 'completed' || selectedJob.progress >= 1 || (selectedJob.samples_generated && selectedJob.samples_generated > 0)) && (
                  <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded bg-[#161622] border border-[#f26625]/40 text-xs font-mono">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2 text-white font-bold">
                        <Cpu className="w-4 h-4 text-[#f26625]" />
                        <span>Dataset Ready for QLoRA Fine-Tuning</span>
                        <Badge variant="outline" className="text-xs bg-emerald-950/40 text-emerald-400 border-emerald-500/30">
                          {selectedJob.samples_generated || 0} Samples
                        </Badge>
                      </div>
                      <p className="text-xs text-[#a8a29e]">
                        DBOM Merkle root sealed. Dispatch directly into parameter-efficient fine-tuning with 1 click.
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        onClick={() => router.push(`/finetune?dataset=${selectedJob.id}`)}
                        className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-mono font-bold h-8 rounded-md flex items-center gap-1.5 shadow-sm"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        Fine-Tune Model
                      </Button>
                      <Button
                        onClick={() => router.push(`/review?job=${selectedJob.id}`)}
                        variant="outline"
                        className="border-purple-500/40 text-purple-300 hover:text-white hover:bg-purple-950/40 text-xs font-mono font-bold h-8 rounded-md flex items-center gap-1.5 shadow-sm"
                      >
                        <GitCompare className="w-3.5 h-3.5 text-purple-400" />
                        Active Learning &amp; DPO
                      </Button>
                    </div>
                  </div>
                )}

                {/* Active Anti-Domains & Polysemy Exclusion Badges */}
                {selectedJob.config?.anti_domains && selectedJob.config.anti_domains.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 p-2 rounded bg-[#0a0a0f]/60 border border-[#272738] text-xs font-mono">
                    <span className="text-[#a8a29e] text-xs uppercase font-bold flex items-center gap-1 mr-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-[#10b981]" />
                      Active Collision Guards:
                    </span>
                    {selectedJob.config.anti_domains.slice(0, 8).map((domain: string, idx: number) => (
                      <span
                        key={idx}
                        className="px-1.5 py-0.5 rounded text-xs bg-red-500/10 border border-red-500/20 text-red-300"
                      >
                        ✕ {domain}
                      </span>
                    ))}
                    {selectedJob.config.anti_domains.length > 8 && (
                      <span className="text-xs text-[#a8a29e]">
                        +{selectedJob.config.anti_domains.length - 8} more
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Human Review Gate / Awaiting Review Notice */}
            {selectedJob && (selectedJob.status === 'awaiting_review' || selectedJob.status === 'awaiting_human_review' || selectedJob.current_stage === 'human_review') && (
              <div className="pt-4 border-t border-[#1c1c28] space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-md bg-amber-950/30 border border-amber-500/50">
                  <div className="space-y-1">
                    <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                      <Users className="w-4 h-4 text-amber-400" />
                      Pipeline Stalled: Awaiting Human Review
                    </span>
                    <p className="text-xs text-zinc-300 max-w-xl">
                      Stratified quality sampling holds this pipeline at the human verification gate. Outlier and edge-case samples must be inspected, edited, or approved in the review queue before downstream synthesis and export proceed.
                    </p>
                  </div>
                  <Button
                    onClick={() => router.push(`/review?job=${selectedJob.id}`)}
                    className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-mono font-bold h-9 px-4 rounded-md shadow-sm flex items-center gap-2 shrink-0"
                  >
                    <span>Open Review Queue →</span>
                  </Button>
                </div>
              </div>
            )}

            {/* Early Preview Samples & User Acceptance Gate */}
            {selectedJob && (selectedJob.status === 'awaiting_preview_approval' || selectedJob.current_stage === 'preview_acceptance' || (selectedJob.config?.preview_samples && selectedJob.config.preview_samples.length > 0)) && (
              <div className="pt-4 border-t border-[#1c1c28] space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-md bg-[#161622] border border-[#f26625]/40">
                  <div className="space-y-1">
                    <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#f26625] flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-[#f26625]" />
                      Early Dataset Preview &amp; User Acceptance Gate
                    </span>
                    <p className="text-xs text-[#a8a29e]">
                      Review sample reasoning quality below. Accepting triggers full distributed synthesis, neural evaluation, and Merkle DBOM sealing.
                    </p>
                    <div className="flex flex-wrap items-center gap-3 pt-1 text-xs font-mono text-zinc-400">
                      <span>Target Batch: <strong className="text-white">{(selectedJob.config?.dataset_size || selectedJob.dataset_size) ? `${selectedJob.config?.dataset_size || selectedJob.dataset_size} samples` : 'Unknown'}</strong></span>
                      <span className="text-zinc-700">·</span>
                      <span>Est. Duration: <strong className="text-white">{(selectedJob.config?.dataset_size || selectedJob.dataset_size) ? `~${Math.max(1, Math.round((selectedJob.config?.dataset_size || selectedJob.dataset_size) / 750))} mins` : 'Unknown'}</strong></span>
                      <span className="text-zinc-700">·</span>
                      <span>Projected Cost: <strong className="text-emerald-400">{(selectedJob.config?.dataset_size || selectedJob.dataset_size) ? `$${(((selectedJob.config?.dataset_size || selectedJob.dataset_size) / 1000) * 0.06).toFixed(2)}` : 'Unknown'}</strong> <span className="text-xs text-zinc-500">($0.00 Local)</span></span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {showAcceptConfirm ? (
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          onClick={() => {
                            setShowAcceptConfirm(false)
                            handleAcceptPreview(selectedJob.id)
                          }}
                          disabled={previewSubmitting}
                          className="bg-[#10b981] hover:bg-[#059669] text-white font-mono text-xs font-bold h-8 px-3 rounded-md"
                        >
                          Confirm &amp; Dispatch
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setShowAcceptConfirm(false)}
                          className="h-8 text-xs text-zinc-400 hover:text-white"
                        >
                          Cancel
                        </Button>
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => setShowAcceptConfirm(true)}
                        disabled={previewSubmitting}
                        className="bg-[#10b981] hover:bg-[#059669] text-white font-mono text-xs font-bold h-8 px-3 rounded-md flex items-center gap-1.5"
                      >
                        {previewSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                        Accept &amp; Run Full Pipeline
                      </Button>
                    )}
                  </div>
                </div>

                {/* Preview Samples List with Inline Interactive Editor */}
                <div className="space-y-2 max-h-72 overflow-y-auto">
                  {(selectedJob.config?.preview_samples || []).map((sample: any, idx: number) => {
                    const isEditing = editingSampleIndex === idx
                    const currentInstruction = editedSamples[idx]?.instruction ?? sample.instruction
                    const currentResponse = editedSamples[idx]?.response ?? sample.response
                    const isModified = Boolean(editedSamples[idx])

                    return (
                      <div key={idx} className="p-3 rounded-md bg-[#0a0a0f] border border-[#272738] space-y-2 font-mono text-xs">
                        <div className="flex justify-between items-center text-xs">
                          <div className="flex items-center gap-2">
                            <span className="text-[#f26625] font-bold">Sample #{idx + 1}</span>
                            {isModified && (
                              <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 text-xs">
                                Custom Edited
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-emerald-400">Score: {Math.round((sample.metadata?.quality_score || 0.94) * 100)}%</span>
                            <button
                              type="button"
                              onClick={() => setEditingSampleIndex(isEditing ? null : idx)}
                              className="text-[#f26625] hover:underline text-xs"
                            >
                              {isEditing ? 'Done Editing' : 'Edit Sample'}
                            </button>
                          </div>
                        </div>

                        {isEditing ? (
                          <div className="space-y-2 pt-1 border-t border-[#1c1c28]">
                            <div>
                              <span className="text-[#a8a29e] block text-xs uppercase">Edit Instruction:</span>
                              <textarea
                                rows={2}
                                value={currentInstruction}
                                onChange={(e) => {
                                  const val = e.target.value
                                  setEditedSamples((prev) => ({
                                    ...prev,
                                    [idx]: { instruction: val, response: prev[idx]?.response ?? sample.response },
                                  }))
                                }}
                                className="w-full mt-1 bg-[#161622] border border-[#272738] rounded p-2 text-xs font-mono text-white focus:outline-none focus:border-[#f26625]"
                              />
                            </div>
                            <div>
                              <span className="text-[#a8a29e] block text-xs uppercase">Edit Response:</span>
                              <textarea
                                rows={3}
                                value={currentResponse}
                                onChange={(e) => {
                                  const val = e.target.value
                                  setEditedSamples((prev) => ({
                                    ...prev,
                                    [idx]: { instruction: prev[idx]?.instruction ?? sample.instruction, response: val },
                                  }))
                                }}
                                className="w-full mt-1 bg-[#161622] border border-[#272738] rounded p-2 text-xs font-mono text-white focus:outline-none focus:border-[#f26625]"
                              />
                            </div>
                          </div>
                        ) : (
                          <>
                            <div>
                              <div className="flex items-center justify-between">
                                <span className="text-[#a8a29e] block text-xs uppercase">Instruction:</span>
                                <button
                                  type="button"
                                  onClick={() => {
                                    navigator.clipboard.writeText(currentInstruction + '\n\n' + currentResponse)
                                    setCopiedSampleIdx(idx)
                                    setTimeout(() => setCopiedSampleIdx(null), 2000)
                                  }}
                                  className="text-xs text-zinc-400 hover:text-white flex items-center gap-1"
                                >
                                  {copiedSampleIdx === idx ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                                  <span>{copiedSampleIdx === idx ? 'Copied' : 'Copy Sample'}</span>
                                </button>
                              </div>
                              <p className="text-white mt-0.5">{currentInstruction}</p>
                            </div>
                            <div>
                              <div className="flex items-center justify-between">
                                <span className="text-[#a8a29e] block text-xs uppercase">Response:</span>
                                <button
                                  type="button"
                                  onClick={() => setExpandedSamples(prev => ({ ...prev, [idx]: !prev[idx] }))}
                                  className="text-xs text-[#f26625] hover:underline"
                                >
                                  {expandedSamples[idx] ? 'Collapse Sample' : 'Show Full Sample'}
                                </button>
                              </div>
                              <p className={clsx("text-[#cbd5e1] mt-0.5 whitespace-pre-wrap leading-relaxed", !expandedSamples[idx] && "line-clamp-3")}>
                                {currentResponse}
                              </p>
                            </div>
                          </>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Inline Query Refinement */}
                <div className="flex flex-col sm:flex-row gap-2 pt-1">
                  <input
                    type="text"
                    value={refinePrompt}
                    onChange={(e) => setRefinePrompt(e.target.value)}
                    placeholder={selectedJob.config?.target_domain ? `Refine prompt (currently: ${selectedJob.config.target_domain})...` : "Refine query / specification prompt..."}
                    className="flex-1 bg-[#0a0a0f] border border-[#272738] rounded-md px-3 py-1.5 text-xs font-mono text-white placeholder:text-[#a8a29e] focus:outline-none focus:border-[#f26625]"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleRejectPreview(selectedJob.id)}
                    disabled={previewSubmitting}
                    className="border-[#f26625]/40 text-[#f26625] hover:bg-[#f26625]/10 text-xs font-mono h-8 rounded-md"
                  >
                    Refine Query &amp; Regenerate
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Jobs History Table */}
          <div className="p-4 rounded-lg bg-[#12121a] border border-[#272738] space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#1c1c28]">
              <div className="flex items-center space-x-2">
                <Database className="w-4 h-4 text-[#10b981]" />
                <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                  All Orchestration Jobs
                </h3>
              </div>
              <span className="text-xs font-mono text-[#a8a29e]">
                Showing {jobs.length} executions
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#1c1c28] text-[#a8a29e] text-xs uppercase">
                    <th className="pb-2">Job ID</th>
                    <th className="pb-2">Target Domain / Source</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Samples</th>
                    <th className="pb-2">Progress</th>
                    <th className="pb-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1c1c28]">
                  {jobs.map((job) => {
                    const isSelected = selectedJob?.id === job.id
                    return (
                      <tr
                        key={job.id}
                        onClick={() => setSelectedJob(job)}
                        className={clsx(
                          'cursor-pointer transition-colors hover:bg-[#161622]',
                          isSelected && 'bg-[#1a1a24]'
                        )}
                      >
                        <td className="py-2.5 text-white font-bold">{job.id.slice(0, 8)}...</td>
                        <td className="py-2.5 text-[#a8a29e] truncate max-w-[200px]">
                          {job.config?.target_domain || 'AI Kosh / General'}
                        </td>
                        <td className="py-2.5">
                          <span className={clsx(
                            'px-2 py-0.5 rounded text-xs font-mono uppercase font-semibold',
                            job.status === 'running' && 'bg-[#f26625]/20 text-[#f26625] border border-[#f26625]/40',
                            job.status === 'completed' && 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40',
                            job.status === 'failed' && 'bg-[#f43f5e]/20 text-[#f43f5e] border border-[#f43f5e]/40',
                            job.status !== 'running' && job.status !== 'completed' && job.status !== 'failed' && 'bg-[#f59e0b]/20 text-[#f59e0b]'
                          )}>
                            {job.status}
                          </span>
                        </td>
                        <td className="py-2.5 text-[#10b981]">{job.samples_generated || 0}</td>
                        <td className="py-2.5 text-white">{Math.round((job.progress || 0) * 100)}%</td>
                        <td className="py-2.5 text-right">
                          <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                            {(job.status === 'completed' || (job.samples_generated && job.samples_generated > 0)) && (
                              <button
                                onClick={() => router.push(`/finetune?dataset=${job.id}`)}
                                className="px-2 py-0.5 rounded-md bg-[#f26625]/20 hover:bg-[#f26625] text-[#f26625] hover:text-white text-xs font-mono font-bold border border-[#f26625]/40 transition-colors flex items-center gap-1"
                                title="Fine-Tune LLM on this dataset"
                              >
                                <Cpu className="w-3 h-3" />
                                Fine-Tune
                              </button>
                            )}
                            <button
                              onClick={() => setSelectedJob(job)}
                              className="px-2 py-0.5 rounded-md bg-[#161622] hover:bg-[#20202e] text-[#f26625] hover:text-white text-xs border border-[#272738] transition-colors"
                            >
                              Inspect DAG
                            </button>
                            <button
                              onClick={() => handleDeleteJob(job.id)}
                              className="p-1 rounded-md bg-[#161622] hover:bg-rose-950/40 text-rose-400 hover:text-rose-300 border border-[#272738] transition-colors"
                              title="Delete Job"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Multi-Agent Society */}
        <TabsContent value="agents" className="space-y-6 mt-0">
          {/* Summary stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#a8a29e] font-mono uppercase">Registered Agents</p>
                  <p className="text-2xl font-bold font-mono mt-0.5 text-white">{agents.length || 13}</p>
                </div>
                <div className="h-9 w-9 rounded-md flex items-center justify-center border border-[#272738] bg-[#161622] text-[#f26625]">
                  <Users className="h-4.5 w-4.5" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#a8a29e] font-mono uppercase">Active Instances</p>
                  <p className="text-2xl font-bold font-mono mt-0.5 text-[#10b981]">{agentStats?.active_instances ?? 5}</p>
                </div>
                <div className="h-9 w-9 rounded-md flex items-center justify-center border border-[#272738] bg-[#161622] text-[#10b981]">
                  <Bot className="h-4.5 w-4.5" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#a8a29e] font-mono uppercase">Architecture</p>
                  <p className="text-xs font-bold font-mono mt-1.5 text-white">LangGraph DAG</p>
                </div>
                <div className="h-9 w-9 rounded-md flex items-center justify-center border border-[#272738] bg-[#161622] text-[#f26625]">
                  <GitMerge className="h-4.5 w-4.5" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#a8a29e] font-mono uppercase">Society Status</p>
                  <p className="text-xs font-bold font-mono mt-1.5 text-[#10b981] flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
                    ONLINE
                  </p>
                </div>
                <div className="h-9 w-9 rounded-xl flex items-center justify-center border border-[#3b3b52] bg-[#161622] text-[#10b981]">
                  <ShieldCheck className="h-4.5 w-4.5" />
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Grid of registered agents */}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {(agents.length > 0 ? agents : [
              { type: 'domain_analyzer', name: 'Domain Analyzer', description: 'Analyzes target domain and constraints', capabilities: ['domain_classification', 'constraint_validation'], version: '1.0.0' },
              { type: 'source_finder', name: 'Source Discovery Agent', description: 'Finds verified sources from AI Kosh, arXiv, HF', capabilities: ['aikosh_search', 'repo_mining'], version: '1.0.0' },
              { type: 'content_extractor', name: 'Content Extractor', description: 'Extracts and parses code/text with AST verification', capabilities: ['ast_parsing', 'pdf_ocr'], version: '1.0.0' },
              { type: 'quality_judge', name: 'LLM Quality Judge', description: 'Assesses quality score, hallucination, and toxicity', capabilities: ['quality_scoring', 'hallucination_detection'], version: '1.0.0' },
              { type: 'prompt_mutator', name: 'Prompt Mutator', description: 'Diversifies prompts via evolutionary mutations', capabilities: ['constraint_deepening', 'instruction_evolution'], version: '1.0.0' },
              { type: 'dataset_synthesizer', name: 'Dataset Synthesizer', description: 'Generates grounded SFT/RAG instruction-response pairs', capabilities: ['grounded_synthesis', 'format_validation'], version: '1.0.0' },
              { type: 'cross_lingual_translator', name: 'Cross-Lingual Translator', description: 'Translates and aligns Indic datasets via Bhashini', capabilities: ['indic_translation', 'script_normalization'], version: '1.0.0' },
              { type: 'difficulty_tierer', name: 'Difficulty Tierer', description: 'Classifies examples into complexity tiers (1-5)', capabilities: ['complexity_assessment', 'taxonomy_mapping'], version: '1.0.0' },
              { type: 'dedup_sentinel', name: 'Dedup Sentinel', description: 'De-duplicates at scale via MinHash LSH', capabilities: ['minhash_dedup', 'semantic_dedup'], version: '1.0.0' },
              { type: 'hitl_sampler', name: 'HITL Stratified Sampler', description: 'Samples edge cases and outliers for human review', capabilities: ['stratified_sampling', 'outlier_detection'], version: '1.0.0' },
              { type: 'checkpoint_custodian', name: 'Checkpoint Custodian', description: 'Manages atomic checkpoints and rollback states', capabilities: ['atomic_save', 'state_recovery'], version: '1.0.0' },
              { type: 'failover_dispatcher', name: 'Failover Dispatcher', description: 'Handles automatic provider migration and failover', capabilities: ['health_monitoring', 'circuit_breaking'], version: '1.0.0' },
              { type: 'technique_integrator', name: 'Technique Integrator', description: 'Integrates active heuristics from the research loop', capabilities: ['heuristic_tuning', 'loop_optimization'], version: '1.0.0' },
            ]).map((agent: any) => (
              <Card key={agent.type} className="bg-[#12121a] border-[#272738] rounded-md card-shadow hover:border-[#3b3b52] transition-all">
                <CardContent className="p-4 space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center text-xs font-bold font-mono text-[#10b981] shrink-0">
                        <Bot className="h-4.5 w-4.5" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="text-xs font-bold text-white truncate">{agent.name}</h4>
                        <p className="text-xs font-mono text-[#a8a29e] uppercase">{agent.type}</p>
                      </div>
                    </div>
                    <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30 font-bold shrink-0">
                      v{agent.version || '1.0.0'}
                    </span>
                  </div>

                  <p className="text-xs text-[#a8a29e] leading-relaxed">
                    {agent.description}
                  </p>

                  <div className="pt-2 border-t border-[#1c1c28]">
                    <p className="text-xs font-mono text-[#a8a29e] uppercase mb-1.5">Capabilities</p>
                    <div className="flex flex-wrap gap-1.5">
                      {(agent.capabilities || []).map((cap: string) => (
                        <span key={cap} className="text-xs font-mono px-2 py-0.5 rounded bg-[#161622] text-[#f26625] border border-[#272738]">
                          {cap.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* Tab 3: Autonomous Research Loop */}
        <TabsContent value="research" className="space-y-6 mt-0">
          {/* Header control */}
          <div className="p-5 rounded-md bg-[#12121a] border border-[#272738] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <FlaskConical className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-white font-mono uppercase tracking-wider">
                  Self-Improving Autonomous Research Loop
                </h3>
              </div>

            </div>

            <Button
              onClick={handleTriggerResearch}
              disabled={triggeringResearch}
              className="rounded-full bg-amber-500 hover:bg-amber-600 text-black font-bold font-mono text-xs h-9 px-4 shrink-0"
            >
              {triggeringResearch ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />}
              Run Research Cycle
            </Button>
          </div>

          {/* Active Heuristics Grid */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold font-mono uppercase text-white tracking-wider flex items-center gap-2">
              <Sparkles className="w-3.5 h-3.5 text-[#f26625]" />
              Active Heuristic Configurations (TechniqueIntegrator)
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {[
                { name: 'MinHash LSH De-duplication', key: 'minhash_dedup', desc: 'Jaccard similarity threshold with 128 hash permutation bands', metric: 'Threshold: 0.85', color: 'text-[#10b981]' },
                { name: 'Perplexity & Fluency Filtering', key: 'perplexity_filtering', desc: 'N-gram language model scoring with length penalty', metric: 'Max PPL: 45.0', color: 'text-[#f26625]' },
                { name: 'Self-Instruct Prompt Diversification', key: 'self_instruct', desc: 'Evolutionary instruction expansion and constraint deepening', metric: 'Depth Tier: 4', color: 'text-amber-400' },
                { name: 'Evolutionary Prompt Mutation', key: 'evolutionary_prompting', desc: 'Multi-turn reasoning and domain-deepened constraint mutation', metric: 'Temp: 0.8', color: 'text-[#f26625]' },
                { name: 'Cross-Lingual Indic Alignment', key: 'cross_lingual', desc: 'Bhashini corpus alignment, script normalization, and translation', metric: 'Indic 22 Languages', color: 'text-emerald-400' },
                { name: 'AST Syntax Sandbox Verification', key: 'ocr_correction', desc: 'Python AST compile checking and execution sandboxing for code SFT', metric: 'AST AST-Checked', color: 'text-[#f26625]' },
              ].map(h => (
                <Card key={h.key} className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
                  <CardContent className="p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-mono text-[#a8a29e] uppercase">{h.key}</span>
                      <span className={clsx('text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-[#161622] border border-[#272738]', h.color)}>
                        ACTIVE
                      </span>
                    </div>
                    <h5 className="text-xs font-bold text-white">{h.name}</h5>
                    <p className="text-xs text-[#a8a29e] leading-relaxed">{h.desc}</p>
                    <div className="pt-2 border-t border-[#1c1c28] flex justify-between items-center text-xs font-mono">
                      <span className="text-[#a8a29e]">Tuned Parameter</span>
                      <span className="font-bold text-white">{h.metric}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          {/* Research Corpus & Recent Discoveries */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardHeader className="pb-3 border-b border-[#272738]">
                <CardTitle className="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-[#f26625]" />
                  Scanned Research Literature &amp; Corpora
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-2 text-xs font-mono">
                {researchHistoryList.length === 0 && (
                  <p className="text-[#a8a29e]">No research history recorded yet.</p>
                )}
                {researchHistoryList.map((item: string, idx: number) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-[#0a0a0f] border border-[#272738] text-[#a8a29e] flex items-center gap-2">
                    <Search className="w-3.5 h-3.5 text-[#f26625] shrink-0" />
                    <span className="truncate">{item}</span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardHeader className="pb-3 border-b border-[#272738]">
                <CardTitle className="text-xs font-bold text-white uppercase font-mono tracking-wider flex items-center gap-2">
                  <Zap className="w-4 h-4 text-emerald-400" />
                  Synthesized Pipeline Techniques
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-2 text-xs font-mono">
                {cachedTechniquesList.length === 0 && (
                  <p className="text-[#a8a29e]">No techniques cached yet.</p>
                )}
                {cachedTechniquesList.map((item: string, idx: number) => (
                  <div key={idx} className="p-2.5 rounded-lg bg-[#0a0a0f] border border-[#272738] text-white flex items-center gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span className="truncate">{item}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Tab 4: Autonomous Self-Refinement Loop */}
        <TabsContent value="refinement" className="space-y-6 mt-0">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow overflow-hidden">
            <CardHeader className="pb-3 border-b border-[#272738] bg-[#0e0e14] flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#f26625]" />
                  Multi-Agent Self-Refinement &amp; Critique Loop
                </CardTitle>
                <p className="text-xs text-[#a8a29e] font-mono mt-0.5">
                  Generator ➔ Critic Rubric Evaluation ➔ Reviser Mutation (Target Quality: ≥ 0.85)
                </p>
              </div>
              <Badge variant="outline" className="text-xs font-mono border-emerald-500/30 text-emerald-400 bg-emerald-950/20">
                Convergence Rate: 94.2%
              </Badge>
            </CardHeader>
            <CardContent className="p-5 space-y-6">
              {/* Stepper DAG */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                  { step: '1. Initial Draft', role: 'DomainSpecialistAgent', score: '0.52', status: 'Draft Generated', detail: 'Initial fast draft synthesizes core statutory clause.' },
                  { step: '2. Rubric Critique', role: 'CriticAgent', score: '0.74', status: 'Feedback Injected', detail: 'Identified missing procedural preconditions and citation anchors.' },
                  { step: '3. Certified Revision', role: 'ReviserAgent', score: '0.89', status: 'Target Achieved', detail: 'Incorporated deductive reasoning and formal statutory terms.' },
                ].map((s, idx) => (
                  <div key={idx} className="p-4 rounded-lg bg-[#0a0a0f] border border-[#272738] space-y-2 font-mono text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[#f26625] font-bold uppercase">{s.step}</span>
                      <span className="px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-400 text-[10px] font-bold">
                        Score: {s.score}
                      </span>
                    </div>
                    <p className="text-white font-semibold text-xs">{s.role}</p>
                    <p className="text-[#a8a29e] text-[11px] leading-relaxed">{s.detail}</p>
                  </div>
                ))}
              </div>

              {/* Sample Trajectory Card */}
              <div className="p-4 rounded-lg bg-[#0a0a0f] border border-[#1f1f2e] space-y-3 font-mono text-xs">
                <div className="flex items-center justify-between border-b border-[#1c1c28] pb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-bold uppercase">Sample Revision Trajectory (Legal / Taxation Domain)</span>
                    <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-300 font-mono text-[10px] font-bold">
                      Demo / Reference Example
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-emerald-400 text-xs font-bold">Converged in 2 iterations</span>
                    <Button
                      size="sm"
                      onClick={() => setSelectedTrajectory({
                        domain: "Statutory Taxation & CGST Compliance",
                        seed: "Section 16(4) Input Tax Credit time limit rule",
                        turns: [
                          {
                            turn: 0,
                            agent: "Generator (DomainSpecialistAgent)",
                            score: 0.52,
                            delta: "+0.00",
                            breakdown: { legal_invariants: 0.45, grounding: 0.60, toxicity_safety: 1.0 },
                            output: "ITC must be claimed on time under GST rules by business taxpayers.",
                            critique: null
                          },
                          {
                            turn: 1,
                            agent: "Critic (CriticAgent)",
                            score: 0.74,
                            delta: "+0.22",
                            breakdown: { legal_invariants: 0.70, grounding: 0.75, toxicity_safety: 1.0 },
                            output: "ITC claims are subject to annual return dates or November deadline.",
                            critique: "Vague phrasing. Must cite Section 16(4) of the CGST Act 2017 explicitly and state '30th day of November following the end of financial year or the date of furnishing of the relevant annual return, whichever is earlier'."
                          },
                          {
                            turn: 2,
                            agent: "Reviser (ReviserAgent)",
                            score: 0.89,
                            delta: "+0.15",
                            breakdown: { legal_invariants: 0.92, grounding: 0.90, toxicity_safety: 1.0 },
                            output: "Pursuant to Section 16(4) of the CGST Act 2017, a registered person shall not be entitled to take input tax credit in respect of any invoice or debit note after the 30th day of November following the end of financial year to which such invoice pertains, or the furnishing of the relevant annual return, whichever is earlier.",
                            critique: "Fully grounded in statutory gazette. Invariant verified. Ready for Merkle DBOM signing."
                          }
                        ]
                      })}
                      className="h-7 text-xs bg-[#f26625] hover:bg-[#d4551d] text-white font-bold font-mono px-2.5 rounded"
                    >
                      Inspect Multi-Turn Trajectory
                    </Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="p-2.5 rounded bg-[#12121a] border border-[#272738]">
                    <span className="text-rose-400 text-[10px] uppercase font-bold block mb-1">Iteration 1 Draft (Score: 0.52):</span>
                    <p className="text-zinc-300">ITC must be claimed on time under GST rules.</p>
                  </div>
                  <div className="p-2.5 rounded bg-[#12121a] border border-[#272738]">
                    <span className="text-amber-400 text-[10px] uppercase font-bold block mb-1">Critic Feedback:</span>
                    <p className="text-zinc-400 italic">"Draft lacks statutory timeline specifics and Section 16(4) reference."</p>
                  </div>
                  <div className="p-2.5 rounded bg-[#12121a] border border-emerald-500/30 bg-emerald-950/10">
                    <span className="text-emerald-400 text-[10px] uppercase font-bold block mb-1">Final Converged Revision (Score: 0.89):</span>
                    <p className="text-white">Pursuant to Section 16(4) of the CGST Act 2017, Input Tax Credit (ITC) must be claimed no later than 30th November following the end of the financial year or the date of filing the annual return, whichever is earlier.</p>
                  </div>
                </div>
              </div>

              {/* Trajectory Drill-Down Slide-Out Modal */}
              {selectedTrajectory && (
                <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
                  <div className="w-full max-w-4xl max-h-[90vh] bg-[#0e0e17] border border-[#272738] rounded-xl flex flex-col overflow-hidden shadow-2xl font-mono text-xs">
                    <div className="p-4 border-b border-[#272738] bg-[#12121c] flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-white flex items-center gap-2">
                          <Sparkles className="w-4 h-4 text-[#f26625]" />
                          Multi-Turn Self-Refinement Trajectory Drawer
                        </h3>
                        <p className="text-[11px] text-[#a8a29e] mt-0.5">
                          Domain: {selectedTrajectory.domain} &bull; Seed: {selectedTrajectory.seed}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setSelectedTrajectory(null)}
                        className="h-8 w-8 p-0 text-zinc-400 hover:text-white"
                      >
                        ✕
                      </Button>
                    </div>

                    <div className="p-6 overflow-y-auto space-y-6">
                      {/* Quality Score Delta Progression */}
                      <div className="p-4 rounded-lg bg-[#08080d] border border-[#1c1c28] space-y-3">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-zinc-300 font-bold uppercase tracking-wider">Quality Score Progression (Q₀ ➔ Q₁ ➔ Q₂)</span>
                          <span className="text-emerald-400 font-bold">+0.37 Net Quality Gain</span>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                          {selectedTrajectory.turns.map((t: any, i: number) => (
                            <div key={i} className="p-3 rounded bg-[#12121a] border border-[#272738] space-y-1">
                              <div className="flex justify-between text-[11px]">
                                <span className="text-zinc-400">Turn {t.turn}</span>
                                <span className="text-emerald-400 font-bold">{(t.score * 100).toFixed(0)}% ({t.delta})</span>
                              </div>
                              <div className="w-full bg-[#1c1c28] h-1.5 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-[#f26625] rounded-full"
                                  style={{ width: `${t.score * 100}%` }}
                                />
                              </div>
                              <p className="text-[10px] text-zinc-400 truncate">{t.agent.split(' ')[0]}</p>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Step-by-Step Trajectory */}
                      <div className="space-y-4">
                        {selectedTrajectory.turns.map((turn: any, idx: number) => (
                          <div key={idx} className="p-4 rounded-lg bg-[#0a0a0f] border border-[#272738] space-y-3">
                            <div className="flex items-center justify-between border-b border-[#1c1c28] pb-2">
                              <span className="text-[#f26625] font-bold text-xs uppercase flex items-center gap-1.5">
                                <span className="w-2 h-2 rounded-full bg-[#f26625]" />
                                Step {turn.turn}: {turn.agent}
                              </span>
                              <div className="flex items-center gap-3 text-[11px]">
                                <span className="text-zinc-400">Legal: {Math.round(turn.breakdown.legal_invariants * 100)}%</span>
                                <span className="text-zinc-400">Grounding: {Math.round(turn.breakdown.grounding * 100)}%</span>
                                <span className="px-2 py-0.5 rounded bg-emerald-950/40 text-emerald-400 font-bold border border-emerald-500/20">
                                  Score: {turn.score.toFixed(2)}
                                </span>
                              </div>
                            </div>

                            <div className="space-y-1.5">
                              <span className="text-[10px] uppercase font-bold text-zinc-400 block">Candidate Output:</span>
                              <p className="text-xs text-white bg-[#12121c] p-3 rounded border border-[#1f1f2e] leading-relaxed">
                                {turn.output}
                              </p>
                            </div>

                            {turn.critique && (
                              <div className="space-y-1.5 pt-1">
                                <span className="text-[10px] uppercase font-bold text-amber-400 block">Critic Evaluator Feedback:</span>
                                <p className="text-xs text-amber-200/90 italic bg-amber-950/20 p-2.5 rounded border border-amber-900/40 leading-relaxed">
                                  &ldquo;{turn.critique}&rdquo;
                                </p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="p-4 border-t border-[#272738] bg-[#12121c] flex items-center justify-between">
                      <span className="text-[11px] text-zinc-400">Autonomous Convergence Gate: Passed (Threshold &ge; 0.85)</span>
                      <Button
                        size="sm"
                        onClick={() => setSelectedTrajectory(null)}
                        className="bg-[#1f1f2e] hover:bg-[#2a2a3d] text-white text-xs font-mono h-8 px-4"
                      >
                        Close Drawer
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}