'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ClipboardCheck, CheckCircle2, XCircle, Flag, Pencil,
  ChevronLeft, ChevronRight, RefreshCw, Play,
  Loader2, AlertCircle, X, Download, CheckSquare, Square,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api/client'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReviewItem {
  id: string; job_id: string; dataset_id: string
  instruction: string; response: string
  source_url: string; source_text: string
  quality_score: number; hallucination_risk: number
  duplicate_score: number; diversity_score: number
  review_status: 'pending' | 'in_review' | 'approved' | 'rejected' | 'flagged'
  review_decision: string | null; review_notes: string
  reviewed_by: string; review_timestamp: string | null
  edited_instruction: string | null; edited_response: string | null
  created_at: string
}

interface ReviewStats {
  total: number; pending: number; in_review: number
  approved: number; rejected: number; flagged: number
  approval_rate: number; rejection_rate: number
}

interface QueueResp {
  items: ReviewItem[]; total: number; page: number; page_size: number; total_pages: number
}

interface Toast { id: number; message: string; variant: 'success' | 'error' | 'info' }

// ── Toast hook ────────────────────────────────────────────────────────────────

function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])
  const ctr = useRef(0)
  const push = useCallback((message: string, variant: Toast['variant'] = 'info') => {
    const id = ++ctr.current
    setToasts(p => [...p, { id, message, variant }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500)
  }, [])
  return { toasts, push }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUS_PILL: Record<ReviewItem['review_status'], string> = {
  pending:   'bg-amber-950/30 text-amber-400 border-amber-500/40',
  in_review: 'bg-emerald-950/40 text-[#10b981] border-emerald-500/40',
  approved:  'bg-emerald-950/30 text-emerald-400 border-emerald-500/40',
  rejected:  'bg-rose-950/30 text-rose-400 border-rose-500/40',
  flagged:   'bg-amber-950/30 text-amber-300 border-amber-500/40',
}
const STATUS_STRIPE: Record<ReviewItem['review_status'], string> = {
  pending: 'border-l-amber-500', in_review: 'border-l-[#10b981]',
  approved: 'border-l-emerald-500', rejected: 'border-l-rose-500', flagged: 'border-l-amber-600',
}

function difficulty(q: number) {
  if (q >= 0.75) return { label: 'Easy', color: 'text-emerald-400' }
  if (q >= 0.45) return { label: 'Med',  color: 'text-amber-400' }
  return { label: 'Hard', color: 'text-rose-400' }
}

// Mini score bar (5 segments, colored based on value)
function ScoreBar({ value, inverted = false }: { value: number; inverted?: boolean }) {
  const pct = inverted ? 1 - value : value
  const segs = 5
  const filled = Math.round(pct * segs)
  const color = pct >= 0.7 ? 'bg-emerald-500' : pct >= 0.4 ? 'bg-amber-500' : 'bg-rose-500'
  return (
    <div className="flex gap-0.5 items-center">
      {Array.from({ length: segs }).map((_, i) => (
        <div key={i} className={clsx('h-1.5 w-2 rounded-sm', i < filled ? color : 'bg-[#161622]')} />
      ))}
    </div>
  )
}

// SVG approval ring
function ApprovalRing({ pct }: { pct: number }) {
  const r = 16, circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  return (
    <svg width={44} height={44} className="-rotate-90">
      <circle cx={22} cy={22} r={r} fill="none" stroke="#272738" strokeWidth={4} />
      <circle cx={22} cy={22} r={r} fill="none" stroke="#10B981"
        strokeWidth={4} strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round" />
      <text x={22} y={22} dominantBaseline="middle" textAnchor="middle"
        className="fill-[#10b981] text-[9px] font-bold rotate-90"
        style={{ transform: 'rotate(90deg)', transformOrigin: '22px 22px', fontSize: 9 }}>
        {Math.round(pct)}%
      </text>
    </svg>
  )
}

const REVIEWER_KEY = 'raso_reviewer_name'

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ReviewPage() {
  const [stats, setStats]           = useState<ReviewStats | null>(null)
  const [queue, setQueue]           = useState<QueueResp | null>(null)
  const [selected, setSelected]     = useState<ReviewItem | null>(null)
  const [loading, setLoading]       = useState(true)
  const [actionLoading, setAction]  = useState(false)
  const [statusFilter, setStatus]   = useState('pending')
  const [jobFilter, setJobFilter]   = useState('')
  const [page, setPage]             = useState(1)
  const [mobileSheet, setSheet]     = useState(false)

  // Edit state
  const [editing, setEditing]               = useState(false)
  const [editInstruction, setEditInst]      = useState('')
  const [editResponse, setEditResp]         = useState('')
  const [notes, setNotes]                   = useState('')
  const [reviewer, setReviewer]             = useState('human-reviewer')

  // Bulk select
  const [selected2, setSelected2] = useState<Set<string>>(new Set())
  // HITL: jobs currently paused at the review gate
  const [pausedJobs, setPausedJobs] = useState<string[]>([])

  const { toasts, push: toast } = useToast()
  const PAGE_SIZE = 20

  // ── Load reviewer name from localStorage ─────────────────────────────────

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(REVIEWER_KEY)
      if (saved) setReviewer(saved)
    }
  }, [])
  const saveReviewer = (v: string) => {
    setReviewer(v)
    if (typeof window !== 'undefined') localStorage.setItem(REVIEWER_KEY, v)
  }

  // ── Data fetch ────────────────────────────────────────────────────────────

  const fetchStats = useCallback(async () => {
    try { const r = await api.getReviewStats(); if (r) setStats(r) } catch {}
  }, [])

  const fetchQueue = useCallback(async () => {
    try {
      const r = await api.getReviewQueue({
        status: statusFilter && statusFilter !== 'all' ? statusFilter : undefined,
        job_id: jobFilter || undefined,
        page, page_size: PAGE_SIZE,
      })
      if (r) setQueue(r)
    } catch {}
  }, [statusFilter, jobFilter, page])

  const fetchPaused = useCallback(async () => {
    try {
      const data = await api.getPausedReviewJobs()
      setPausedJobs(Array.isArray(data?.paused_jobs) ? data.paused_jobs : [])
    } catch {}
  }, [])

  useEffect(() => {
    ;(async () => {
      await Promise.all([fetchStats(), fetchQueue(), fetchPaused()])
      setLoading(false)
    })()
  }, [fetchStats, fetchQueue, fetchPaused])

  useEffect(() => {
    const id = setInterval(() => { fetchStats(); fetchQueue(); fetchPaused() }, 12000)
    return () => clearInterval(id)
  }, [fetchStats, fetchQueue, fetchPaused])

  // ── Keyboard shortcuts ────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!selected || editing) return
      if ((e.target as HTMLElement).tagName === 'INPUT' ||
          (e.target as HTMLElement).tagName === 'TEXTAREA') return
      if (e.key === 'a') act('approve', selected)
      if (e.key === 'r') act('reject', selected)
      if (e.key === 'e') { setEditing(true); setSheet(true) }
      if (e.key === 'f') act('flag', selected)
      if (e.key === 'Escape') { setSelected(null); setSheet(false) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selected, editing])

  // ── Queue navigation ──────────────────────────────────────────────────────

  const queueItems = queue?.items ?? []
  const currentIdx = selected ? queueItems.findIndex(i => i.id === selected.id) : -1

  const navigateTo = (idx: number) => {
    if (idx >= 0 && idx < queueItems.length) selectItem(queueItems[idx])
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  const act = useCallback(async (
    action: 'approve' | 'reject' | 'flag' | 'edit', item: ReviewItem
  ) => {
    setAction(true)
    try {
      if (action === 'approve') await api.approveReviewItem(item.id, reviewer, notes)
      else if (action === 'reject') await api.rejectReviewItem(item.id, reviewer, notes)
      else if (action === 'flag')   await api.flagReviewItem(item.id, reviewer, notes)
      else if (action === 'edit') {
        await api.editReviewItem(item.id, reviewer,
          editInstruction || undefined, editResponse || undefined, notes)
        setEditing(false)
      }
      toast(action === 'approve' ? 'Approved ✓' : action === 'reject' ? 'Rejected' : action === 'flag' ? 'Flagged' : 'Saved & approved', 'success')
      setSelected(null); setSheet(false); setNotes('')
      await Promise.all([fetchStats(), fetchQueue()])
    } catch (err: any) {
      toast(`Failed: ${err?.message ?? err}`, 'error')
    } finally {
      setAction(false)
    }
  }, [reviewer, notes, editInstruction, editResponse, fetchStats, fetchQueue, toast])

  const bulkAct = async (type: 'approve' | 'reject') => {
    if (selected2.size === 0) return
    setAction(true)
    let ok = 0
    for (const id of Array.from(selected2)) {
      try {
        if (type === 'approve') await api.approveReviewItem(id, reviewer, 'bulk')
        else await api.rejectReviewItem(id, reviewer, 'bulk')
        ok++
      } catch {}
    }
    toast(`${type === 'approve' ? 'Approved' : 'Rejected'} ${ok} items`, 'success')
    setSelected2(new Set())
    await Promise.all([fetchStats(), fetchQueue()])
    setAction(false)
  }

  const resumeJob = async (jobId: string) => {
    try {
      await api.resumeHITLJob(jobId)
      toast(`Job ${jobId.slice(0, 8)} resumed`, 'success')
    } catch (err: any) {
      toast(`Resume failed: ${err?.message ?? err}`, 'error')
    }
  }

  const selectItem = (item: ReviewItem) => {
    setSelected(item)
    setEditing(false); setNotes('')
    setEditInst(item.edited_instruction || item.instruction)
    setEditResp(item.edited_response || item.response)
    setSheet(true)
  }

  const toggleBulk = (id: string) => {
    setSelected2(p => {
      const n = new Set(p)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const exportApproved = () => {
    const url = `${API_BASE}/api/review/queue/export${jobFilter ? `?job_id=${jobFilter}` : ''}`
    window.open(url, '_blank')
  }

  const reviewProgress = stats
    ? Math.round((stats.approved / Math.max(stats.approved + stats.pending, 1)) * 100)
    : 0

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">
      {/* Toasts */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className={clsx(
            'pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-full border shadow-lg text-xs font-semibold animate-slide-in',
            t.variant === 'success' && 'bg-emerald-950/80 text-white border-emerald-500/40',
            t.variant === 'error'   && 'bg-rose-950/80 text-white border-rose-500/40',
            t.variant === 'info'    && 'bg-[#12121a] text-white border-[#272738]',
          )}>
            {t.variant === 'success' && <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[#10b981]" />}
            {t.variant === 'error'   && <AlertCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />}
            {t.message}
          </div>
        ))}
      </div>

      {/* Mobile detail sheet */}
      <div className={clsx(
        'fixed inset-x-0 bottom-0 z-40 bg-[#12121a] border-t border-[#272738] rounded-t-3xl shadow-2xl transition-transform duration-300 md:hidden overflow-y-auto',
        mobileSheet && selected ? 'translate-y-0' : 'translate-y-full',
      )} style={{ maxHeight: '90vh' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#272738] sticky top-0 bg-[#12121a] z-10">
          <div className="flex items-center gap-2">
            {currentIdx > 0 && (
              <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full text-[#94a3b8] hover:text-white"
                onClick={() => navigateTo(currentIdx - 1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}
            <span className="text-xs font-mono font-bold text-white">
              {currentIdx + 1}/{queueItems.length}
            </span>
            {currentIdx < queueItems.length - 1 && (
              <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full text-[#94a3b8] hover:text-white"
                onClick={() => navigateTo(currentIdx + 1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            )}
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7 rounded-full text-[#94a3b8] hover:text-white"
            onClick={() => { setSheet(false); setEditing(false) }}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="p-4">
          {selected && (
            <DetailPane
              item={selected} editing={editing} editInstruction={editInstruction}
              editResponse={editResponse} notes={notes} reviewer={reviewer}
              actionLoading={actionLoading}
              onAct={act} onSetEditing={setEditing}
              onEditInst={setEditInst} onEditResp={setEditResp}
              onNotes={setNotes} onReviewer={saveReviewer}
              onResume={resumeJob}
            />
          )}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected2.size > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-[#12121a] border border-[#272738] rounded-full px-5 py-2.5 shadow-xl animate-slide-in">
          <span className="text-xs font-mono font-bold text-white">{selected2.size} selected</span>
          <Button size="sm" className="bg-[#10b981] hover:bg-emerald-600 text-white h-7 text-xs rounded-full font-mono font-semibold"
            onClick={() => bulkAct('approve')} disabled={actionLoading}>
            <CheckCircle2 className="h-3 w-3 mr-1" />Approve all
          </Button>
          <Button size="sm" variant="destructive" className="h-7 text-xs rounded-full font-mono"
            onClick={() => bulkAct('reject')} disabled={actionLoading}>
            <XCircle className="h-3 w-3 mr-1" />Reject all
          </Button>
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0 rounded-full text-[#94a3b8] hover:text-white"
            onClick={() => setSelected2(new Set())}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#272738] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#161622] border border-[#272738] text-[#10b981] font-bold uppercase tracking-wider">
              Quality Inspection Queue
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              HITL Review Studio
            </h1>
          </div>
          <p className="text-xs text-[#94a3b8]">
            Review samples — <kbd className="text-[10px] bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">a</kbd> approve&nbsp;
            <kbd className="text-[10px] bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">r</kbd> reject&nbsp;
            <kbd className="text-[10px] bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">e</kbd> edit&nbsp;
            <kbd className="text-[10px] bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">f</kbd> flag
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" size="sm" className="rounded-full border-[#272738] text-white hover:bg-[#161622] font-mono text-xs" onClick={exportApproved}>
            <Download className="h-3.5 w-3.5 mr-1 text-[#10b981]" />Export Approved JSONL
          </Button>
          <Button variant="outline" size="sm" className="rounded-full border-[#272738] text-white hover:bg-[#161622] font-mono text-xs" onClick={async () => {
            setLoading(true)
            await Promise.all([fetchStats(), fetchQueue(), fetchPaused()])
            setLoading(false)
          }} disabled={loading}>
            <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#6366f1]', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* HITL paused jobs banner */}
      {pausedJobs.length > 0 && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-950/20 px-4 py-3">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-white">
                {pausedJobs.length} dataset job{pausedJobs.length > 1 ? 's' : ''} awaiting human review gate
              </p>
              <p className="text-xs text-[#94a3b8] mt-0.5">
                Approvals are applied automatically. Resuming wakes the job immediately to continue pipeline execution.
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                {pausedJobs.map(jid => (
                  <div key={jid} className="flex items-center gap-1.5 bg-[#0a0a0f] border border-amber-500/30 rounded-full px-3 py-1">
                    <span className="text-xs font-mono font-bold text-amber-300">{jid.slice(0, 8)}…</span>
                    <Button
                      variant="ghost" size="sm"
                      className="h-5 text-xs px-2 text-[#10b981] hover:bg-[#161622] rounded-full font-bold font-mono"
                      onClick={() => resumeJob(jid)}
                    >
                      <Play className="h-2.5 w-2.5 mr-1 fill-current text-[#10b981]" />Resume
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Review progress bar */}
      {stats && stats.total > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs font-mono text-[#94a3b8]">
            <span>Review progress</span>
            <span className="font-bold text-[#10b981]">{stats.approved} / {stats.approved + stats.pending} reviewed ({reviewProgress}%)</span>
          </div>
          <div className="h-2 bg-[#161622] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#10b981] rounded-full transition-all duration-700"
              style={{ width: `${reviewProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Stat cards */}
      {loading
        ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i} className="bg-[#12121a] border-[#272738] rounded-2xl">
                <CardContent className="pt-3 pb-3 px-4 space-y-2">
                  <Skeleton className="h-3 w-16 bg-[#161622]" />
                  <Skeleton className="h-6 w-10 bg-[#161622]" />
                </CardContent>
              </Card>
            ))}
          </div>
        )
        : stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {[
              { label: 'Total',     val: stats.total,     color: 'text-white', stripe: 'border-l-indigo-500' },
              { label: 'Pending',   val: stats.pending,   color: 'text-amber-400', stripe: 'border-l-amber-500' },
              { label: 'In Review', val: stats.in_review, color: 'text-cyan-400',  stripe: 'border-l-cyan-500'   },
              { label: 'Approved',  val: stats.approved,  color: 'text-[#10b981]', stripe: 'border-l-emerald-500'  },
              { label: 'Rejected',  val: stats.rejected,  color: 'text-rose-400', stripe: 'border-l-rose-500'    },
              { label: 'Flagged',   val: stats.flagged,   color: 'text-amber-400', stripe: 'border-l-amber-600' },
            ].map(({ label, val, color, stripe }) => (
              <Card key={label} className={clsx('border-l-4 bg-[#12121a] border-[#272738] rounded-2xl card-shadow animate-fade-in', stripe)}>
                <CardContent className="pt-3 pb-2 px-4">
                  <p className="text-[10px] text-[#94a3b8] font-mono uppercase">{label}</p>
                  <p className={clsx('text-xl font-bold font-mono mt-0.5', color)}>{val}</p>
                </CardContent>
              </Card>
            ))}
            <Card className="border-l-4 border-l-emerald-500 bg-[#12121a] border-[#272738] rounded-2xl card-shadow animate-fade-in col-span-2 sm:col-span-1">
              <CardContent className="pt-2 pb-2 px-3 flex items-center gap-3">
                <ApprovalRing pct={stats.approval_rate} />
                <div>
                  <p className="text-[10px] text-[#94a3b8] font-mono uppercase">Approval</p>
                  <p className="text-sm font-bold font-mono text-[#10b981]">{stats.approval_rate}%</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )
      }

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={statusFilter} onValueChange={v => { setStatus(v); setPage(1) }}>
          <SelectTrigger className="w-36 h-8 text-xs rounded-full border-[#272738] bg-[#0a0a0f] text-white font-mono">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="in_review">In Review</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
            <SelectItem value="flagged">Flagged</SelectItem>
          </SelectContent>
        </Select>
        <Input placeholder="Filter by Job ID" className="w-52 h-8 text-xs rounded-full border-[#272738] bg-[#0a0a0f] text-white font-mono focus:border-[#6366f1]"
          value={jobFilter} onChange={e => { setJobFilter(e.target.value); setPage(1) }} />
        {jobFilter && (
          <Button variant="outline" size="sm" className="h-8 rounded-full border-[#272738] text-white hover:bg-[#161622] font-mono text-xs"
            onClick={() => resumeJob(jobFilter)}>
            <Play className="h-3.5 w-3.5 mr-1 fill-current text-[#10b981]" />Resume Job
          </Button>
        )}
        {selected2.size > 0 && (
          <span className="text-xs font-mono font-bold text-white ml-auto">
            {selected2.size} selected
          </span>
        )}
      </div>

      {/* Main split: list + detail */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">

        {/* Queue list */}
        <div className="md:col-span-2 space-y-2">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border-l-4 border-l-[#3b3b52] border border-[#272738] bg-[#12121a] p-3 space-y-2 animate-pulse">
                <Skeleton className="h-3 w-full bg-[#161622]" />
                <Skeleton className="h-3 w-3/4 bg-[#161622]" />
                <div className="flex gap-1">
                  {Array.from({ length: 5 }).map((_, j) => <Skeleton key={j} className="h-1.5 w-2 rounded" />)}
                </div>
              </div>
            ))
            : !queue || !Array.isArray(queue.items) || queue.items.length === 0
              ? (
                <div className="flex flex-col items-center justify-center py-16 space-y-3 bg-[#12121a] rounded-2xl border border-[#272738]">
                  <ClipboardCheck className="h-10 w-10 text-[#64748b]" />
                  <p className="text-xs text-[#94a3b8] font-mono">No items match this filter</p>
                </div>
              )
              : (
                <>
                  {(queue.items || []).map((item, idx) => {
                    const diff = difficulty(item.quality_score)
                    const isChecked = selected2.has(item.id)
                    return (
                      <div
                        key={item.id}
                        className={clsx(
                          'border-l-4 rounded-xl p-3.5 cursor-pointer transition-all group',
                          'bg-[#12121a] border border-[#272738] card-shadow hover:border-[#3b3b52] hover:bg-[#0a0a0f]',
                          STATUS_STRIPE[item.review_status],
                          selected?.id === item.id && 'border-[#6366f1] bg-[#161622]/60',
                        )}
                        onClick={() => selectItem(item)}
                      >
                        <div className="flex items-start gap-2.5">
                          {/* Bulk checkbox */}
                          <button
                            className="mt-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-[#94a3b8] hover:text-white"
                            onClick={e => { e.stopPropagation(); toggleBulk(item.id) }}
                          >
                            {isChecked
                              ? <CheckSquare className="h-4 w-4 text-[#10b981]" />
                              : <Square className="h-4 w-4 text-[#64748b]" />}
                          </button>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-1">
                              <p className="text-xs font-semibold text-white group-hover:text-indigo-300 transition-colors line-clamp-2 flex-1 leading-4">
                                {item.instruction}
                              </p>
                              <span className={clsx('shrink-0 text-[10px] px-2 py-0.5 rounded-full border font-mono ml-1', STATUS_PILL[item.review_status])}>
                                {item.review_status}
                              </span>
                            </div>
                            {/* Score bars */}
                            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                              <div className="flex items-center gap-1">
                                <span className="text-[10px] font-mono text-[#94a3b8]">Q</span>
                                <ScoreBar value={item.quality_score} />
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="text-[10px] font-mono text-[#94a3b8]">Hall</span>
                                <ScoreBar value={item.hallucination_risk} inverted />
                              </div>
                              <span className={clsx('text-[10px] font-bold font-mono', diff.color)}>{diff.label}</span>
                            </div>
                            <p className="text-[10px] font-mono text-[#64748b] mt-1 truncate">
                              Job: {item.job_id.slice(0, 8)}
                            </p>
                          </div>
                        </div>
                      </div>
                    )
                  })}

                  {/* Pagination */}
                  <div className="flex items-center justify-between pt-1">
                    <Button variant="ghost" size="sm" className="rounded-full text-[#94a3b8] hover:text-white" disabled={page <= 1}
                      onClick={() => setPage(p => p - 1)}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-xs font-mono text-[#94a3b8]">
                      {page} / {queue.total_pages} ({queue.total})
                    </span>
                    <Button variant="ghost" size="sm" className="rounded-full text-[#94a3b8] hover:text-white" disabled={page >= queue.total_pages}
                      onClick={() => setPage(p => p + 1)}>
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </>
              )
          }
        </div>

        {/* Detail pane (desktop) */}
        <div className="md:col-span-3 hidden md:block">
          {selected
            ? (
              <div className="space-y-1">
                {/* Prev/Next navigation */}
                <div className="flex items-center justify-between mb-2">
                  <Button variant="ghost" size="sm" className="h-7 text-xs rounded-full text-[#94a3b8] hover:text-white font-mono"
                    disabled={currentIdx <= 0}
                    onClick={() => navigateTo(currentIdx - 1)}>
                    <ChevronLeft className="h-3.5 w-3.5 mr-1" />Prev
                  </Button>
                  <span className="text-xs font-mono text-[#94a3b8]">
                    {currentIdx + 1} / {queueItems.length}
                  </span>
                  <Button variant="ghost" size="sm" className="h-7 text-xs rounded-full text-[#94a3b8] hover:text-white font-mono"
                    disabled={currentIdx >= queueItems.length - 1}
                    onClick={() => navigateTo(currentIdx + 1)}>
                    Next<ChevronRight className="h-3.5 w-3.5 ml-1" />
                  </Button>
                </div>
                <DetailPane
                  item={selected} editing={editing} editInstruction={editInstruction}
                  editResponse={editResponse} notes={notes} reviewer={reviewer}
                  actionLoading={actionLoading}
                  onAct={act} onSetEditing={setEditing}
                  onEditInst={setEditInst} onEditResp={setEditResp}
                  onNotes={setNotes} onReviewer={saveReviewer}
                  onResume={resumeJob}
                />
              </div>
            )
            : (
              <div className="flex flex-col items-center justify-center h-full min-h-[380px] border border-dashed border-[#272738] bg-[#12121a] rounded-2xl gap-3">
                <ClipboardCheck className="h-10 w-10 text-[#64748b]" />
                <p className="text-xs text-white font-mono font-bold">Select a sample to review</p>
                <p className="text-[11px] text-[#94a3b8] font-mono">
                  Keyboard: a approve · r reject · e edit · f flag
                </p>
              </div>
            )
          }
        </div>
      </div>
    </div>
  )
}

// ── Detail pane ───────────────────────────────────────────────────────────────

interface DPProps {
  item: ReviewItem; editing: boolean
  editInstruction: string; editResponse: string; notes: string; reviewer: string
  actionLoading: boolean
  onAct: (action: 'approve' | 'reject' | 'flag' | 'edit', item: ReviewItem) => void
  onSetEditing: (v: boolean) => void
  onEditInst: (v: string) => void; onEditResp: (v: string) => void
  onNotes: (v: string) => void; onReviewer: (v: string) => void
  onResume: (jobId: string) => void
}

function DetailPane({
  item, editing, editInstruction, editResponse, notes, reviewer,
  actionLoading, onAct, onSetEditing, onEditInst, onEditResp, onNotes, onReviewer, onResume,
}: DPProps) {
  return (
    <Card className="bg-[#12121a] border-[#272738] rounded-2xl card-shadow">
      <CardHeader className="pb-2 border-b border-[#272738]">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm font-bold text-white">Sample Quality Audit</CardTitle>
          <span className={clsx('text-[10px] font-mono px-2.5 py-0.5 rounded-full border', STATUS_PILL[item.review_status])}>
            {item.review_status}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        {/* Score grid */}
        <div className="grid grid-cols-2 gap-2 text-xs bg-[#0a0a0f] rounded-xl p-3 border border-[#272738]">
          {[
            { label: 'Quality',          val: item.quality_score,      inv: false },
            { label: 'Hallucin. risk',   val: item.hallucination_risk,  inv: true  },
            { label: 'Duplicate',        val: item.duplicate_score,     inv: true  },
            { label: 'Diversity',        val: item.diversity_score,     inv: false },
          ].map(({ label, val, inv }) => (
            <div key={label} className="flex items-center justify-between gap-2">
              <span className="text-[#94a3b8] font-mono text-[11px] shrink-0">{label}</span>
              <div className="flex items-center gap-1.5">
                <ScoreBar value={val} inverted={inv} />
                <span className="font-mono w-7 text-right font-bold text-white">{(val * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
          <div className="col-span-2 text-[#94a3b8] font-mono text-[11px] truncate">
            Job Reference: <code className="text-xs font-bold text-indigo-300">{item.job_id}</code>
          </div>
        </div>

        {/* Instruction */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-400">Instruction / Prompt</label>
            {editing && (
              <span className="text-xs font-mono text-[#94a3b8]">
                {editInstruction.length} chars
              </span>
            )}
          </div>
          {editing
            ? <textarea
                className="w-full bg-[#0a0a0f] border border-[#272738] rounded-xl p-3 text-xs text-white min-h-[72px] resize-y focus:outline-none focus:border-[#6366f1] font-mono"
                value={editInstruction}
                onChange={e => onEditInst(e.target.value)}
              />
            : <div className="bg-[#0a0a0f] rounded-xl p-3 text-xs text-white border border-[#272738] whitespace-pre-wrap leading-relaxed max-h-28 overflow-y-auto font-sans">
                {item.instruction}
              </div>
          }
        </div>

        {/* Response */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#10b981]">Synthesized Response</label>
            {editing && (
              <span className="text-xs font-mono text-[#94a3b8]">
                {editResponse.length} chars
              </span>
            )}
          </div>
          {editing
            ? <textarea
                className="w-full bg-[#0a0a0f] border border-[#272738] rounded-xl p-3 text-xs text-white min-h-[100px] resize-y focus:outline-none focus:border-[#6366f1] font-mono"
                value={editResponse}
                onChange={e => onEditResp(e.target.value)}
              />
            : <ScrollArea className="max-h-44">
                <div className="bg-[#0a0a0f] rounded-xl p-3 text-xs text-[#f1f5f9] border border-[#272738] whitespace-pre-wrap leading-relaxed font-sans">
                  {item.response}
                </div>
              </ScrollArea>
          }
        </div>

        {item.source_url && (
          <p className="text-xs text-[#94a3b8] truncate font-mono">
            Grounding Source:{' '}
            <a href={item.source_url} target="_blank" rel="noopener noreferrer"
              className="text-[#10b981] font-bold hover:underline">{item.source_url}</a>
          </p>
        )}

        {item.source_text && (
          <details className="rounded-xl border border-[#272738] bg-[#0a0a0f] p-3">
            <summary className="cursor-pointer text-xs font-bold text-white hover:text-indigo-300 transition-colors">
              Inspect Grounded Reference Context
            </summary>
            <div className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-[#94a3b8] font-mono">
              {item.source_text}
            </div>
          </details>
        )}

        {/* Notes + reviewer */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <label className="text-[10px] font-mono uppercase mb-1 block font-bold text-[#94a3b8]">Reviewer name</label>
            <Input value={reviewer} onChange={e => onReviewer(e.target.value)}
              className="h-8 text-xs rounded-full border-[#272738] bg-[#0a0a0f] text-white font-mono" placeholder="your-name" />
          </div>
          <div>
            <label className="text-[10px] font-mono uppercase mb-1 block font-bold text-[#94a3b8]">Review notes</label>
            <Input value={notes} onChange={e => onNotes(e.target.value)}
              className="h-8 text-xs rounded-full border-[#272738] bg-[#0a0a0f] text-white font-mono" placeholder="Optional audit note…" />
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-[#272738]">
          <Button
            size="sm"
            className="bg-[#10b981] hover:bg-emerald-600 text-white font-mono text-xs rounded-full flex-1"
            disabled={actionLoading}
            onClick={() => editing ? onAct('edit', item) : onAct('approve', item)}
          >
            <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
            {editing ? 'Save & Approve' : 'Approve (a)'}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            className="text-xs rounded-full font-mono flex-1"
            disabled={actionLoading}
            onClick={() => onAct('reject', item)}
          >
            <XCircle className="h-3.5 w-3.5 mr-1" />
            Reject (r)
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs rounded-full border-[#272738] text-white hover:bg-[#161622] font-mono"
            disabled={actionLoading}
            onClick={() => onSetEditing(!editing)}
          >
            <Pencil className="h-3.5 w-3.5 mr-1 text-indigo-400" />
            {editing ? 'Cancel edit' : 'Edit (e)'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs rounded-full border-[#272738] text-amber-400 hover:bg-[#161622] font-mono"
            disabled={actionLoading}
            onClick={() => onAct('flag', item)}
          >
            <Flag className="h-3.5 w-3.5 mr-1" />
            Flag (f)
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
