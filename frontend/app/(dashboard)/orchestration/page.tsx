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
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge, StatusBadge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/lib/api/client'

// Pipeline stages
const PIPELINE_STAGES = [
  { id: 'analyzing_constraints', label: 'Analyzing', icon: '🔍' },
  { id: 'discovering_sources', label: 'Discovering', icon: '🌐' },
  { id: 'extracting_content', label: 'Extracting', icon: '📄' },
  { id: 'filtering_quality', label: 'Filtering', icon: '✨' },
  { id: 'constructing_dataset', label: 'Constructing', icon: '🧩' },
  { id: 'exporting', label: 'Exporting', icon: '📤' },
  { id: 'completed', label: 'Complete', icon: '✓' },
]

interface JobData {
  id: string
  status: string
  created_at: string
  progress: number
  cost_usd: number
  samples_generated: number
  current_stage?: string
  target_domain?: string
}

export default function OrchestrationPage() {
  const [jobs, setJobs] = useState<JobData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('jobs')

  const fetchJobs = useCallback(async () => {
    try {
      setError(null)
      const response = await api.getJobs({ limit: 20 }).catch(() => ({ data: [] }))
      setJobs(response.data || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load jobs')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 5000) // Poll every 5s for real-time updates
    return () => clearInterval(interval)
  }, [fetchJobs])

  const runningJobs = jobs.filter(j => j.status === 'running')
  const pendingJobs = jobs.filter(j => j.status === 'pending' || j.status === 'negotiating')
  const completedJobs = jobs.filter(j => j.status === 'completed')
  const failedJobs = jobs.filter(j => j.status === 'failed')

  // Get stage label for a job
  const getStageLabel = (stage?: string) => {
    if (!stage) return 'Pending'
    const found = PIPELINE_STAGES.find(s => s.id === stage)
    return found ? found.label : stage
  }

  // Empty state
  if (!loading && jobs.length === 0 && !error) {
    return (
      <div className="space-y-6 max-w-7xl mx-auto pb-8">
        <div className="flex items-center justify-between border-b border-[#E2E6E0] pb-4">
          <div>
            <div className="flex items-center gap-2.5 mb-1">
              <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-bold uppercase tracking-wider">
                Multi-Agent Workflow
              </span>
              <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">Orchestration</h1>
            </div>
            <p className="text-xs text-[#55635B]">
              Monitor and manage autonomous dataset generation pipelines
            </p>
          </div>
        </div>
        <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Activity className="h-12 w-12 text-[#809085] mb-4" />
            <h3 className="text-lg font-bold text-[#1B3B2B] mb-2">No Active Pipelines</h3>
            <p className="text-xs text-[#55635B] mb-4 text-center max-w-md">
              Create a dataset in the Studio to start an orchestration pipeline.
              The system will automatically manage discovery, extraction, filtering, and export.
            </p>
            <Button variant="outline" className="rounded-full border-[#D1D8CE] text-[#1B3B2B]" onClick={fetchJobs}>
              <RefreshCw className="h-4 w-4 mr-2 text-[#1B3B2B]" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-8">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-[#E2E6E0] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-bold uppercase tracking-wider">
              Multi-Agent Workflow
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">Orchestration Engine</h1>
          </div>
          <p className="text-xs text-[#55635B]">
            Monitor and manage dataset generation pipelines & multi-stage synthesis
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-2 rounded-full border-[#D1D8CE] text-[#1B3B2B] hover:bg-[#E8ECE6]"
            onClick={fetchJobs}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin text-[#1B3B2B]" />
            ) : (
              <RefreshCw className="h-4 w-4 text-[#1B3B2B]" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-rose-300 bg-rose-50/80 rounded-2xl">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-rose-600" />
            <div className="flex-1">
              <p className="text-sm font-bold text-rose-950">Failed to load orchestration data</p>
              <p className="text-xs text-rose-800">{error}</p>
            </div>
            <Button variant="outline" size="sm" className="rounded-full" onClick={fetchJobs}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      {!loading && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#55635B] font-mono uppercase">Running</p>
                  <p className="text-2xl font-bold font-mono text-[#1B3B2B]">{runningJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <Loader2 className="h-5 w-5 text-[#1B3B2B] animate-spin" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#55635B] font-mono uppercase">Pending</p>
                  <p className="text-2xl font-bold font-mono text-[#1B3B2B]">{pendingJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <Clock className="h-5 w-5 text-amber-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#55635B] font-mono uppercase">Completed</p>
                  <p className="text-2xl font-bold font-mono text-[#1B3B2B]">{completedJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#55635B] font-mono uppercase">Failed</p>
                  <p className="text-2xl font-bold font-mono text-[#1B3B2B]">{failedJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <XCircle className="h-5 w-5 text-rose-500" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <Card className="border-[#E2E6E0] bg-white rounded-2xl">
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-[#1B3B2B] mb-4" />
            <p className="text-xs font-mono text-[#55635B]">Loading pipelines...</p>
          </CardContent>
        </Card>
      )}

      {/* Main Content */}
      {!loading && jobs.length > 0 && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-[#E8ECE6] rounded-full border border-[#D1D8CE]">
            <TabsTrigger value="jobs" className="rounded-full">Active Jobs</TabsTrigger>
            <TabsTrigger value="pipeline" className="rounded-full">Pipeline Stages</TabsTrigger>
          </TabsList>

          {/* Active Jobs Tab */}
          <TabsContent value="jobs" className="mt-6">
            <div className="space-y-3">
              {jobs.map((job) => {
                const stageLabel = getStageLabel(job.current_stage)
                const isRunning = job.status === 'running'

                return (
                  <Card key={job.id} className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
                    <CardContent className="p-4">
                      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <div
                            className={clsx(
                              'h-10 w-10 rounded-xl flex items-center justify-center border border-[#D1D8CE]',
                              isRunning ? 'bg-[#E8ECE6]' : 'bg-[#F6F7F4]'
                            )}
                          >
                            {isRunning ? (
                              <Loader2 className="h-5 w-5 text-[#1B3B2B] animate-spin" />
                            ) : job.status === 'completed' ? (
                              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                            ) : job.status === 'failed' ? (
                              <XCircle className="h-5 w-5 text-rose-500" />
                            ) : (
                              <Clock className="h-5 w-5 text-[#55635B]" />
                            )}
                          </div>
                          <div>
                            <p className="font-bold text-xs text-[#1B3B2B]">{job.target_domain || job.id}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <StatusBadge status={job.status} />
                              <span className="text-xs text-[#55635B] font-mono">
                                {stageLabel}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-6 w-full sm:w-auto justify-between sm:justify-end border-t sm:border-0 pt-3 sm:pt-0">
                          <div className="text-right">
                            <p className="text-[10px] text-[#55635B] font-mono uppercase">Progress</p>
                            <p className="font-mono text-xs font-bold text-[#1B3B2B]">{Math.round(job.progress * 100)}%</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[10px] text-[#55635B] font-mono uppercase">Samples</p>
                            <p className="font-mono text-xs font-bold text-[#1B3B2B]">{job.samples_generated.toLocaleString()}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-[10px] text-[#55635B] font-mono uppercase">Cost</p>
                            <p className="font-mono text-xs font-bold text-[#1B3B2B]">${job.cost_usd.toFixed(2)}</p>
                          </div>
                          <div className="w-28 hidden md:block">
                            <Progress value={job.progress * 100} className="h-1.5 bg-[#E8ECE6]" />
                          </div>
                        </div>
                      </div>

                      {/* Pipeline Progress Bar */}
                      {isRunning && job.current_stage && (
                        <div className="mt-4 p-3 bg-[#F6F7F4] rounded-xl border border-[#E2E6E0]">
                          <div className="flex items-center gap-1 overflow-x-auto">
                            {PIPELINE_STAGES.slice(0, -1).map((stage, index) => {
                              const currentIndex = PIPELINE_STAGES.findIndex(
                                s => s.id === job.current_stage
                              )
                              const isCompleted = index < currentIndex
                              const isCurrent = index === currentIndex

                              return (
                                <div key={stage.id} className="flex items-center flex-1 min-w-[40px]">
                                  <div
                                    className={clsx(
                                      'flex items-center justify-center w-8 h-8 rounded-full text-xs transition-all duration-300 font-bold',
                                      isCompleted && 'bg-emerald-100 text-emerald-800 border border-emerald-300',
                                      isCurrent && 'bg-[#1B3B2B] text-white border-2 border-[#1B3B2B] animate-pulse',
                                      !isCompleted && !isCurrent && 'bg-[#E8ECE6] text-[#55635B] border border-[#D1D8CE]'
                                    )}
                                    title={stage.label}
                                  >
                                    {isCompleted ? '✓' : stage.icon}
                                  </div>
                                  {index < PIPELINE_STAGES.length - 2 && (
                                    <div
                                      className={clsx(
                                        'flex-1 h-0.5 mx-1 transition-all duration-500',
                                        isCompleted ? 'bg-emerald-400' : isCurrent ? 'bg-[#1B3B2B]' : 'bg-[#D1D8CE]'
                                      )}
                                    />
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          </TabsContent>

          {/* Pipeline Stages Tab */}
          <TabsContent value="pipeline" className="mt-6">
            <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader className="pb-3 border-b border-[#E2E6E0]">
                <CardTitle className="text-sm font-bold text-[#1B3B2B]">Pipeline Architecture</CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="flex flex-wrap items-center justify-center gap-4 py-6">
                  {PIPELINE_STAGES.map((stage, index) => {
                    const jobsInStage = jobs.filter(j => {
                      const sIndex = PIPELINE_STAGES.findIndex(s => s.id === j.current_stage)
                      return sIndex === index
                    })
                    const hasActiveJobs = jobsInStage.some(j => j.status === 'running')

                    return (
                      <div key={stage.id} className="flex items-center gap-4">
                        <div
                          className={clsx(
                            "flex flex-col items-center justify-center p-4 rounded-2xl border w-32 h-32 transition-all duration-300 relative card-shadow",
                            hasActiveJobs
                              ? "border-[#1B3B2B] bg-[#E8ECE6]/60"
                              : jobsInStage.length > 0
                              ? "border-amber-300 bg-amber-50"
                              : "border-[#E2E6E0] bg-[#F6F7F4]"
                          )}
                        >
                          {hasActiveJobs && (
                            <span className="absolute -top-1.5 -right-1.5 flex h-3 w-3">
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75"></span>
                              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                            </span>
                          )}
                          <div className={clsx(
                            "text-3xl mb-2 filter drop-shadow",
                            hasActiveJobs && "animate-bounce"
                          )}>{stage.icon}</div>
                          <p className="font-bold text-xs text-[#1B3B2B]">{stage.label}</p>
                          <p className="text-xs text-[#55635B] mt-1 font-mono">
                            {jobsInStage.length} {jobsInStage.length === 1 ? 'job' : 'jobs'}
                          </p>
                        </div>
                        {index < PIPELINE_STAGES.length - 1 && (
                          <ArrowRight className={clsx(
                            "h-5 w-5 text-[#809085]",
                            hasActiveJobs && "text-[#1B3B2B] animate-pulse"
                          )} />
                        )}
                      </div>
                    )
                  })}
                </div>

                <div className="mt-6 p-4 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0]">
                  <h4 className="font-bold text-xs text-[#1B3B2B] mb-1">Pipeline Description</h4>
                  <p className="text-xs text-[#55635B] leading-relaxed">
                    The dataset generation pipeline consists of 7 stages: analyzing constraints,
                    discovering sources, extracting content, filtering quality, constructing dataset,
                    exporting, and completion. Each stage can be checkpointed for resumability.
                  </p>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}