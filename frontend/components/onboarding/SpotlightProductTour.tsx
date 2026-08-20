'use client'

import { useState, useEffect, useCallback } from 'react'
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
  Activity,
  Layers,
  Search,
  Sliders
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface SpotlightStep {
  targetSelector: string
  title: string
  subtitle: string
  description: string
  actionLabel: string
  actionHref: string
  badgeText: string
  icon: any
}

const SPOTLIGHT_STEPS: SpotlightStep[] = [
  {
    targetSelector: '[data-tour="top-nav-brand"]',
    title: '1. RasoSynthTune Platform Overview',
    subtitle: 'Autonomous Multi-Provider Synthetic Dataset Engine',
    description: 'Welcome to RasoSynthTune! RasoSynthTune is an end-to-end AI Dataset & Fine-Tuning platform. It automates dataset synthesis, multi-provider consensus, 4-tier deduplication, HITL curation, and PEFT/LoRA model training.',
    actionLabel: 'Next: Global Search →',
    actionHref: '/',
    badgeText: 'Platform Core',
    icon: Sparkles
  },
  {
    targetSelector: '[data-tour="top-nav-search"]',
    title: '2. Instant Cmd+K Command Palette',
    subtitle: 'Keyboard-First Navigation Across All 9 Tools',
    description: 'Press Cmd+K anywhere (or click this Search bar) to launch instant fuzzy search across all pages, 1-Click benchmark presets, quality benchmarks, and fine-tuning parameters.',
    actionLabel: 'Next: Dual Execution Mode →',
    actionHref: '/',
    badgeText: 'Global Search',
    icon: Search
  },
  {
    targetSelector: '[data-tour="top-nav-mode"]',
    title: '3. Live API vs Offline Demo Execution',
    subtitle: 'Dual Backend Execution Switcher',
    description: 'Toggle between Live Cloud API execution and Offline Demo mode anytime. Offline Demo mode runs instant 0-latency synthetic data workflows for quick testing.',
    actionLabel: 'Next: Quick Workspace →',
    actionHref: '/',
    badgeText: 'Execution Engine',
    icon: Sliders
  },
  {
    targetSelector: '[data-tour="sidebar-quick-workspace"]',
    title: '4. Quick Workspace Shortcuts & Telemetry',
    subtitle: 'Fast Workflow Launchpad',
    description: 'Access 1-Click Presets, Quality Benchmarks, Fine-Tune Studio, and HITL Curation Queue, along with real-time active dataset job counters.',
    actionLabel: 'Next: Synthetic Studio →',
    actionHref: '/studio',
    badgeText: 'Workspace Launcher',
    icon: Layers
  },
  {
    targetSelector: '[data-tour="launch-studio-btn"]',
    title: '5. Build — Dataset Studio & 1-Click Presets',
    subtitle: 'Natural Language Prompts & Benchmark Presets',
    description: 'Synthesize custom datasets from natural language prompts or select 1-Click Industry Presets (Medical Diagnostics, Python Async, Legal Risk, Finance, Cyber Security).',
    actionLabel: 'Next: Dataset Explorer →',
    actionHref: '/datasets',
    badgeText: 'Synthetic Studio',
    icon: FlaskConical
  },
  {
    targetSelector: '[data-tour="top-nav-brand"]',
    title: '6. Explore — Dataset Manager & Multi-Format Exporter',
    subtitle: 'JSONL, CSV & Parquet Exporting',
    description: 'Explore generated synthetic datasets, filter sample pairs, inspect domain metadata, and export production-ready files in JSONL, CSV, or Parquet formats.',
    actionLabel: 'Next: Quality Benchmarks →',
    actionHref: '/quality',
    badgeText: 'Dataset Explorer',
    icon: Database
  },
  {
    targetSelector: '[data-tour="top-nav-brand"]',
    title: '7. Verify — Quality Benchmarks & Consensus',
    subtitle: '4-Tier Deduplication & Hallucination Guarding',
    description: 'Every dataset undergoes 4-tier deduplication (exact, fuzzy, embedding, cluster) and multi-provider agreement validation across Gemini, Claude, NVIDIA NIM, OpenAI.',
    actionLabel: 'Next: HITL Inspection →',
    actionHref: '/review',
    badgeText: 'Quality Engine',
    icon: BarChart2
  },
  {
    targetSelector: '[data-tour="top-nav-brand"]',
    title: '8. Curate — Human-In-The-Loop Inspection Queue',
    subtitle: 'Rapid Keyboard Hotkeys (A = Approve, R = Reject, E = Edit)',
    description: 'Domain experts inspect, edit, approve, or reject synthetic data samples with rapid hotkeys before sending them to fine-tuning.',
    actionLabel: 'Next: Fine-Tune Studio →',
    actionHref: '/finetune',
    badgeText: 'HITL Review',
    icon: ClipboardCheck
  },
  {
    targetSelector: '[data-tour="top-nav-brand"]',
    title: '9. Train — PEFT & LoRA Fine-Tuning Studio',
    subtitle: 'Parameter-Efficient Model Training & Loss Streaming',
    description: 'Export verified datasets to train parameter-efficient fine-tuning (PEFT / LoRA) adapter models with real-time loss chart streaming and epoch tracking.',
    actionLabel: 'Next: System Observability →',
    actionHref: '/observability',
    badgeText: 'LoRA Studio',
    icon: Cpu
  },
  {
    targetSelector: '[data-tour="top-nav-brand"]',
    title: '10. Observe — OpenTelemetry Tracing & Provider Health',
    subtitle: 'Token Budgets, Latency & Metrics',
    description: 'Monitor token cost budgets, provider rate limits, OpenTelemetry system spans, and multi-provider health metrics in real-time.',
    actionLabel: '⚡ Finish Tour & Start Building',
    actionHref: '/studio',
    badgeText: 'Observability',
    icon: Activity
  }
]

