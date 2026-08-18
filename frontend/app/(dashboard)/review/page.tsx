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

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
  pending:   'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  in_review: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  approved:  'bg-green-500/15 text-green-300 border-green-500/30',
  rejected:  'bg-red-500/15 text-red-300 border-red-500/30',
  flagged:   'bg-orange-500/15 text-orange-300 border-orange-500/30',
}
const STATUS_STRIPE: Record<ReviewItem['review_status'], string> = {
  pending: 'border-l-yellow-500', in_review: 'border-l-blue-500',
  approved: 'border-l-green-500', rejected: 'border-l-red-500', flagged: 'border-l-orange-500',
}

function difficulty(q: number) {
  if (q >= 0.75) return { label: 'Easy', color: 'text-green-400' }
  if (q >= 0.45) return { label: 'Med',  color: 'text-yellow-400' }
  return { label: 'Hard', color: 'text-red-400' }
}

// Mini score bar (5 segments, colored based on value)
function ScoreBar({ value, inverted = false }: { value: number; inverted?: boolean }) {
  const pct = inverted ? 1 - value : value
  const segs = 5
  const filled = Math.round(pct * segs)
  const color = pct >= 0.7 ? 'bg-green-500' : pct >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex gap-0.5 items-center">
      {Array.from({ length: segs }).map((_, i) => (
        <div key={i} className={clsx('h-1.5 w-2 rounded-sm', i < filled ? color : 'bg-border')} />
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
      <circle cx={22} cy={22} r={r} fill="none" stroke="hsl(var(--border))" strokeWidth={4} />
      <circle cx={22} cy={22} r={r} fill="none" stroke="hsl(var(--success))"
        strokeWidth={4} strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round" />
      <text x={22} y={22} dominantBaseline="middle" textAnchor="middle"
        className="fill-foreground text-[9px] font-bold rotate-90"
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
        status: statusFilter || undefined,
        job_id: jobFilter || undefined,
        page, page_size: PAGE_SIZE,
      })
      if (r) setQueue(r)
    } catch {}
  }, [statusFilter, jobFilter, page])

  useEffect(() => {
    ;(async () => {
      await Promise.all([fetchStats(), fetchQueue()])
      setLoading(false)
    })()
  }, [fetchStats, fetchQueue])

  useEffect(() => {
    const id = setInterval(() => { fetchStats(); fetchQueue() }, 12000)
    return () => clearInterval(id)
  }, [fetchStats, fetchQueue])

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
  // eslint-disable-next-line react-hooks/exhaustive-deps
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

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-5 animate-fade-in">

      {/* Toasts */}
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

      {/* Mobile detail sheet */}
      <div className={clsx(
        'fixed inset-x-0 bottom-0 z-40 bg-background border-t border-border rounded-t-2xl shadow-2xl transition-transform duration-300 md:hidden overflow-y-auto',
        mobileSheet && selected ? 'translate-y-0' : 'translate-y-full',
      )} style={{ maxHeight: '90vh' }}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border sticky top-0 bg-background z-10">
          <div className="flex items-center gap-2">
            {currentIdx > 0 && (
              <Button variant="ghost" size="icon" className="h-7 w-7"
                onClick={() => navigateTo(currentIdx - 1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}
            <span className="text-sm font-medium">
              {currentIdx + 1}/{queueItems.length}
            </span>
            {currentIdx < queueItems.length - 1 && (
              <Button variant="ghost" size="icon" className="h-7 w-7"
                onClick={() => navigateTo(currentIdx + 1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            )}
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7"
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
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-surface border border-border rounded-full px-4 py-2 shadow-2xl animate-slide-in">
          <span className="text-sm text-muted-foreground">{selected2.size} selected</span>
          <Button size="sm" className="bg-green-700 hover:bg-green-600 h-7 text-xs rounded-full"
            onClick={() => bulkAct('approve')} disabled={actionLoading}>
            <CheckCircle2 className="h-3 w-3 mr-1" />Approve all
          </Button>
          <Button size="sm" variant="destructive" className="h-7 text-xs rounded-full"
            onClick={() => bulkAct('reject')} disabled={actionLoading}>
            <XCircle className="h-3 w-3 mr-1" />Reject all
          </Button>
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0 rounded-full"
            onClick={() => setSelected2(new Set())}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5 sm:h-6 sm:w-6 text-orange-400" />
            Human Review Queue
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Review samples — <kbd className="text-xs bg-surface border border-border px-1 rounded">a</kbd> approve&nbsp;
            <kbd className="text-xs bg-surface border border-border px-1 rounded">r</kbd> reject&nbsp;
            <kbd className="text-xs bg-surface border border-border px-1 rounded">e</kbd> edit&nbsp;
            <kbd className="text-xs bg-surface border border-border px-1 rounded">f</kbd> flag
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button variant="outline" size="sm" onClick={exportApproved}>
            <Download className="h-3.5 w-3.5 mr-1" />Export JSONL
          </Button>
          <Button variant="outline" size="sm" onClick={async () => {
            setLoading(true)
            await Promise.all([fetchStats(), fetchQueue()])
            setLoading(false)
          }} disabled={loading}>
            <RefreshCw className={clsx('h-3.5 w-3.5 mr-1', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Review progress bar */}
      {stats && stats.total > 0 && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Review progress</span>
            <span>{stats.approved} / {stats.approved + stats.pending} reviewed ({reviewProgress}%)</span>
          </div>
          <div className="h-2 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-orange-500 to-green-500 rounded-full transition-all duration-700"
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
              <Card key={i} className="bg-surface/40 border-border">
                <CardContent className="pt-3 pb-3 px-4 space-y-2">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-6 w-10" />
                </CardContent>
              </Card>
            ))}
          </div>
        )
        : stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
            {[
              { label: 'Total',     val: stats.total,     color: '',               stripe: 'border-l-border' },
              { label: 'Pending',   val: stats.pending,   color: 'text-yellow-400', stripe: 'border-l-yellow-500' },
              { label: 'In Review', val: stats.in_review, color: 'text-blue-400',   stripe: 'border-l-blue-500'   },
              { label: 'Approved',  val: stats.approved,  color: 'text-green-400',  stripe: 'border-l-green-500'  },
              { label: 'Rejected',  val: stats.rejected,  color: 'text-red-400',    stripe: 'border-l-red-500'    },
              { label: 'Flagged',   val: stats.flagged,   color: 'text-orange-400', stripe: 'border-l-orange-500' },
            ].map(({ label, val, color, stripe }) => (
              <Card key={label} className={clsx('border-l-4 bg-surface/40 border-border animate-fade-in', stripe)}>
                <CardContent className="pt-3 pb-2 px-4">
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className={clsx('text-xl font-bold mt-0.5', color)}>{val}</p>
                </CardContent>
              </Card>
            ))}
            <Card className="border-l-4 border-l-green-500 bg-surface/40 border-border animate-fade-in col-span-2 sm:col-span-1">
              <CardContent className="pt-2 pb-2 px-3 flex items-center gap-3">
                <ApprovalRing pct={stats.approval_rate} />
                <div>
                  <p className="text-xs text-muted-foreground">Approval</p>
                  <p className="text-sm font-bold text-green-400">{stats.approval_rate}%</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )
      }

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <Select value={statusFilter} onValueChange={v => { setStatus(v); setPage(1) }}>
          <SelectTrigger className="w-36 h-8 text-sm">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="in_review">In Review</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
            <SelectItem value="flagged">Flagged</SelectItem>
          </SelectContent>
        </Select>
        <Input placeholder="Filter by Job ID" className="w-52 h-8 text-sm"
          value={jobFilter} onChange={e => { setJobFilter(e.target.value); setPage(1) }} />
        {jobFilter && (
          <Button variant="outline" size="sm" className="h-8"
            onClick={() => resumeJob(jobFilter)}>
            <Play className="h-3.5 w-3.5 mr-1" />Resume Job
          </Button>
        )}
        {selected2.size > 0 && (
          <span className="text-xs text-muted-foreground ml-auto">
            {selected2.size} selected
          </span>
        )}
      </div>

      {/* Main split: list + detail */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">

        {/* Queue list */}
        <div className="md:col-span-2 space-y-1.5">
          {loading
            ? Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-lg border-l-4 border-l-border border border-border p-3 space-y-2 animate-pulse">
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-3/4" />
                <div className="flex gap-1">
                  {Array.from({ length: 5 }).map((_, j) => <Skeleton key={j} className="h-1.5 w-2 rounded" />)}
                </div>
              </div>
            ))
            : !queue || queue.items.length === 0
              ? (
                <div className="flex flex-col items-center justify-center py-16 space-y-3">
                  <ClipboardCheck className="h-10 w-10 text-muted-foreground/20" />
                  <p className="text-sm text-muted-foreground">No items match this filter</p>
                </div>
              )
              : (
                <>
                  {queue.items.map((item, idx) => {
                    const diff = difficulty(item.quality_score)
                    const isChecked = selected2.has(item.id)
                    return (
                      <div
                        key={item.id}
                        className={clsx(
                          'border-l-4 rounded-lg p-3 cursor-pointer transition-all group',
                          'bg-surface/40 border border-border hover:border-orange-500/40 hover:bg-surface/70',
                          STATUS_STRIPE[item.review_status],
                          selected?.id === item.id && 'border-orange-500/60 bg-orange-500/5',
                        )}
                        onClick={() => selectItem(item)}
                      >
                        <div className="flex items-start gap-2">
                          {/* Bulk checkbox */}
                          <button
                            className="mt-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={e => { e.stopPropagation(); toggleBulk(item.id) }}
                          >
                            {isChecked
                              ? <CheckSquare className="h-4 w-4 text-orange-400" />
                              : <Square className="h-4 w-4 text-muted-foreground" />}
                          </button>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-1">
                              <p className="text-xs line-clamp-2 flex-1 leading-4">
                                {item.instruction}
                              </p>
                              <span className={clsx('shrink-0 text-xs px-1.5 py-0.5 rounded-full border ml-1', STATUS_PILL[item.review_status])}>
                                {item.review_status}
                              </span>
                            </div>
                            {/* Score bars */}
                            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                              <div className="flex items-center gap-1">
                                <span className="text-xs text-muted-foreground">Q</span>
                                <ScoreBar value={item.quality_score} />
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="text-xs text-muted-foreground">Hall</span>
                                <ScoreBar value={item.hallucination_risk} inverted />
                              </div>
                              <span className={clsx('text-xs font-medium', diff.color)}>{diff.label}</span>
                            </div>
                            <p className="text-xs text-muted-foreground/40 mt-1 truncate">
                              {item.job_id.slice(0, 8)}
                            </p>
                          </div>
                        </div>
                        {/* Hover preview */}
                        <p className="text-xs text-muted-foreground/60 mt-1.5 line-clamp-1 hidden group-hover:block">
                          ↳ {item.response.slice(0, 100)}…
                        </p>
                      </div>
                    )
                  })}

                  {/* Pagination */}
                  <div className="flex items-center justify-between pt-1">
                    <Button variant="ghost" size="sm" disabled={page <= 1}
                      onClick={() => setPage(p => p - 1)}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-xs text-muted-foreground">
                      {page} / {queue.total_pages} ({queue.total})
                    </span>
                    <Button variant="ghost" size="sm" disabled={page >= queue.total_pages}
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
                  <Button variant="ghost" size="sm" className="h-7 text-xs"
                    disabled={currentIdx <= 0}
                    onClick={() => navigateTo(currentIdx - 1)}>
                    <ChevronLeft className="h-3.5 w-3.5 mr-1" />Prev
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    {currentIdx + 1} / {queueItems.length}
                  </span>
                  <Button variant="ghost" size="sm" className="h-7 text-xs"
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
              <div className="flex flex-col items-center justify-center h-full min-h-[380px] border border-dashed border-border rounded-xl gap-3">
                <ClipboardCheck className="h-10 w-10 text-muted-foreground/20" />
                <p className="text-sm text-muted-foreground">Select a sample to review</p>
                <p className="text-xs text-muted-foreground/60">
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
    <Card className="bg-surface/40 border-border">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-sm">Sample Review</CardTitle>
          <span className={clsx('text-xs px-2 py-0.5 rounded-full border', STATUS_PILL[item.review_status])}>
            {item.review_status}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Score grid */}
        <div className="grid grid-cols-2 gap-2 text-xs bg-background/40 rounded-lg p-3 border border-border/40">
          {[
            { label: 'Quality',          val: item.quality_score,      inv: false },
            { label: 'Hallucin. risk',   val: item.hallucination_risk,  inv: true  },
            { label: 'Duplicate',        val: item.duplicate_score,     inv: true  },
            { label: 'Diversity',        val: item.diversity_score,     inv: false },
          ].map(({ label, val, inv }) => (
            <div key={label} className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground shrink-0">{label}</span>
              <div className="flex items-center gap-1.5">
                <ScoreBar value={val} inverted={inv} />
                <span className="font-mono w-7 text-right">{(val * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
          <div className="col-span-2 text-muted-foreground/60 truncate">
            Job: <code className="text-xs">{item.job_id}</code>
          </div>
        </div>

        {/* Instruction */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-muted-foreground">Instruction</label>
            {editing && (
              <span className="text-xs text-muted-foreground/60">
                {editInstruction.length} chars
              </span>
            )}
          </div>
          {editing
            ? <textarea
                className="w-full bg-background border border-border rounded-md p-2 text-sm min-h-[72px] resize-y focus:outline-none focus:ring-1 focus:ring-orange-500/40"
                value={editInstruction}
                onChange={e => onEditInst(e.target.value)}
              />
            : <div className="bg-background rounded-md p-2.5 text-sm border border-border/40 whitespace-pre-wrap leading-relaxed max-h-28 overflow-y-auto">
                {item.instruction}
              </div>
          }
        </div>

        {/* Response */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-medium text-muted-foreground">Response</label>
            {editing && (
              <span className="text-xs text-muted-foreground/60">
                {editResponse.length} chars
              </span>
            )}
          </div>
          {editing
            ? <textarea
                className="w-full bg-background border border-border rounded-md p-2 text-sm min-h-[100px] resize-y focus:outline-none focus:ring-1 focus:ring-orange-500/40"
                value={editResponse}
                onChange={e => onEditResp(e.target.value)}
              />
            : <ScrollArea className="max-h-44">
                <div className="bg-background rounded-md p-2.5 text-sm border border-border/40 whitespace-pre-wrap leading-relaxed">
                  {item.response}
                </div>
              </ScrollArea>
          }
        </div>

        {item.source_url && (
          <p className="text-xs text-muted-foreground truncate">
            Source:{' '}
            <a href={item.source_url} target="_blank" rel="noopener noreferrer"
              className="text-orange-400 hover:underline">{item.source_url}</a>
          </p>
        )}

        {/* Notes + reviewer */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <label className="text-xs mb-1 block text-muted-foreground">Reviewer name</label>
            <Input value={reviewer} onChange={e => onReviewer(e.target.value)}
              className="h-8 text-sm" placeholder="your-name" />
          </div>
          <div>
            <label className="text-xs mb-1 block text-muted-foreground">Notes (optional)</label>
            <Input value={notes} onChange={e => onNotes(e.target.value)}
              className="h-8 text-sm" placeholder="Add a note…" />
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2">
          {!editing ? (
            <>
              <Button size="sm" className="bg-green-700 hover:bg-green-600 text-white h-8"
                disabled={actionLoading} onClick={() => onAct('approve', item)}>
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />Approve
                <kbd className="ml-1 text-xs opacity-60 font-normal">a</kbd>
              </Button>
              <Button size="sm" variant="destructive" className="h-8"
                disabled={actionLoading} onClick={() => onAct('reject', item)}>
                <XCircle className="h-3.5 w-3.5 mr-1" />Reject
                <kbd className="ml-1 text-xs opacity-60 font-normal">r</kbd>
              </Button>
              <Button size="sm" variant="outline" className="h-8"
                disabled={actionLoading} onClick={() => onSetEditing(true)}>
                <Pencil className="h-3.5 w-3.5 mr-1" />Edit
                <kbd className="ml-1 text-xs opacity-60 font-normal">e</kbd>
              </Button>
              <Button size="sm" variant="outline"
                className="h-8 border-orange-500/40 text-orange-400 hover:bg-orange-500/10"
                disabled={actionLoading} onClick={() => onAct('flag', item)}>
                <Flag className="h-3.5 w-3.5 mr-1" />Flag
                <kbd className="ml-1 text-xs opacity-60 font-normal">f</kbd>
              </Button>
              {actionLoading && <Loader2 className="h-4 w-4 animate-spin self-center ml-1" />}
            </>
          ) : (
            <>
              <Button size="sm" className="bg-green-700 hover:bg-green-600 text-white h-8"
                disabled={actionLoading} onClick={() => onAct('edit', item)}>
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />Save &amp; Approve
              </Button>
              <Button size="sm" variant="outline" className="h-8"
                onClick={() => onSetEditing(false)}>Cancel</Button>
            </>
          )}
        </div>

        {/* HITL resume */}
        <div className="border-t border-border/40 pt-3 space-y-2">
          <p className="text-xs text-muted-foreground">
            If this dataset job is paused at a review gate, resume it here after approving.
          </p>
          <Button size="sm" variant="outline"
            className="h-8 border-orange-500/40 text-orange-400 hover:bg-orange-500/10"
            onClick={() => onResume(item.job_id)}>
            <Play className="h-3.5 w-3.5 mr-1" />Resume Dataset Job
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
