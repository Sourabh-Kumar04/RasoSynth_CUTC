'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import {
  Sparkles,
  FlaskConical,
  Database,
  Cpu,
  ClipboardCheck,
  BarChart2,
  ArrowRight,
  CheckCircle2,
  X,
  Zap,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Play
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface TourStep {
  title: string
  subtitle: string
  icon: any
  description: string
  actionLabel: string
  actionHref: string
  targetElement?: string
  badgeText: string
}

const TOUR_STEPS: TourStep[] = [
  {
    title: '1. Build — 1-Click Studio Presets',
    subtitle: 'Step 1: Synthesize High-Craft Datasets',
    icon: FlaskConical,
    description: 'Use natural language prompts or launch 1-Click Benchmark Presets (Medical, Python Async, Legal Risk, Finance, Cyber Security) to auto-fill configurations.',
    actionLabel: '⚡ Test 1-Click Preset in Studio',
    actionHref: '/studio',
    badgeText: 'Build Engine'
  },
  {
    title: '2. Verify — Quality Benchmarks',
    subtitle: 'Step 2: Multi-Provider Consensus & Grounding',
    icon: BarChart2,
    description: 'Every dataset undergoes 4-tier deduplication (exact, fuzzy, embedding, cluster) and multi-provider agreement validation across Gemini, Claude, NVIDIA NIM, OpenAI.',
    actionLabel: '📊 Inspect Quality Scores',
    actionHref: '/quality',
    badgeText: 'Deduplication & Rules'
  },
  {
    title: '3. Inspect — Human-In-The-Loop Gate',
    subtitle: 'Step 3: Curation Queue & Keyboard Hotkeys',
    icon: ClipboardCheck,
    description: 'Domain experts inspect, edit, approve, or reject synthetic data samples with rapid hotkeys (A = Approve, R = Reject, E = Edit) before model training.',
    actionLabel: '📋 Test HITL Curation Queue',
    actionHref: '/review',
    badgeText: 'Human Review'
  },
  {
    title: '4. Train — PEFT / LoRA Fine-Tuning',
    subtitle: 'Step 4: Parameter-Efficient Model Training',
    icon: Cpu,
    description: 'Export verified datasets in JSONL or Parquet formats, or launch parameter-efficient fine-tuning (PEFT / LoRA) with live loss chart streaming.',
    actionLabel: '💻 Open Fine-Tune Studio',
    actionHref: '/finetune',
    badgeText: 'LoRA Studio'
  },
  {
    title: '5. Observe — OpenTelemetry Tracing',
    subtitle: 'Step 5: Distributed Metrics & Provider Budgets',
    icon: Zap,
    description: 'Monitor token cost budgets, rate-limiting queues, OpenTelemetry spans, and multi-provider health metrics in real-time.',
    actionLabel: '⚡ Inspect OpenTelemetry Spans',
    actionHref: '/observability',
    badgeText: 'Observability'
  }
]

