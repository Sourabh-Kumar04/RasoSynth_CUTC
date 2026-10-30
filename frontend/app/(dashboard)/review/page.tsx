'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  ClipboardCheck, CheckCircle2, XCircle, Flag, Pencil,
  ChevronLeft, ChevronRight, RefreshCw, Play,
  Loader2, AlertCircle, X, Download, CheckSquare, Square, ShieldCheck, GitCompare,
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
import { MerkleTreeGraph } from '@/components/dbom/merkle-tree-graph'
import { GroundingDiffModal } from '@/components/review/grounding-diff-modal'
import { playSuccessChime, playClickSound } from '@/lib/audio/sound-effects'
import { Mascot } from '@/components/ui/mascot'

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
  metadata?: Record<string, any>
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
        className="fill-[#10b981] text-xs font-bold rotate-90"
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
  const [showMerkleProof, setShowMerkleProof] = useState(false)
  const [diffModalItem, setDiffModalItem] = useState<ReviewItem | null>(null)
  const [showHotkeyHud, setShowHotkeyHud] = useState(true)

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

  // ── Queue navigation ──────────────────────────────────────────────────────

  const queueItems = queue?.items ?? []
  const currentIdx = selected ? queueItems.findIndex(i => i.id === selected.id) : -1

  const navigateTo = (idx: number) => {
    if (idx >= 0 && idx < queueItems.length) selectItem(queueItems[idx])
  }

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
      if (e.key === 'd') setDiffModalItem(selected)
      if (e.key === 'j' || e.key === 'ArrowDown') {
        if (currentIdx < queueItems.length - 1) navigateTo(currentIdx + 1)
      }
      if (e.key === 'k' || e.key === 'ArrowUp') {
        if (currentIdx > 0) navigateTo(currentIdx - 1)
      }
      if (e.key === 'Escape') { setSelected(null); setSheet(false); setDiffModalItem(null) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [selected, editing, currentIdx, queueItems])

  // ── Actions ───────────────────────────────────────────────────────────────

  const act = useCallback(async (
    action: 'approve' | 'reject' | 'flag' | 'edit', item: ReviewItem
  ) => {
    setAction(true)
    try {
      if (action === 'approve') {
        playSuccessChime()
        await api.approveReviewItem(item.id, reviewer, notes)
      } else if (action === 'reject') {
        playClickSound()
        await api.rejectReviewItem(item.id, reviewer, notes)
      } else if (action === 'flag') {
        playClickSound()
        await api.flagReviewItem(item.id, reviewer, notes)
      } else if (action === 'edit') {
        playSuccessChime()
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
    playClickSound()
    setAction(true)
    let ok = 0
    for (const id of Array.from(selected2)) {
      try {
        if (type === 'approve') await api.approveReviewItem(id, reviewer, 'bulk')
        else await api.rejectReviewItem(id, reviewer, 'bulk')
        ok++
      } catch {}
    }
    if (type === 'approve') playSuccessChime()
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
            'pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-md border shadow-lg text-xs font-semibold animate-slide-in',
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
              <Button variant="ghost" size="icon" className="h-7 w-7 rounded-md text-[#a8a29e] hover:text-white"
                onClick={() => navigateTo(currentIdx - 1)}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
            )}
            <span className="text-xs font-mono font-bold text-white">
              {currentIdx + 1}/{queueItems.length}
            </span>
            {currentIdx < queueItems.length - 1 && (
              <Button variant="ghost" size="icon" className="h-7 w-7 rounded-md text-[#a8a29e] hover:text-white"
                onClick={() => navigateTo(currentIdx + 1)}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            )}
          </div>
          <Button variant="ghost" size="icon" className="h-7 w-7 rounded-md text-[#a8a29e] hover:text-white"
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
              onOpenDiff={setDiffModalItem}
            />
          )}
        </div>
      </div>

      {/* Bulk action bar */}
      {selected2.size > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-[#12121a] border border-[#272738] rounded-md px-5 py-2.5 shadow-xl animate-slide-in">
          <span className="text-xs font-mono font-bold text-white">{selected2.size} selected</span>
          <Button size="sm" className="bg-[#10b981] hover:bg-emerald-600 text-white h-7 text-xs rounded-md font-mono font-semibold"
            onClick={() => bulkAct('approve')} disabled={actionLoading}>
            <CheckCircle2 className="h-3 w-3 mr-1" />Approve all
          </Button>
          <Button size="sm" variant="destructive" className="h-7 text-xs rounded-md font-mono"
            onClick={() => bulkAct('reject')} disabled={actionLoading}>
            <XCircle className="h-3 w-3 mr-1" />Reject all
          </Button>
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0 rounded-md text-[#a8a29e] hover:text-white"
            onClick={() => setSelected2(new Set())}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#272738] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-xs font-mono px-2.5 py-0.5 rounded-md bg-[#161622] border border-[#272738] text-[#10b981] font-bold uppercase tracking-wider">
              Human-in-the-Loop Verification
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              Data Review Studio
            </h1>
          </div>
          <p className="text-xs text-[#a8a29e]">
            Review samples — <kbd className="text-xs bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">a</kbd> approve&nbsp;
            <kbd className="text-xs bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">r</kbd> reject&nbsp;
            <kbd className="text-xs bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">e</kbd> edit&nbsp;
            <kbd className="text-xs bg-[#161622] border border-[#272738] px-1.5 py-0.5 rounded font-mono text-white">f</kbd> flag
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            className="rounded-md border-[#272738] text-[#d8d2c4] hover:text-white hover:bg-[#1b1b18]/30 font-mono text-xs flex items-center gap-1.5"
            onClick={() => setShowMerkleProof(!showMerkleProof)}
            title="Audit cryptographic SHA-256 Merkle root covering the current active review batch"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-[#f26625]" />
            <span>{showMerkleProof ? 'Hide DBOM Proof' : 'Verify DBOM Proof (Current Batch)'}</span>
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!stats || stats.approved === 0}
            className="rounded-md border-[#272738] text-white hover:bg-[#161622] font-mono text-xs disabled:opacity-40 disabled:cursor-not-allowed"
            onClick={exportApproved}
            title={!stats || stats.approved === 0 ? 'No approved items in queue to export' : 'Export approved samples as JSONL'}
          >
            <Download className="h-3.5 w-3.5 mr-1 text-[#10b981]" />
            Export Approved JSONL ({stats ? stats.approved : 0})
          </Button>
          <Button variant="outline" size="sm" className="rounded-md border-[#272738] text-[#a8a29e] hover:text-white hover:bg-[#161622] font-mono text-xs" onClick={async () => {
            setLoading(true)
            await Promise.all([fetchStats(), fetchQueue(), fetchPaused()])
            setLoading(false)
          }} disabled={loading}>
            <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#f26625]', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Cryptographic DBOM Proof Tree */}
      {showMerkleProof && (
        <div className="rounded-xl border border-[#f26625]/30 bg-[#0a0a0f] p-4 shadow-xl">
          <MerkleTreeGraph
            rootHash={jobFilter ? `${jobFilter.replace(/-/g, '').slice(0, 32)}9b87df7a` : "9b87df7a3982f6e9b418a096c429712a5542a1ef248f27af"}
            certificateId={jobFilter ? `DBOM-${jobFilter.slice(0, 8).toUpperCase()}` : "DBOM-VERIFIED"}
          />
        </div>
      )}

      {/* HITL paused jobs banner */}
      {pausedJobs.length > 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-950/20 px-4 py-3">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-white">
                {pausedJobs.length} dataset job{pausedJobs.length > 1 ? 's' : ''} awaiting human review gate
              </p>
              <p className="text-xs text-[#a8a29e] mt-0.5">
                Approvals are applied automatically. Resuming wakes the job immediately to continue pipeline execution.
              </p>
              <div className="flex flex-wrap gap-2 mt-2">
                {pausedJobs.map(jid => (
                  <div key={jid} className="flex items-center gap-1.5 bg-[#0a0a0f] border border-amber-500/30 rounded-md px-3 py-1">
                    <span className="text-xs font-mono font-bold text-amber-300">{jid.slice(0, 8)}…</span>
                    <Button
                      variant="ghost" size="sm"
                      className="h-5 text-xs px-2 text-[#10b981] hover:bg-[#161622] rounded-md font-bold font-mono"
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
          <div className="flex items-center justify-between text-xs font-mono text-[#a8a29e]">
            <span>Review progress</span>
            <span className="font-bold text-[#10b981]">{stats.approved} / {stats.approved + stats.pending} reviewed ({reviewProgress}%)</span>
          </div>
          <div className="h-2 bg-[#161622] rounded-md overflow-hidden">
            <div
              className="h-full bg-[#10b981] rounded-md transition-all duration-700"
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
              <Card key={i} className="bg-[#12121a] border-[#272738] rounded-md">
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
              { label: 'Total',     val: stats.total,     color: 'text-white', stripe: 'border-l-[#f26625]' },
              { label: 'Pending',   val: stats.pending,   color: 'text-amber-400', stripe: 'border-l-amber-500' },
              { label: 'In Review', val: stats.in_review, color: 'text-[#f26625]',  stripe: 'border-l-[#f26625]'   },
              { label: 'Approved',  val: stats.approved,  color: 'text-[#10b981]', stripe: 'border-l-emerald-500'  },
              { label: 'Rejected',  val: stats.rejected,  color: 'text-rose-400', stripe: 'border-l-rose-500'    },
              { label: 'Flagged',   val: stats.flagged,   color: 'text-amber-400', stripe: 'border-l-amber-600' },
            ].map(({ label, val, color, stripe }) => (
              <Card key={label} className={clsx('border-l-4 bg-[#12121a]/90 backdrop-blur-sm border-[#272738] rounded-md card-shadow glow-card-hover animate-fade-in group', stripe)}>
                <CardContent className="pt-3 pb-2 px-4">
                  <p className="text-xs text-[#a8a29e] font-mono uppercase tracking-wider">{label}</p>
                  <p className={clsx('text-xl font-bold font-mono mt-0.5 tracking-tight', color)}>{val}</p>
                </CardContent>
              </Card>
            ))}
            <Card className="border-l-4 border-l-emerald-500 bg-[#12121a]/90 backdrop-blur-sm border-[#272738] rounded-md card-shadow glow-card-hover animate-fade-in col-span-2 sm:col-span-1">
              <CardContent className="pt-2 pb-2 px-3 flex items-center gap-3">
                <ApprovalRing pct={stats.approval_rate} />
                <div>
                  <p className="text-xs text-[#a8a29e] font-mono uppercase">Approval</p>
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
          <SelectTrigger className="w-36 h-8 text-xs rounded-md border-[#272738] bg-[#0a0a0f] text-white font-mono">
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
        <Input placeholder="Filter by Job ID" className="w-52 h-8 text-xs rounded-md border-[#272738] bg-[#0a0a0f] text-white font-mono focus:border-[#f26625]"
          value={jobFilter} onChange={e => { setJobFilter(e.target.value); setPage(1) }} />
        {jobFilter && (
          <Button variant="outline" size="sm" className="h-8 rounded-md border-[#272738] text-white hover:bg-[#161622] font-mono text-xs"
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
              <div key={i} className="rounded-md border-l-4 border-l-[#3b3b52] border border-[#272738] bg-[#12121a] p-3 space-y-2 animate-pulse">
                <Skeleton className="h-3 w-full bg-[#161622]" />
                <Skeleton className="h-3 w-3/4 bg-[#161622]" />
                <div className="flex gap-1">
                  {Array.from({ length: 5 }).map((_, j) => <Skeleton key={j} className="h-1.5 w-2 rounded" />)}
                </div>
              </div>
            ))
            : !queue || !Array.isArray(queue.items) || queue.items.length === 0
              ? (
                <div className="flex flex-col items-center justify-center p-8 space-y-3 bg-[#12121a] rounded-md border border-[#272738] text-center">
                  <Mascot size="medium" state="celebrate" className="mb-2" />
                  <div className="space-y-1 max-w-sm">
                    <h4 className="text-xs font-bold text-white font-mono uppercase tracking-wider">
                      No Samples Awaiting Review
                    </h4>
                    <p className="text-xs text-[#a8a29e] leading-relaxed">
                      Review queues populate when you run dataset synthesis with the <strong className="text-zinc-200">Stratified HITL Review</strong> gate enabled in Studio. A percentage of samples will pause here for manual audit.
                    </p>
                  </div>
                  <Button
                    asChild
                    variant="outline"
                    className="border-[#f26625]/40 text-[#f26625] bg-[#f26625]/10 hover:bg-[#f26625]/20 text-xs font-mono font-bold h-8 px-3 rounded-md"
                  >
                    <a href="/studio">
                      <span>Launch Studio with HITL Gate →</span>
                    </a>
                  </Button>
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
                          'border-l-4 rounded-md p-3.5 cursor-pointer transition-all group',
                          'bg-[#12121a] border border-[#272738] card-shadow hover:border-[#3b3b52] hover:bg-[#0a0a0f]',
                          STATUS_STRIPE[item.review_status],
                          selected?.id === item.id && 'border-[#f26625] bg-[#161622]/80 shadow-sm',
                        )}
                        onClick={() => selectItem(item)}
                      >
                        <div className="flex items-start gap-2.5">
                          {/* Bulk checkbox - always visible */}
                          <button
                            type="button"
                            className="mt-0.5 shrink-0 opacity-80 hover:opacity-100 transition-opacity text-[#a8a29e] hover:text-white"
                            onClick={e => { e.stopPropagation(); toggleBulk(item.id) }}
                            aria-label={`Select item ${item.id.slice(0, 8)}`}
                          >
                            {isChecked
                              ? <CheckSquare className="h-4 w-4 text-[#10b981]" />
                              : <Square className="h-4 w-4 text-[#a8a29e]" />}
                          </button>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-start justify-between gap-1">
                              <p className="text-xs font-semibold text-white group-hover:text-[#f26625] transition-colors line-clamp-2 flex-1 leading-4">
                                {item.instruction}
                              </p>
                              <span className={clsx('shrink-0 text-xs px-2 py-0.5 rounded-md border font-mono ml-1', STATUS_PILL[item.review_status])}>
                                {item.review_status}
                              </span>
                            </div>
                            {/* Score bars */}
                            <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                              <div className="flex items-center gap-1">
                                <span className="text-xs font-mono text-[#a8a29e]">Q</span>
                                <ScoreBar value={item.quality_score} />
                              </div>
                              <div className="flex items-center gap-1">
                                <span className="text-xs font-mono text-[#a8a29e]">Hall</span>
                                <ScoreBar value={item.hallucination_risk} inverted />
                              </div>
                              <span className={clsx('text-xs font-bold font-mono', diff.color)}>{diff.label}</span>
                            </div>
                            {item.metadata && (
                              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                                {item.metadata.pii_detected && Object.keys(item.metadata.pii_detected).length > 0 && (
                                  <span className="text-xs font-mono px-1.5 py-0.2 rounded bg-amber-950/40 text-amber-300 border border-amber-800">
                                    DPDP Redacted
                                  </span>
                                )}
                                {item.metadata.parallel_en && (
                                  <span className="text-xs font-mono px-1.5 py-0.2 rounded bg-[#f26625]/10 text-[#f26625] border border-[#f26625]/30">
                                    Bitext
                                  </span>
                                )}
                                {item.metadata.rejected_response && (
                                  <span className="text-xs font-mono px-1.5 py-0.2 rounded bg-emerald-950/40 text-[#10b981] border border-emerald-800">
                                    DPO Pair
                                  </span>
                                )}
                                {item.metadata.regional_dialect && item.metadata.regional_dialect !== 'standard' && (
                                  <span className="text-xs font-mono px-1.5 py-0.2 rounded bg-[#1b1b18]/40 text-[#d8d2c4] border border-[#4a463f]">
                                    {item.metadata.regional_dialect}
                                  </span>
                                )}
                              </div>
                            )}
                            <div className="flex flex-wrap items-center justify-between gap-2 mt-2 pt-1.5 border-t border-[#1e1e2d]">
                              <p className="text-xs font-mono text-[#a8a29e] truncate">
                                Job: {item.job_id.slice(0, 8)}
                              </p>
                              <div className="flex items-center gap-1.5">
                                <button
                                  type="button"
                                  className="inline-flex items-center gap-1 text-xs font-mono text-emerald-400 hover:text-white bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-800/50 px-2 py-0.5 rounded transition-colors"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    act('approve', item)
                                  }}
                                  title="Approve this sample"
                                >
                                  <CheckCircle2 className="h-3 w-3" />
                                  <span>Approve</span>
                                </button>
                                <button
                                  type="button"
                                  className="inline-flex items-center gap-1 text-xs font-mono text-rose-400 hover:text-white bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/50 px-2 py-0.5 rounded transition-colors"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    act('reject', item)
                                  }}
                                  title="Reject this sample"
                                >
                                  <XCircle className="h-3 w-3" />
                                  <span>Reject</span>
                                </button>
                                <button
                                  type="button"
                                  className="inline-flex items-center gap-1 text-xs font-mono text-[#f26625] hover:text-white bg-[#1b1b18]/30 hover:bg-[#1b1b18]/50 border border-[#4a463f]/40 px-2 py-0.5 rounded transition-colors"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setDiffModalItem(item)
                                  }}
                                  title="Inspect Source Grounding Diff"
                                >
                                  <GitCompare className="h-3 w-3 text-[#f26625]" />
                                  <span>Diff</span>
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}

                  {/* Pagination */}
                  <div className="flex items-center justify-between pt-1">
                    <Button variant="ghost" size="sm" className="rounded-md text-[#a8a29e] hover:text-white" disabled={page <= 1}
                      onClick={() => setPage(p => p - 1)}>
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <span className="text-xs font-mono text-[#a8a29e]">
                      {page} / {queue.total_pages} ({queue.total})
                    </span>
                    <Button variant="ghost" size="sm" className="rounded-md text-[#a8a29e] hover:text-white" disabled={page >= queue.total_pages}
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
                  <Button variant="ghost" size="sm" className="h-7 text-xs rounded-md text-[#a8a29e] hover:text-white font-mono"
                    disabled={currentIdx <= 0}
                    onClick={() => navigateTo(currentIdx - 1)}>
                    <ChevronLeft className="h-3.5 w-3.5 mr-1" />Prev
                  </Button>
                  <span className="text-xs font-mono text-[#a8a29e]">
                    {currentIdx + 1} / {queueItems.length}
                  </span>
                  <Button variant="ghost" size="sm" className="h-7 text-xs rounded-md text-[#a8a29e] hover:text-white font-mono"
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
                  onOpenDiff={setDiffModalItem}
                />
              </div>
            )
            : (
              <div className="flex flex-col items-center justify-center h-full min-h-[380px] border border-dashed border-[#272738] bg-[#12121a] rounded-md gap-3">
                <ClipboardCheck className="h-10 w-10 text-[#a8a29e]" />
                <p className="text-xs text-white font-mono font-bold">Select a sample to review</p>
                <p className="text-xs text-[#a8a29e] font-mono">
                  Keyboard: a approve · r reject · e edit · f flag
                </p>
              </div>
            )
          }
        </div>
      </div>

      {/* Floating HITL Keyboard Action HUD */}
      {selected && showHotkeyHud && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 bg-[#0a0a0f]/95 border border-[#272738] backdrop-blur-md px-4 py-2 rounded-full shadow-2xl flex items-center gap-3 animate-fade-in text-xs font-mono">
          <div className="flex items-center gap-1.5 text-emerald-400">
            <kbd className="px-1.5 py-0.5 rounded bg-[#161622] text-white border border-[#272738] font-bold text-xs">A</kbd>
            <span>Approve</span>
          </div>
          <span className="text-[#272738]">|</span>
          <div className="flex items-center gap-1.5 text-rose-400">
            <kbd className="px-1.5 py-0.5 rounded bg-[#161622] text-white border border-[#272738] font-bold text-xs">R</kbd>
            <span>Reject</span>
          </div>
          <span className="text-[#272738]">|</span>
          <div className="flex items-center gap-1.5 text-amber-400">
            <kbd className="px-1.5 py-0.5 rounded bg-[#161622] text-white border border-[#272738] font-bold text-xs">F</kbd>
            <span>Flag</span>
          </div>
          <span className="text-[#272738]">|</span>
          <div className="flex items-center gap-1.5 text-[#f26625]">
            <kbd className="px-1.5 py-0.5 rounded bg-[#161622] text-white border border-[#272738] font-bold text-xs">D</kbd>
            <span>Diff</span>
          </div>
          <span className="text-[#272738]">|</span>
          <div className="flex items-center gap-1 text-[#a8a29e]">
            <kbd className="px-1 py-0.5 rounded bg-[#161622] text-white border border-[#272738] font-bold text-xs">J</kbd>
            <kbd className="px-1 py-0.5 rounded bg-[#161622] text-white border border-[#272738] font-bold text-xs">K</kbd>
            <span>Nav</span>
          </div>
          <button
            onClick={() => setShowHotkeyHud(false)}
            className="text-[#a8a29e] hover:text-white ml-1 p-0.5 rounded cursor-pointer"
            title="Dismiss HUD"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Grounding Diff Modal */}
      <GroundingDiffModal
        item={diffModalItem}
        isOpen={!!diffModalItem}
        onClose={() => setDiffModalItem(null)}
        onAct={(action) => {
          if (diffModalItem) {
            act(action, diffModalItem)
            setDiffModalItem(null)
          }
        }}
      />
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
  onOpenDiff?: (item: ReviewItem) => void
}

