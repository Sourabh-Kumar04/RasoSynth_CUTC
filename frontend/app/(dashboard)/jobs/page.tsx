'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import Link from 'next/link'
import {
  Briefcase,
  Play,
  RefreshCw,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  AlertCircle,
  ExternalLink,
  Loader2,
  Sparkles,
  Database,
  Cpu,
  Layers,
  ArrowRight,
  Copy,
  Check,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { PageHeader } from '@/components/ui/page-header'
import { api } from '@/lib/api/client'
import { formatErrorMessage, formatRelativeTime } from '@/lib/utils'

export type RunType = 'all' | 'dataset' | 'finetune'
export type RunStatus = 'all' | 'running' | 'completed' | 'failed'

export interface UnifiedRun {
  id: string
  runType: 'dataset' | 'finetune'
  title: string
  domain: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | string
  created_at: string
  progress: number
  yield_info: string
  compute_cost?: string
  error?: string | null
  actionUrl: string
  actionLabel: string
}

export default function JobsPage() {
  const [runs, setRuns] = useState<UnifiedRun[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<RunStatus>('all')
  const [typeFilter, setTypeFilter] = useState<RunType>('all')
  const [error, setError] = useState<string | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const handleCopyId = useCallback((id: string) => {
    navigator.clipboard.writeText(id)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }, [])

  const fetchJobs = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true)
    setError(null)
    try {
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Request timed out (~10s): Can't reach the job scheduler")), 10000)
      )

      const [datasetResponse, finetuneResponse] = (await Promise.race([
        Promise.all([
          api.getJobs({ limit: 50 }).catch(() => null),
          api.listFineTuneJobs(50).catch(() => null),
        ]),
        timeoutPromise,
      ])) as [any, any]

      const rawDatasetList = datasetResponse?.data || (Array.isArray(datasetResponse) ? datasetResponse : [])
      const datasetList: any[] = Array.isArray(rawDatasetList) ? rawDatasetList : []

      const rawFtList = finetuneResponse?.jobs || (Array.isArray(finetuneResponse) ? finetuneResponse : [])
      const ftList: any[] = Array.isArray(rawFtList) ? rawFtList : []

      const unifiedRuns: UnifiedRun[] = []

      // 1. Map Dataset Generation Jobs
      for (const j of datasetList) {
        const domainText = j.domain || j.config?.target_domain || 'General Domain'
        const friendlyTitle = j.domain
          ? `${j.domain} Dataset Generation`
          : j.dataset_type
          ? `${j.dataset_type.toUpperCase()} Instruction Dataset`
          : 'Instruction Dataset Generation'

        const yieldCount = j.samples_generated != null ? j.samples_generated.toLocaleString() : '0'
        const targetCount = (j.dataset_size ?? j.config?.dataset_size ?? j.config?.target_samples ?? j.target_size)?.toLocaleString() ?? '100'

        unifiedRuns.push({
          id: j.id,
          runType: 'dataset',
          title: friendlyTitle,
          domain: domainText,
          status: j.status || 'pending',
          created_at: j.created_at,
          progress: typeof j.progress === 'number' ? j.progress : j.status === 'completed' ? 1.0 : 0,
          yield_info: `${yieldCount} / ${targetCount} rows`,
          compute_cost: `$${((j.cost_usd ?? 0)).toFixed(2)} (Local Compute)`,
          error: j.error,
          actionUrl: `/datasets?selected=${j.id}`,
          actionLabel: 'Library',
        })
      }

      // 2. Map Model Training Jobs
      for (const ft of ftList) {
        const baseModel = ft.base_model || 'Custom Model Architecture'
        const friendlyTitle = ft.output_model_name
          ? `${ft.output_model_name} Training`
          : 'QLoRA Model Training'

        const currentEpoch = ft.current_epoch ?? 0
        const totalEpochs = ft.total_epochs ?? 3

        unifiedRuns.push({
          id: ft.id,
          runType: 'finetune',
          title: friendlyTitle,
          domain: baseModel,
          status: ft.status || 'pending',
          created_at: ft.created_at,
          progress: typeof ft.progress === 'number' ? ft.progress / 100 : ft.status === 'completed' ? 1.0 : 0,
          yield_info: `Epoch ${currentEpoch}/${totalEpochs} · Loss ${ft.train_loss != null ? ft.train_loss.toFixed(4) : '—'}`,
          compute_cost: ft.execution_target ? `${ft.execution_target.toUpperCase()} Pool` : 'GPU Accelerated',
          error: ft.error,
          actionUrl: '/finetune',
          actionLabel: 'Training Studio',
        })
      }

      // Sort newest first
      unifiedRuns.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      setRuns(unifiedRuns)
    } catch (err: unknown) {
      console.warn('Failed to load jobs list:', err)
      const errStr = formatErrorMessage(err)
      if (errStr.includes('401') || errStr.toLowerCase().includes('token') || errStr.toLowerCase().includes('auth')) {
        setRuns([])
      } else {
        setError(errStr)
      }
    } finally {
      setLoading(false)
      if (isManual) setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    const timer = setInterval(() => fetchJobs(false), 8000)
    return () => clearInterval(timer)
  }, [fetchJobs])

  const filteredRuns = useMemo(() => {
    return runs.filter((r) => {
      if (statusFilter !== 'all' && r.status?.toLowerCase() !== statusFilter) return false
      if (typeFilter !== 'all' && r.runType !== typeFilter) return false
      if (searchQuery.trim().length > 0) {
        const query = searchQuery.toLowerCase()
        const matchId = r.id?.toLowerCase().includes(query)
        const matchTitle = r.title?.toLowerCase().includes(query)
        const matchDomain = r.domain?.toLowerCase().includes(query)
        if (!matchId && !matchTitle && !matchDomain) return false
      }
      return true
    })
  }, [runs, statusFilter, typeFilter, searchQuery])

  const counts = useMemo(() => {
    return {
      all: runs.length,
      running: runs.filter((r) => r.status === 'running').length,
      completed: runs.filter((r) => r.status === 'completed').length,
      failed: runs.filter((r) => r.status === 'failed').length,
      dataset: runs.filter((r) => r.runType === 'dataset').length,
      finetune: runs.filter((r) => r.runType === 'finetune').length,
    }
  }, [runs])

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <PageHeader
        eyebrow={`${counts.running} Active Runs`}
        title="Jobs Execution Dashboard"
        purpose="Real-time monitoring and orchestration of synthetic dataset generation runs and fine-tuning pipelines."
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchJobs(true)}
              disabled={refreshing}
              className="text-xs font-mono border-[#272738] bg-[#12121a] hover:bg-[#161622] text-zinc-300"
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${refreshing ? 'animate-spin text-[#f26625]' : ''}`} />
              Refresh
            </Button>
            <Link href="/studio">
              <Button size="sm" className="text-xs font-mono bg-[#f26625] hover:bg-[#de581a] text-white font-bold">
                <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
                New Generation Run
              </Button>
            </Link>
          </div>
        }
      />

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          {/* Job Type Filter */}
          <div className="flex items-center gap-1.5 bg-[#0e0e16] p-1 rounded-lg border border-[#272738]">
            <span className="text-[11px] font-mono text-[#a8a29e] uppercase px-2 font-bold flex items-center gap-1">
              <Filter className="w-3 h-3 text-[#f26625]" />
              Type:
            </span>
            <button
              onClick={() => setTypeFilter('all')}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-all ${
                typeFilter === 'all'
                  ? 'bg-[#f26625] text-white font-bold shadow-sm'
                  : 'text-[#a8a29e] hover:text-white'
              }`}
            >
              All Runs ({counts.all})
            </button>
            <button
              onClick={() => setTypeFilter('dataset')}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-all flex items-center gap-1 ${
                typeFilter === 'dataset'
                  ? 'bg-[#f26625] text-white font-bold shadow-sm'
                  : 'text-[#a8a29e] hover:text-white'
              }`}
            >
              <Database className="w-3 h-3" />
              Dataset Generation ({counts.dataset})
            </button>
            <button
              onClick={() => setTypeFilter('finetune')}
              className={`px-2.5 py-1 rounded text-xs font-mono transition-all flex items-center gap-1 ${
                typeFilter === 'finetune'
                  ? 'bg-[#f26625] text-white font-bold shadow-sm'
                  : 'text-[#a8a29e] hover:text-white'
              }`}
            >
              <Cpu className="w-3 h-3" />
              Model Training ({counts.finetune})
            </button>
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-[#a8a29e]" />
            <Input
              placeholder="Search runs by ID, title, or domain..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-9 text-xs font-mono bg-[#12121a] border-[#272738] text-white placeholder:text-zinc-600 focus-visible:ring-[#f26625]"
            />
          </div>
        </div>

        {/* Status Filter Bar */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0">
          {(['all', 'running', 'completed', 'failed'] as const).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono capitalize transition-all whitespace-nowrap ${
                statusFilter === status
                  ? 'bg-[#1e1e2d] text-white font-bold border border-[#f26625]'
                  : 'bg-[#12121a] text-[#a8a29e] hover:text-white hover:bg-[#181824] border border-[#272738]'
              }`}
            >
              {status} ({counts[status]})
            </button>
          ))}
        </div>
      </div>

      {/* Error banner if non-auth failure occurs when runs list is present */}
      {error && runs.length > 0 && (
        <Card className="border border-rose-500/30 bg-rose-950/20 text-rose-300 rounded-md">
          <CardContent className="p-4 flex items-center justify-between text-xs font-mono">
            <div className="flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{formatErrorMessage(error)}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchJobs(true)}
              className="text-xs font-mono border-rose-500/40 text-rose-300 hover:bg-rose-950/40"
            >
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Runs List */}
      {loading ? (
        <Card className="border-[#272738] bg-[#12121a]/60 rounded-md p-12 text-center">
          <Loader2 className="w-6 h-6 animate-spin text-[#f26625] mx-auto mb-3" />
          <p className="text-xs font-mono text-[#a8a29e]">Connecting to job scheduler...</p>
        </Card>
      ) : error && runs.length === 0 ? (
        <Card className="border-[#272738] bg-[#12121a]/60 rounded-md p-12 text-center">
          <AlertCircle className="w-8 h-8 text-amber-500 mx-auto mb-3" />
          <h3 className="text-sm font-bold font-mono text-white mb-1">
            Can&apos;t reach the scheduler
          </h3>
          <p className="text-xs font-mono text-[#a8a29e] max-w-md mx-auto mb-6">
            The job scheduler did not respond. The backend may be offline or unreachable.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button
              onClick={() => fetchJobs(true)}
              className="text-xs font-mono bg-[#f26625] hover:bg-[#de581a] text-white font-bold"
            >
              <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              Retry Connection
            </Button>
            <Link href="/studio">
              <Button variant="outline" className="text-xs font-mono border-[#272738] bg-[#12121a] hover:bg-[#161622] text-zinc-300">
                Create your first dataset
              </Button>
            </Link>
          </div>
        </Card>
      ) : filteredRuns.length === 0 ? (
        <Card className="border-[#272738] bg-[#12121a]/60 rounded-md p-12 text-center">
          <Briefcase className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <h3 className="text-sm font-bold font-mono text-white mb-1">
            {runs.length === 0 ? 'No Pipeline Runs Found' : 'No Matching Runs'}
          </h3>
          <p className="text-xs font-mono text-[#a8a29e] max-w-md mx-auto mb-6">
            {runs.length === 0
              ? 'Launch your first synthetic dataset generation or model training run directly from the studio.'
              : 'Try clearing your search query or switching filters.'}
          </p>
          <Link href="/studio">
            <Button className="text-xs font-mono bg-[#f26625] hover:bg-[#de581a] text-white font-bold">
              <Play className="w-3.5 h-3.5 mr-1.5 fill-current" />
              Create your first dataset
            </Button>
          </Link>
        </Card>
      ) : (
        <div className="space-y-3 font-mono">
          {filteredRuns.map((run) => {
            const isRunning = run.status === 'running'
            const isCompleted = run.status === 'completed'
            const isFailed = run.status === 'failed'

            return (
              <Card
                key={run.id}
                className="border-[#272738] bg-[#12121a]/90 backdrop-blur-sm rounded-md hover:border-[#f26625]/40 transition-all p-4 space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        isRunning
                          ? 'bg-amber-400 animate-pulse'
                          : isCompleted
                          ? 'bg-emerald-400'
                          : isFailed
                          ? 'bg-rose-400'
                          : 'bg-zinc-500'
                      }`}
                    />
                    <h3 className="text-sm font-bold text-white tracking-tight">{run.title}</h3>

                    {/* Truncated copyable ID chip */}
                    <button
                      type="button"
                      onClick={() => handleCopyId(run.id)}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-[#161622] hover:bg-[#1e1e2d] border border-[#272738] text-zinc-400 hover:text-white text-[11px] transition-colors"
                      title="Copy full Run ID"
                    >
                      <span>#{run.id.slice(0, 8)}</span>
                      {copiedId === run.id ? (
                        <Check className="w-3 h-3 text-emerald-400" />
                      ) : (
                        <Copy className="w-3 h-3 text-zinc-500" />
                      )}
                    </button>

                    <Badge
                      variant="outline"
                      className={`text-[10px] uppercase font-mono ${
                        run.runType === 'finetune'
                          ? 'border-purple-500/40 text-purple-400 bg-purple-500/10'
                          : 'border-cyan-500/40 text-cyan-400 bg-cyan-500/10'
                      }`}
                    >
                      {run.runType === 'finetune' ? 'QLoRA Training' : 'Dataset Synthesis'}
                    </Badge>

                    <Badge
                      variant="outline"
                      className={`text-[10px] uppercase font-mono ${
                        isRunning
                          ? 'border-amber-500/40 text-amber-400 bg-amber-500/10'
                          : isCompleted
                          ? 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10'
                          : isFailed
                          ? 'border-rose-500/40 text-rose-400 bg-rose-500/10'
                          : 'border-zinc-700 text-zinc-400'
                      }`}
                    >
                      {run.status?.replace(/_/g, ' ')}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-[#a8a29e]">
                    <span>{run.created_at ? formatRelativeTime(run.created_at) : 'recently'}</span>
                    <Link href={run.actionUrl}>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs font-mono border-[#272738] bg-[#161622] hover:bg-[#1c1c28] text-zinc-200"
                      >
                        {run.runType === 'finetune' ? (
                          <Cpu className="w-3 h-3 mr-1 text-[#f26625]" />
                        ) : (
                          <Database className="w-3 h-3 mr-1 text-[#f26625]" />
                        )}
                        {run.actionLabel}
                      </Button>
                    </Link>
                  </div>
                </div>

                {/* Domain & Parameters */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs pt-1 border-t border-[#1c1c28]">
                  <div>
                    <span className="text-[#a8a29e] block text-[10px] uppercase">
                      {run.runType === 'finetune' ? 'Base Model' : 'Domain Context'}
                    </span>
                    <span className="text-zinc-200 truncate block font-medium">
                      {run.domain}
                    </span>
                  </div>
                  <div>
                    <span className="text-[#a8a29e] block text-[10px] uppercase">Yield / Metrics</span>
                    <span className="text-zinc-200">
                      {run.yield_info}
                    </span>
                  </div>
                  <div>
                    <span className="text-[#a8a29e] block text-[10px] uppercase">Compute Profile</span>
                    <span className="text-emerald-400 font-bold">
                      {run.compute_cost || 'Local Hardware'}
                    </span>
                  </div>
                </div>

                {/* Progress bar if running */}
                {isRunning && (
                  <div className="space-y-1 pt-1">
                    <div className="flex justify-between text-[11px] text-[#a8a29e]">
                      <span>
                        {run.runType === 'finetune'
                          ? 'Optimizing model parameters...'
                          : 'Synthesizing instruction curriculum...'}
                      </span>
                      <span>{Math.round(run.progress * 100)}%</span>
                    </div>
                    <Progress value={Math.round(run.progress * 100)} className="h-1.5 bg-[#0a0a0f]" />
                  </div>
                )}

                {/* Clean error message if failed */}
                {run.error && (
                  <div className="p-2.5 rounded bg-rose-950/30 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    <span>{formatErrorMessage(run.error)}</span>
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