export function InteractiveProductTour() {
  const router = useRouter()
  const pathname = usePathname()
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [isExpanded, setIsExpanded] = useState(false)
  const [isDismissed, setIsDismissed] = useState(false)

  // Auto-expand for first-time visitors
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const dismissed = localStorage.getItem('productTourDismissed')
      if (!dismissed) {
        setIsExpanded(true)
      }
    }
  }, [])

  const handleDismiss = () => {
    setIsExpanded(false)
    setIsDismissed(true)
    if (typeof window !== 'undefined') {
      localStorage.setItem('productTourDismissed', 'true')
    }
  }

  const handleRunAction = (href: string) => {
    router.push(href)
  }

  if (isDismissed && !isExpanded) {
    return (
      <button
        onClick={() => {
          setIsDismissed(false)
          setIsExpanded(true)
        }}
        className="fixed bottom-4 right-4 z-[90] flex items-center gap-2 bg-[#1B3B2B] text-white px-3.5 py-2 rounded-full shadow-2xl border border-emerald-500/30 text-xs font-mono font-bold hover:scale-105 transition-transform"
      >
        <Sparkles className="h-4 w-4 text-emerald-400 fill-current animate-pulse" />
        <span>Interactive Product Tour</span>
      </button>
    )
  }

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="fixed bottom-4 right-4 z-[90] flex items-center gap-2 bg-[#1B3B2B] text-white px-3.5 py-2 rounded-full shadow-2xl border border-emerald-500/30 text-xs font-mono font-bold hover:scale-105 transition-transform"
      >
        <Sparkles className="h-4 w-4 text-emerald-400 fill-current" />
        <span>Product Tour ({currentStepIndex + 1}/5)</span>
      </button>
    )
  }

  const step = TOUR_STEPS[currentStepIndex]
  const Icon = step.icon

  return (
    <div className="fixed bottom-4 right-4 z-[90] w-full max-w-sm sm:max-w-md bg-white border border-[#E2E6E0] rounded-3xl shadow-2xl overflow-hidden animate-fade-in flex flex-col font-sans">
      {/* Tour Header */}
      <div className="bg-[#1B3B2B] text-white p-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-xl bg-white/10 flex items-center justify-center border border-white/20">
            <Icon className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-bold">
                Interactive Tour ({currentStepIndex + 1} of {TOUR_STEPS.length})
              </span>
            </div>
            <h3 className="text-xs font-bold text-white tracking-tight">{step.title}</h3>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsExpanded(false)}
            className="text-emerald-300 hover:text-white p-1 rounded-full hover:bg-white/10 transition-colors"
            title="Minimize Tour"
          >
            <Minimize2 className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={handleDismiss}
            className="text-emerald-300 hover:text-white p-1 rounded-full hover:bg-white/10 transition-colors"
            title="Dismiss Tour"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Tour Content */}
      <div className="p-4 space-y-3.5 bg-white">
        <Badge variant="outline" className="text-[10px] font-mono rounded-full border-[#D1D8CE] bg-[#F6F7F4] text-[#1B3B2B]">
          {step.badgeText}
        </Badge>
        <p className="text-xs text-[#55635B] leading-relaxed">{step.description}</p>

        {/* Live Interactive Action Button */}
        <Button
          size="sm"
          className="w-full justify-center gap-2 bg-[#1B3B2B] hover:bg-[#142D21] text-white text-xs font-medium rounded-full shadow-xs py-2"
          onClick={() => handleRunAction(step.actionHref)}
        >
          <span>{step.actionLabel}</span>
          <ArrowRight className="h-3.5 w-3.5 text-emerald-400" />
        </Button>
      </div>

      {/* Tour Footer Controls */}
      <div className="p-3 bg-[#F6F7F4] border-t border-[#E2E6E0] flex items-center justify-between">
        <div className="flex items-center gap-1">
          {TOUR_STEPS.map((_, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentStepIndex(idx)}
              className={`h-1.5 rounded-full transition-all ${
                idx === currentStepIndex ? 'w-5 bg-[#1B3B2B]' : 'w-1.5 bg-[#D1D8CE] hover:bg-[#809085]'
              }`}
            />
          ))}
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            disabled={currentStepIndex === 0}
            onClick={() => setCurrentStepIndex((c) => c - 1)}
            className="h-7 px-2 text-[11px] border-[#D1D8CE] text-[#1B3B2B] rounded-full disabled:opacity-40"
          >
            <ChevronLeft className="h-3 w-3" />
            <span>Prev</span>
          </Button>

          {currentStepIndex < TOUR_STEPS.length - 1 ? (
            <Button
              size="sm"
              onClick={() => setCurrentStepIndex((c) => c + 1)}
              className="h-7 px-3 text-[11px] bg-[#1B3B2B] hover:bg-[#142D21] text-white rounded-full font-medium"
            >
              <span>Next</span>
              <ChevronRight className="h-3 w-3" />
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={handleDismiss}
              className="h-7 px-3 text-[11px] bg-emerald-700 hover:bg-emerald-800 text-white rounded-full font-medium"
            >
              <span>Complete</span>
              <CheckCircle2 className="h-3 w-3 ml-1" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
