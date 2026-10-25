'use client'

import { useRef, useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import gsap from 'gsap'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Sparkles,
  Play,
  ArrowRight,
  ShieldCheck,
  Cpu,
  Layers,
  Database,
  Terminal,
  Activity,
  CheckCircle2,
  ExternalLink,
  ChevronDown,
  FileCode,
  Zap,
} from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api/client'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'

const ENGINES = [
  {
    id: 'cot',
    name: 'Chain-of-Thought',
    badge: 'CoT',
    description: 'Multi-step deliberate cognitive paths with self-correction verification.',
    detail: 'Enforces rigorous step-by-step mathematical, statutory, and causal derivations.',
  },
  {
    id: 'socratic',
    name: 'Socratic Dialectic',
    badge: 'Socratic',
    description: 'Inquisitive guided dialogue probing edge-cases and latent assumptions.',
    detail: 'Iterative dialectical reasoning that draws out edge-case nuances and proofs.',
  },
  {
    id: 'preference',
    name: 'DPO Preference Pairs',
    badge: 'DPO',
    description: 'Rigorous chosen vs rejected comparative pairs for policy alignment.',
    detail: 'Direct Preference Optimization pairs calibrated by LLM-Judge rubric.',
  },
  {
    id: 'multi_turn',
    name: 'Multi-Turn Agentic',
    badge: 'Multi-Turn',
    description: 'Extended conversational sessions with state tracking & context drift.',
    detail: 'Simulates complex long-horizon human-agent collaboration and memory retention.',
  },
  {
    id: 'tool_calling',
    name: 'Tool Calling & API',
    badge: 'Tool Calling',
    description: 'Executable JSON function schemas with arguments & structured outputs.',
    detail: 'Synthesizes enterprise-grade function calling tokens and deterministic execution.',
  },
  {
    id: 'contrastive',
    name: 'Contrastive Anchors',
    badge: 'Contrastive',
    description: 'Direct negative boundary calibration against anti-domain pollution.',
    detail: 'Maps negative semantic boundaries to immunize against out-of-domain hallucinations.',
  },
  {
    id: 'rag',
    name: 'RAG Grounded Corpus',
    badge: 'RAG',
    description: 'Statutory citations and factual grounding against verified document nodes.',
    detail: 'Extracts real circulars, legal rulings, and technical repos without hallucination.',
  },
]

const QUICK_SEEDS = [
  {
    label: 'AI Kosh GST & Tax',
    domain: 'Finance & Taxation (AI Kosh)',
    engine: 'rag',
    prompt:
      'Synthesize 10,000 multi-turn instruction dialogues from AI Kosh tax rulings & GST Section 16(4) with self-correction',
  },
  {
    label: 'Aerospace & Airfoils',
    domain: 'Aerospace Engineering',
    engine: 'cot',
    prompt:
      'Build a chain-of-thought aerodynamic reasoning dataset covering supercritical airfoil design and FAA FAR Part 25 certification',
  },
  {
    label: 'Bhashini Indic Corpus',
    domain: 'Indic Multilingual',
    engine: 'socratic',
    prompt:
      'Construct a parallel multilingual SFT corpus semantically aligned across Hindi, Tamil, Telugu, and English with script preservation',
  },
  {
    label: 'Python Code Synthesis',
    domain: 'Python Systems',
    engine: 'tool_calling',
    prompt:
      'Generate production-grade Python async concurrency pipelines with Pydantic v2 schemas and pytest invariant test cases',
  },
  {
    label: 'Clinical Reasoning',
    domain: 'Medical Reasoning',
    engine: 'cot',
    prompt:
      'Synthesize chain-of-thought differential diagnosis reasoning using Bayesian pre-test probability and Beers Criteria analysis',
  },
]