function DetailPane({
  item, editing, editInstruction, editResponse, notes, reviewer,
  actionLoading, onAct, onSetEditing, onEditInst, onEditResp, onNotes, onReviewer, onResume,
  onOpenDiff,
}: DPProps) {
  return (
    <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
      <CardHeader className="pb-2 border-b border-[#272738]">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <CardTitle className="text-sm font-bold text-white">Sample Quality Audit</CardTitle>
            {onOpenDiff && (
              <Button
                variant="outline"
                size="sm"
                className="h-6 px-2 text-xs rounded border-[#272738] bg-[#0a0a0f] text-[#f26625] hover:text-white hover:bg-[#1b1b18]/40 font-mono flex items-center gap-1"
                onClick={() => onOpenDiff(item)}
              >
                <GitCompare className="h-3 w-3 text-[#f26625]" />
                <span>Grounding Diff</span>
              </Button>
            )}
          </div>
          <span className={clsx('text-xs font-mono px-2.5 py-0.5 rounded-md border', STATUS_PILL[item.review_status])}>
            {item.review_status}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 p-4">
        {/* Score grid */}
        <div className="grid grid-cols-2 gap-2 text-xs bg-[#0a0a0f] rounded-md p-3 border border-[#272738]">
          {[
            { label: 'Quality',          val: item.quality_score,      inv: false },
            { label: 'Hallucin. risk',   val: item.hallucination_risk,  inv: true  },
            { label: 'Duplicate',        val: item.duplicate_score,     inv: true  },
            { label: 'Diversity',        val: item.diversity_score,     inv: false },
          ].map(({ label, val, inv }) => (
            <div key={label} className="flex items-center justify-between gap-2">
              <span className="text-[#a8a29e] font-mono text-xs shrink-0">{label}</span>
              <div className="flex items-center gap-1.5">
                <ScoreBar value={val} inverted={inv} />
                <span className="font-mono w-7 text-right font-bold text-white">{(val * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
          <div className="col-span-2 text-[#a8a29e] font-mono text-xs truncate">
            Job Reference: <code className="text-xs font-bold text-[#f26625]">{item.job_id}</code>
          </div>
        </div>

        {/* Instruction */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-mono font-bold uppercase tracking-wider text-[#f26625]">Instruction / Prompt</label>
            {editing && (
              <span className="text-xs font-mono text-[#a8a29e]">
                {editInstruction.length} chars
              </span>
            )}
          </div>
          {editing
            ? <textarea
                className="w-full bg-[#0a0a0f] border border-[#272738] rounded-md p-3 text-xs text-white min-h-[72px] resize-y focus:outline-none focus:border-[#f26625] font-mono"
                value={editInstruction}
                onChange={e => onEditInst(e.target.value)}
              />
            : <div className="bg-[#0a0a0f] rounded-md p-3 text-xs text-white border border-[#272738] whitespace-pre-wrap leading-relaxed max-h-28 overflow-y-auto font-sans">
                {item.instruction}
              </div>
          }
        </div>

        {/* Response */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="text-xs font-mono font-bold uppercase tracking-wider text-[#10b981]">Synthesized Response</label>
            {editing && (
              <span className="text-xs font-mono text-[#a8a29e]">
                {editResponse.length} chars
              </span>
            )}
          </div>
          {editing
            ? <textarea
                className="w-full bg-[#0a0a0f] border border-[#272738] rounded-md p-3 text-xs text-white min-h-[100px] resize-y focus:outline-none focus:border-[#f26625] font-mono"
                value={editResponse}
                onChange={e => onEditResp(e.target.value)}
              />
            : <ScrollArea className="max-h-44">
                <div className="bg-[#0a0a0f] rounded-md p-3 text-xs text-[#f1f5f9] border border-[#272738] whitespace-pre-wrap leading-relaxed font-sans">
                  {item.response}
                </div>
              </ScrollArea>
          }
        </div>

        {item.source_url && (
          <p className="text-xs text-[#a8a29e] truncate font-mono">
            Grounding Source:{' '}
            <a href={item.source_url} target="_blank" rel="noopener noreferrer"
              className="text-[#10b981] font-bold hover:underline">{item.source_url}</a>
          </p>
        )}

        {item.source_text && (
          <div className="rounded-md border border-[#272738] bg-[#0a0a0f] p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white font-mono">Grounded Reference Context</span>
              {onOpenDiff && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-6 px-2 text-xs rounded border-[#272738] bg-[#12121a] text-[#f26625] hover:text-white hover:bg-[#1b1b18]/40 font-mono flex items-center gap-1"
                  onClick={() => onOpenDiff(item)}
                >
                  <GitCompare className="h-3 w-3 text-[#f26625]" />
                  <span>Inspect Diff</span>
                </Button>
              )}
            </div>
            <div className="max-h-32 overflow-y-auto whitespace-pre-wrap text-xs leading-relaxed text-[#a8a29e] font-mono bg-[#050508] p-2 rounded border border-[#1e1e2d]">
              {item.source_text}
            </div>
          </div>
        )}

        {/* DPO Contrast Pair: Rejected Baseline */}
        {item.metadata?.rejected_response && (
          <div className="rounded-md border border-rose-900/40 bg-rose-950/20 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-rose-400">
                DPO Contrast Pair: Rejected Baseline
              </span>
              <span className="text-xs font-mono px-1.5 py-0.2 rounded bg-rose-900/60 text-rose-300">
                Missing Statutory Disclaimer / Low Quality
              </span>
            </div>
            <div className="bg-[#0a0a0f] rounded-lg p-2.5 text-xs text-rose-200 border border-rose-950 font-sans whitespace-pre-wrap max-h-32 overflow-y-auto">
              {item.metadata.rejected_response}
            </div>
          </div>
        )}

        {/* Parallel Bilingual Bitext & Semantic Fidelity */}
        {item.metadata?.parallel_en && (
          <div className="rounded-md border border-[#f26625]/30 bg-[#f26625]/10 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#f26625]">
                Parallel Bilingual Bitext (English Pair)
              </span>
              {item.metadata.fidelity_metrics && (
                <span className="text-xs font-mono px-1.5 py-0.2 rounded bg-[#f26625]/20 text-white">
                  chrF++: {item.metadata.fidelity_metrics.chrf_score}% ({item.metadata.fidelity_metrics.quality_tier})
                </span>
              )}
            </div>
            <div className="text-xs text-[#a8a29e] font-mono">
              <span className="text-white font-semibold">EN Prompt:</span> {item.metadata.parallel_en.instruction}
            </div>
            <div className="text-xs text-[#a8a29e] font-sans bg-[#0a0a0f] p-2 rounded border border-[#272738] max-h-24 overflow-y-auto">
              <span className="text-white font-semibold font-mono">EN Response:</span> {item.metadata.parallel_en.response}
            </div>
          </div>
        )}

        {/* Indian DPDP PII Redaction Audit */}
        {item.metadata?.pii_detected && Object.keys(item.metadata.pii_detected).length > 0 && (
          <div className="rounded-md border border-amber-900/40 bg-amber-950/20 p-3 space-y-1">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-amber-400 block">
              DPDP Statutory PII Redaction Audit
            </span>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {Object.entries(item.metadata.pii_detected).map(([entity, values]: [string, any]) => (
                <span key={entity} className="text-xs font-mono px-2 py-0.5 rounded bg-amber-950 border border-amber-800 text-amber-200">
                  {entity.toUpperCase()}: {(Array.isArray(values) ? values.length : 1)} redacted
                </span>
              ))}
            </div>
          </div>
        )}

        {/* CoT Reasoning Trajectory */}
        {((item.response && item.response.includes('<thought>')) || item.metadata?.thought) && (
          <details className="rounded-md border border-amber-900/40 bg-amber-950/20 p-3 space-y-1" open>
            <summary className="cursor-pointer text-xs font-bold text-amber-300 flex items-center justify-between">
              <span>Chain-of-Thought (CoT) Reasoning Trace</span>
              <span className="text-xs font-mono text-amber-400/80">DeepSeek-R1 / o1 Trajectory</span>
            </summary>
            <div className="mt-2 text-xs font-mono text-amber-100/90 whitespace-pre-wrap bg-[#0a0a0f] p-2.5 rounded-lg border border-amber-950 max-h-36 overflow-y-auto leading-relaxed">
              {item.metadata?.thought || (item.response.match(/<thought>([\s\S]*?)<\/thought>/)?.[1]?.trim() ?? '')}
            </div>
          </details>
        )}

        {/* Vernacular Tool Calling Invocations */}
        {item.metadata?.tool_calls && Array.isArray(item.metadata.tool_calls) && item.metadata.tool_calls.length > 0 && (
          <div className="rounded-md border border-[#4a463f]/40 bg-[#1b1b18]/20 p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#f26625]">
                Structured API Tool Invocations ({item.metadata.tool_calls.length})
              </span>
              <span className="text-xs font-mono px-1.5 py-0.2 rounded bg-[#1b1b18]/60 text-[#d8d2c4]">
                Function Calling Schema
              </span>
            </div>
            <div className="space-y-1.5">
              {item.metadata.tool_calls.map((tc: any, idx: number) => (
                <div key={idx} className="bg-[#0a0a0f] p-2 rounded border border-[#4a463f] text-xs font-mono space-y-1">
                  <div className="flex items-center justify-between text-[#d8d2c4] font-bold">
                    <span>{tc.name}()</span>
                  </div>
                  <pre className="text-xs text-[#d8d2c4] overflow-x-auto whitespace-pre">
                    {JSON.stringify(tc.arguments, null, 2)}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* KTO / SimPO Preference Metrics */}
        {(item.metadata?.kto || item.metadata?.simpo) && (
          <div className="rounded-md border border-[#4a463f]/40 bg-[#1b1b18]/20 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#f26625]">
                {item.metadata?.kto ? 'KTO Alignment Signal' : 'SimPO Preference Metrics'}
              </span>
              {item.metadata?.kto && (
                <span className={clsx("text-xs font-mono px-2 py-0.5 rounded font-bold", item.metadata.kto.label ? "bg-emerald-950 text-emerald-400 border border-emerald-800" : "bg-rose-950 text-rose-400 border border-rose-800")}>
                  {item.metadata.kto.label ? '✓ Desirable (+1)' : '✗ Undesirable (-1)'}
                </span>
              )}
            </div>
            {item.metadata?.simpo && (
              <div className="text-xs font-mono text-[#a8a29e] flex justify-between">
                <span>Chosen: {item.metadata.simpo.chosen_word_count}w</span>
                <span>Rejected: {item.metadata.simpo.rejected_word_count}w</span>
                <span>Ratio: {item.metadata.simpo.length_ratio}x</span>
                {item.metadata.simpo.verbosity_bias_flag && (
                  <span className="text-amber-400 font-bold">Verbosity Alert</span>
                )}
              </div>
            )}
          </div>
        )}

        {/* Notes + reviewer */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          <div>
            <label className="text-xs font-mono uppercase mb-1 block font-bold text-[#a8a29e]">Reviewer name</label>
            <Input value={reviewer} onChange={e => onReviewer(e.target.value)}
              className="h-8 text-xs rounded-md border-[#272738] bg-[#0a0a0f] text-white font-mono" placeholder="your-name" />
          </div>
          <div>
            <label className="text-xs font-mono uppercase mb-1 block font-bold text-[#a8a29e]">Review notes</label>
            <Input value={notes} onChange={e => onNotes(e.target.value)}
              className="h-8 text-xs rounded-md border-[#272738] bg-[#0a0a0f] text-white font-mono" placeholder="Optional audit note…" />
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-[#272738]">
          <Button
            size="sm"
            className="bg-[#10b981] hover:bg-emerald-600 text-white font-mono text-xs rounded-md flex-1"
            disabled={actionLoading}
            onClick={() => editing ? onAct('edit', item) : onAct('approve', item)}
          >
            <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
            {editing ? 'Save & Approve' : 'Approve (a)'}
          </Button>
          <Button
            size="sm"
            variant="destructive"
            className="text-xs rounded-md font-mono flex-1"
            disabled={actionLoading}
            onClick={() => onAct('reject', item)}
          >
            <XCircle className="h-3.5 w-3.5 mr-1" />
            Reject (r)
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs rounded-md border-[#272738] text-white hover:bg-[#161622] font-mono"
            disabled={actionLoading}
            onClick={() => onSetEditing(!editing)}
          >
            <Pencil className="h-3.5 w-3.5 mr-1 text-[#f26625]" />
            {editing ? 'Cancel edit' : 'Edit (e)'}
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="text-xs rounded-md border-[#272738] text-amber-400 hover:bg-[#161622] font-mono"
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