export function SpotlightProductTour() {
  const router = useRouter()
  const pathname = usePathname()
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [isOpen, setIsOpen] = useState(false)
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)
  const [windowDimensions, setWindowDimensions] = useState({ width: 1200, height: 800 })

  // Measure element coordinates and window dimensions
  const measureTarget = useCallback(() => {
    if (typeof window !== 'undefined') {
      setWindowDimensions({ width: window.innerWidth, height: window.innerHeight })
    }

    const step = SPOTLIGHT_STEPS[currentStepIndex]
    if (!step) return

    const element = document.querySelector(step.targetSelector)
    if (element) {
      const rect = element.getBoundingClientRect()
      setTargetRect(rect)
    } else {
      setTargetRect(null)
    }
  }, [currentStepIndex])

  // Reset and open on initial load if not completed
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const seen = localStorage.getItem('spotlightTourCompleted_v3')
      if (!seen) {
        setIsOpen(true)
      }
    }
  }, [])

  useEffect(() => {
    if (isOpen) {
      measureTarget()
      window.addEventListener('resize', measureTarget)
      window.addEventListener('scroll', measureTarget)
      return () => {
        window.removeEventListener('resize', measureTarget)
        window.removeEventListener('scroll', measureTarget)
      }
    }
  }, [isOpen, measureTarget])

  const handleNext = () => {
    if (currentStepIndex < SPOTLIGHT_STEPS.length - 1) {
      const nextIndex = currentStepIndex + 1
      setCurrentStepIndex(nextIndex)
      const nextStep = SPOTLIGHT_STEPS[nextIndex]
      if (nextStep.actionHref && nextStep.actionHref !== pathname) {
        router.push(nextStep.actionHref)
      }
    } else {
      handleComplete()
    }
  }

  const handlePrev = () => {
    if (currentStepIndex > 0) {
      const prevIndex = currentStepIndex - 1
      setCurrentStepIndex(prevIndex)
      const prevStep = SPOTLIGHT_STEPS[prevIndex]
      if (prevStep.actionHref && prevStep.actionHref !== pathname) {
        router.push(prevStep.actionHref)
      }
    }
  }

  const handleComplete = () => {
    setIsOpen(false)
    if (typeof window !== 'undefined') {
      localStorage.setItem('spotlightTourCompleted_v3', 'true')
    }
  }

  const handleRestart = () => {
    setCurrentStepIndex(0)
    setIsOpen(true)
    if (pathname !== '/') router.push('/')
  }

  if (!isOpen) {
    return (
      <button
        onClick={handleRestart}
        className="fixed bottom-4 right-4 z-[90] flex items-center gap-2 bg-[#1B3B2B] text-white px-4 py-2.5 rounded-full shadow-2xl border border-emerald-500/30 text-xs font-mono font-bold hover:scale-105 transition-transform"
        title="Start Interactive Spotlight Tour"
      >
        <Sparkles className="h-4 w-4 text-emerald-400 fill-current animate-pulse" />
        <span>⚡ Product Tour</span>
      </button>
    )
  }

  const step = SPOTLIGHT_STEPS[currentStepIndex]
  const isLastStep = currentStepIndex === SPOTLIGHT_STEPS.length - 1
  const StepIcon = step.icon

  // Viewport Safety Math (Guarantees zero right-edge clipping on mobile/desktop)
  const cardWidth = Math.min(420, windowDimensions.width - 32)
  let cardLeft = Math.max(16, (windowDimensions.width - cardWidth) / 2)
  let cardTop = Math.max(80, (windowDimensions.height - 300) / 2)

  if (targetRect) {
    cardLeft = Math.max(16, Math.min(windowDimensions.width - cardWidth - 16, targetRect.left))
    if (targetRect.bottom > windowDimensions.height - 300) {
      cardTop = Math.max(16, targetRect.top - 310)
    } else {
      cardTop = Math.min(windowDimensions.height - 310, targetRect.bottom + 16)
    }
  }

  return (
    <div className="fixed inset-0 z-[100] pointer-events-none font-sans">
      {/* Darkened Backdrop Overlay */}
      <div className="absolute inset-0 bg-black/65 backdrop-blur-xs pointer-events-auto transition-all duration-300" />

      {/* Glowing Target Element Cutout */}
      {targetRect && (
        <div
          className="absolute border-2 border-emerald-400 rounded-2xl shadow-[0_0_25px_rgba(52,211,153,0.85)] pointer-events-none transition-all duration-300 animate-pulse"
          style={{
            top: `${Math.max(0, targetRect.top - 6)}px`,
            left: `${Math.max(0, targetRect.left - 6)}px`,
            width: `${targetRect.width + 12}px`,
            height: `${targetRect.height + 12}px`,
            zIndex: 101,
          }}
        />
      )}

      {/* Viewport-Clamped Popover Card */}
      <div
        className="fixed z-[102] pointer-events-auto w-[calc(100vw-32px)] sm:w-full max-w-sm sm:max-w-md bg-white border border-[#E2E6E0] rounded-3xl shadow-2xl overflow-hidden transition-all duration-300"
        style={{
          top: `${cardTop}px`,
          left: `${cardLeft}px`,
        }}
      >
        {/* Header Banner */}
        <div className="bg-[#1B3B2B] text-white p-4 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-xl bg-white/10 flex items-center justify-center border border-white/20">
              <StepIcon className="h-4 w-4 text-emerald-400" />
            </div>
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-bold">
                Product Tour ({currentStepIndex + 1} of {SPOTLIGHT_STEPS.length})
              </span>
              <h3 className="text-xs font-bold text-white tracking-tight">{step.title}</h3>
            </div>
          </div>
          <button
            onClick={handleComplete}
            className="text-emerald-300 hover:text-white p-1 rounded-full hover:bg-white/10 transition-colors"
            title="Exit Tour"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Step Body */}
        <div className="p-4 space-y-3 bg-white">
          <div className="flex items-center justify-between">
            <Badge variant="outline" className="text-[10px] font-mono rounded-full border-[#D1D8CE] bg-[#F6F7F4] text-[#1B3B2B]">
              {step.badgeText}
            </Badge>
            <span className="text-[10px] font-mono text-[#55635B] truncate max-w-[200px]">{step.subtitle}</span>
          </div>

          <p className="text-xs text-[#55635B] leading-relaxed">{step.description}</p>
        </div>

        {/* Footer Controls */}
        <div className="p-3.5 bg-[#F6F7F4] border-t border-[#E2E6E0] flex items-center justify-between">
          {/* Progress Dots */}
          <div className="flex items-center gap-1">
            {SPOTLIGHT_STEPS.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentStepIndex(idx)}
                className={`h-2 rounded-full transition-all ${
                  idx === currentStepIndex ? 'w-5 bg-[#1B3B2B]' : 'w-1.5 bg-[#D1D8CE] hover:bg-[#809085]'
                }`}
              />
            ))}
          </div>

          {/* Navigation Buttons */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentStepIndex === 0}
              onClick={handlePrev}
              className="h-7 px-2.5 text-xs border-[#D1D8CE] text-[#1B3B2B] rounded-full disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5 mr-0.5" />
              <span>Back</span>
            </Button>

            <Button
              size="sm"
              onClick={handleNext}
              className="h-7 px-3.5 text-xs bg-[#1B3B2B] hover:bg-[#142D21] text-white rounded-full font-medium shadow-xs"
            >
              <span>{isLastStep ? 'Finish' : 'Next'}</span>
              {!isLastStep && <ChevronRight className="h-3.5 w-3.5 ml-0.5" />}
              {isLastStep && <CheckCircle2 className="h-3.5 w-3.5 ml-1 text-emerald-400" />}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
