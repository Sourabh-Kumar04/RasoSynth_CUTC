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
  if (data.length < 2) return <span className="text-xs text-muted-foreground">—</span>
  const W = 80, H = 28, PAD = 2
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1
  const pts = data.map((v, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2)
    const y = H - PAD - ((v - min) / range) * (H - PAD * 2)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return (
    <svg width={W} height={H} className="inline-block align-middle">
      <polyline points={pts} fill="none" stroke="rgb(249 115 22)"
        strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_PILL: Record<FTJob['status'], string> = {
  pending:   'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  running:   'bg-blue-500/15 text-blue-300 border-blue-500/30',
  completed: 'bg-green-500/15 text-green-300 border-green-500/30',
  failed:    'bg-red-500/15 text-red-300 border-red-500/30',
  cancelled: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
}

const STATUS_STRIPE: Record<FTJob['status'], string> = {
  pending: 'border-l-yellow-500', running: 'border-l-blue-500',
  completed: 'border-l-green-500', failed: 'border-l-red-500',
  cancelled: 'border-l-zinc-500',
}

function StatusPill({ status }: { status: FTJob['status'] }) {
  return (
    <span className={clsx('inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border font-medium shrink-0', STATUS_PILL[status])}>
      {status === 'running' && (
        <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
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
    <div className="rounded-lg border border-border/50 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-surface/40 hover:bg-surface/70 transition-colors text-left"
      >
        <span className="text-sm font-medium">{title}</span>
        {open
          ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
      </button>
      {open && <div className="px-4 py-3 space-y-3">{children}</div>}
    </div>
  )
}

// ── Log line renderer ─────────────────────────────────────────────────────────

const LOG_COLOR: Record<string, string> = {
  error: 'text-red-400', completed: 'text-green-400', pushed: 'text-green-300',
  progress: 'text-blue-300', eval: 'text-purple-300', saved: 'text-teal-300',
  started: 'text-orange-300', checkpoint: 'text-yellow-300', cancelled: 'text-zinc-400',
}

function LogRow({ line }: { line: LogLine }) {
  const color = LOG_COLOR[line.type] ?? 'text-muted-foreground'
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
      <span className="text-muted-foreground/40 select-none">
        [{line.timestamp?.slice(11, 19)}]{' '}
      </span>
      {text}
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function JobSkeleton() {
  return (
    <div className="rounded-lg border-l-4 border-l-border border border-border p-3 space-y-2">
      <div className="flex justify-between">
        <Skeleton className="h-3.5 w-32" />
        <Skeleton className="h-4 w-14 rounded-full" />
      </div>
      <Skeleton className="h-3 w-48" />
      <Skeleton className="h-1.5 w-full rounded-full" />
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
      <Card className="bg-surface/40 border-border">
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <CardTitle className="text-sm truncate max-w-[200px]">
              {job.output_model_name || job.id.slice(0, 16)}
            </CardTitle>
            <div className="flex items-center gap-2">
              <StatusPill status={job.status} />
              {(job.status === 'running' || job.status === 'pending') && (
                <Button variant="destructive" size="sm" onClick={() => onCancel(job.id)}>
                  <Square className="h-3 w-3 mr-1" />Cancel
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {job.status === 'running' && <Progress value={job.progress} className="h-2" />}

          {lossHistory.length > 1 && (
            <div className="flex items-center gap-3 bg-background/50 rounded-lg px-3 py-2 border border-border/40">
              <span className="text-xs text-muted-foreground shrink-0">Loss</span>
              <LossSparkline data={lossHistory} />
              <span className="text-xs font-mono text-orange-400 shrink-0">
                {lossHistory[lossHistory.length - 1]?.toFixed(4)}
              </span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            <div><span className="text-muted-foreground">Model </span>{job.base_model}</div>
            <div><span className="text-muted-foreground">Epochs </span>
              <span className="font-mono">{job.current_epoch}/{job.total_epochs}</span>
            </div>
            <div><span className="text-muted-foreground">Train loss </span>
              <span className="font-mono">{job.train_loss?.toFixed(4) ?? '—'}</span>
            </div>
            <div><span className="text-muted-foreground">Eval loss </span>
              <span className="font-mono">{job.eval_loss?.toFixed(4) ?? '—'}</span>
            </div>
            <div><span className="text-muted-foreground">Started </span>{fmtDate(job.started_at)}</div>
            <div><span className="text-muted-foreground">Done </span>{fmtDate(job.completed_at)}</div>
          </div>

          {job.error && (
            <div className="flex items-start gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              {job.error}
            </div>
          )}

          {job.hf_repo_url && (
            <a href={job.hf_repo_url} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-orange-400 hover:underline">
              <ExternalLink className="h-3 w-3" />View on HuggingFace Hub
            </a>
          )}

          {job.output_path && (
            <div className="flex items-center gap-2">
              <code className="text-xs font-mono bg-background/60 px-2 py-0.5 rounded border border-border/40 truncate max-w-[260px]">
                {job.output_path}
              </code>
              <Button variant="ghost" size="icon" className="h-6 w-6 shrink-0"
                onClick={() => onCopy(job.output_path!)}>
                <Copy className="h-3 w-3" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="bg-surface/40 border-border">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">Training Log</CardTitle>
            {job.status === 'running' && (
              <Button variant="ghost" size="sm" className="h-7 text-xs"
                onClick={() => onReconnect(job.id)}>
                <RefreshCw className="h-3 w-3 mr-1" />Reconnect
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-3 pt-0">
          <ScrollArea className="h-52 sm:h-64 rounded-md bg-background border border-border/40">
            <div className="p-3 space-y-0.5">
              {logs.length === 0
                ? <p className="text-xs text-muted-foreground">
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
    <div className="space-y-5 animate-fade-in">

      {/* Toast stack */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className={clsx(
            'pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-lg border shadow-lg text-sm font-medium animate-slide-in',
            t.variant === 'success' && 'bg-green-950/95 border-green-600/40 text-green-200',
            t.variant === 'error'   && 'bg-red-950/95 border-red-600/40 text-red-200',
            t.variant === 'info'    && 'bg-surface border-border text-foreground',
          )}>
            {t.variant === 'success' && <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />}
            {t.variant === 'error'   && <AlertCircle className="h-3.5 w-3.5 shrink-0" />}
            {t.message}
          </div>
        ))}
      </div>

      {/* Mobile bottom sheet */}
      <div className={clsx(
        'fixed inset-x-0 bottom-0 z-40 bg-background border-t border-border rounded-t-2xl shadow-2xl transition-transform duration-300 lg:hidden overflow-y-auto',
        mobileSheet && selectedJob ? 'translate-y-0' : 'translate-y-full',
      )} style={{ maxHeight: '88vh' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border sticky top-0 bg-background z-10">
          <span className="font-medium text-sm truncate">
            {selectedJob?.output_model_name || selectedJob?.id.slice(0, 12)}
          </span>
          <Button variant="ghost" size="icon" className="h-7 w-7"
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Cpu className="h-5 w-5 sm:h-6 sm:w-6 text-orange-400" />
            Fine-Tune Studio
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            PEFT/LoRA fine-tuning on generated datasets
          </p>
        </div>
        <div className="flex gap-2 self-start sm:self-auto">
          <Button variant={tab === 'jobs' ? 'default' : 'outline'} size="sm"
            onClick={() => setTab('jobs')}>
            <List className="h-3.5 w-3.5 mr-1" />Jobs
          </Button>
          <Button variant={tab === 'new' ? 'default' : 'outline'} size="sm"
            onClick={() => setTab('new')}>
            <Plus className="h-3.5 w-3.5 mr-1" />New Job
          </Button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {(
          [
            { key: 'pending',   label: 'Pending',   stripe: 'border-l-yellow-500' },
            { key: 'running',   label: 'Running',   stripe: 'border-l-blue-500'   },
            { key: 'completed', label: 'Completed', stripe: 'border-l-green-500'  },
            { key: 'failed',    label: 'Failed',    stripe: 'border-l-red-500'    },
          ] as const
        ).map(({ key, label, stripe }) => (
          <Card key={key} className={clsx('border-l-4 bg-surface/40 border-border', stripe)}>
            <CardContent className="pt-3 pb-3 px-4">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="text-2xl font-bold mt-0.5">{counts[key]}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── New job form ── */}
      {tab === 'new' && (
        <Card className="bg-surface/40 border-border">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Configure Fine-Tuning Job</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && (
                <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {formError}
                </div>
              )}

              <Section title="Dataset Source">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs mb-1 block text-muted-foreground">JSONL file path</label>
                    <Input placeholder="outputs/my-dataset.jsonl"
                      value={form.dataset_path}
                      onChange={e => f('dataset_path', e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs mb-1 block text-muted-foreground">Or Dataset ID (from DB)</label>
                    <Input placeholder="17487774-1b8e-..."
                      value={form.dataset_id}
                      onChange={e => f('dataset_id', e.target.value)} />
                  </div>
                </div>
              </Section>

              <Section title="Base Model">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs mb-1 block text-muted-foreground">Model</label>
                    <Select value={form.base_model}
                      onValueChange={v => f('base_model', v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
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
                    <label className="text-xs mb-1 block text-muted-foreground">Output model name</label>
                    <Input placeholder="my-finetuned-model"
                      value={form.output_model_name}
                      onChange={e => f('output_model_name', e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs mb-1 block text-muted-foreground">Chat template</label>
                    <Select value={form.chat_template}
                      onValueChange={v => f('chat_template', v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
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
                      <label className="text-xs mb-1 block text-muted-foreground" title={tip}>
                        {label}
                      </label>
                      <Input
                        type="number"
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
                      <label htmlFor={key} className="text-sm text-muted-foreground cursor-pointer">
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
                  <label htmlFor="push_hub" className="text-sm text-muted-foreground cursor-pointer">
                    Push to Hub after training
                  </label>
                </div>
                {form.push_to_hub && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs mb-1 block text-muted-foreground">HF Token</label>
                      <Input type="password" placeholder="hf_..."
                        value={form.hf_token}
                        onChange={e => f('hf_token', e.target.value)} />
                    </div>
                    <div>
                      <label className="text-xs mb-1 block text-muted-foreground">Org (optional)</label>
                      <Input placeholder="my-org"
                        value={form.hf_org}
                        onChange={e => f('hf_org', e.target.value)} />
                    </div>
                  </div>
                )}
              </Section>

              <Button type="submit" disabled={submitting}
                className="w-full bg-orange-600 hover:bg-orange-700 text-white">
                {submitting
                  ? <><Loader2 className="h-4 w-4 animate-spin mr-2" />Starting…</>
                  : <><Play className="h-4 w-4 mr-2" />Start Fine-Tuning</>}
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
                  <div className="flex flex-col items-center justify-center py-16 space-y-4">
                    <div className="w-14 h-14 rounded-2xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
                      <Cpu className="h-7 w-7 text-orange-400/70" />
                    </div>
                    <p className="text-sm text-muted-foreground">No fine-tuning jobs yet</p>
                    <Button size="sm" onClick={() => setTab('new')}>
                      <Plus className="h-3.5 w-3.5 mr-1" />Create first job
                    </Button>
                  </div>
                )
                : jobs.map(job => (
                  <div
                    key={job.id}
                    onClick={() => handleSelectJob(job)}
                    className={clsx(
                      'border-l-4 rounded-lg p-3 cursor-pointer transition-all',
                      'bg-surface/40 border border-border',
                      'hover:border-orange-500/40 hover:bg-surface/70',
                      STATUS_STRIPE[job.status],
                      selectedJob?.id === job.id && 'border-orange-500/60 bg-orange-500/5',
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">
                          {job.output_model_name || job.id.slice(0, 8)}
                        </p>
                        <p className="text-xs text-muted-foreground truncate mt-0.5">
                          {job.base_model}
                        </p>
                      </div>
                      <StatusPill status={job.status} />
                    </div>
                    {job.status === 'running' && (
                      <div className="mt-2 space-y-1">
                        <Progress value={job.progress} className="h-1.5" />
                        <p className="text-xs text-muted-foreground">
                          {job.progress.toFixed(0)}% · epoch {job.current_epoch}/{job.total_epochs}
                        </p>
                      </div>
                    )}
                    <p className="text-xs text-muted-foreground/50 mt-1.5">
                      {fmtDate(job.created_at)}
                    </p>
                    {/* Mobile CTA */}
                    <Button
                      variant="ghost" size="sm"
                      className="w-full mt-1.5 lg:hidden text-xs h-7 border border-border/40"
                      onClick={e => { e.stopPropagation(); handleSelectJob(job) }}
                    >
                      View details →
                    </Button>
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
                <div className="flex flex-col items-center justify-center h-full min-h-[420px] border border-dashed border-border rounded-xl gap-3">
                  <Cpu className="h-10 w-10 text-muted-foreground/20" />
                  <p className="text-sm text-muted-foreground">
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
