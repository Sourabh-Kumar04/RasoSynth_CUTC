import * as React from 'react'
import { Check, CircleDashed, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'

/** Pipeline stages for a dataset-generation job, in execution order. */
export const PIPELINE_STAGES = ['discovery', 'extraction', 'filtering', 'construction', 'export', 'completed'] as const

export type PipelineStage = (typeof PIPELINE_STAGES)[number]

export type StageState = 'done' | 'active' | 'upcoming' | 'unknown'

/**
 * PipelineStages — interactive pipeline visualization.
 * Stage states come from the selected job's real `current_stage` (and
 * `status`) from the backend. When a job reports no stage, or when no
 * job data is available at all, every stage renders as Unknown — never
 * as a fabricated success.
 */
export function stageStatesFor(currentStage: string | null | undefined, jobStatus: string | null | undefined): StageState[] {
  if (!currentStage || currentStage === 'unknown') {
    return PIPELINE_STAGES.map(() => 'unknown' as StageState)
  }
  const idx = PIPELINE_STAGES.indexOf(currentStage as PipelineStage)
  if (idx === -1) {
    return PIPELINE_STAGES.map(() => 'unknown' as StageState)
  }
  return PIPELINE_STAGES.map((_, i) => {
    if (i < idx) return 'done'
    if (i === idx) return jobStatus === 'completed' && currentStage === 'completed' ? 'done' : 'active'
    return 'upcoming'
  })
}

export function PipelineStages({
  currentStage,
  jobStatus,
  progress,
}: {
  currentStage: string | null | undefined
  jobStatus: string | null | undefined
  /** 0–1 progress, rendered only when the backend actually returned a number. */
  progress: number | null
}) {
  const states = stageStatesFor(currentStage, jobStatus)
  const allUnknown = states.every((s) => s === 'unknown')
  return (
    <div>
      <ol className="flex flex-col gap-2 sm:flex-row sm:items-start">
        {PIPELINE_STAGES.map((stage, i) => {
          const state = states[i]
          const Icon = state === 'done' ? Check : state === 'active' ? Loader2 : CircleDashed
          return (
            <li key={stage} className="flex flex-1 items-start gap-2 sm:flex-col">
              <span
                className={clsx(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border',
                  state === 'done' && 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400',
                  state === 'active' && 'border-[#f26625]/50 bg-[#f26625]/10 text-[#f26625]',
                  state === 'upcoming' && 'border-[#272738] bg-[#161622] text-[#a8a29e]',
                  state === 'unknown' && 'border-[#272738] bg-[#161622] text-[#a8a29e]',
                )}
              >
                <Icon className={clsx('h-3.5 w-3.5', state === 'active' && 'animate-spin')} />
              </span>
              <span className="min-w-0">
                <span className="block font-mono text-xs font-bold capitalize text-white">{stage}</span>
                <span className="block font-mono text-xs capitalize text-[#a8a29e]">{state}</span>
              </span>
              {i < PIPELINE_STAGES.length - 1 ? (
                <span aria-hidden="true" className="mx-1 hidden h-px flex-1 bg-[#272738] sm:mt-3.5 sm:block" />
              ) : null}
            </li>
          )
        })}
      </ol>
      <div className="mt-3 font-mono text-xs text-[#a8a29e]">
        {allUnknown
          ? 'Stage state: unknown — the selected job reports no stage, or no job data is available.'
          : `Current stage: ${currentStage}${typeof progress === 'number' ? ` · Progress: ${Math.round(progress * 100)}%` : ' · Progress: unknown'}`}
      </div>
    </div>
  )
}

