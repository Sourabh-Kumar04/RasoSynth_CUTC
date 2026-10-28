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
  Copy,
  Check,
  GitBranch,
  FileText,
  Binary,
  Compass,
  Lock,
  Server,
  BarChart3,
  Network,
  Scale,
  Menu,
  X,
  HelpCircle,
} from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api/client'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'
import { MerkleTreeGraph } from '@/components/dbom/merkle-tree-graph'
import { computeSampleHash, computeMerkleRoot } from '@/lib/crypto'
import { BrandLogo } from '@/components/ui/brand-logo'
import { SynthesisFlowDiagram } from '@/components/ui/synthesis-flow-diagram'

// 7 Synthesis Engines Definition with example preview data (illustrative, not live output)
const ENGINES = [
  {
    id: 'cot',
    name: 'Chain-of-Thought',
    badge: 'CoT',
    description: 'Multi-step deliberate cognitive paths with self-correction verification.',
    detail: 'Enforces rigorous step-by-step mathematical, statutory, and causal derivations.',
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
    description: 'Inquisitive guided dialogue probing edge-cases and latent assumptions.',
    detail: 'Iterative dialectical reasoning that draws out edge-case nuances and proofs.',
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
    description: 'Rigorous chosen vs rejected comparative pairs for policy alignment.',
    detail: 'Direct Preference Optimization pairs calibrated by LLM-Judge rubric.',
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
    description: 'Extended conversational sessions with state tracking & context drift.',
    detail: 'Simulates complex long-horizon human-agent collaboration and memory retention.',
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
    description: 'Executable JSON function schemas with arguments & structured outputs.',
    detail: 'Synthesizes enterprise-grade function calling tokens and deterministic execution.',
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
    description: 'Direct negative boundary calibration against anti-domain pollution.',
    detail: 'Maps negative semantic boundaries to immunize against out-of-domain hallucinations.',
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
    description: 'Statutory citations and factual grounding against verified document nodes.',
    detail: 'Extracts real circulars, legal rulings, and technical repos without hallucination.',
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

// 4-Stage Pipeline Architecture Stages

// Code Quickstart Snippets
const CODE_SNIPPETS = {
  python: `from rasosynth import RasoSynthClient

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

console.log('Job dispatched to Ray cluster:', job.id)`,
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
  const [showVerifyModal, setShowVerifyModal] = useState(false)
  const [recomputedRoot, setRecomputedRoot] = useState<string | null>(null)
  const [isRecomputing, setIsRecomputing] = useState(false)

  const handleRecomputeClientSide = () => {
    setIsRecomputing(true)
    playClickSound()
    setTimeout(() => {
      const demoSamples = [
        { instruction: 'Verify if input tax credit on purchases made in FY 2022-23 can be claimed in GSTR-3B filed on 25th November 2023 under Section 16(4) CGST Act.', response: 'Under Section 16(4) of the CGST Act 2017, the deadline to claim ITC is 30th November following the end of financial year.', input: '' },
        { instruction: 'Corporate surcharge applicability for domestic companies opting for Section 115BAA.', response: 'A flat 10% surcharge applies across all income brackets under Section 115BAA.', input: '' },
      ]
      const hashes = demoSamples.map((s) => computeSampleHash(s))
      const root = computeMerkleRoot(hashes)
      setRecomputedRoot(root)
      setIsRecomputing(false)
      playSuccessChime()
    }, 300)
  }

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
      className="relative min-h-screen bg-[#0a0a0f] text-[#f8fafc] overflow-hidden selection:bg-[#f26625]/30 selection:text-white font-sans"
    >
      {/* GSAP Fluid Aura Field */}
      <div
        ref={auraRef}
        className="pointer-events-none absolute -top-0 -left-0 w-[500px] h-[500px] rounded-full bg-[radial-gradient(circle,rgba(242,102,37,0.1)_0%,rgba(242,102,37,0.02)_40%,transparent_70%)] blur-3xl z-0"
      />

      {/* Subtle Spatial Dot Grid (negative space backdrop) */}
      <div className="absolute inset-0 bg-dot-grid opacity-20 pointer-events-none z-0" />

      {/* ─────────────────────────────────────────────────────────────
          SECTION 0: Top Minimalist Aperture Bar
      ───────────────────────────────────────────────────────────── */}
      <header className="relative z-20 flex items-center justify-between px-6 sm:px-12 py-5 border-b border-[#1c1c28]/40 backdrop-blur-md">
        <div className="flex items-center space-x-3">
          <Link href="/" className="flex items-center space-x-2.5 group">
            <BrandLogo size={32} />
            <div className="flex flex-col">
              <span className="font-display text-sm font-bold tracking-tight text-white">
                Raso<span className="bg-gradient-to-r from-[#f26625] via-[#ff8238] to-[#f59e0b] bg-clip-text text-transparent">Synth</span><span className="text-[#94a3b8] font-semibold">Tune</span>
              </span>
              <span className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
                Sovereign Synthesis Hub
              </span>
            </div>
          </Link>
        </div>

        <nav className="hidden md:flex items-center space-x-6 text-xs font-mono text-zinc-400">
          <Link href="#engines" className="hover:text-white transition-colors">
            Engines
          </Link>
          <Link href="#dag" className="hover:text-white transition-colors">
            Architecture
          </Link>
          <Link href="#dbom" className="hover:text-white transition-colors">
            DBOM Attestor
          </Link>
          <Link href="#quality" className="hover:text-white transition-colors">
            Neural Quality
          </Link>
          <Link href="#sdk" className="hover:text-white transition-colors">
            API Quickstart
          </Link>
        </nav>

        <div className="flex items-center space-x-3">
          <Link
            href="/providers"
            className="hidden sm:flex items-center space-x-2 text-xs font-mono px-2.5 py-1 rounded bg-[#12121a] border border-[#272738] text-zinc-300 hover:border-[#f26625]/40 transition-colors"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>7 ENGINES CONFIGURED</span>
          </Link>

          <Link
            href="/studio"
            className="hidden sm:inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md border border-[#272738] bg-[#12121a] hover:bg-[#1a1a24] text-xs font-mono font-medium text-zinc-300 hover:text-white transition-all shadow-sm active:scale-95"
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
                href="/datasets"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Data Library</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/finetune"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Model Training</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/orchestration"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Pipelines</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/review"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Review</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/quality"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Quality</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/observability"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Telemetry</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/research"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Benchmarks</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/providers"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>Providers</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
              <Link
                href="/settings"
                onClick={() => setIsMobileMenuOpen(false)}
                className="p-2 rounded bg-[#141420] border border-[#222232] hover:border-[#f26625]/50 flex items-center justify-between"
              >
                <span>System Status</span>
                <ArrowRight className="w-3 h-3 text-[#f26625]" />
              </Link>
            </div>
            <div className="pt-2 flex items-center justify-between text-xs text-zinc-400 border-t border-[#1c1c28]">
              <a href="#engines" onClick={() => setIsMobileMenuOpen(false)} className="hover:text-white">Engines</a>
              <a href="#dag" onClick={() => setIsMobileMenuOpen(false)} className="hover:text-white">Architecture</a>
              <a href="#dbom" onClick={() => setIsMobileMenuOpen(false)} className="hover:text-white">DBOM</a>
              <a href="#quality" onClick={() => setIsMobileMenuOpen(false)} className="hover:text-white">Quality</a>
              <a href="#sdk" onClick={() => setIsMobileMenuOpen(false)} className="hover:text-white">SDK</a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 1: Zen Spatial Command Hub (Hero)
      ───────────────────────────────────────────────────────────── */}
      <section className="relative z-10 flex flex-col items-center justify-center min-h-[82vh] px-4 sm:px-6 max-w-5xl mx-auto py-12">
        {/* Subtle Aperture Tag */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="inline-flex items-center space-x-2 px-3.5 py-1 rounded-full bg-[#12121a]/90 border border-[#272738] text-xs font-mono text-zinc-400 mb-6 backdrop-blur-md shadow-sm"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-[#f26625] animate-ping" />
          <span className="tracking-widest uppercase text-white font-semibold">SYNTH_NEXUS // VERIFIED DBOM</span>
          <span className="text-zinc-600">/</span>
          <span className="text-zinc-400">Async Multiprocess · SHA-256 Sealed</span>
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
                title="Execute directly via background API task"
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

        {/* Real-time Telemetry Strip */}
        <div className="mt-12 flex flex-wrap items-center justify-center gap-6 text-xs font-mono text-zinc-500 border-t border-[#1c1c28]/60 pt-6">
          <Link href="/observability" className="flex items-center gap-2 hover:text-zinc-300 transition-colors group">
            <Server className="w-3.5 h-3.5 text-[#f26625]" />
            <span>Worker Pool: <strong className="text-zinc-200 font-normal group-hover:text-white">8 Threads Configured</strong></span>
          </Link>
          <span className="text-zinc-700">·</span>
          <Link href="/review" className="flex items-center gap-2 hover:text-zinc-300 transition-colors group">
            <Lock className="w-3.5 h-3.5 text-purple-400" />
            <span>DBOM Proofs: <strong className="text-zinc-200 font-normal group-hover:text-white">SHA-256 Merkle Sealed</strong></span>
          </Link>
          <span className="text-zinc-700">·</span>
          <Link href="/quality" className="flex items-center gap-2 hover:text-zinc-300 transition-colors group">
            <Scale className="w-3.5 h-3.5 text-emerald-400" />
            <span>Neural Judge: <strong className="text-zinc-200 font-normal group-hover:text-white">Dual-Layer Cosine + LLM Rubric</strong></span>
          </Link>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 2: Interactive 7-Engine Cognitive Synthesis Sandbox
      ───────────────────────────────────────────────────────────── */}
      <section id="engines" className="relative z-10 max-w-6xl mx-auto px-6 py-20 border-t border-[#1c1c28]">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-8 gap-4">
          <div>
            <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-widest text-[#f26625] mb-1">
              <Layers className="w-3.5 h-3.5" />
              <span>Cognitive Architecture</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white font-display">
              7 Autonomous Synthesis Engines Sandbox
            </h2>
            <p className="text-xs text-zinc-400 mt-1 max-w-2xl">
              Select an engine to inspect its live cognitive output, thought steps, and structured invariants.
            </p>
          </div>

          <Link
            href="/studio"
            className="text-xs font-mono text-[#f26625] hover:text-[#de581a] flex items-center space-x-1 self-start sm:self-auto"
          >
            <span>Open Studio Lab</span>
            <ExternalLink className="w-3 h-3" />
          </Link>
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
                    'px-3 py-2.5 transition-colors cursor-pointer relative',
                    isCurrent
                      ? 'bg-[#14141e] border-l-2 border-l-[#f26625]'
                      : 'hover:bg-[#161622]'
                  )}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#1c1c28] text-white font-semibold">
                      {eng.badge}
                    </span>
                    {isCurrent && (
                      <span className="flex items-center gap-1 text-xs font-mono text-[#f26625]">
                        <CheckCircle2 className="w-3 h-3" />
                        Selected
                      </span>
                    )}
                  </div>
                  <h3 className="text-xs font-bold text-white">{eng.name}</h3>
                  <p className="text-xs text-zinc-400 mt-0.5 leading-relaxed">{eng.description}</p>
                </div>
              )
            })}
          </div>

          {/* Engine Output Inspector Sandbox — demo samples, not live output */}
          <div className="lg:col-span-7 rounded-xl border border-[#272738] bg-[#09090e] p-5 flex flex-col justify-between space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#1c1c28]">
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-[#f26625]" />
                <span className="inline-flex items-center rounded-sm border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-xs font-bold text-amber-400">
                  DEMO
                </span>
                <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                  Example output (illustrative) ({currentEngineObj.name})
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

            <div className="pt-2 border-t border-[#1c1c28] flex items-center justify-between text-xs font-mono text-zinc-500">
              <span>Grounding Invariant: Strict DPDP Act &amp; Citation Rules</span>
              <span className="text-[#f26625]">Example quality score: 0.94 / 1.00 (illustrative, not a live result)</span>
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
          <p className="text-xs text-zinc-400 mt-2">
            Non-linear state machine executing discovery, multi-engine cognitive loops, neural validation, and cryptographic attestation.
          </p>
        </div>

        {/* Dynamic Vector Architecture Stream */}
        <SynthesisFlowDiagram />

        <div className="mt-4 p-3 rounded-lg bg-[#0e0e16] border border-[#1f1f2e] text-xs font-mono text-zinc-400 text-center">
          * Latency benchmarked on local multi-worker container setup (45ms corpus discovery, 280ms synthesis, 120ms neural evaluation, 15ms Merkle packaging). Real LLM provider API latency varies from 1.2s to 4.5s depending on model and context window size.
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 4: Cryptographic DBOM & Data Nutrition Label Explorer
      ───────────────────────────────────────────────────────────── */}
      <section id="dbom" className="relative z-10 max-w-6xl mx-auto px-6 py-20 border-t border-[#1c1c28]">
        <div className="mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2 text-xs font-mono uppercase tracking-widest text-purple-400 mb-1">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Cryptographic Provenance Guarantee</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-white font-display">
              Data Bill of Materials (DBOM) &amp; Nutrition Labels
            </h2>
            <p className="text-xs text-zinc-400 mt-1 max-w-2xl">
              Every synthesized batch is cryptographically anchored into a SHA-256 Merkle tree. Certificates attest to zero PII leakage and statutory fidelity.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                playClickSound()
                setShowVerifyModal(true)
              }}
              className="text-xs font-mono text-zinc-300 hover:text-white px-2.5 py-1.5 rounded bg-[#161622] hover:bg-[#1f1f2e] border border-[#272738] transition-colors flex items-center space-x-1"
            >
              <HelpCircle className="w-3.5 h-3.5 text-[#f26625]" />
              <span>Verify Hash Yourself</span>
            </button>
            <Link
              href="/review"
              className="text-xs font-mono text-purple-400 hover:text-purple-300 flex items-center space-x-1"
            >
              <span>Verify Certificates</span>
              <ExternalLink className="w-3 h-3" />
            </Link>
          </div>
        </div>

        {/* 3-Step Verification Guide Modal */}
        <AnimatePresence>
          {showVerifyModal && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
              className="mb-8 p-5 rounded-xl border border-purple-500/40 bg-[#0e0c18] font-mono text-xs text-zinc-300 space-y-4"
            >
              <div className="flex items-center justify-between border-b border-purple-900/40 pb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[#f26625]" />
                  <span className="font-bold text-white uppercase tracking-wider">
                    How to Independently Verify the DBOM Hash (3 Steps)
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowVerifyModal(false)}
                  className="text-zinc-400 hover:text-white p-1"
                  aria-label="Close verification guide"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-3 rounded-lg bg-[#07060d] border border-purple-900/30 space-y-1.5">
                  <span className="text-xs text-[#f26625] font-bold">STEP 1: Export Payload</span>
                  <p className="text-xs text-zinc-400 font-sans">
                    Download the raw certified JSONL samples from the dataset library.
                  </p>
                  <code className="text-xs text-purple-300 block bg-[#12101e] p-1.5 rounded overflow-x-auto">
                    curl -s https://rasosynthtune.vercel.app/api/export -o samples.jsonl
                  </code>
                </div>

                <div className="p-3 rounded-lg bg-[#07060d] border border-purple-900/30 space-y-1.5">
                  <span className="text-xs text-purple-400 font-bold">STEP 2: Compute SHA-256</span>
                  <p className="text-xs text-zinc-400 font-sans">
                    Run native standard SHA-256 on your local machine to obtain leaf digests.
                  </p>
                  <code className="text-xs text-purple-300 block bg-[#12101e] p-1.5 rounded overflow-x-auto">
                    python3 -c &quot;import hashlib; print(hashlib.sha256(open(&apos;samples.jsonl&apos;,&apos;rb&apos;).read()).hexdigest())&quot;
                  </code>
                </div>

                <div className="p-3 rounded-lg bg-[#07060d] border border-purple-900/30 space-y-1.5">
                  <span className="text-xs text-emerald-400 font-bold">STEP 3: Fold Merkle Parent</span>
                  <p className="text-xs text-zinc-400 font-sans">
                    Pairwise hash siblings: H(Leaf0 || Leaf1). Example 64-hex root (illustrative):
                  </p>
                  <code className="text-xs text-emerald-300 block bg-[#12101e] p-1.5 rounded overflow-x-auto truncate">
                    9b87df7a3982f6e9b418a096c429712a5542a1ef248f27af3b028da3d91cf972
                  </code>
                </div>
              </div>

              {/* In-Browser Interactive Recomputation Bar */}
              <div className="pt-3 border-t border-purple-900/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0a0814] p-3 rounded-lg border border-purple-950">
                <div className="space-y-0.5">
                  <div className="flex items-center space-x-1.5 text-white font-bold text-xs">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="inline-flex items-center rounded-sm border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 font-mono text-xs font-bold text-amber-400">
                      DEMO
                    </span>
                    <span>In-Browser Demo Verifier (2 example samples)</span>
                  </div>
                  <p className="text-xs text-zinc-400 font-sans">
                    Demo only: hashes 2 fixed example samples in-browser. It does not hash or verify any active dataset.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={handleRecomputeClientSide}
                  disabled={isRecomputing}
                  className="px-3 py-1.5 rounded bg-purple-600/30 hover:bg-purple-600/50 border border-purple-500/50 text-white text-xs font-mono transition-all flex items-center justify-center space-x-1.5 disabled:opacity-50 shrink-0"
                >
                  {isRecomputing ? (
                    <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Zap className="w-3 h-3 text-purple-300" />
                  )}
                  <span>{recomputedRoot ? 'Re-run Demo' : 'Run 2-Sample Demo'}</span>
                </button>
              </div>

              {recomputedRoot && (
                <div className="p-2.5 rounded bg-[#0e1612] border border-emerald-500/40 text-emerald-300 text-xs space-y-1">
                  <div className="flex items-center space-x-2 font-bold">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Demo recomputation complete: root of the 2 example samples (not compared to any stored dataset root)</span>
                  </div>
                  <div className="font-mono text-xs break-all text-zinc-300 bg-[#070b09] p-1.5 rounded">
                    Root: {recomputedRoot}
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Interactive Merkle Tree Graph */}
          <div className="lg:col-span-7">
            <p className="text-xs font-mono text-amber-300 mb-3">Example attestation - the root, certificate ID, sample count, and date below are illustrative, not fetched from a live dataset.</p>
            <MerkleTreeGraph
              rootHash="9b87df7a3982f6e9b418a096c429712a5542a1ef248f27af3b028da3d91cf972"
              certificateId="DBOM-VERIFIED-DATASET"
              totalSamples={100}
              issuedAt="2026-10-28T12:00:00Z"
            />
          </div>

          {/* Right Column: Digital Data Nutrition Label Card */}
          <div className="lg:col-span-5 p-5 rounded-xl border border-[#272738] bg-[#0c0c14] space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#1c1c28]">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                  Data Nutrition Facts (Reference Example)
                </span>
              </div>
              <span className="text-xs font-mono text-emerald-400 font-semibold">Reference Example</span>
            </div>

            <div className="space-y-2.5 text-xs font-mono">
              <div className="flex justify-between py-1 border-b border-[#1c1c28]/60 text-zinc-400">
                <span>Dataset Certificate:</span>
                <span className="text-white font-bold">DBOM-VERIFIED-DATASET</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#1c1c28]/60 text-zinc-400">
                <span>Indic DPDP PII Exposure:</span>
                <span className="text-emerald-400 font-bold">0.00% (Zero Leakage)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#1c1c28]/60 text-zinc-400">
                <span>Script Purity (Devanagari):</span>
                <span className="text-emerald-400 font-bold">99.8% Native Script</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#1c1c28]/60 text-zinc-400">
                <span>Token Fertility (Sarvam Indic):</span>
                <span className="text-white font-bold">1.28 tokens / word</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#1c1c28]/60 text-zinc-400">
                <span>Token Fertility (Llama-3 Indic):</span>
                <span className="text-white font-bold">3.65 tokens / word</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#1c1c28]/60 text-zinc-400">
                <span>Semantic Cosine Gate:</span>
                <span className="text-emerald-400 font-bold">&gt; 0.92 Dedup / 0.40 Domain</span>
              </div>
              <div className="flex justify-between py-1 text-zinc-400">
                <span>Export Formats:</span>
                <span className="text-[#f26625] font-bold">HuggingFace · DPO · Parquet</span>
              </div>
            </div>

            <div className="pt-2 border-t border-[#1c1c28]">
              <Link
                href="/datasets"
                className="w-full inline-flex items-center justify-center gap-2 py-2 rounded-lg bg-[#161622] hover:bg-[#202030] text-xs font-mono text-zinc-300 hover:text-white transition-colors border border-[#272738]"
              >
                <span>Browse Attested Datasets</span>
                <ArrowRight className="w-3.5 h-3.5 text-[#f26625]" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 5: Neural Evaluation & Quality Scorer Matrix
      ───────────────────────────────────────────────────────────── */}
      <section id="quality" className="relative z-10 max-w-6xl mx-auto px-6 py-20 border-t border-[#1c1c28]">
        <div className="mb-10 text-center max-w-2xl mx-auto">
          <div className="inline-flex items-center space-x-2 text-xs font-mono uppercase tracking-widest text-[#10b981] mb-2">
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Neural Quality Scorer</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold text-white font-display">
            Rigorous Neural Quality Metrics
          </h2>
          <p className="text-xs text-zinc-400 mt-2">
            Every sample is filtered against neural cosine embeddings and graded by our pure LLM Judge rubric before admission into the dataset. The figures in this section are reference values, not measured per-dataset results.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-5 rounded-xl border border-[#272738] bg-[#0c0c14] space-y-2">
            <span className="text-xs font-mono text-zinc-500 uppercase">Reasoning Depth</span>
            <div className="text-2xl font-bold text-white font-mono">+48.2%</div>
            <p className="text-xs text-zinc-400">Cognitive multi-step reasoning steps vs generic web crawling.</p>
            <div className="w-full bg-[#1c1c28] h-1.5 rounded-full overflow-hidden mt-3">
              <div className="bg-[#f26625] h-full rounded-full" style={{ width: '92%' }} />
            </div>
          </div>

          <div className="p-5 rounded-xl border border-[#272738] bg-[#0c0c14] space-y-2">
            <span className="text-xs font-mono text-zinc-500 uppercase">Statutory Grounding</span>
            <div className="text-2xl font-bold text-emerald-400 font-mono">99.4%</div>
            <p className="text-xs text-zinc-400">Verified statutory and circular citations with zero hallucination.</p>
            <div className="w-full bg-[#1c1c28] h-1.5 rounded-full overflow-hidden mt-3">
              <div className="bg-emerald-400 h-full rounded-full" style={{ width: '99%' }} />
            </div>
          </div>

          <div className="p-5 rounded-xl border border-[#272738] bg-[#0c0c14] space-y-2">
            <span className="text-xs font-mono text-zinc-500 uppercase">Script Fidelity</span>
            <div className="text-2xl font-bold text-purple-400 font-mono">99.8%</div>
            <p className="text-xs text-zinc-400">Zero Romanized transliteration leakage on native Indic corpora.</p>
            <div className="w-full bg-[#1c1c28] h-1.5 rounded-full overflow-hidden mt-3">
              <div className="bg-purple-400 h-full rounded-full" style={{ width: '99.8%' }} />
            </div>
          </div>

          <div className="p-5 rounded-xl border border-[#272738] bg-[#0c0c14] space-y-2">
            <span className="text-xs font-mono text-zinc-500 uppercase">Deduplication Distance</span>
            <div className="text-2xl font-bold text-cyan-400 font-mono">0.85</div>
            <p className="text-xs text-zinc-400">Cosine similarity threshold eliminating redundant synthetic tokens.</p>
            <div className="w-full bg-[#1c1c28] h-1.5 rounded-full overflow-hidden mt-3">
              <div className="bg-cyan-400 h-full rounded-full" style={{ width: '85%' }} />
            </div>
          </div>
        </div>
      </section>

      {/* ─────────────────────────────────────────────────────────────
          SECTION 6: Developer Quickstart & SDK Terminal
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
          <p className="text-xs text-zinc-400 mt-2">
            Trigger autonomous dataset pipelines programmatically from your training workflows and CI/CD runs.
          </p>
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
          SECTION 7: Comprehensive System Footer
      ───────────────────────────────────────────────────────────── */}
      <footer className="relative z-10 py-12 border-t border-[#1c1c28] bg-[#07070b]">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-10 text-xs font-mono">
            {/* Col 1 */}
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <BrandLogo size={24} />
                <span className="font-display font-bold text-white text-sm tracking-tight">
                  Raso<span className="bg-gradient-to-r from-[#f26625] via-[#ff8238] to-[#f59e0b] bg-clip-text text-transparent">Synth</span><span className="text-[#94a3b8] font-semibold">Tune</span>
                </span>
              </div>
              <p className="text-xs text-zinc-400 leading-relaxed font-sans">
                Autonomous dataset synthesis and evaluation orchestration platform for frontier AI models.
              </p>
              <div className="flex items-center gap-2 text-xs text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>Hybrid Standalone · Operational</span>
              </div>
            </div>

            {/* Col 2: Synthesis Engines */}
            <div className="space-y-2">
              <span className="text-zinc-200 font-bold uppercase tracking-wider text-xs">7 Engines</span>
              <ul className="space-y-1.5 text-zinc-400 text-xs">
                <li>Chain-of-Thought (CoT)</li>
                <li>Socratic Dialectic</li>
                <li>DPO Preference Pairs</li>
                <li>Multi-Turn Agentic</li>
                <li>Tool Calling Schemas</li>
                <li>Contrastive Boundaries</li>
                <li>RAG Grounded Corpus</li>
              </ul>
            </div>

            {/* Col 3: Navigation */}
            <div className="space-y-2">
              <span className="text-zinc-200 font-bold uppercase tracking-wider text-xs">Platform</span>
              <ul className="space-y-1.5 text-zinc-400 text-xs">
                <li><Link href="/studio" className="hover:text-white transition-colors">Studio Lab</Link></li>
                <li><Link href="/review" className="hover:text-white transition-colors">Review &amp; DBOM Audit</Link></li>
                <li><Link href="/datasets" className="hover:text-white transition-colors">Attested Datasets</Link></li>
                <li><Link href="/finetune" className="hover:text-white transition-colors">Fine-Tuning Pipeline</Link></li>
                <li><Link href="/observability" className="hover:text-white transition-colors">Cluster Observability</Link></li>
              </ul>
            </div>

            {/* Col 4: Cryptographic Governance */}
            <div className="space-y-2">
              <span className="text-zinc-200 font-bold uppercase tracking-wider text-xs">Governance</span>
              <ul className="space-y-1.5 text-zinc-400 text-xs">
                <li>SHA-256 Merkle Provenance</li>
                <li>Indian DPDP Act Masking</li>
                <li>Data Nutrition Labels</li>
                <li>Redis Sliding Limiter</li>
                <li>LLM Judge Rubric v2</li>
              </ul>
            </div>
          </div>

          <div className="pt-8 border-t border-[#1c1c28]/60 flex flex-col sm:flex-row items-center justify-between text-xs font-mono text-zinc-500 gap-4">
            <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-4">
              <p>© 2026 RasoSynthTune · Apache 2.0 Open Source Architecture</p>
              <span className="hidden sm:inline text-zinc-700">·</span>
              <a
                href="https://github.com/Sourabh-Kumar04/RasoSynthTune"
                target="_blank"
                rel="noreferrer"
                className="hover:text-white transition-colors underline underline-offset-2"
              >
                GitHub Repository
              </a>
              <span className="hidden sm:inline text-zinc-700">·</span>
              <a
                href="https://huggingface.co/spaces/Sourabh-Kumar04/RasoSynthTune"
                target="_blank"
                rel="noreferrer"
                className="hover:text-white transition-colors underline underline-offset-2"
              >
                Hugging Face Space
              </a>
            </div>
            <div className="flex items-center space-x-3 text-zinc-400">
              <span className="text-emerald-400">● Hosted Space Demo Ready</span>
              <span>·</span>
              <span>Python 3.12 · Next.js 14</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
