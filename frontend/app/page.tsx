'use client'

import { useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import gsap from 'gsap'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import {
  Sparkles,
  Play,
  ArrowRight,
  ShieldCheck,
  Layers,
  Terminal,
  CheckCircle2,
  FileCode,
  Copy,
  Check,
  GitBranch,
  Menu,
  X,
  Briefcase,
  Database,
  Workflow,
} from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api/client'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'
import { BrandLogo } from '@/components/ui/brand-logo'
import { Mascot } from '@/components/ui/mascot'
import { Button } from '@/components/ui/button'
import { SynthesisFlowDiagram } from '@/components/ui/synthesis-flow-diagram'
import { FooterStatus } from '@/components/layout/footer-status'

// 7 Synthesis Engines Definition with example preview data (illustrative, not live output)
const ENGINES = [
  {
    id: 'cot',
    name: 'Chain-of-Thought',
    badge: 'CoT',
    sample: {
      instruction:
        'Verify if input tax credit on purchases made in FY 2022-23 can be claimed in GSTR-3B filed on 25th November 2023 under Section 16(4) CGST Act.',
      thought:
        '1. Section 16(4) specifies deadline as 30th November following the financial year end or furnishing annual return.\n2. Finance Act 2022 amendment extended this from September due date to 30th November.\n3. Return filed on 25th Nov 2023 is prior to 30th Nov deadline.\n4. Conclusion: ITC claim is statutorily valid.',
      response:
        'Under Section 16(4) of the CGST Act (as amended by Finance Act 2022), the statutory deadline is 30th November following the financial year. Since GSTR-3B was filed on 25th November 2023, the ITC claim is timely and permissible.',
    },
  },
  {
    id: 'socratic',
    name: 'Socratic Dialectic',
    badge: 'Socratic',
    sample: {
      instruction: 'Is a machine learning model capable of true causal reasoning from observational data?',
      thought:
        'Explore observational correlation vs Pearlian interventional calculus (do-calculus). Pose probing questions on confounding variables.',
      response:
        'Consider two variables X and Y that correlate strongly. If an unobserved confounder Z drives both, can observing X predict the effect of intervening on X? According to Pearl’s do-calculus, observational data alone cannot distinguish correlation from causation without causal graphs or instrumental variables.',
    },
  },
  {
    id: 'preference',
    name: 'DPO Preference Pairs',
    badge: 'DPO',
    sample: {
      instruction: 'A customer demands immediate tax exemption without presenting an authorized GST registration.',
      chosen:
        'Refuse exemption diplomatically. Cite Rule 138 of CGST Rules requiring valid 15-digit GSTIN, and offer step-by-step registration guidance.',
      rejected:
        'Grant the exemption to preserve customer goodwill and handle the documentation audit during annual filing.',
      rewardDelta: '+0.88 margin (Safety & Statutory Invariant)',
    },
  },
  {
    id: 'multi_turn',
    name: 'Multi-Turn Agentic',
    badge: 'Multi-Turn',
    sample: {
      turn1_user: 'We want to optimize our transonic wing design for Mach 0.82 cruise.',
      turn1_agent: 'At Mach 0.82, shock-induced boundary layer separation dominates drag. Are you targeting supercritical airfoil profiles or active suction?',
      turn2_user: 'Supercritical profile with fixed sweep angle of 28 degrees.',
      turn2_agent: 'Applying Korn equation for drag divergence: supercritical camber flattens the upper surface, delaying supersonic expansion shock. Let’s evaluate the lift-to-drag penalty at off-design Mach 0.84.',
    },
  },
  {
    id: 'tool_calling',
    name: 'Tool Calling & API',
    badge: 'Tool Calling',
    sample: {
      tool_name: 'query_gstin_ledger',
      parameters: { gstin: '27AABCU9603R1ZM', period: '2023-Q3', return_type: 'GSTR_2B' },
      execution_mock: {
        status: 200,
        eligible_itc_inr: 4520000,
        mismatched_invoices: 3,
        hash: 'sha256:7f83b1657ff1...',
      },
    },
  },
  {
    id: 'contrastive',
    name: 'Contrastive Anchors',
    badge: 'Contrastive',
    sample: {
      target_domain: 'Indian Indirect Taxation (GST & Customs)',
      anti_domain_invariants: [
        'No US IRS 45Q carbon tax regurgitation',
        'No medical glutathione terminology',
        'No hallucinated circular numbers not in CBIC gazette',
      ],
      immunity_score: '99.94% anti-domain rejection threshold (example value)',
    },
  },
  {
    id: 'rag',
    name: 'RAG Grounded Corpus',
    badge: 'RAG',
    sample: {
      source_repository: 'AI Kosh / CBIC Statutory Gazettes',
      verified_citation: 'CBIC Circular No. 183/15/2022-GST dated 27-Dec-2022',
      extracted_anchor: 'Clarification regarding manner of dealing with discrepancies between ITC claimed in GSTR-3B vs GSTR-2A.',
    },
  },
]

// 1-Click Seeds
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
    label: 'Python Systems & Code',
    domain: 'Python Systems',
    engine: 'tool_calling',
    prompt:
      'Generate production-grade Python async concurrency pipelines with Pydantic v2 schemas and pytest invariant test cases',
  },
  {
    label: 'Clinical Medical Reasoning',
    domain: 'Medical Reasoning',
    engine: 'cot',
    prompt:
      'Synthesize chain-of-thought differential diagnosis reasoning using Bayesian pre-test probability and Beers Criteria analysis',
  },
]

