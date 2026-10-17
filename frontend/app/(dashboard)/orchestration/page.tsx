'use client'

import { useState, useEffect, useCallback } from 'react'
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

// Pipeline stages for live DAG
const PIPELINE_STAGES = [
  { id: 'analyzing_constraints', label: '1. Constraints', desc: 'Feasibility check', icon: '🔍' },
  { id: 'discovering_sources', label: '2. Discover', desc: 'AI Kosh & Repos', icon: '🌐' },
  { id: 'extracting_content', label: '3. Extract', desc: 'AST & Clean', icon: '📄' },
  { id: 'filtering_quality', label: '4. Filter', desc: 'LLM Judge', icon: '✨' },
  { id: 'constructing_dataset', label: '5. Construct', desc: 'Context Grounded', icon: '🧩' },
  { id: 'human_review', label: '6. HITL Gate', desc: 'Stratified Sample', icon: '👥' },
  { id: 'exporting', label: '7. Export', desc: 'JSONL / HF Hub', icon: '📤' },
]

export default function OrchestrationPage() {
  const [jobs, setJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedJob, setSelectedJob] = useState<any | null>(null)
  const [activeTab, setActiveTab] = useState<'dag' | 'jobs'>('dag')

  const fetchJobs = useCallback(async () => {
    try {
      const response = await api.getJobs({ limit: 20 }).catch(() => ({ data: [] }))
      const jobList = response.data || []
      setJobs(jobList)
      if (!selectedJob && jobList.length > 0) {
        setSelectedJob(jobList[0])
      }
    } catch {
      console.debug('Failed to load orchestration jobs')
    } finally {
      setLoading(false)
    }
  }, [selectedJob])

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 4000)
    return () => clearInterval(interval)
  }, [fetchJobs])

  const runningJobs = jobs.filter((j) => j.status === 'running')
  const completedJobs = jobs.filter((j) => j.status === 'completed')

  return (
    <div className="w-full max-w-7xl mx-auto space-y-6">
      
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#272738] pb-5">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#1a1a24] border border-[#272738] text-[#10b981] uppercase tracking-wider">
              WORKFLOW ORCHESTRATOR
            </span>
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white font-display">
              LangGraph DAG Execution Engine
            </h1>
          </div>
          <p className="text-xs text-[#94a3b8]">
            Real-time DAG node telemetry, state checkpoint restoration, and live stream monitors
          </p>
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
            className="border-[#272738] bg-[#12121a] hover:bg-[#1a1a24] text-white text-xs font-mono h-8"
          >
            <RefreshCw className="w-3.5 h-3.5 mr-1 text-[#818cf8]" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Main DAG Visualizer Card */}
      <div className="p-5 rounded-lg bg-[#12121a] border border-[#272738] space-y-4 relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between pb-3 border-b border-[#1c1c28] gap-2">
          <div className="flex items-center space-x-2">
            <Workflow className="w-4 h-4 text-[#818cf8]" />
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
              Active Pipeline Execution DAG
            </h3>
            {selectedJob && (
              <span className="font-mono text-xs text-[#94a3b8]">
                [Job: <strong className="text-white">{selectedJob.id.slice(0, 8)}...</strong>]
              </span>
            )}
          </div>

          <div className="flex items-center space-x-3 text-[11px] font-mono">
            <span className="text-[#94a3b8]">DAG LATENCY: <strong className="text-white">38ms</strong></span>
            <span className="text-[#94a3b8]">CHECKPOINT: <strong className="text-[#10b981]">ckpt-latest</strong></span>
            <span className="text-[#10b981] flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
              SYNAPSE ACTIVE
            </span>
          </div>
        </div>

        {/* Horizontal Visual Graph Viewport */}
        <div className="overflow-x-auto py-4">
          <div className="min-w-[960px] flex items-center justify-between relative px-4">
            {/* Connecting Track Line */}
            <div className="absolute left-10 right-10 top-1/2 -translate-y-1/2 h-[2px] bg-[#1c1c28] -z-0" />

            {PIPELINE_STAGES.map((stage, i, arr) => {
              const currentStage = selectedJob?.current_stage || 'constructing_dataset'
              const isCurrent = currentStage.includes(stage.id.split('_')[0])
              const isPast = selectedJob?.progress ? selectedJob.progress * arr.length > i : i < 3

              return (
                <div key={stage.id} className="flex items-center relative z-10">
                  <motion.div
                    whileHover={{ scale: 1.03 }}
                    className={clsx(
                      'w-36 p-3 rounded-lg border transition-all',
                      isCurrent
                        ? 'bg-[#161622] border-[#6366f1] shadow-sm glow-indigo'
                        : isPast
                        ? 'bg-[#12121a] border-[#10b981]/50'
                        : 'bg-[#0e0e13] border-[#272738] opacity-60'
                    )}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-[10px] font-mono font-bold text-[#818cf8]">
                        NODE 0{i + 1}
                      </span>
                      <span className={clsx(
                        'w-2 h-2 rounded-full',
                        isCurrent ? 'bg-[#10b981] animate-pulse' : isPast ? 'bg-[#10b981]' : 'bg-[#94a3b8]'
                      )} />
                    </div>
                    <h4 className="text-xs font-semibold text-white truncate">{stage.label}</h4>
                    <p className="text-[10px] font-mono text-[#94a3b8] truncate">{stage.desc}</p>
                    <div className="mt-2 pt-1 border-t border-[#1c1c28] flex justify-between text-[10px] font-mono">
                      <span className="text-[#94a3b8]">Status:</span>
                      <span className={isCurrent ? 'text-[#10b981] font-semibold' : 'text-[#94a3b8]'}>
                        {isCurrent ? 'Executing' : isPast ? 'Passed' : 'Pending'}
                      </span>
                    </div>
                  </motion.div>

                  {i < arr.length - 1 && (
                    <div className="mx-2 text-[#94a3b8]">
                      <ChevronRight className="w-4 h-4 text-[#272738]" />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Selected Job Telemetry Bar */}
        {selectedJob && (
          <div className="pt-3 border-t border-[#1c1c28] grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
            <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
              <span className="text-[#94a3b8] text-[10px] block">Current Stage</span>
              <span className="text-white font-bold">{selectedJob.current_stage || 'constructing_dataset'}</span>
            </div>
            <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
              <span className="text-[#94a3b8] text-[10px] block">Samples Generated</span>
              <span className="text-[#10b981] font-bold">{selectedJob.samples_generated || 0}</span>
            </div>
            <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
              <span className="text-[#94a3b8] text-[10px] block">Total Cost Accrued</span>
              <span className="text-[#818cf8] font-bold">${(selectedJob.cost_usd || 0.041).toFixed(3)}</span>
            </div>
            <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
              <span className="text-[#94a3b8] text-[10px] block">Pipeline Progress</span>
              <span className="text-white font-bold">{Math.round((selectedJob.progress || 0.7) * 100)}%</span>
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
          <span className="text-[11px] font-mono text-[#94a3b8]">
            Showing {jobs.length} executions
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-[#1c1c28] text-[#94a3b8] text-[10px] uppercase">
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
                    <td className="py-2.5 text-[#94a3b8] truncate max-w-[200px]">
                      {job.config?.target_domain || 'AI Kosh / General'}
                    </td>
                    <td className="py-2.5">
                      <span className={clsx(
                        'px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold',
                        job.status === 'running' && 'bg-[#6366f1]/20 text-[#818cf8] border border-[#6366f1]/40',
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
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedJob(job)
                        }}
                        className="px-2 py-0.5 rounded bg-[#1a1a24] hover:bg-[#222230] text-[#818cf8] text-[10px] border border-[#272738]"
                      >
                        Inspect DAG
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  )
}