'use client'

import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  Cpu, Play, Square, RefreshCw, ExternalLink,
  List, Plus, ChevronDown, ChevronUp, Copy,
  CheckCircle2, AlertCircle, Loader2, X,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api/client'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SupportedModel {
  id: string; name: string; params: string
  recommended_template: string; requires_gpu: boolean
}

interface FTJob {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  base_model: string; output_model_name: string; progress: number
  current_epoch: number; total_epochs: number; train_loss: number | null
  eval_loss: number | null; error: string | null; output_path: string | null
  hf_repo_url: string | null; created_at: string
  started_at: string | null; completed_at: string | null
}

interface LogLine {
  type: string; epoch?: number; step?: number; loss?: number
  eval_loss?: number; progress?: number; message?: string
  path?: string; url?: string; output_path?: string; timestamp: string
}

interface Toast { id: number; message: string; variant: 'success' | 'error' | 'info' }

// ── Toast hook ────────────────────────────────────────────────────────────────

function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])
  const counter = useRef(0)
  const push = useCallback((message: string, variant: Toast['variant'] = 'info') => {
    const id = ++counter.current
    setToasts(p => [...p, { id, message, variant }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500)
  }, [])
  return { toasts, push }
}

// ── Sparkline ─────────────────────────────────────────────────────────────────

