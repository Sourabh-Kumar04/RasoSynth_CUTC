'use client'

import { useState, useEffect } from 'react'
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
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

interface Step {
  title: string
  subtitle: string
  icon: any
  description: string
  actionText: string
  actionHref: string
  highlights: string[]
}

const TOUR_STEPS: Step[] = [
  {
    title: 'Welcome to RasoSynthTune',
    subtitle: 'Autonomous Multi-Provider Synthetic Dataset Engine',
    icon: Sparkles,
    description: 'RasoSynthTune is an end-to-end AI Data Engineering & Fine-Tuning platform. It automates dataset synthesis, deduplication, human-in-the-loop review, and PEFT/LoRA model training.',
    actionText: 'Start Guided Tour',
    actionHref: '/studio',
    highlights: [
      'Multi-Provider Consensus (Gemini, Claude, NVIDIA NIM, OpenAI, Groq)',
      'Automated Quality & 4-Tier Semantic Deduplication',
      'Human-in-the-Loop (HITL) Quality Control Gate',
      'Integrated PEFT / LoRA Fine-Tuning Studio'
    ]
  },
  {
    title: '1. Build — Dataset Generation Studio',
    subtitle: 'Step 1: Describe or Load 1-Click Presets',
    icon: FlaskConical,
    description: 'In the Studio (/studio), describe your target dataset prompt in natural language, or click one of the 1-Click Industry Benchmark Prompts (Medical, Python Async, Legal Risk, Finance, Cyber Security) to auto-configure your workflow.',
    actionText: 'Go to Studio',
    actionHref: '/studio',
    highlights: [
      '1-Click Benchmark Presets auto-fill complex prompts',
      'Select multi-provider consensus routes (e.g. Gemini + NIM)',
      'Configure dataset size, format (JSONL, Parquet), and domain constraints'
    ]
  },
  {
    title: '2. Verify — Quality & Grounding Benchmarks',
    subtitle: 'Step 2: Automated Hallucination & Diversity Scoring',
    icon: BarChart2,
    description: 'Every generated dataset undergoes 4 levels of deduplication (exact, fuzzy, embedding, cluster) and multi-provider consensus validation. Explore quality scores and source breakdowns in the Quality Dashboard (/quality).',
    actionText: 'View Quality Dashboard',
    actionHref: '/quality',
    highlights: [
      'Multi-provider consensus agreement scoring',
      'Hallucination risk detection & citation grounding',
      '5-dimensional diversity analysis (topic, instruction, response)'
    ]
  },
  {
    title: '3. Inspect — Human-in-the-Loop (HITL) Gate',
    subtitle: 'Step 3: Manual Sample Approval & Editing',
    icon: ClipboardCheck,
    description: 'The Review Queue (/review) allows domain experts to inspect, edit, approve, or reject synthetic data samples before exporting or model fine-tuning. Keyboard shortcuts (A = Approve, R = Reject, E = Edit) enable rapid curation.',
    actionText: 'Explore Review Queue',
    actionHref: '/review',
    highlights: [
      'Keyboard-driven rapid curation queue (A/R/E/F)',
      'Inline sample editor with instant diff preview',
      'Bulk approval and export of verified datasets'
    ]
  },
  {
    title: '4. Train & Operate — Fine-Tune Studio & Telemetry',
    subtitle: 'Step 4: Train LoRA Adapters & Monitor OpenTelemetry',
    icon: Cpu,
    description: 'Once curated, export your dataset in standard ML formats or train PEFT/LoRA adapter models in the Fine-Tune Studio (/finetune). Monitor system latency, rate limits, and OpenTelemetry spans in Observability (/observability).',
    actionText: 'Go to Fine-Tune Studio',
    actionHref: '/finetune',
    highlights: [
      'PEFT / LoRA parameter-efficient training studio',
      'Real-time streaming training logs & loss charts',
      'OpenTelemetry distributed tracing & provider health'
    ]
  }
]

export function OnboardingModal({ open, onOpenChange }: { open?: boolean; onOpenChange?: (open: boolean) => void }) {
  const [isOpen, setIsOpen] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)

  useEffect(() => {
    if (open !== undefined) {
      setIsOpen(open)
    } else if (typeof window !== 'undefined') {
      const hasSeen = localStorage.getItem('hasSeenRasoSynthOnboarding')
      if (!hasSeen) {
        setIsOpen(true)
      }
    }
  }, [open])

  const handleClose = () => {
    setIsOpen(false)
    if (onOpenChange) onOpenChange(false)
    if (typeof window !== 'undefined') {
      localStorage.setItem('hasSeenRasoSynthOnboarding', 'true')
    }
  }

  if (!isOpen) return null

  const step = TOUR_STEPS[currentStep]
  const Icon = step.icon

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-xl bg-white border border-[#E2E6E0] rounded-3xl shadow-2xl overflow-hidden flex flex-col">
        {/* Top Header Banner */}
        <div className="bg-[#1B3B2B] text-white p-6 relative">
          <button
            onClick={handleClose}
            className="absolute top-4 right-4 text-emerald-300 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-2xl bg-white/10 flex items-center justify-center border border-white/20">
              <Icon className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400 font-bold">
                Platform Guide ({currentStep + 1} of {TOUR_STEPS.length})
              </span>
              <h2 className="text-xl font-bold text-white tracking-tight">{step.title}</h2>
            </div>
          </div>
          <p className="text-xs text-emerald-100/90 font-mono mt-1">{step.subtitle}</p>
        </div>

        {/* Step Body Content */}
        <div className="p-6 space-y-5 flex-1">
          <p className="text-xs text-[#55635B] leading-relaxed">{step.description}</p>

          {/* Key Capabilities Bullet Points */}
          <div className="p-4 rounded-2xl bg-[#F6F7F4] border border-[#E2E6E0] space-y-2.5">
            <p className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#1B3B2B]">
              Key Highlights &amp; Capabilities
            </p>
            <div className="grid grid-cols-1 gap-2">
              {step.highlights.map((item, idx) => (
                <div key={idx} className="flex items-start gap-2 text-xs text-[#1B3B2B]">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Progress Indicators */}
          <div className="flex items-center justify-center gap-1.5 pt-2">
            {TOUR_STEPS.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentStep(idx)}
                className={`h-2 rounded-full transition-all ${
                  idx === currentStep ? 'w-8 bg-[#1B3B2B]' : 'w-2 bg-[#D1D8CE] hover:bg-[#809085]'
                }`}
              />
            ))}
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-[#F6F7F4] border-t border-[#E2E6E0] flex items-center justify-between gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleClose}
            className="text-xs text-[#55635B] hover:text-[#1B3B2B] rounded-full"
          >
            Skip Tour
          </Button>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentStep(c => c - 1)}
                className="text-xs border-[#D1D8CE] text-[#1B3B2B] rounded-full"
              >
                Previous
              </Button>
            )}

            {currentStep < TOUR_STEPS.length - 1 ? (
              <Button
                size="sm"
                onClick={() => setCurrentStep(c => c + 1)}
                className="gap-1.5 bg-[#1B3B2B] hover:bg-[#142D21] text-white text-xs rounded-full font-medium"
              >
                <span>Next Step</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            ) : (
              <Link href={step.actionHref} onClick={handleClose}>
                <Button size="sm" className="gap-1.5 bg-[#1B3B2B] hover:bg-[#142D21] text-white text-xs rounded-full font-medium">
                  <span>Explore Workspace</span>
                  <Zap className="h-3.5 w-3.5 text-emerald-400 fill-current" />
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
