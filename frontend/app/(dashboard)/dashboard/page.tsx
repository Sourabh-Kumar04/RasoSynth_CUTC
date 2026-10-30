'use client'

import React, { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { RefreshCw } from 'lucide-react'
import { api } from '@/lib/api/client'
import { PageHeader } from '@/components/ui/page-header'
import { StatusStrip } from '@/components/ui/status-strip'
import { Button } from '@/components/ui/button'
import { MetricCard, type MetricState } from '@/components/dashboard/metric-card'
import { PipelineStages } from '@/components/dashboard/pipeline-stages'

type SourceState = 'loading' | 'ok' | 'unavailable'
type AnyRecord = Record<string, any>

function str(v: unknown): string | null {
  return typeof v === 'string' && v.length > 0 ? v : null
}

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

function jobLabel(job: AnyRecord): string {
  return str(job.dataset_name) || str(job.config?.dataset_name) || str(job.target_domain) || `Job ${String(job.id ?? '').slice(0, 8)}`
}

function shortId(id: unknown): string {
  return typeof id === 'string' ? id.slice(0, 8) : 'unknown'
}

/** Message shown when a live source cannot be read. Never a made-up value. */
const UNAVAILABLE_NOTE =
  'Unknown — live data is unavailable. The backend may be unreachable, or the call may need a valid login session (data calls return 401 without one). Sign in to view live results.'

/**
 * Dashboard — the primary workspace view for dataset generation and
 * fine-tuning. Every number on this page comes from a live backend
 * response rendered in this component; every source that fails renders
 * as Unknown with the reason above. Data refreshes every 30 seconds
 * while the page is open, plus on manual refresh.
 *
 * Sources:
 * - Dataset jobs: api.getJobs (GET /jobs via the proxy)
 * - Fine-tuning jobs: api.listFineTuneJobs (GET /api/finetune/jobs)
 * - Quality metrics: api.getQualityOverview (GET /api/quality/overview)
 * - Backend liveness: api.getHealth (GET /health)
 */
export default function DashboardPage() {
  const [jobs, setJobs] = useState<AnyRecord[]>([])
  const [jobsState, setJobsState] = useState<SourceState>('loading')
  const [ftJobs, setFtJobs] = useState<AnyRecord[]>([])
  const [ftState, setFtState] = useState<SourceState>('loading')
  const [quality, setQuality] = useState<AnyRecord | null>(null)
  const [qualityState, setQualityState] = useState<SourceState>('loading')
  const [health, setHealth] = useState<AnyRecord | null>(null)
  const [healthState, setHealthState] = useState<SourceState>('loading')
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [isMockMode, setIsMockMode] = useState(false)

  useEffect(() => {
    try {
      setIsMockMode(localStorage.getItem('mockMode') === 'true')
    } catch {
      setIsMockMode(false)
    }
  }, [])

  const load = useCallback(async () => {
    await Promise.all([
      (async () => {
        try {
          const res = await api.getJobs({ limit: 20 })
          const list = Array.isArray(res?.data) ? res.data : []
          setJobs(list)
          setJobsState('ok')
          setSelectedJobId((prev) => prev ?? (list[0]?.id != null ? String(list[0].id) : null))
        } catch {
          setJobsState('unavailable')
        }
      })(),
      (async () => {
        try {
          const res = await api.listFineTuneJobs(20)
          const list = Array.isArray(res?.jobs) ? res.jobs : Array.isArray(res) ? res : []
          setFtJobs(list)
          setFtState('ok')
        } catch {
          setFtState('unavailable')
        }
      })(),
      (async () => {
        try {
          const res = await api.getQualityOverview()
          setQuality(res && typeof res === 'object' ? res : null)
          setQualityState('ok')
        } catch {
          setQualityState('unavailable')
        }
      })(),
      (async () => {
        try {
          const res = await api.getHealth()
          setHealth(res && typeof res === 'object' ? res : null)
          setHealthState('ok')
        } catch {
          setHealthState('unavailable')
        }
      })(),
    ])
    setLastUpdated(new Date().toLocaleTimeString())
  }, [])

  useEffect(() => {
    load()
    const timer = setInterval(load, 30000)
    return () => clearInterval(timer)
  }, [load])

  const selectedJob = jobs.find((j) => String(j.id) === selectedJobId) ?? jobs[0] ?? null
  const metric = (s: SourceState): MetricState => (s === 'ok' ? 'ok' : s === 'loading' ? 'unknown' : 'error')
  const avgQuality = quality ? num(quality.average_quality) : null
  const samplesReviewed = quality ? num(quality.total_samples_reviewed) : null
  const approvalRate = quality ? num(quality.approval_rate) : null
  const selectedProgress = selectedJob ? num(selectedJob.progress) ?? num(selectedJob.progress_fraction) : null

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workspace"
        title="Dashboard"
        purpose={isMockMode ? "Dataset generation and fine-tuning jobs, pipeline stages, and quality metrics." : "Dataset generation and fine-tuning jobs, pipeline stages, and quality metrics. Only live backend data is shown; anything unavailable is marked Unknown."}
        action={
          <>
            <Button variant="outline" size="sm" onClick={load} className="rounded-md border-[#272738] font-mono text-xs text-[#a8a29e] hover:text-white">
              <RefreshCw className="mr-1 h-3.5 w-3.5 text-[#f26625]" /> Refresh
            </Button>
            <Link href="/studio">
              <Button size="sm" className="rounded-md bg-[#f26625] font-mono text-xs font-bold text-white hover:bg-[#de581a]">
                New Dataset
              </Button>
            </Link>
          </>
        }
        status={
          (() => {
            const backendRaw = (str(health?.status) || 'unknown').toLowerCase()
            const isBackendHealthy = healthState === 'ok' && backendRaw === 'healthy'
            const isBackendStandby = healthState === 'ok' && backendRaw === 'standby'
            const isBackendDegraded = healthState === 'ok' && backendRaw === 'degraded'
            const isBackendError = healthState === 'ok' && (backendRaw === 'unhealthy' || backendRaw === 'error')

            const backendTone = isBackendHealthy
              ? ('ok' as const)
              : isBackendStandby || isBackendDegraded
              ? ('warn' as const)
              : isBackendError
              ? ('bad' as const)
              : ('neutral' as const)

            const backendLabel = isBackendHealthy
              ? 'Backend: healthy'
              : isBackendStandby
              ? 'Backend: standby'
              : isBackendDegraded
              ? 'Backend: degraded'
              : isBackendError
              ? `Backend: ${backendRaw}`
              : 'Backend: unknown'

            const allSourcesFailed =
              jobsState === 'unavailable' &&
              ftState === 'unavailable' &&
              qualityState === 'unavailable' &&
              healthState !== 'ok'

            const someSourcesFailed =
              jobsState === 'unavailable' ||
              ftState === 'unavailable' ||
              qualityState === 'unavailable'

            const items: Array<{ label: string; qualifier?: string; tone: 'ok' | 'warn' | 'bad' | 'neutral' }> = [
              {
                label: backendLabel,
                qualifier: !isBackendHealthy && healthState !== 'ok' ? 'liveness check did not return' : undefined,
                tone: backendTone,
              },
            ]

            if (allSourcesFailed) {
              items.push({
                label: 'All data sources unavailable',
                qualifier: 'Backend unreachable or authentication required. Please sign in.',
                tone: 'bad' as const,
              })
            } else if (someSourcesFailed) {
              items.push({
                label: 'Some live data unavailable',
                qualifier: 'shown as Unknown below — no substitute numbers',
                tone: 'warn' as const,
              })
            } else {
              items.push({
                label: 'Live data connected',
                tone: 'ok' as const,
              })
            }

            return <StatusStrip items={items} />
          })()
        }
      />

      {lastUpdated ? (
        <p className="font-mono text-xs text-[#a8a29e]">Last refreshed: {lastUpdated} · Auto-refresh: every 30 seconds while this page is open.</p>
      ) : null}

      {/* Metrics — real backend values only */}
      <section aria-label="Metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Dataset jobs returned"
          state={metric(jobsState)}
          value={jobsState === 'ok' ? String(jobs.length) : undefined}
          source="/jobs (latest 20)"
          note={jobsState === 'loading' ? 'Loading live job list.' : UNAVAILABLE_NOTE}
        />
        <MetricCard
          label="Average quality"
          state={qualityState === 'ok' && avgQuality !== null ? 'ok' : metric(qualityState)}
          value={avgQuality !== null ? avgQuality.toFixed(3) : undefined}
          source="/api/quality/overview"
          note={qualityState === 'loading' ? 'Loading live quality overview.' : qualityState === 'ok' ? 'The backend returned no average quality value.' : UNAVAILABLE_NOTE}
        />
        <MetricCard
          label="Samples reviewed"
          state={qualityState === 'ok' && samplesReviewed !== null ? 'ok' : metric(qualityState)}
          value={samplesReviewed !== null ? String(samplesReviewed) : undefined}
          source="/api/quality/overview"
          note={qualityState === 'loading' ? 'Loading live quality overview.' : qualityState === 'ok' ? 'The backend returned no samples-reviewed value.' : UNAVAILABLE_NOTE}
        />
        <MetricCard
          label="Fine-tuning jobs returned"
          state={metric(ftState)}
          value={ftState === 'ok' ? String(ftJobs.length) : undefined}
          source="/api/finetune/jobs (latest 20)"
          note={ftState === 'loading' ? 'Loading live fine-tuning jobs.' : UNAVAILABLE_NOTE}
        />
      </section>

      {/* Interactive pipeline visualization */}
      <section aria-label="Pipeline" className="rounded-md border border-[#272738] bg-[#12121a] p-4 sm:p-5">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-display text-xl font-bold text-white">Synthesis Pipeline</h2>
            <p className="mt-1 text-xs text-[#a8a29e]">Stages for the selected job, from its live backend stage. No stage data means every stage shows Unknown.</p>
          </div>
          {jobs.length > 0 ? (
            <label className="flex items-center gap-2 font-mono text-xs text-[#a8a29e]">
              Job
              <select
                value={selectedJob ? String(selectedJob.id) : ''}
                onChange={(e) => setSelectedJobId(e.target.value)}
                className="rounded-md border border-[#272738] bg-[#161622] px-2 py-1.5 font-mono text-xs text-white"
              >
                {jobs.map((j) => (
                  <option key={String(j.id)} value={String(j.id)}>
                    {jobLabel(j)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        {selectedJob ? (
          <PipelineStages
            currentStage={str(selectedJob.current_stage) ?? str(selectedJob.stage)}
            jobStatus={str(selectedJob.status)}
            progress={selectedProgress}
          />
        ) : (
          <PipelineStages currentStage={null} jobStatus={null} progress={null} />
        )}
        {selectedJob ? (
          <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-[#a8a29e]">
            <span>
              Job: <span className="text-white">{shortId(selectedJob.id)}</span>
            </span>
            <span>
              Status: <span className="text-white">{str(selectedJob.status) ?? 'unknown'}</span>
            </span>
            <span>
              Dataset: <span className="text-white">{jobLabel(selectedJob)}</span>
            </span>
          </div>
        ) : (
          <p className="mt-4 text-xs text-[#a8a29e]">{jobsState === 'loading' ? 'Loading jobs.' : 'No job selected: no live job data was returned.'}</p>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <Link href="/orchestration" className="rounded-md border border-[#272738] px-3 py-1.5 font-mono text-xs text-[#a8a29e] hover:text-white">
            Open Pipelines
          </Link>
          <Link href="/quality" className="rounded-md border border-[#272738] px-3 py-1.5 font-mono text-xs text-[#a8a29e] hover:text-white">
            Open Quality Inspector
          </Link>
          <Link href="/finetune" className="rounded-md border border-[#272738] px-3 py-1.5 font-mono text-xs text-[#a8a29e] hover:text-white">
            Open Model Training
          </Link>
        </div>
      </section>

      {/* Job lists */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-[#272738] bg-[#12121a] p-4">
          <h2 className="font-display text-lg font-bold text-white">Dataset Jobs</h2>
          <p className="mt-1 text-xs text-[#a8a29e]">Latest jobs from /jobs. Status and stage are shown exactly as returned.</p>
          {jobsState === 'loading' ? (
            <p className="mt-4 text-xs text-[#a8a29e]">Loading.</p>
          ) : jobsState === 'unavailable' ? (
            <p className="mt-4 text-xs leading-relaxed text-[#a8a29e]">{UNAVAILABLE_NOTE}</p>
          ) : jobs.length === 0 ? (
            <p className="mt-4 text-xs text-[#a8a29e]">No jobs returned. Create one in the Studio.</p>
          ) : (
            <ul className="mt-4 divide-y divide-[#1c1c28]">
              {jobs.slice(0, 10).map((j) => (
                <li key={String(j.id)} className="flex items-center justify-between gap-3 py-2">
                  <span className="min-w-0">
                    <span className="block truncate text-sm text-white">{jobLabel(j)}</span>
                    <span className="block font-mono text-xs text-[#a8a29e]">ID {shortId(j.id)}</span>
                  </span>
                  <span className="shrink-0 text-right font-mono text-xs text-[#a8a29e]">
                    <span className="block text-white">{str(j.status) ?? 'unknown'}</span>
                    <span className="block">{str(j.current_stage) ?? str(j.stage) ?? 'stage unknown'}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-md border border-[#272738] bg-[#12121a] p-4">
          <h2 className="font-display text-lg font-bold text-white">Fine-Tuning Jobs</h2>
          <p className="mt-1 text-xs text-[#a8a29e]">Latest jobs from /api/finetune/jobs. Training loss is shown only when the backend returns it.</p>
          {ftState === 'loading' ? (
            <p className="mt-4 text-xs text-[#a8a29e]">Loading.</p>
          ) : ftState === 'unavailable' ? (
            <p className="mt-4 text-xs leading-relaxed text-[#a8a29e]">{UNAVAILABLE_NOTE}</p>
          ) : ftJobs.length === 0 ? (
            <p className="mt-4 text-xs text-[#a8a29e]">No fine-tuning jobs returned.</p>
          ) : (
            <ul className="mt-4 divide-y divide-[#1c1c28]">
              {ftJobs.slice(0, 10).map((j) => {
                const loss = num(j.final_train_loss) ?? num(j.train_loss) ?? num(j.loss)
                return (
                  <li key={String(j.id ?? j.job_id)} className="flex items-center justify-between gap-3 py-2">
                    <span className="min-w-0">
                      <span className="block truncate text-sm text-white">
                        {str(j.output_model_name) ?? str(j.base_model) ?? str(j.model) ?? `Job ${shortId(j.id ?? j.job_id)}`}
                      </span>
                      <span className="block font-mono text-xs text-[#a8a29e]">ID {shortId(j.id ?? j.job_id)}</span>
                    </span>
                    <span className="shrink-0 text-right font-mono text-xs text-[#a8a29e]">
                      <span className="block text-white">{str(j.status) ?? 'unknown'}</span>
                      <span className="block">{loss !== null ? `loss ${loss}` : 'loss unknown'}</span>
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </section>

      {/* Quality detail — only values the backend actually returned */}
      <section aria-label="Quality detail" className="rounded-md border border-[#272738] bg-[#12121a] p-4">
        <h2 className="font-display text-lg font-bold text-white">Dataset Quality</h2>
        {qualityState === 'loading' ? (
          <p className="mt-2 text-xs text-[#a8a29e]">Loading.</p>
        ) : qualityState === 'unavailable' ? (
          <p className="mt-2 text-xs leading-relaxed text-[#a8a29e]">{UNAVAILABLE_NOTE}</p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 font-mono text-xs text-[#a8a29e]">
            <span>
              Average quality: <span className="text-white">{avgQuality !== null ? avgQuality.toFixed(3) : 'unknown'}</span>
            </span>
            <span>
              Approval rate: <span className="text-white">{approvalRate !== null ? (approvalRate <= 1.0 ? `${(approvalRate * 100).toFixed(1)}%` : `${approvalRate.toFixed(1)}%`) : 'unknown'}</span>
            </span>
            <span>
              Samples reviewed: <span className="text-white">{samplesReviewed !== null ? String(samplesReviewed) : 'unknown'}</span>
            </span>
            <span>Source: /api/quality/overview</span>
          </div>
        )}
        <p className="mt-3 text-xs text-[#a8a29e]">
          Training and quality figures update only from live backend responses. If a figure is absent from the response, it stays Unknown — it is not estimated or filled in.
        </p>
      </section>
    </div>
  )
}