function LossSparkline({ data }: { data: number[] }) {
  if (data.length < 2) return <span className="text-xs text-[#55635B]">—</span>
  const W = 80, H = 28, PAD = 2
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1
  const pts = data.map((v, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2)
    const y = H - PAD - ((v - min) / range) * (H - PAD * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <svg width={W} height={H} className="inline-block align-middle">
      <polyline points={pts} fill="none" stroke="#1B3B2B"
        strokeWidth="1.75" strokeLinejoin="round" />
    </svg>
  )
}

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_PILL: Record<FTJob['status'], string> = {
  pending:   'bg-amber-100 text-amber-800 border-amber-300',
  running:   'bg-[#E8ECE6] text-[#1B3B2B] border-[#D1D8CE]',
  completed: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  failed:    'bg-rose-100 text-rose-800 border-rose-300',
  cancelled: 'bg-[#E8ECE6] text-[#55635B] border-[#D1D8CE]',
}

const STATUS_STRIPE: Record<FTJob['status'], string> = {
  pending: 'border-l-amber-500', running: 'border-l-[#1B3B2B]',
  completed: 'border-l-emerald-500', failed: 'border-l-rose-500',
  cancelled: 'border-l-slate-400',
}

function StatusPill({ status }: { status: FTJob['status'] }) {
  return (
    <span className={clsx('inline-flex items-center gap-1 text-[10px] px-2.5 py-0.5 rounded-full border font-mono font-medium shrink-0', STATUS_PILL[status])}>
      {status === 'running' && (
        <span className="w-1.5 h-1.5 rounded-full bg-[#1B3B2B] animate-pulse" />
      )}
      {status}
    </span>
  )
}

function fmtDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

// ── Collapsible form section ──────────────────────────────────────────────────

function Section({
  title, children, defaultOpen = true,
}: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="rounded-xl border border-[#E2E6E0] overflow-hidden bg-white">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-[#F6F7F4] hover:bg-[#E8ECE6]/60 transition-colors text-left"
      >
        <span className="text-xs font-bold text-[#1B3B2B] font-mono uppercase">{title}</span>
        {open
          ? <ChevronUp className="h-3.5 w-3.5 text-[#55635B]" />
          : <ChevronDown className="h-3.5 w-3.5 text-[#55635B]" />}
      </button>
      {open && <div className="px-4 py-3 space-y-3">{children}</div>}
    </div>
  )
}

// ── Log line renderer ─────────────────────────────────────────────────────────

const LOG_COLOR: Record<string, string> = {
  error: 'text-rose-700 font-bold', completed: 'text-emerald-800 font-bold', pushed: 'text-emerald-700',
  progress: 'text-[#1B3B2B]', eval: 'text-amber-800', saved: 'text-teal-800',
  started: 'text-[#1B3B2B] font-bold', checkpoint: 'text-amber-700', cancelled: 'text-[#55635B]',
}

function LogRow({ line }: { line: LogLine }) {
  const color = LOG_COLOR[line.type] ?? 'text-[#55635B]'
  let text: string
  switch (line.type) {
    case 'progress':   text = `epoch ${line.epoch}  step ${line.step}  loss=${line.loss}  (${line.progress}%)`; break
    case 'eval':       text = `eval_loss=${line.eval_loss}  @ epoch ${line.epoch}`; break
    case 'completed':  text = `✓ done → ${line.output_path}`; break
    case 'pushed':     text = `✓ pushed → ${line.url}`; break
    case 'saved':      text = `✓ saved → ${line.path}`; break
    case 'error':      text = `✗ ${line.message}`; break
    case 'cancelled':  text = '⊘ cancelled'; break
    case 'started':    text = '▶ training started'; break
    case 'checkpoint': text = '💾 checkpoint saved'; break
    default:           text = JSON.stringify(line)
  }
  return (
    <div className={clsx('leading-5 font-mono text-xs', color)}>
      <span className="text-[#809085] select-none">
        [{line.timestamp?.slice(11, 19)}]{' '}
      </span>
      {text}
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function JobSkeleton() {
  return (
    <div className="rounded-xl border-l-4 border-l-[#D1D8CE] border border-[#E2E6E0] bg-white p-3 space-y-2">
      <div className="flex justify-between">
        <Skeleton className="h-3.5 w-32 bg-[#E8ECE6]" />
        <Skeleton className="h-4 w-14 rounded-full bg-[#E8ECE6]" />
      </div>
      <Skeleton className="h-3 w-48 bg-[#E8ECE6]" />
      <Skeleton className="h-1.5 w-full rounded-full bg-[#E8ECE6]" />
    </div>
  )
}

// ── Detail pane (desktop + mobile sheet) ─────────────────────────────────────

interface DetailPaneProps {
  job: FTJob
  logs: LogLine[]
  lossHistory: number[]
  onCancel: (id: string) => void
  onCopy: (s: string) => void
  onReconnect: (id: string) => void
  logsEndRef: React.RefObject<HTMLDivElement>
}

function DetailPane({ job, logs, lossHistory, onCancel, onCopy, onReconnect, logsEndRef }: DetailPaneProps) {
  return (
    <div className="space-y-4">
      <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
        <CardHeader className="pb-2 border-b border-[#E2E6E0]">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-sm font-bold text-[#1B3B2B] truncate max-w-[200px]">
              {job.output_model_name || job.id.slice(0, 16)}
            </CardTitle>
            <div className="flex items-center gap-2">
              <StatusPill status={job.status} />
              {(job.status === 'running' || job.status === 'pending') && (
                <Button variant="destructive" size="sm" className="rounded-full h-7 text-xs" onClick={() => onCancel(job.id)}>
                  <Square className="h-3 w-3 mr-1" />Cancel
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 p-4">
          {job.status === 'running' && <Progress value={job.progress} className="h-2 bg-[#E8ECE6]" />}

          {lossHistory.length > 1 && (
            <div className="flex items-center gap-3 bg-[#F6F7F4] rounded-xl px-3 py-2 border border-[#E2E6E0]">
              <span className="text-xs text-[#55635B] font-mono shrink-0">Loss</span>
              <LossSparkline data={lossHistory} />
              <span className="text-xs font-mono text-[#1B3B2B] font-bold shrink-0">
                {lossHistory[lossHistory.length - 1]?.toFixed(4)}
              </span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            <div><span className="text-[#55635B]">Model </span><span className="font-bold text-[#1B3B2B]">{job.base_model}</span></div>
            <div><span className="text-[#55635B]">Epochs </span>
              <span className="font-mono font-bold text-[#1B3B2B]">{job.current_epoch}/{job.total_epochs}</span>
            </div>
            <div><span className="text-[#55635B]">Train loss </span>
              <span className="font-mono text-[#1B3B2B]">{job.train_loss?.toFixed(4) ?? '—'}</span>
            </div>
            <div><span className="text-[#55635B]">Eval loss </span>
              <span className="font-mono text-[#1B3B2B]">{job.eval_loss?.toFixed(4) ?? '—'}</span>
            </div>
            <div><span className="text-[#55635B]">Started </span><span className="text-[#1B3B2B]">{fmtDate(job.started_at)}</span></div>
            <div><span className="text-[#55635B]">Done </span><span className="text-[#1B3B2B]">{fmtDate(job.completed_at)}</span></div>
          </div>

          {job.error && (
            <div className="flex items-start gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
              <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              {job.error}
            </div>
          )}

          {job.hf_repo_url && (
            <a href={job.hf_repo_url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-[#1B3B2B] font-bold hover:underline">
              <ExternalLink className="h-3 w-3" />View on HuggingFace Hub
            </a>
          )}

          {job.output_path && (
            <div className="flex items-center gap-2">
              <code className="text-xs font-mono bg-[#F6F7F4] text-[#1B3B2B] px-2 py-0.5 rounded-lg border border-[#E2E6E0] truncate max-w-[260px]">
                {job.output_path}
              </code>
              <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0 rounded-full text-[#1B3B2B]"
                onClick={() => onCopy(job.output_path!)}>
                <Copy className="h-3 w-3" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
        <CardHeader className="pb-2 border-b border-[#E2E6E0]">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-bold text-[#1B3B2B]">Training Log</CardTitle>
            {job.status === 'running' && (
              <Button variant="ghost" size="sm" className="h-7 text-xs rounded-full text-[#1B3B2B] hover:bg-[#E8ECE6]"
                onClick={() => onReconnect(job.id)}>
                <RefreshCw className="h-3 w-3 mr-1" />Reconnect
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-3">
          <ScrollArea className="h-52 sm:h-64 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0]">
            <div className="p-3 space-y-0.5">
              {logs.length === 0
                ? <p className="text-xs text-[#55635B] font-mono">
                    {job.status === 'running' ? 'Waiting for events…' : 'No log available.'}
                  </p>
                : logs.map((line, i) => <LogRow key={i} line={line} />)
              }
              <div ref={logsEndRef} />
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function FineTunePage() {
  const [models, setModels] = useState<SupportedModel[]>([])
  const [jobs, setJobs] = useState<FTJob[]>([])
  const [selectedJob, setSelectedJob] = useState<FTJob | null>(null)
  const [logs, setLogs] = useState<LogLine[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [tab, setTab] = useState<'jobs' | 'new'>('jobs')
  const [mobileSheet, setMobileSheet] = useState(false)
  const [formError, setFormError] = useState('')
  const { toasts, push: toast } = useToast()
  const wsRef = useRef<WebSocket | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const [form, setForm] = useState({
    dataset_path: '', dataset_id: '',
    base_model: 'HuggingFaceTB/SmolLM2-1.7B-Instruct',
    output_model_name: '', lora_r: 16, lora_alpha: 32,
    num_train_epochs: 3, per_device_train_batch_size: 4,
    gradient_accumulation_steps: 4, learning_rate: 0.0002,
    load_in_4bit: true, bf16: true,
    push_to_hub: false, hf_token: '', hf_org: '',
    chat_template: 'alpaca', output_dir: 'outputs/finetune',
  })

  const lossHistory = useMemo(() =>
    logs.filter(l => l.type === 'progress' && l.loss != null).slice(-40).map(l => l.loss as number),
    [logs])

  const counts = useMemo(() => ({
    pending:   jobs.filter(j => j.status === 'pending').length,
    running:   jobs.filter(j => j.status === 'running').length,
    completed: jobs.filter(j => j.status === 'completed').length,
    failed:    jobs.filter(j => j.status === 'failed').length,
  }), [jobs])

  // ── Data ──────────────────────────────────────────────────────────────────

  const fetchJobs = useCallback(async () => {
    try {
      const res = await api.listFineTuneJobs()
      const raw = res?.jobs || (Array.isArray(res) ? res : [])
      if (Array.isArray(raw)) setJobs(raw)
    } catch {}
  }, [])

  useEffect(() => {
    ;(async () => {
      try {
        const m = await api.getSupportedModels()
        const rawModels = m?.models || (Array.isArray(m) ? m : [])
        if (Array.isArray(rawModels)) setModels(rawModels)
      } catch {}
      await fetchJobs()
      setLoading(false)
    })()
  }, [fetchJobs])

  useEffect(() => {
    if (tab !== 'jobs') return
    const id = setInterval(fetchJobs, 5000)
    return () => clearInterval(id)
  }, [tab, fetchJobs])

  // ── WebSocket ─────────────────────────────────────────────────────────────

  const connectStream = useCallback((jobId: string) => {
    wsRef.current?.close()
    setLogs([])
    const ws = new WebSocket(
      `${API_BASE.replace(/^http/, 'ws')}/api/finetune/jobs/${jobId}/stream`
    )
    wsRef.current = ws
    ws.onmessage = e => {
      try {
        const ev = JSON.parse(e.data)
        if (ev.type === 'ping') return
        setLogs(p => [...p, { ...ev, timestamp: new Date().toISOString() }])
        if (ev.type === 'progress') {
          setSelectedJob(p =>
            p ? {
              ...p,
              progress: ev.progress ?? p.progress,
              current_epoch: Math.floor(ev.epoch ?? p.current_epoch),
              train_loss: ev.loss ?? p.train_loss,
            } : p
          )
        }
        if (ev.type === 'completed') { fetchJobs(); toast('Training completed!', 'success') }
        if (ev.type === 'error')     { fetchJobs(); toast(`Error: ${ev.message}`, 'error') }
        if (ev.type === 'cancelled') { fetchJobs() }
      } catch {}
    }
    ws.onerror = () => toast('Stream connection lost', 'error')
  }, [fetchJobs, toast])

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  useEffect(() => () => { wsRef.current?.close() }, [])

  // ── Actions ───────────────────────────────────────────────────────────────

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError('')
    if (!form.dataset_path && !form.dataset_id) {
      setFormError('Provide a Dataset Path or Dataset ID.')
      return
    }
    setSubmitting(true)
    try {
      const res = await api.createFineTuneJob(form)
      if (res) {
        await fetchJobs()
        setTab('jobs')
        setSelectedJob(res)
        connectStream(res.id)
        toast('Fine-tuning started', 'success')
      }
    } catch (err: any) {
      toast(`Failed: ${err?.message ?? err}`, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSelectJob = async (job: FTJob) => {
    setSelectedJob(job)
    setMobileSheet(true)
    const res = await api.getFineTuneJob(job.id)
    if (res) setSelectedJob(res)
    if (job.status === 'running') connectStream(job.id)
    else setLogs([])
  }

  const handleCancel = async (jobId: string) => {
    try {
      await api.cancelFineTuneJob(jobId)
      await fetchJobs()
      if (selectedJob?.id === jobId) setSelectedJob(null)
      toast('Job cancelled', 'info')
    } catch (err: any) {
      toast(`Cancel failed: ${err?.message ?? err}`, 'error')
    }
  }

  const copyPath = (text: string) => {
    navigator.clipboard.writeText(text).then(() => toast('Copied!', 'success'))
  }

  const f = (key: keyof typeof form, val: unknown) =>
    setForm(p => ({ ...p, [key]: val }))

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">

      {/* Toast stack */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className={clsx(
            'pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-full border shadow-lg text-xs font-semibold animate-slide-in',
            t.variant === 'success' && 'bg-emerald-900 text-white border-emerald-700',
            t.variant === 'error'   && 'bg-rose-900 text-white border-rose-700',
            t.variant === 'info'    && 'bg-white text-[#1B3B2B] border-[#D1D8CE]',
          )}>
            {t.variant === 'success' && <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />}
            {t.variant === 'error'   && <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />}
            {t.message}
          </div>
        ))}
      </div>

      {/* Mobile bottom sheet */}
      <div className={clsx(
        'fixed inset-x-0 bottom-0 z-40 bg-white border-t border-[#E2E6E0] rounded-t-3xl shadow-2xl transition-transform duration-300 lg:hidden overflow-y-auto',
        mobileSheet && selectedJob ? 'translate-y-0' : 'translate-y-full',
      )} style={{ maxHeight: '88vh' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#E2E6E0] sticky top-0 bg-white z-10">
          <span className="font-bold text-sm text-[#1B3B2B] truncate">
            {selectedJob?.output_model_name || selectedJob?.id.slice(0, 12)}
          </span>
          <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full text-[#1B3B2B]"
            onClick={() => setMobileSheet(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="p-4">
          {selectedJob && (
            <DetailPane
              job={selectedJob} logs={logs} lossHistory={lossHistory}
              onCancel={handleCancel} onCopy={copyPath}
              onReconnect={connectStream} logsEndRef={logsEndRef}
            />
          )}
        </div>
      </div>

      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E6E0] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-bold uppercase tracking-wider">
              PEFT / LoRA Fine-Tuning
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">
              Fine-Tune Studio
            </h1>
          </div>
          <p className="text-xs text-[#55635B]">
            PEFT/LoRA fine-tuning & adapter optimization on synthetic datasets
          </p>
        </div>
        <div className="flex gap-2 self-start sm:self-auto">
          <Button variant={tab === 'jobs' ? 'default' : 'outline'} size="sm" className="rounded-full text-xs"
            onClick={() => setTab('jobs')}>
            <List className="h-3.5 w-3.5 mr-1" />Jobs
          </Button>
          <Button variant={tab === 'new' ? 'default' : 'outline'} size="sm" className="rounded-full text-xs"
            onClick={() => setTab('new')}>
            <Plus className="h-3.5 w-3.5 mr-1" />New Job
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {(
          [
            { key: 'pending',   label: 'Pending',   stripe: 'border-l-amber-500' },
            { key: 'running',   label: 'Running',   stripe: 'border-l-[#1B3B2B]'   },
            { key: 'completed', label: 'Completed', stripe: 'border-l-emerald-500'  },
            { key: 'failed',    label: 'Failed',    stripe: 'border-l-rose-500'    },
          ] as const
        ).map(({ key, label, stripe }) => (
          <Card key={key} className={clsx('border-l-4 bg-white border-[#E2E6E0] rounded-2xl card-shadow', stripe)}>
            <CardContent className="pt-4 pb-4 px-4">
              <p className="text-xs text-[#55635B] font-mono uppercase tracking-wider">{label}</p>
              <p className="text-2xl font-bold font-mono text-[#1B3B2B] mt-0.5">{counts[key]}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── New job form ── */}
      {tab === 'new' && (
        <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
          <CardHeader className="pb-3 border-b border-[#E2E6E0]">
            <CardTitle className="text-base font-bold text-[#1B3B2B]">Configure Fine-Tuning Job</CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && (
                <div className="flex items-center gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-xl px-3 py-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {formError}
                </div>
              )}

              <Section title="Dataset Source">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs mb-1 block font-bold text-[#1B3B2B]">JSONL file path</label>
                    <Input placeholder="outputs/my-dataset.jsonl" className="rounded-full border-[#D1D8CE] text-xs"
                      value={form.dataset_path}
                      onChange={e => f('dataset_path', e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs mb-1 block font-bold text-[#1B3B2B]">Or Dataset ID (from DB)</label>
                    <Input placeholder="17487774-1b8e-..." className="rounded-full border-[#D1D8CE] text-xs"
                      value={form.dataset_id}
                      onChange={e => f('dataset_id', e.target.value)} />
                  </div>
                </div>
              </Section>

              <Section title="Base Model">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs mb-1 block font-bold text-[#1B3B2B]">Model</label>
                    <Select value={form.base_model}
                      onValueChange={v => f('base_model', v)}>
                      <SelectTrigger className="rounded-full border-[#D1D8CE] text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {models.map(m => (
                          <SelectItem key={m.id} value={m.id}>
                            {m.name} ({m.params}) {m.requires_gpu ? '🖥' : '💻'}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <label className="text-xs mb-1 block font-bold text-[#1B3B2B]">Output model name</label>
                    <Input placeholder="my-finetuned-model" className="rounded-full border-[#D1D8CE] text-xs"
                      value={form.output_model_name}
                      onChange={e => f('output_model_name', e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs mb-1 block font-bold text-[#1B3B2B]">Chat template</label>
                    <Select value={form.chat_template}
                      onValueChange={v => f('chat_template', v)}>
                      <SelectTrigger className="rounded-full border-[#D1D8CE] text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="alpaca">Alpaca</SelectItem>
                        <SelectItem value="chatml">ChatML</SelectItem>
                        <SelectItem value="llama3">Llama 3</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </Section>

              <Section title="Training Hyperparameters" defaultOpen={false}>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                  {([
                    { key: 'num_train_epochs',            label: 'Epochs',        tip: 'Full passes over dataset',          int: true  },
                    { key: 'per_device_train_batch_size', label: 'Batch size',    tip: 'Samples per GPU per step',          int: true  },
                    { key: 'gradient_accumulation_steps', label: 'Grad accum',    tip: 'Steps before weight update',        int: true  },
                    { key: 'learning_rate',               label: 'Learning rate', tip: 'AdamW LR (1e-4 to 5e-4 typical)',  int: false },
                    { key: 'lora_r',                      label: 'LoRA r',        tip: 'LoRA rank (higher = more params)',  int: true  },
                    { key: 'lora_alpha',                  label: 'LoRA alpha',    tip: 'LoRA scaling (usually 2× rank)',    int: true  },
                  ] as const).map(({ key, label, tip, int: isInt }) => (
                    <div key={key}>
                      <label className="text-xs mb-1 block font-bold text-[#1B3B2B]" title={tip}>
                        {label}
                      </label>
                      <Input
                        type="number"
                        className="rounded-full border-[#D1D8CE] text-xs"
                        step={isInt ? 1 : 0.00001}
                        value={(form as Record<string, unknown>)[key] as number}
                        onChange={e => f(
                          key as keyof typeof form,
                          isInt ? parseInt(e.target.value) : parseFloat(e.target.value)
                        )}
                      />
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap gap-6 pt-2">
                  {([
                    { key: 'load_in_4bit', label: '4-bit quantisation' },
                    { key: 'bf16',         label: 'BF16 mixed precision' },
                  ] as const).map(({ key, label }) => (
                    <div key={key} className="flex items-center gap-2">
                      <Switch
                        id={key}
                        checked={form[key] as boolean}
                        onCheckedChange={v => f(key, v)}
                      />
                      <label htmlFor={key} className="text-xs text-[#55635B] cursor-pointer">
                        {label}
                      </label>
                    </div>
                  ))}
                </div>
              </Section>

              <Section title="HuggingFace Hub" defaultOpen={false}>
                <div className="flex items-center gap-2 mb-2">
                  <Switch id="push_hub" checked={form.push_to_hub}
                    onCheckedChange={v => f('push_to_hub', v)} />
                  <label htmlFor="push_hub" className="text-xs text-[#55635B] cursor-pointer">
                    Push to Hub after training
                  </label>
                </div>
                {form.push_to_hub && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs mb-1 block font-bold text-[#1B3B2B]">HF Token</label>
                      <Input type="password" placeholder="hf_..." className="rounded-full border-[#D1D8CE] text-xs"
                        value={form.hf_token}
                        onChange={e => f('hf_token', e.target.value)} />
                    </div>
                    <div>
                      <label className="text-xs mb-1 block font-bold text-[#1B3B2B]">Org (optional)</label>
                      <Input placeholder="my-org" className="rounded-full border-[#D1D8CE] text-xs"
                        value={form.hf_org}
                        onChange={e => f('hf_org', e.target.value)} />
                    </div>
                  </div>
                )}
              </Section>

              <Button type="submit" disabled={submitting}
                className="w-full bg-[#1B3B2B] hover:bg-[#142D21] text-white rounded-full font-medium">
                {submitting
                  ? <><Loader2 className="h-4 w-4 animate-spin mr-2 text-emerald-400" />Starting…</>
                  : <><Play className="h-4 w-4 mr-2 text-emerald-400" />Start Fine-Tuning</>}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {/* ── Jobs view ── */}
      {tab === 'jobs' && (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
          {/* List */}
          <div className="lg:col-span-2 space-y-2">
            {loading
              ? Array.from({ length: 4 }).map((_, i) => <JobSkeleton key={i} />)
              : jobs.length === 0
                ? (
                  <div className="flex flex-col items-center justify-center py-16 space-y-4 bg-white rounded-2xl border border-[#E2E6E0]">
                    <div className="w-14 h-14 rounded-2xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                      <Cpu className="h-7 w-7 text-[#1B3B2B]" />
                    </div>
                    <p className="text-xs text-[#55635B] font-mono">No fine-tuning jobs yet</p>
                    <Button size="sm" className="bg-[#1B3B2B] hover:bg-[#142D21] text-white rounded-full" onClick={() => setTab('new')}>
                      <Plus className="h-3.5 w-3.5 mr-1 text-emerald-400" />Create first job
                    </Button>
                  </div>
                )
                : jobs.map(job => (
                  <div
                    key={job.id}
                    onClick={() => handleSelectJob(job)}
                    className={clsx(
                      'border-l-4 rounded-xl p-3.5 cursor-pointer transition-all',
                      'bg-white border border-[#E2E6E0] card-shadow',
                      'hover:border-[#D1D8CE] hover:bg-[#F6F7F4]',
                      STATUS_STRIPE[job.status],
                      selectedJob?.id === job.id && 'border-[#1B3B2B] bg-[#E8ECE6]/40',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-[#1B3B2B] truncate">
                          {job.output_model_name || job.id.slice(0, 8)}
                        </p>
                        <p className="text-[11px] text-[#55635B] font-mono truncate mt-0.5">
                          {job.base_model}
                        </p>
                      </div>
                      <StatusPill status={job.status} />
                    </div>
                    {job.status === 'running' && (
                      <div className="mt-2 space-y-1">
                        <Progress value={job.progress ?? 0} className="h-1.5 bg-[#E8ECE6]" />
                        <p className="text-[11px] font-mono text-[#55635B]">
                          {(job.progress ?? 0).toFixed(0)}% · epoch {job.current_epoch}/{job.total_epochs}
                        </p>
                      </div>
                    )}
                    <p className="text-[10px] font-mono text-[#809085] mt-1.5">
                      {fmtDate(job.created_at)}
                    </p>
                  </div>
                ))
            }
          </div>

          {/* Desktop detail */}
          <div className="lg:col-span-3 hidden lg:block">
            {selectedJob
              ? (
                <DetailPane
                  job={selectedJob} logs={logs} lossHistory={lossHistory}
                  onCancel={handleCancel} onCopy={copyPath}
                  onReconnect={connectStream} logsEndRef={logsEndRef}
                />
              )
              : (
                <div className="flex flex-col items-center justify-center h-full min-h-[420px] border border-dashed border-[#D1D8CE] bg-white rounded-2xl gap-3">
                  <Cpu className="h-10 w-10 text-[#809085]" />
                  <p className="text-xs text-[#55635B] font-mono">
                    Select a job to view details &amp; live logs
                  </p>
                </div>
              )}
          </div>
        </div>
      )}
    </div>
  )
}
