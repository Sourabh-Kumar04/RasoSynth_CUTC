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
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { PageHeader } from '@/components/ui/page-header'
import { api } from '@/lib/api/client'
import { formatErrorMessage, formatRelativeTime } from '@/lib/utils'

interface JobRecord {
  id: string
  domain?: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | string
  created_at: string
  progress?: number
  samples_generated?: number
  target_size?: number
  cost_usd?: number
  dataset_type?: string
  error?: string
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'running' | 'completed' | 'failed'>('all')
  const [error, setError] = useState<string | null>(null)

  const fetchJobs = useCallback(async (isManual = false) => {
    if (isManual) setRefreshing(true)
    setError(null)
    try {
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Request timed out (~10s): Can't reach the job scheduler")), 10000)
      )
      const response = (await Promise.race([
        api.getJobs({ limit: 50 }),
        timeoutPromise,
      ])) as any
      const rawList = response?.data || (Array.isArray(response) ? response : [])
      const list = Array.isArray(rawList) ? rawList : []
      setJobs(list)
    } catch (err: unknown) {
      console.warn('Failed to load jobs list:', err)
      const errStr = formatErrorMessage(err)
      // Unauthenticated / 401 gracefully resolves to empty state per product specification
      if (errStr.includes('401') || errStr.toLowerCase().includes('token') || errStr.toLowerCase().includes('auth')) {
        setJobs([])
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

  const filteredJobs = useMemo(() => {
    return jobs.filter((j) => {
      if (statusFilter !== 'all' && j.status?.toLowerCase() !== statusFilter) return false
      if (searchQuery.trim().length > 0) {
        const query = searchQuery.toLowerCase()
        const matchId = j.id?.toLowerCase().includes(query)
        const matchDomain = j.domain?.toLowerCase().includes(query)
        if (!matchId && !matchDomain) return false
      }
      return true
    })
  }, [jobs, statusFilter, searchQuery])

  const counts = useMemo(() => {
    return {
      all: jobs.length,
      running: jobs.filter((j) => j.status === 'running').length,
      completed: jobs.filter((j) => j.status === 'completed').length,
      failed: jobs.filter((j) => j.status === 'failed').length,
    }
  }, [jobs])

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
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto pb-1 sm:pb-0">
          {(['all', 'running', 'completed', 'failed'] as const).map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono capitalize transition-all whitespace-nowrap ${
                statusFilter === status
                  ? 'bg-[#f26625] text-white font-bold shadow-sm'
                  : 'bg-[#12121a] text-[#a8a29e] hover:text-white hover:bg-[#181824] border border-[#272738]'
              }`}
            >
              {status} ({counts[status]})
            </button>
          ))}
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-[#a8a29e]" />
          <Input
            placeholder="Search by Job ID or domain..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9 h-9 text-xs font-mono bg-[#12121a] border-[#272738] text-white placeholder:text-zinc-600 focus-visible:ring-[#f26625]"
          />
        </div>
      </div>

      {/* Error banner if non-auth failure occurs */}
      {error && (
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

      {/* Jobs List */}
      {loading ? (
        <Card className="border-[#272738] bg-[#12121a]/60 rounded-md p-12 text-center">
          <Loader2 className="w-6 h-6 animate-spin text-[#f26625] mx-auto mb-3" />
          <p className="text-xs font-mono text-[#a8a29e]">Connecting to job scheduler...</p>
        </Card>
      ) : error && jobs.length === 0 ? (
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
      ) : filteredJobs.length === 0 ? (
        <Card className="border-[#272738] bg-[#12121a]/60 rounded-md p-12 text-center">
          <Briefcase className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
          <h3 className="text-sm font-bold font-mono text-white mb-1">
            {jobs.length === 0 ? 'No Generation Jobs Found' : 'No Matching Jobs'}
          </h3>
          <p className="text-xs font-mono text-[#a8a29e] max-w-md mx-auto mb-6">
            {jobs.length === 0
              ? 'Launch your first synthetic dataset generation run with zero sign-up directly from Dataset Studio.'
              : 'Try clearing your search query or switching status filters.'}
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
          {filteredJobs.map((job) => {
            const isRunning = job.status === 'running'
            const isCompleted = job.status === 'completed'
            const isFailed = job.status === 'failed'

            return (
              <Card
                key={job.id}
                className="border-[#272738] bg-[#12121a]/90 backdrop-blur-sm rounded-md hover:border-[#f26625]/40 transition-all p-4 space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2.5">
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
                    <span className="text-xs font-bold text-white break-all">{job.id}</span>
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
                      {job.status}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-3 text-xs text-[#a8a29e]">
                    <span>{job.created_at ? formatRelativeTime(job.created_at) : 'recently'}</span>
                    <Link href={`/datasets?selected=${job.id}`}>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs font-mono border-[#272738] bg-[#161622] hover:bg-[#1c1c28] text-zinc-200"
                      >
                        <Database className="w-3 h-3 mr-1 text-[#f26625]" />
                        Library
                      </Button>
                    </Link>
                  </div>
                </div>

                {/* Domain & Parameters */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs pt-1 border-t border-[#1c1c28]">
                  <div>
                    <span className="text-[#a8a29e] block text-[10px] uppercase">Domain</span>
                    <span className="text-zinc-200 truncate block font-medium">
                      {job.domain || 'Taxation & Statutory Reasoning'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[#a8a29e] block text-[10px] uppercase">Yield</span>
                    <span className="text-zinc-200">
                      {job.samples_generated != null ? job.samples_generated.toLocaleString() : '0'} /{' '}
                      {job.target_size != null ? job.target_size.toLocaleString() : '10,000'} rows
                    </span>
                  </div>
                  <div>
                    <span className="text-[#a8a29e] block text-[10px] uppercase">Est. Compute</span>
                    <span className="text-emerald-400 font-bold">
                      ${((job.cost_usd ?? 0)).toFixed(2)} (Free Local Demo)
                    </span>
                  </div>
                </div>

                {/* Progress bar if running */}
                {isRunning && (
                  <div className="space-y-1 pt-1">
                    <div className="flex justify-between text-[11px] text-[#a8a29e]">
                      <span>Synthesizing instruction curriculum...</span>
                      <span>{Math.round((job.progress ?? 0) * 100)}%</span>
                    </div>
                    <Progress value={Math.round((job.progress ?? 0) * 100)} className="h-1.5 bg-[#0a0a0f]" />
                  </div>
                )}

                {/* Error string if failed */}
                {job.error && (
                  <div className="p-2 rounded bg-rose-950/30 border border-rose-500/30 text-rose-300 text-xs">
                    {formatErrorMessage(job.error)}
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