// Code Quickstart Snippets
const CODE_SNIPPETS = {
  python: `from rasosynthtune import RasoSynthClient

client = RasoSynthClient(api_key="rs_live_49f82d1...")

# Launch an autonomous synthesis pipeline
job = client.synthesize(
    domain="Finance & Taxation (AI Kosh)",
    synthesis_mode="cot",  # Options: cot, socratic, preference, rag, tool_calling
    dataset_size=10000,
    language="indic_multilingual",
    mask_indian_pii=True,
    dbom_attestation=True
)

print(f"Synthesis Job Active: {job.id}")
print(f"Merkle Provenance Root: {job.merkle_root}")`,
  curl: `curl -X POST "https://api.rasosynth.ai/jobs" \\
  -H "Authorization: Bearer rs_live_49f82d1..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "target_domain": "Finance & Taxation (AI Kosh)",
    "dataset_name": "GST-SFT-CoT-v2",
    "synthesis_mode": "cot",
    "dataset_size": 10000,
    "quality_level": "standard",
    "mask_indian_pii": true
  }'`,
  typescript: `import { RasoSynthClient } from '@rasosynth/sdk'

const client = new RasoSynthClient({ apiKey: process.env.RASO_API_KEY })

const job = await client.jobs.create({
  targetDomain: 'Aerospace Engineering',
  synthesisMode: 'cot',
  datasetSize: 15000,
  enableResearchLoop: true
})

console.log('Job dispatched to cluster:', job.id)`,
}

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
  const [codeTab, setCodeTab] = useState<'python' | 'curl' | 'typescript'>('python')
  const [copiedCode, setCopiedCode] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

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

  const handleCopyCode = (text: string) => {
    playClickSound()
    navigator.clipboard.writeText(text)
    setCopiedCode(true)
    setTimeout(() => setCopiedCode(false), 2000)
  }

  const currentEngineObj = ENGINES.find((e) => e.id === selectedEngine) || ENGINES[0]

  return (
    <div
      ref={canvasRef}
      className="relative min-h-screen bg-[#0a0a0f] text-[#f5f2ea] overflow-hidden selection:bg-[#f26625]/30 selection:text-white font-sans"
    >
      {/* GSAP Fluid Aura Field */}
      <div
        ref={auraRef}
        className="pointer-events-none absolute -top-0 -left-0 w-[500px] h-[500px] rounded-full bg-[#f26625]/5 z-0"
      />

      {/* Subtle Spatial Dot Grid */}
      <div className="absolute inset-0 bg-dot-grid opacity-20 pointer-events-none z-0" />

      {/* Top Header */}
      <header className="relative z-20 flex items-center justify-between px-6 sm:px-12 py-5 border-b border-[#1c1c28]/40 backdrop-blur-md">
        <div className="flex items-center space-x-3">
          <Link href="/" className="flex items-center space-x-2.5 group">
            <BrandLogo size={44} />
            <div className="flex flex-col">
              <span className="font-display text-sm font-bold tracking-tight text-white">
                Raso<span className="text-[#f26625]">Synth</span><span className="text-[#a8a29e] font-semibold">Tune</span>
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center space-x-3">
          <Link
            href="/studio"
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md border border-[#272738] bg-[#12121a] hover:bg-[#1a1a24] text-xs font-mono font-medium text-zinc-300 hover:text-white transition-all shadow-sm active:scale-95"
            onClick={playClickSound}
          >
            <span>Dataset Studio</span>
            <ArrowRight className="w-3 h-3 text-[#f26625]" />
          </Link>

          {/* Mobile Menu Hamburger Button */}
          <button
            type="button"
            aria-label="Toggle navigation menu"
            onClick={() => {
              playClickSound()
              setIsMobileMenuOpen(!isMobileMenuOpen)
            }}
            className="md:hidden p-2 rounded-md bg-[#12121a] border border-[#272738] text-zinc-300 hover:text-white focus-visible:ring-2 focus-visible:ring-[#f26625] focus-visible:outline-none"
          >
            {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </header>

      {/* Mobile Navigation Drawer */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden relative z-30 bg-[#0d0d15] border-b border-[#272738] px-6 py-4 space-y-3 font-mono text-xs overflow-hidden"
          >
            <div className="text-xs uppercase tracking-wider text-zinc-400 pb-1 border-b border-[#1c1c28]">
              Platform Navigation
            </div>
            <div className="grid grid-cols-2 gap-2 text-zinc-300">
              <Link
                href="/studio"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Studio</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/jobs"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Jobs</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/datasets"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Datasets</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/orchestration"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Orchestration</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/dbom"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between col-span-2"
              >
                <span>DBOM Attestation</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 1: Hero
      ───────────────────────────────────────────────────────────── */}
      <section className="relative z-10 flex flex-col items-center justify-center min-h-[75vh] px-4 sm:px-6 max-w-5xl mx-auto py-12">
        {/* Hero mascot */}
        <Mascot size="large" state="wave" interactive className="mb-2" />

        {/* Hero tagline + orange underline bar */}
        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.25 }}
          className="mt-6 text-xl sm:text-2xl font-extrabold tracking-wide text-center text-white"
        >
          RAW IDEAS. REAL DATASETS. <span className="text-[#f26625]">REAL MODELS.</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="mt-4 text-xs sm:text-sm text-zinc-400 text-center max-w-2xl font-sans"
        >
          Turn raw ideas into verified datasets and fine-tuned models.
        </motion.p>
        <div className="mt-4 h-1.5 w-[120px] rounded bg-[#f26625]" aria-hidden="true" />

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6, delay: 0.35 }}
          className="mt-6 flex flex-wrap items-center justify-center gap-3"
        >
          <Button asChild size="lg">
            <Link href="/studio">Open Studio</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/datasets">View Datasets</Link>
          </Button>
        </motion.div>

        {/* Central Floating Command Bar */}
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-8 w-full max-w-3xl rounded-2xl border border-[#272738]/80 bg-[#0d0d14]/90 p-4 shadow-2xl backdrop-blur-xl transition-all hover:border-[#f26625]/40"
        >
          <div className="relative">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={3}
              placeholder="Describe dataset scope, target statutory corpus, or instruction intent..."
              className="w-full bg-transparent resize-none border-0 text-xs sm:text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-0 leading-relaxed font-sans"
            />
          </div>

          {/* Engine Selector Pills */}
          <div className="pt-3 border-t border-[#1c1c28] flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center flex-wrap gap-1">
              <span className="text-xs font-mono text-zinc-500 mr-1 uppercase">Engine:</span>
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
                      'relative px-2.5 py-1 rounded text-xs font-mono transition-all',
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
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  playClickSound()
                  router.push(`/studio?prompt=${encodeURIComponent(prompt)}&engine=${selectedEngine}&domain=${encodeURIComponent(targetDomain)}`)
                }}
                className="inline-flex items-center space-x-2 px-4 py-2 rounded-lg bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white text-xs font-mono font-bold transition-all shadow-md active:scale-95 focus-visible:ring-2 focus-visible:ring-[#f26625] focus-visible:outline-none"
              >
                <span>Launch Studio with this prompt</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={handleLaunch}
                disabled={isSubmitting || !prompt.trim()}
                className="inline-flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-[#161622] hover:bg-[#1f1f2e] border border-[#272738] text-zinc-300 hover:text-white text-xs font-mono transition-all active:scale-95 disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-[#f26625] focus-visible:outline-none"
              >
                {isSubmitting ? (
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Play className="w-3 h-3 fill-current text-[#f26625]" />
                )}
                <span>Instant Run</span>
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
          <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest mr-1">
            Presets:
          </span>
          {QUICK_SEEDS.map((seed, idx) => (
            <button
              key={idx}
              onClick={() => handleApplySeed(seed)}
              className="px-2.5 py-1 rounded-full bg-[#12121a] hover:bg-[#1c1c28] border border-[#272738] hover:border-[#f26625]/50 text-xs font-mono text-zinc-300 transition-colors shadow-sm active:scale-95"
            >
              {seed.label}
            </button>
          ))}
        </motion.div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 2: 7-Engine Cognitive Architecture Sandbox
      ───────────────────────────────────────────────────────────── */}
      <section id="engines" className="relative z-10 max-w-6xl mx-auto px-6 py-20 border-t border-[#1c1c28]">
        <div className="mb-8">
          <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-widest text-[#f26625] mb-1">
            <Layers className="w-3.5 h-3.5" />
            <span>Cognitive Architecture</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-bold text-white font-display">
            7 Autonomous Synthesis Engines
          </h2>
        </div>

        {/* 2-Column Sandbox Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Engine Selector Column */}
          <div className="lg:col-span-5 divide-y divide-[#272738] rounded-md border border-[#272738] bg-[#0e0e15] overflow-hidden">
            {ENGINES.map((eng) => {
              const isCurrent = selectedEngine === eng.id
              return (
                <div
                  key={eng.id}
                  onClick={() => {
                    playClickSound()
                    setSelectedEngine(eng.id)
                  }}
                  className={clsx(
                    'px-3.5 py-3 transition-colors cursor-pointer relative flex items-center justify-between',
                    isCurrent
                      ? 'bg-[#141420] border-l-2 border-l-[#f26625]'
                      : 'hover:bg-[#161622]'
                  )}
                >
                  <div className="flex items-center space-x-3">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#1c1c28] text-white font-semibold">
                      {eng.badge}
                    </span>
                    <h3 className="text-xs font-bold text-white">{eng.name}</h3>
                  </div>
                  {isCurrent && (
                    <span className="flex items-center gap-1 text-xs font-mono text-[#f26625]">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </span>
                  )}
                </div>
              )
            })}
          </div>

          {/* Engine Output Inspector Sandbox */}
          <div className="lg:col-span-7 rounded-xl border border-[#272738] bg-[#09090e] p-5 flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#1c1c28]">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-[#f26625]" />
                <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                  Example Output ({currentEngineObj.name})
                </span>
              </div>
              <button
                onClick={() => handleCopyCode(JSON.stringify(currentEngineObj.sample, null, 2))}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#161622] hover:bg-[#202030] text-zinc-300 hover:text-white text-xs font-mono transition-colors"
              >
                {copiedCode ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedCode ? 'Copied' : 'Copy Sample'}</span>
              </button>
            </div>

            {/* Structured Preview */}
            <div className="rounded-lg bg-[#050508] border border-[#1a1a24] p-4 font-mono text-xs text-zinc-300 leading-relaxed overflow-x-auto max-h-[380px] space-y-3">
              <pre className="text-emerald-400 whitespace-pre-wrap">
                {JSON.stringify(currentEngineObj.sample, null, 2)}
              </pre>
            </div>

            <div className="pt-2 border-t border-[#1c1c28] flex items-center justify-end text-xs font-mono text-zinc-500">
              <span>Example output</span>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 3: Autonomous Distributed Pipeline DAG Architecture
      ───────────────────────────────────────────────────────────── */}
      <section id="dag" className="relative z-10 max-w-6xl mx-auto px-6 py-20 border-t border-[#1c1c28]">
        <div className="mb-12 text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center space-x-2 text-xs font-mono uppercase tracking-widest text-[#f26625] mb-2">
            <GitBranch className="w-3.5 h-3.5" />
            <span>Distributed Orchestration DAG</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
            Autonomous 4-Stage Synthesis Pipeline
          </h2>
        </div>

        {/* Dynamic Vector Architecture Stream */}
        <SynthesisFlowDiagram />
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 4: Cryptographic DBOM Attestation
      ───────────────────────────────────────────────────────────── */}
      <section id="dbom" className="relative z-10 max-w-6xl mx-auto px-6 py-16 border-t border-[#1c1c28]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6 p-8 rounded-2xl bg-[#0d0d15] border border-[#272738]">
          <div className="space-y-2 max-w-2xl">
            <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-widest text-[#f26625]">
              <ShieldCheck className="w-4 h-4" />
              <span>Cryptographic Provenance</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white font-display">
              Data Bill of Materials (DBOM)
            </h2>
            <p className="text-xs text-zinc-400 leading-relaxed font-sans">
              Cryptographically verify datasets with SHA-256 Merkle tree roots, automated PII scan reports, and tamper-evident provenance certificates.
            </p>
            <div className="pt-2 text-xs font-mono text-zinc-500">
              <span>Example</span>
            </div>
          </div>
          <div className="shrink-0">
            <Link
              href="/dbom"
              className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-mono font-bold transition-all shadow-md active:scale-95"
            >
              <span>Explore DBOM Attestation</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 5: Developer Quickstart & SDK
      ───────────────────────────────────────────────────────────── */}
      <section id="sdk" className="relative z-10 max-w-6xl mx-auto px-6 py-20 border-t border-[#1c1c28]">
        <div className="mb-10 text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center space-x-2 text-xs font-mono uppercase tracking-widest text-[#f26625] mb-2">
            <Terminal className="w-3.5 h-3.5" />
            <span>Developer Integration</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
            Synthesize Directly via API or Python SDK
          </h2>
        </div>

        {/* Code Terminal Box */}
        <div className="max-w-3xl mx-auto rounded-xl border border-[#272738] bg-[#09090e] overflow-hidden shadow-2xl">
          {/* Tabs */}
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1c1c28] bg-[#0d0d14]">
            <div className="flex items-center space-x-2">
              {(['python', 'curl', 'typescript'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => {
                    playClickSound()
                    setCodeTab(tab)
                  }}
                  className={clsx(
                    'px-3 py-1 rounded text-xs font-mono transition-all uppercase',
                    codeTab === tab
                      ? 'bg-[#181824] text-white font-bold border border-[#272738]'
                      : 'text-zinc-500 hover:text-zinc-300'
                  )}
                >
                  {tab === 'python' ? 'Python SDK' : tab === 'curl' ? 'cURL / REST' : 'TypeScript'}
                </button>
              ))}
            </div>

            <button
              onClick={() => handleCopyCode(CODE_SNIPPETS[codeTab])}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#161622] hover:bg-[#202030] text-zinc-300 hover:text-white text-xs font-mono transition-colors"
            >
              {copiedCode ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              <span>{copiedCode ? 'Copied' : 'Copy'}</span>
            </button>
          </div>

          {/* Snippet Output */}
          <div className="p-5 font-mono text-xs text-zinc-200 overflow-x-auto bg-[#050508] leading-relaxed">
            <pre className="text-zinc-300">{CODE_SNIPPETS[codeTab]}</pre>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 6: Presentation Footer
      ───────────────────────────────────────────────────────────── */}
      <footer className="relative z-10 py-4 border-t border-[#1c1c28] bg-[#07070b] text-xs font-mono text-zinc-500">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>© 2026 RasoSynthTune · Autonomous Synthetic Data Engine</span>
          <FooterStatus />
        </div>
      </footer>
    </div>
  )
}