export default function ZenPortalPage() {
  const router = useRouter()
  const canvasRef = useRef<HTMLDivElement>(null)
  const auraRef = useRef<HTMLDivElement>(null)
  const [prompt, setPrompt] = useState(
    'Synthesize 10,000 multi-turn instruction dialogues from AI Kosh tax rulings & GST statutes with self-correction'
  )
  const [selectedEngine, setSelectedEngine] = useState('cot')
  const [targetDomain, setTargetDomain] = useState('Finance & Taxation (AI Kosh)')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState<'prompt' | 'engines' | 'merkle'>('prompt')

  // GSAP 60fps Ambient Cursor Spotlight Tracker
  useEffect(() => {
    if (!canvasRef.current || !auraRef.current) return

    const canvas = canvasRef.current
    const aura = auraRef.current

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top

      gsap.to(aura, {
        x: x - 250,
        y: y - 250,
        duration: 0.8,
        ease: 'power3.out',
      })
    }

    canvas.addEventListener('mousemove', handleMouseMove)
    return () => canvas.removeEventListener('mousemove', handleMouseMove)
  }, [])

  const handleLaunch = async () => {
    playClickSound()
    setIsSubmitting(true)

    try {
      const payload = {
        target_domain: prompt.trim() || targetDomain,
        dataset_name: targetDomain || 'Autonomous Synthesis',
        dataset_type: 'sft',
        synthesis_mode: selectedEngine,
        instruction_format: 'alpaca',
        language: 'en',
        dataset_size: 100,
        quality_level: 'standard',
        generation_mode: 'hybrid',
        allow_seedless_generation: true,
        enable_research_loop: true,
      }

      const res = await api.createJob(payload)
      playSuccessChime()
      if (res?.id) {
        router.push(`/orchestration?job=${res.id}`)
      } else {
        router.push('/orchestration')
      }
    } catch {
      router.push('/orchestration')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleApplySeed = (seed: typeof QUICK_SEEDS[0]) => {
    playClickSound()
    setPrompt(seed.prompt)
    setTargetDomain(seed.domain)
    setSelectedEngine(seed.engine)
  }

  return (
    <div
      ref={canvasRef}
      className="relative min-h-screen bg-[#0a0a0f] text-[#f8fafc] overflow-hidden selection:bg-[#f26625]/30 selection:text-white"
    >
      {/* GSAP Fluid Aura Field */}
      <div
        ref={auraRef}
        className="pointer-events-none absolute -top-0 -left-0 w-[500px] h-[500px] rounded-full bg-[radial-gradient(circle,rgba(242,102,37,0.1)_0%,rgba(242,102,37,0.02)_40%,transparent_70%)] blur-3xl z-0"
      />

      {/* Subtle Spatial Dot Grid (negative space backdrop) */}
      <div className="absolute inset-0 bg-dot-grid opacity-20 pointer-events-none z-0" />

      {/* Minimal Top Aperture Bar */}
      <header className="relative z-20 flex items-center justify-between px-6 sm:px-12 py-6 border-b border-[#1c1c28]/40 backdrop-blur-md">
        <div className="flex items-center space-x-3">
          <div className="w-7 h-7 rounded-md bg-[#f26625]/10 border border-[#f26625]/40 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-[#f26625]" />
          </div>
          <span className="font-mono text-xs font-bold tracking-widest uppercase text-white">
            RasoSynth<span className="text-[#f26625]">Tune</span>
          </span>
          <span className="hidden sm:inline-block px-2 py-0.5 rounded text-[10px] font-mono bg-[#12121a] border border-[#272738] text-zinc-400">
            v2.4 Sovereign
          </span>
        </div>

        <div className="flex items-center space-x-4">
          <div className="hidden md:flex items-center space-x-2 text-[11px] font-mono text-zinc-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>7 ENGINES DEPLOYED</span>
          </div>

          <Link
            href="/studio"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md border border-[#272738] bg-[#12121a] hover:bg-[#1a1a24] text-xs font-mono font-medium text-zinc-300 hover:text-white transition-all shadow-sm active:scale-95"
            onClick={playClickSound}
          >
            <span>Full Lab Studio</span>
            <ArrowRight className="w-3 h-3 text-[#f26625]" />
          </Link>
        </div>
      </header>

      {/* Main Expansive Spatial Hero ("Looks empty, not actually empty") */}
      <main className="relative z-10 flex flex-col items-center justify-center min-h-[82vh] px-4 sm:px-6 max-w-5xl mx-auto py-12">
        {/* Subtle Zen Aperture Tag */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-[#12121a]/80 border border-[#272738] text-[10px] font-mono text-zinc-400 mb-8 backdrop-blur-md shadow-sm"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#f26625]" />
          <span className="tracking-widest uppercase">Zen Spatial Nexus</span>
          <span className="text-zinc-600">/</span>
          <span className="text-zinc-300">Lenis + GSAP + Framer</span>
        </motion.div>

        {/* Hero Title */}
        <motion.h1
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1 }}
          className="text-3xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-center text-white font-display max-w-4xl leading-[1.15]"
        >
          Autonomous Dataset <br className="hidden sm:inline" />
          <span className="bg-gradient-to-r from-white via-zinc-200 to-[#f26625] bg-clip-text text-transparent">
            Synthesis &amp; Alignment.
          </span>
        </motion.h1>

        {/* Minimal Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-4 text-xs sm:text-sm text-zinc-400 text-center max-w-2xl font-sans"
        >
          Pure reasoning trajectories, statutory grounded invariance, and cryptographically verified
          Merkle DBOM provenance for frontier LLM fine-tuning.
        </motion.p>

        {/* Central Floating Command Bar */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-10 w-full max-w-3xl rounded-2xl border border-[#272738]/80 bg-[#0d0d14]/90 p-3 sm:p-4 shadow-2xl backdrop-blur-xl transition-all hover:border-[#f26625]/40"
        >
          {/* Text Area */}
          <div className="relative">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Describe dataset scope, target statutory corpus, or instruction intent..."
              className="w-full bg-transparent resize-none border-0 text-xs sm:text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-0 leading-relaxed font-sans"
            />
          </div>

          {/* Engine Selector Pills (Framer Motion spring physics) */}
          <div className="pt-3 border-t border-[#1c1c28] flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center flex-wrap gap-1">
              <span className="text-[10px] font-mono text-zinc-500 mr-1 uppercase">Engine:</span>
              {ENGINES.map((eng) => {
                const isSelected = selectedEngine === eng.id
                return (
                  <button
                    key={eng.id}
                    onClick={() => {
                      playClickSound()
                      setSelectedEngine(eng.id)
                    }}
                    className={clsx(
                      'relative px-2.5 py-1 rounded text-[10px] font-mono transition-all',
                      isSelected
                        ? 'text-white font-semibold'
                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-[#161622]'
                    )}
                  >
                    {isSelected && (
                      <motion.span
                        layoutId="activeEnginePill"
                        className="absolute inset-0 rounded bg-[#f26625]/20 border border-[#f26625]/60 z-0"
                        transition={{ type: 'spring', stiffness: 450, damping: 30 }}
                      />
                    )}
                    <span className="relative z-10">{eng.badge}</span>
                  </button>
                )
              })}
            </div>

            {/* Launch CTA */}
            <div className="flex items-center space-x-2">
              <button
                onClick={handleLaunch}
                disabled={isSubmitting || !prompt.trim()}
                className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white text-xs font-mono font-bold transition-all shadow-md active:scale-95 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Play className="w-3 h-3 fill-current" />
                )}
                <span>Launch Pipeline</span>
              </button>
            </div>
          </div>
        </motion.div>

        {/* Quick Seed Invariant Chips */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="mt-6 flex flex-wrap items-center justify-center gap-2 max-w-2xl"
        >
          <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mr-1">
            Presets:
          </span>
          {QUICK_SEEDS.map((seed, idx) => (
            <button
              key={idx}
              onClick={() => handleApplySeed(seed)}
              className="px-2.5 py-1 rounded-full bg-[#12121a] hover:bg-[#1c1c28] border border-[#272738] hover:border-[#f26625]/50 text-[10px] font-mono text-zinc-300 transition-colors shadow-sm active:scale-95"
            >
              {seed.label}
            </button>
          ))}
        </motion.div>

        {/* Subtle Lenis Scroll Invitation */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 0.6 }}
          transition={{ duration: 0.8, delay: 0.6 }}
          className="mt-16 flex flex-col items-center space-y-1 text-zinc-500 cursor-pointer hover:text-zinc-300 transition-colors"
          onClick={() => {
            if (typeof window !== 'undefined') {
              window.scrollBy({ top: 400, behavior: 'smooth' })
            }
          }}
        >
          <span className="text-[9px] font-mono uppercase tracking-widest">
            Scroll for Architectural Invariants
          </span>
          <ChevronDown className="w-3.5 h-3.5 animate-bounce" />
        </motion.div>
      </main>

      {/* Down-Scroll Section: Architecture & Telemetry Grid (Lenis Inertial Flow) */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 py-20 border-t border-[#1c1c28]">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 gap-4">
          <div>
            <div className="flex items-center space-x-2 text-[10px] font-mono uppercase tracking-widest text-[#f26625] mb-1">
              <Layers className="w-3.5 h-3.5" />
              <span>Synthesis Engines Specification</span>
            </div>
            <h2 className="text-xl font-bold text-white font-display">
              7 Autonomous Synthesis Engines
            </h2>
            <p className="text-xs text-zinc-400 mt-1 max-w-xl">
              Each sample is constructed via dedicated cognitive loops and validated by our pure
              LLM Judge and cosine semantic router.
            </p>
          </div>

          <Link
            href="/studio"
            className="text-xs font-mono text-[#f26625] hover:text-[#de581a] flex items-center space-x-1"
          >
            <span>Open Studio Lab</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
        </div>

        {/* 7 Engines Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {ENGINES.map((eng) => {
            const isCurrent = selectedEngine === eng.id
            return (
              <motion.div
                key={eng.id}
                whileHover={{ y: -2 }}
                onClick={() => {
                  playClickSound()
                  setSelectedEngine(eng.id)
                }}
                className={clsx(
                  'p-4 rounded-xl border transition-all cursor-pointer relative overflow-hidden',
                  isCurrent
                    ? 'bg-[#14141e] border-[#f26625]/70 shadow-lg glow-yc'
                    : 'bg-[#0f0f17] border-[#222230] hover:border-[#333348]'
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#1c1c28] text-white font-semibold">
                    {eng.badge}
                  </span>
                  {isCurrent && (
                    <span className="flex items-center gap-1 text-[9px] font-mono text-[#f26625]">
                      <CheckCircle2 className="w-3 h-3" />
                      Active
                    </span>
                  )}
                </div>
                <h3 className="text-xs font-bold text-white mb-1">{eng.name}</h3>
                <p className="text-[11px] text-zinc-400 leading-relaxed">{eng.description}</p>
                <div className="mt-3 pt-2.5 border-t border-[#1c1c28]/80 text-[10px] font-mono text-zinc-500">
                  {eng.detail}
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* DBOM Attestation & Ray Cluster Dock */}
        <div className="mt-12 p-6 rounded-2xl bg-[#0d0d14] border border-[#272738] flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center space-x-4">
            <div className="w-10 h-10 rounded-xl bg-purple-950/40 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                Cryptographic DBOM Attestation
              </h4>
              <p className="text-[11px] text-zinc-400 mt-0.5">
                Every record hashed with SHA-256 and sealed into an immutable Merkle tree root.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <Link
              href="/review"
              className="px-4 py-2 rounded-lg bg-[#161622] hover:bg-[#202030] border border-[#272738] text-xs font-mono text-zinc-300 hover:text-white transition-colors"
            >
              Verify Merkle Root
            </Link>
            <Link
              href="/orchestration"
              className="px-4 py-2 rounded-lg bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-xs font-mono font-bold text-white transition-colors"
            >
              View Active Jobs
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 py-8 border-t border-[#1c1c28]/40 text-center text-[10px] font-mono text-zinc-500">
        <p>RasoSynth Autonomous Dataset Synthesis Platform · Locked YC Obsidian Signal Orange</p>
      </footer>
    </div>
  )
}
