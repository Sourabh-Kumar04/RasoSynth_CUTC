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
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Orchestration</h1>
            <p className="text-sm text-muted-foreground">
              Monitor and manage dataset generation pipelines
            </p>
          </div>
        </div>
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Activity className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">No Active Pipelines</h3>
            <p className="text-sm text-muted-foreground mb-4 text-center max-w-md">
              Create a dataset in the Studio to start an orchestration pipeline.
              The system will automatically manage discovery, extraction, filtering, and export.
            </p>
            <Button variant="outline" onClick={fetchJobs}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Orchestration</h1>
          <p className="text-sm text-muted-foreground">
            Monitor and manage dataset generation pipelines
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={fetchJobs}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <div className="flex-1">
              <p className="text-sm font-medium">Failed to load orchestration data</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={fetchJobs}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      {!loading && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Running</p>
                  <p className="text-2xl font-semibold">{runningJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Loader2 className="h-5 w-5 text-accent animate-spin" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Pending</p>
                  <p className="text-2xl font-semibold">{pendingJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <Clock className="h-5 w-5 text-warning" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Completed</p>
                  <p className="text-2xl font-semibold">{completedJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-success/10 flex items-center justify-center">
                  <CheckCircle2 className="h-5 w-5 text-success" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Failed</p>
                  <p className="text-2xl font-semibold">{failedJobs.length}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-error/10 flex items-center justify-center">
                  <XCircle className="h-5 w-5 text-error" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-accent mb-4" />
            <p className="text-sm text-muted-foreground">Loading pipelines...</p>
          </CardContent>
        </Card>
      )}

      {/* Main Content */}
      {!loading && jobs.length > 0 && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="jobs">Active Jobs</TabsTrigger>
            <TabsTrigger value="pipeline">Pipeline Stages</TabsTrigger>
          </TabsList>

          {/* Active Jobs Tab */}
          <TabsContent value="jobs" className="mt-6">
            <div className="space-y-3">
              {jobs.map((job) => {
                const stageLabel = getStageLabel(job.current_stage)
                const isRunning = job.status === 'running'

                return (
                  <Card key={job.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div
                            className={clsx(
                              'h-10 w-10 rounded-lg flex items-center justify-center',
                              isRunning ? 'bg-accent/10' : 'bg-surface'
                            )}
                          >
                            {isRunning ? (
                              <Loader2 className="h-5 w-5 text-accent animate-spin" />
                            ) : job.status === 'completed' ? (
                              <CheckCircle2 className="h-5 w-5 text-success" />
                            ) : job.status === 'failed' ? (
                              <XCircle className="h-5 w-5 text-error" />
                            ) : (
                              <Clock className="h-5 w-5 text-muted-foreground" />
                            )}
                          </div>
                          <div>
                            <p className="font-medium">{job.target_domain || job.id}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <StatusBadge status={job.status} />
                              <span className="text-xs text-muted-foreground">
                                {stageLabel}
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-6">
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">Progress</p>
                            <p className="font-mono">{Math.round(job.progress * 100)}%</p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">Samples</p>
                            <p className="font-mono">{job.samples_generated.toLocaleString()}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-muted-foreground">Cost</p>
                            <p className="font-mono">${job.cost_usd.toFixed(2)}</p>
                          </div>
                          <div className="w-32">
                            <Progress value={job.progress * 100} className="h-2" />
                          </div>
                        </div>
                      </div>

                      {/* Pipeline Progress Bar */}
                      {isRunning && job.current_stage && (
                        <div className="mt-4 p-3 bg-surface/30 rounded-lg border border-border-subtle">
                          <div className="flex items-center gap-1">
                            {PIPELINE_STAGES.slice(0, -1).map((stage, index) => {
                              const currentIndex = PIPELINE_STAGES.findIndex(
                                s => s.id === job.current_stage
                              )
                              const isCompleted = index < currentIndex
                              const isCurrent = index === currentIndex

                              return (
                                <div key={stage.id} className="flex items-center flex-1">
                                  <div
                                    className={clsx(
                                      'flex items-center justify-center w-8 h-8 rounded-full text-xs transition-all duration-300 font-bold',
                                      isCompleted && 'bg-success/20 text-success border border-success/40',
                                      isCurrent && 'bg-accent text-white border-2 border-accent shadow-[0_0_12px_rgba(99,102,241,0.6)] animate-pulse',
                                      !isCompleted && !isCurrent && 'bg-surface text-muted-foreground border border-border'
                                    )}
                                    title={stage.label}
                                  >
                                    {isCompleted ? '✓' : stage.icon}
                                  </div>
                                  {index < PIPELINE_STAGES.length - 2 && (
                                    <div
                                      className={clsx(
                                        'flex-1 h-0.5 mx-1 transition-all duration-500',
                                        isCompleted ? 'bg-success/50 shadow-[0_0_4px_rgba(34,197,94,0.3)]' : isCurrent ? 'bg-gradient-to-r from-accent to-border animate-pulse' : 'bg-border'
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
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Pipeline Architecture</CardTitle>
              </CardHeader>
              <CardContent>
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
                            "flex flex-col items-center justify-center p-4 rounded-xl border w-32 h-32 transition-all duration-300 relative",
                            hasActiveJobs
                              ? "border-accent bg-accent/10 shadow-[0_0_20px_rgba(99,102,241,0.4)] ring-1 ring-accent"
                              : jobsInStage.length > 0
                              ? "border-warning/50 bg-warning/5"
                              : "border-border bg-surface"
                          )}
                        >
                          {hasActiveJobs && (
                            <span className="absolute -top-1.5 -right-1.5 flex h-3 w-3">
                              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                              <span className="relative inline-flex rounded-full h-3 w-3 bg-accent"></span>
                            </span>
                          )}
                          <div className={clsx(
                            "text-3xl mb-2 filter drop-shadow",
                            hasActiveJobs && "animate-bounce"
                          )}>{stage.icon}</div>
                          <p className="font-semibold text-sm text-foreground">{stage.label}</p>
                          <p className="text-xs text-muted-foreground mt-1 font-mono">
                            {jobsInStage.length} {jobsInStage.length === 1 ? 'job' : 'jobs'}
                          </p>
                        </div>
                        {index < PIPELINE_STAGES.length - 1 && (
                          <ArrowRight className={clsx(
                            "h-5 w-5 text-muted-foreground/40",
                            hasActiveJobs && "text-accent animate-pulse"
                          )} />
                        )}
                      </div>
                    )
                  })}
                </div>

                <div className="mt-6 p-4 rounded-lg bg-surface/50">
                  <h4 className="font-medium mb-2">Pipeline Description</h4>
                  <p className="text-sm text-muted-foreground">
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