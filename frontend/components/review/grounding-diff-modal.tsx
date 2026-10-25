'use client'

import React, { useState, useEffect } from 'react'
import {
  X, GitCompare, Copy, Check, ExternalLink,
  CheckCircle2, XCircle, Flag, FileText, Bot, Sparkles, Scale
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'

export interface ReviewItem {
  id: string
  job_id: string
  dataset_id: string
  instruction: string
  response: string
  source_url: string
  source_text: string
  quality_score: number
  hallucination_risk: number
  duplicate_score: number
  diversity_score: number
  review_status: 'pending' | 'in_review' | 'approved' | 'rejected' | 'flagged'
  review_decision: string | null
  review_notes: string
  reviewed_by: string
  review_timestamp: string | null
  edited_instruction: string | null
  edited_response: string | null
  created_at: string
  metadata?: Record<string, any>
}

interface GroundingDiffModalProps {
  item: ReviewItem | null
  isOpen: boolean
  onClose: () => void
  onAct?: (action: 'approve' | 'reject' | 'flag') => void
}

export function GroundingDiffModal({
  item,
  isOpen,
  onClose,
  onAct,
}: GroundingDiffModalProps) {
  const [copied, setCopied] = useState(false)
  const [viewMode, setViewMode] = useState<'split' | 'unified' | 'dpo'>('split')

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen || !item) return null

  const rawSource = item.source_text || item.metadata?.source_snippet || item.metadata?.context || 'Reference ground truth context loaded from source ingest document.'
  const sourceWordCount = rawSource.trim().split(/\s+/).filter(Boolean).length
  const responseWordCount = item.response.trim().split(/\s+/).filter(Boolean).length
  const expansionRatio = sourceWordCount > 0 ? (responseWordCount / sourceWordCount).toFixed(2) : '1.00'

  // Extract CoT trace if available
  const cotTrace = item.metadata?.thought || (item.response.match(/<thought>([\s\S]*?)<\/thought>/)?.[1]?.trim() ?? null)
  const cleanResponse = item.response.replace(/<thought>[\s\S]*?<\/thought>/, '').trim()

  const copyToClipboard = () => {
    const text = `PROMPT:\n${item.instruction}\n\nRESPONSE:\n${item.response}\n\nSOURCE:\n${rawSource}`
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-sm animate-fade-in">
      <div 
        className="w-full max-w-6xl max-h-[92vh] flex flex-col rounded-xl border border-[#272738] bg-[#0c0c14] shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#272738] bg-[#12121a]">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-[#f26625]/15 border border-[#f26625]/40 flex items-center justify-center text-[#f26625]">
              <GitCompare className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white tracking-wide">
                  Source-to-Synthesis Grounding Diff
                </h2>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#161622] text-[#94a3b8] border border-[#272738]">
                  ID: {item.id.slice(0, 8)}
                </span>
                <span className={clsx(
                  "font-mono text-[10px] px-2 py-0.5 rounded border uppercase font-semibold",
                  item.review_status === 'approved' ? 'bg-emerald-950/40 text-emerald-400 border-emerald-500/40' :
                  item.review_status === 'rejected' ? 'bg-rose-950/40 text-rose-400 border-rose-500/40' :
                  item.review_status === 'flagged' ? 'bg-amber-950/40 text-amber-400 border-amber-500/40' :
                  'bg-[#161622] text-[#94a3b8] border-[#272738]'
                )}>
                  {item.review_status}
                </span>
              </div>
              <p className="text-xs text-[#94a3b8] font-mono mt-0.5">
                Job: <span className="text-white font-bold">{item.job_id.slice(0, 12)}</span> · Compare source grounding fidelity against synthesized cognitive reasoning
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex rounded-md bg-[#0a0a0f] border border-[#272738] p-0.5">
              <button
                className={clsx(
                  "px-2.5 py-1 text-xs font-mono rounded transition-colors",
                  viewMode === 'split' ? "bg-[#161622] text-white font-bold" : "text-[#94a3b8] hover:text-white"
                )}
                onClick={() => setViewMode('split')}
              >
                Side-by-Side
              </button>
              {item.metadata?.rejected_response && (
                <button
                  className={clsx(
                    "px-2.5 py-1 text-xs font-mono rounded transition-colors flex items-center gap-1",
                    viewMode === 'dpo' ? "bg-rose-950/50 text-rose-300 font-bold border border-rose-800/40" : "text-rose-400/80 hover:text-rose-300"
                  )}
                  onClick={() => setViewMode('dpo')}
                >
                  <Scale className="h-3 w-3" />
                  DPO Contrast
                </button>
              )}
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={copyToClipboard}
              className="h-8 border-[#272738] bg-[#0a0a0f] text-xs font-mono text-[#94a3b8] hover:text-white"
            >
              {copied ? <Check className="h-3.5 w-3.5 mr-1 text-[#10b981]" /> : <Copy className="h-3.5 w-3.5 mr-1" />}
              {copied ? 'Copied' : 'Copy'}
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-8 w-8 text-[#94a3b8] hover:text-white hover:bg-[#161622] rounded-md"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Metrics Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 px-6 py-3 bg-[#09090f] border-b border-[#272738] text-xs font-mono">
          <div className="flex flex-col">
            <span className="text-[10px] text-[#94a3b8] uppercase">Quality Score</span>
            <span className="text-sm font-bold text-emerald-400">{(item.quality_score * 100).toFixed(1)}%</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-[#94a3b8] uppercase">Hallucination Risk</span>
            <span className={clsx("text-sm font-bold", item.hallucination_risk < 0.15 ? "text-emerald-400" : "text-amber-400")}>
              {(item.hallucination_risk * 100).toFixed(1)}%
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-[#94a3b8] uppercase">Expansion Ratio</span>
            <span className="text-sm font-bold text-[#f26625]">{expansionRatio}x ({sourceWordCount}w → {responseWordCount}w)</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-[#94a3b8] uppercase">Diversity Score</span>
            <span className="text-sm font-bold text-cyan-400">{(item.diversity_score * 100).toFixed(1)}%</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-[#94a3b8] uppercase">Engine Mode</span>
            <span className="text-sm font-bold text-purple-300 truncate">
              {item.metadata?.synthesis_mode || item.metadata?.engine || 'Cognitive CoT'}
            </span>
          </div>
        </div>

        {/* Modal Body: Split or DPO View */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {viewMode === 'dpo' && item.metadata?.rejected_response ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Chosen / Approved Candidate */}
              <div className="rounded-lg border border-emerald-900/50 bg-[#09130d] p-4 flex flex-col space-y-2">
                <div className="flex items-center justify-between border-b border-emerald-900/40 pb-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <span className="text-xs font-bold text-emerald-300 font-mono uppercase tracking-wide">
                      Chosen Response (High Fidelity)
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-emerald-400/80">
                    {responseWordCount} words
                  </span>
                </div>
                <div className="text-xs text-emerald-100 font-sans leading-relaxed whitespace-pre-wrap flex-1 overflow-y-auto max-h-[500px]">
                  {cleanResponse}
                </div>
              </div>

              {/* Rejected / Counterpart Candidate */}
              <div className="rounded-lg border border-rose-900/50 bg-[#160a0d] p-4 flex flex-col space-y-2">
                <div className="flex items-center justify-between border-b border-rose-900/40 pb-2">
                  <div className="flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-rose-400" />
                    <span className="text-xs font-bold text-rose-300 font-mono uppercase tracking-wide">
                      Rejected Candidate (Baseline / Flawed)
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-rose-400/80">
                    {item.metadata.rejected_response.split(/\s+/).filter(Boolean).length} words
                  </span>
                </div>
                <div className="text-xs text-rose-200 font-sans leading-relaxed whitespace-pre-wrap flex-1 overflow-y-auto max-h-[500px]">
                  {item.metadata.rejected_response}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Left Column: Raw Grounding Source */}
              <div className="rounded-lg border border-[#272738] bg-[#0a0a0f] p-4 flex flex-col space-y-3">
                <div className="flex items-center justify-between border-b border-[#272738] pb-2.5">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-[#f26625]" />
                    <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                      Raw Source Grounding
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-[#94a3b8]">
                    {sourceWordCount} words · {rawSource.length} chars
                  </span>
                </div>

                {item.source_url && (
                  <div className="flex items-center gap-1.5 text-xs font-mono text-[#94a3b8] bg-[#12121a] p-2 rounded border border-[#272738]">
                    <span className="text-[10px] uppercase text-[#f26625] font-bold">URI:</span>
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#10b981] hover:underline truncate flex items-center gap-1 flex-1"
                    >
                      {item.source_url}
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                  </div>
                )}

                <div className="flex-1 bg-[#050508] border border-[#1e1e2d] rounded-md p-3 overflow-y-auto max-h-[520px] font-mono text-xs leading-relaxed text-[#cbd5e1] whitespace-pre-wrap selection:bg-[#f26625]/30">
                  {rawSource}
                </div>
              </div>

              {/* Right Column: Synthesized Cognitive Output */}
              <div className="rounded-lg border border-[#272738] bg-[#0a0a0f] p-4 flex flex-col space-y-3">
                <div className="flex items-center justify-between border-b border-[#272738] pb-2.5">
                  <div className="flex items-center gap-2">
                    <Bot className="h-4 w-4 text-[#10b981]" />
                    <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                      Synthesized Output & Reasoning
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-[#94a3b8]">
                    {responseWordCount} words · {item.response.length} chars
                  </span>
                </div>

                {/* Prompt / Instruction */}
                <div className="bg-[#12121a] border border-[#272738] rounded-md p-3 space-y-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-[#f26625] font-bold block">
                    Curriculum Prompt / Instruction:
                  </span>
                  <p className="text-xs font-medium text-white font-sans leading-relaxed">
                    {item.instruction}
                  </p>
                </div>

                {/* Optional CoT Thinking Trajectory */}
                {cotTrace && (
                  <div className="rounded-md border border-amber-900/40 bg-amber-950/20 p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-mono uppercase tracking-wider text-amber-400 font-bold flex items-center gap-1">
                        <Sparkles className="h-3 w-3" />
                        Chain-of-Thought (CoT) Trajectory
                      </span>
                      <span className="text-[9px] font-mono text-amber-400/80">DeepSeek-R1 / o1 Reasoning</span>
                    </div>
                    <div className="text-[11px] font-mono text-amber-200/90 whitespace-pre-wrap bg-[#050508] p-2 rounded border border-amber-950/60 max-h-36 overflow-y-auto leading-relaxed">
                      {cotTrace}
                    </div>
                  </div>
                )}

                {/* Synthesized Response */}
                <div className="flex-1 bg-[#050508] border border-[#1e1e2d] rounded-md p-3 overflow-y-auto max-h-[400px] text-xs font-sans leading-relaxed text-[#f1f5f9] whitespace-pre-wrap selection:bg-[#10b981]/30">
                  {cleanResponse}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer / Direct Actions */}
        <div className="flex items-center justify-between px-6 py-3 border-t border-[#272738] bg-[#12121a]">
          <div className="text-xs text-[#94a3b8] font-mono flex items-center gap-2">
            <span>Press <kbd className="px-1.5 py-0.5 rounded bg-[#161622] text-white border border-[#272738] text-[10px]">ESC</kbd> to close</span>
          </div>

          <div className="flex items-center gap-2">
            {onAct && (
              <>
                <Button
                  size="sm"
                  className="bg-[#10b981] hover:bg-emerald-600 text-white font-mono text-xs rounded-md"
                  onClick={() => onAct('approve')}
                >
                  <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                  Approve Sample
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  className="font-mono text-xs rounded-md"
                  onClick={() => onAct('reject')}
                >
                  <XCircle className="h-3.5 w-3.5 mr-1" />
                  Reject
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-[#272738] text-amber-400 hover:bg-[#161622] font-mono text-xs rounded-md"
                  onClick={() => onAct('flag')}
                >
                  <Flag className="h-3.5 w-3.5 mr-1" />
                  Flag
                </Button>
              </>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="border-[#272738] text-[#94a3b8] hover:text-white hover:bg-[#161622] font-mono text-xs rounded-md"
            >
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
