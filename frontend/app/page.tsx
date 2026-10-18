'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { clsx } from 'clsx'
import {
  Database,
  Cpu,
  FlaskConical,
  Activity,
  ClipboardCheck,
  Zap,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  Server,
  Layers,
  BarChart2,
  Clock,
  Play,
  Workflow,
  Search,
  Filter,
  Check,
  ChevronRight,
  Terminal,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { api, HealthStatus } from '@/lib/api/client'
import { TopNav } from '@/components/layout/top-nav'
import { Sidebar } from '@/components/layout/sidebar'

export default function OverviewDashboardPage() {
  const router = useRouter()
  const [health, setHealth] = useState<any | null>(null)
  const [datasetJobs, setDatasetJobs] = useState<any[]>([])
  const [finetuneJobs, setFinetuneJobs] = useState<any[]>([])
  const [reviewCount, setReviewCount] = useState<number>(0)
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [queryInput, setQueryInput] = useState<string>(
    'Synthesize 10,000 multi-turn instruction dialogues from AI Kosh tax rulings & GST statutes with self-correction'
  )
  const [selectedDomain, setSelectedDomain] = useState<string>('Finance & Taxation (AI Kosh)')
  const [generationMode, setGenerationMode] = useState<'grounded' | 'synthetic'>('grounded')

  useEffect(() => {
    async function loadDashboardData() {
      setIsLoading(true)
      try {
        const [healthRes, datasetsRes, finetuneRes, reviewRes] = await Promise.allSettled([
          api.getHealth(),
          api.getJobs({ limit: 6 }),
          api.listFineTuneJobs(),
          api.getReviewQueue()
        ])

        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (datasetsRes.status === 'fulfilled' && datasetsRes.value?.data) {
          setDatasetJobs(datasetsRes.value.data.slice(0, 6))
        }
        if (finetuneRes.status === 'fulfilled' && finetuneRes.value?.jobs) {
          setFinetuneJobs(finetuneRes.value.jobs.slice(0, 5))
        }
        if (reviewRes.status === 'fulfilled' && Array.isArray(reviewRes.value)) {
          setReviewCount(reviewRes.value.filter((r: any) => r.status === 'pending').length)
        }
      } catch (err: any) {
        console.error('Failed to load dashboard data:', err)
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboardData()
    const interval = setInterval(loadDashboardData, 10000)
    return () => clearInterval(interval)
  }, [])

  const activeJobsCount = datasetJobs.filter((j) => j.status === 'running').length
  const completedJobsCount = datasetJobs.filter((j) => j.status === 'completed').length

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-[#f8fafc] flex flex-col font-sans antialiased bg-dot-grid">
      <TopNav />
      <div className="flex-1 flex w-full">
        <Sidebar />
        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 space-y-6">
          <div className="w-full max-w-7xl mx-auto space-y-6">
            
            {/* Top Command Banner */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#272738] pb-5">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#1a1a24] border border-[#272738] text-[#10b981] uppercase tracking-wider">
                    AUTONOMOUS STUDIO
                  </span>
                  <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white font-display">
                    Engineering Command Center
                  </h1>
                </div>
                <p className="text-xs text-[#94a3b8]">
                  Grounded multi-source dataset discovery, AST extraction, LangGraph DAG execution, & PEFT/LoRA fine-tuning
                </p>
              </div>

              <div className="flex items-center gap-2.5">
                <Link href="/studio">
                  <Button className="bg-[#6366f1] hover:bg-[#818cf8] text-white text-xs font-mono font-medium shadow-sm glow-indigo flex items-center gap-1.5 h-8">
                    <FlaskConical className="w-3.5 h-3.5" />
                    <span>Open Dataset Studio</span>
                  </Button>
                </Link>
                <Link href="/orchestration">
                  <Button variant="outline" className="border-[#272738] bg-[#12121a] hover:bg-[#1a1a24] text-white text-xs font-mono h-8">
                    <Workflow className="w-3.5 h-3.5 mr-1 text-[#818cf8]" />
                    Live DAG Trace
                  </Button>
                </Link>
              </div>
            </div>

            {/* Quick Natural Language Intent & Query Optimizer Input Bar */}
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-4 rounded-lg bg-[#12121a] border border-[#272738] space-y-3 relative overflow-hidden"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-[#818cf8]" />
                  <span className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                    Natural Language Intent & Compute-Saving Query Optimizer
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-[11px] font-mono">
                  <span className="text-[#10b981] flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                    Refiner Active (-42% compute tokens)
                  </span>
                </div>
              </div>

              <div className="relative">
                <textarea
                  value={queryInput}
                  onChange={(e) => setQueryInput(e.target.value)}
                  rows={2}
                  className="w-full bg-[#0a0a0f] border border-[#272738] focus:border-[#6366f1] rounded-md p-3 text-xs font-mono text-[#f8fafc] placeholder:text-[#94a3b8] focus:outline-none transition-colors resize-none"
                  placeholder="Describe your dataset target domain, schema, and quality constraints..."
                />
              </div>

              {/* 1-Click Domain Presets & CTA */}
              <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1">
                <div className="flex flex-wrap items-center gap-1.5 text-xs font-mono">
                  <span className="text-[#94a3b8] text-[11px]">Presets:</span>
                  {[
                    'Finance & Taxation (AI Kosh)',
                    'Indic Multilingual (Bhashini)',
                    'Python Math & Code',
                    'Medical Clinical Reasoning',
                  ].map((preset) => (
                    <button
                      key={preset}
                      onClick={() => {
                        setSelectedDomain(preset)
                        if (preset.includes('AI Kosh')) {
                          setQueryInput('Extract high-precision tax tribunal disputes, GST input-tax-credit reconciliation case studies, and compliance dialogues from AI Kosh')
                        } else if (preset.includes('Bhashini')) {
                          setQueryInput('Compile parallel Indic English-to-Hindi, Tamil, Telugu technical domain translation corpus with validation benchmarks')
                        } else if (preset.includes('Python')) {
                          setQueryInput('Synthesize 25,000 algorithmic Python code translation and debugging pairs with test cases and complexity analysis')
                        } else {
                          setQueryInput('Extract clinical reasoning diagnosis trajectories from PubMed preprints and medical case notes with contraindication checks')
                        }
                      }}
                      className={clsx(
                        'px-2 py-0.5 rounded text-[11px] transition-all border',
                        selectedDomain === preset
                          ? 'bg-[#1a1a24] border-[#6366f1] text-[#818cf8] font-medium'
                          : 'bg-[#0e0e13] border-[#272738] text-[#94a3b8] hover:text-white hover:border-[#3b3b52]'
                      )}
                    >
                      {preset}
                    </button>
                  ))}
                </div>

                <div className="flex items-center space-x-2">
                  <span className="text-[11px] font-mono text-[#94a3b8]">Est: <strong className="text-[#10b981]">$18.20</strong></span>
                  <Link href={`/studio?prompt=${encodeURIComponent(queryInput)}&domain=${encodeURIComponent(selectedDomain)}`}>
                    <Button className="bg-[#6366f1] hover:bg-[#818cf8] text-white text-xs font-mono h-7 px-3 flex items-center gap-1">
                      <span>Launch Pipeline</span>
                      <ArrowRight className="w-3 h-3" />
                    </Button>
                  </Link>
                </div>
              </div>
            </motion.div>

            {/* Grid 1: Source Ingestion Engine & Interactive Coverage Matrix */}
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
              
              {/* Left Column: Source Ingestion Engine (5 cols) */}
              <div className="xl:col-span-5 p-4 rounded-lg bg-[#12121a] border border-[#272738] flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-center justify-between pb-2 mb-3 border-b border-[#1c1c28]">
                    <div className="flex items-center space-x-2">
                      <Database className="w-4 h-4 text-[#10b981]" />
                      <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                        Source Ingestion Engine
                      </h3>
                    </div>

                    {/* Grounded vs Synthetic Mode Switch */}
                    <div className="inline-flex p-0.5 rounded bg-[#0a0a0f] border border-[#272738]">
                      <button
                        onClick={() => setGenerationMode('grounded')}
                        className={clsx(
                          'px-2 py-0.5 rounded text-[10px] font-mono transition-all',
                          generationMode === 'grounded'
                            ? 'bg-[#1a1a24] text-white font-semibold border border-[#272738]'
                            : 'text-[#94a3b8] hover:text-white'
                        )}
                      >
                        Grounded Source
                      </button>
                      <button
                        onClick={() => setGenerationMode('synthetic')}
                        className={clsx(
                          'px-2 py-0.5 rounded text-[10px] font-mono transition-all',
                          generationMode === 'synthetic'
                            ? 'bg-[#1a1a24] text-white font-semibold border border-[#272738]'
                            : 'text-[#94a3b8] hover:text-white'
                        )}
                      >
                        Pure Synthetic
                      </button>
                    </div>
                  </div>

                  {/* Active Data Repositories */}
                  <div className="space-y-2">
                    {/* AI Kosh IndiaAI Card */}
                    <div className="p-2.5 rounded bg-[#0e0e13] border border-[#272738] hover:border-[#6366f1]/50 transition-colors flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-7 h-7 rounded bg-[#1a1a24] border border-[#272738] flex items-center justify-center font-mono font-bold text-xs text-[#818cf8]">
                          AK
                        </div>
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className="text-xs font-semibold text-white">AI Kosh (IndiaAI / Bhashini)</span>
                            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                          </div>
                          <span className="text-[10px] font-mono text-[#94a3b8]">38,400 Seed Docs · Synced</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-mono font-bold text-[#10b981]">100%</span>
                        <span className="block text-[9px] font-mono text-[#94a3b8]">GROUNDED</span>
                      </div>
                    </div>

                    {/* HuggingFace Card */}
                    <div className="p-2.5 rounded bg-[#0e0e13] border border-[#272738] hover:border-[#6366f1]/50 transition-colors flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-7 h-7 rounded bg-[#1a1a24] border border-[#272738] flex items-center justify-center font-mono font-bold text-xs text-[#6366f1]">
                          HF
                        </div>
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className="text-xs font-semibold text-white">HuggingFace Datasets</span>
                            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                          </div>
                          <span className="text-[10px] font-mono text-[#94a3b8]">45.2k Samples · Verified</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-mono font-bold text-white">45.2k</span>
                        <span className="block text-[9px] font-mono text-[#94a3b8]">RECORDS</span>
                      </div>
                    </div>

                    {/* OpenML Card */}
                    <div className="p-2.5 rounded bg-[#0e0e13] border border-[#272738] hover:border-[#6366f1]/50 transition-colors flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-7 h-7 rounded bg-[#1a1a24] border border-[#272738] flex items-center justify-center font-mono font-bold text-xs text-[#10b981]">
                          OM
                        </div>
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className="text-xs font-semibold text-white">OpenML Registry</span>
                            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                          </div>
                          <span className="text-[10px] font-mono text-[#94a3b8]">12.8k Tabular Schemas</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-mono font-bold text-white">12.8k</span>
                        <span className="block text-[9px] font-mono text-[#94a3b8]">SCHEMAS</span>
                      </div>
                    </div>

                    {/* ArXiv Preprints */}
                    <div className="p-2.5 rounded bg-[#0e0e13] border border-[#272738] hover:border-[#6366f1]/50 transition-colors flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-7 h-7 rounded bg-[#1a1a24] border border-[#272738] flex items-center justify-center font-mono font-bold text-xs text-[#f59e0b]">
                          AX
                        </div>
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className="text-xs font-semibold text-white">ArXiv Research Preprints</span>
                            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
                          </div>
                          <span className="text-[10px] font-mono text-[#94a3b8]">6,210 Preprints Indexed</span>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs font-mono font-bold text-white">6.2k</span>
                        <span className="block text-[9px] font-mono text-[#94a3b8]">PAPERS</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Ingestion Dials */}
                <div className="pt-2 border-t border-[#1c1c28] grid grid-cols-2 gap-2 text-[11px] font-mono">
                  <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
                    <span className="text-[#94a3b8] block mb-1">Dedup Ratio (MinHash)</span>
                    <span className="text-sm font-bold text-[#10b981]">94.2%</span>
                  </div>
                  <div className="p-2 rounded bg-[#0a0a0f] border border-[#272738]">
                    <span className="text-[#94a3b8] block mb-1">Cosine Sim Filter</span>
                    <span className="text-sm font-bold text-[#818cf8]">&gt; 0.82 BGE</span>
                  </div>
                </div>
              </div>

              {/* Right Column: Interactive Coverage Matrix & Curriculum Planner (7 cols) */}
              <div className="xl:col-span-7 p-4 rounded-lg bg-[#12121a] border border-[#272738] flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-center justify-between pb-2 mb-3 border-b border-[#1c1c28]">
                    <div className="flex items-center space-x-2">
                      <Layers className="w-4 h-4 text-[#818cf8]" />
                      <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                        Curriculum Coverage Matrix (5 Tiers)
                      </h3>
                    </div>
                    <span className="text-[11px] font-mono text-[#94a3b8]">
                      Total Target: <strong className="text-white">50,000 Samples</strong>
                    </span>
                  </div>

                  {/* 5 Difficulty Tiers Breakdown */}
                  <div className="space-y-2">
                    {[
                      { tier: 'Tier 1: Foundational QA', count: '12,400', pass: '98%', color: '#10b981', w: '98%' },
                      { tier: 'Tier 2: Multi-Step Logic', count: '18,920', pass: '92%', color: '#38bdf8', w: '92%' },
                      { tier: 'Tier 3: Corner Cases & Law', count: '9,450', pass: '86%', color: '#818cf8', w: '86%' },
                      { tier: 'Tier 4: Hallucination Traps', count: '6,100', pass: '74%', color: '#f59e0b', w: '74%' },
                      { tier: 'Tier 5: Novel Synthesis (OOD)', count: '3,130', pass: '69%', color: '#10b981', w: '69%' },
                    ].map((item, i) => (
                      <div key={i} className="p-2 rounded bg-[#0e0e13] border border-[#1c1c28] space-y-1">
                        <div className="flex justify-between items-center text-xs font-mono">
                          <span className="text-white">{item.tier}</span>
                          <span className="text-[#94a3b8]">
                            <strong className="text-white">{item.count}</strong> spls · pass: <strong style={{ color: item.color }}>{item.pass}</strong>
                          </span>
                        </div>
                        <div className="w-full bg-[#1a1a24] h-1.5 rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-500" style={{ width: item.w, backgroundColor: item.color }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Heatmap Visual Matrix Indicator */}
                <div className="pt-2 border-t border-[#1c1c28] flex items-center justify-between text-[11px] font-mono text-[#94a3b8]">
                  <div className="flex items-center space-x-1.5">
                    <span>Density:</span>
                    <div className="flex space-x-1">
                      <span className="w-3 h-3 rounded-xs bg-[#1a1a24]" />
                      <span className="w-3 h-3 rounded-xs bg-[#10b981]/30" />
                      <span className="w-3 h-3 rounded-xs bg-[#10b981]/60" />
                      <span className="w-3 h-3 rounded-xs bg-[#10b981]" />
                    </div>
                    <span className="text-white">Saturated</span>
                  </div>
                  <span>Stratified 10-Fold Distribution</span>
                </div>
              </div>
            </div>

            {/* Grid 2: Live LangGraph Orchestration DAG Horizontal Visualizer */}
            <div className="p-4 rounded-lg bg-[#12121a] border border-[#272738] space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#1c1c28]">
                <div className="flex items-center space-x-2">
                  <Workflow className="w-4 h-4 text-[#818cf8]" />
                  <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                    Live LangGraph Orchestration DAG Pipeline
                  </h3>
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#1a1a24] text-[#818cf8] border border-[#272738]">
                    SYNAPSE RUNNING
                  </span>
                </div>

                <div className="flex items-center space-x-4 text-[11px] font-mono">
                  <span className="text-[#94a3b8]">DAG LATENCY: <strong className="text-white">42ms</strong></span>
                  <span className="text-[#94a3b8]">ACTIVE CKPT: <strong className="text-[#10b981]">ckpt-04</strong></span>
                  <span className="text-[#10b981] flex items-center gap-1 font-semibold">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                    2,400 tok/s
                  </span>
                </div>
              </div>

              {/* Horizontal Nodes */}
              <div className="overflow-x-auto py-2">
                <div className="min-w-[840px] flex items-center justify-between relative px-2">
                  {[
                    { step: '01', title: '1. Discover', desc: 'AI Kosh & Web Crawl', count: '84,200', active: true },
                    { step: '02', title: '2. Extract', desc: 'De-dupe & AST Clean', count: '99.1%', active: true },
                    { step: '03', title: '3. Filter', desc: 'LLM-as-a-Judge', count: '0.942 Q', active: true },
                    { step: '04', title: '4. Construct', desc: 'Context Grounded', count: '5.8 turns', active: true },
                    { step: '05', title: '5. HITL Gate', desc: 'Stratified Sample', count: `${reviewCount || 218} pending`, active: true },
                    { step: '06', title: '6. Export', desc: 'JSONL / HF Hub', count: 'Unsloth/PEFT', active: false },
                  ].map((node, i, arr) => (
                    <div key={i} className="flex items-center">
                      <div className={clsx(
                        'w-36 p-2.5 rounded bg-[#0e0e13] border transition-all',
                        node.active
                          ? 'border-[#6366f1] shadow-sm glow-indigo'
                          : 'border-[#272738]'
                      )}>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] font-mono font-bold text-[#818cf8]">NODE {node.step}</span>
                          <span className={clsx('w-1.5 h-1.5 rounded-full', node.active ? 'bg-[#10b981] animate-pulse' : 'bg-[#94a3b8]')} />
                        </div>
                        <h4 className="text-xs font-semibold text-white truncate">{node.title}</h4>
                        <p className="text-[10px] font-mono text-[#94a3b8] truncate">{node.desc}</p>
                        <div className="mt-1 pt-1 border-t border-[#1c1c28] flex justify-between text-[10px] font-mono">
                          <span className="text-[#94a3b8]">Metric:</span>
                          <span className="text-[#10b981] font-medium">{node.count}</span>
                        </div>
                      </div>

                      {i < arr.length - 1 && (
                        <div className="mx-2 text-[#94a3b8]">
                          <ChevronRight className="w-4 h-4 text-[#272738]" />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Grid 3: HITL Review Queue & Quick LoRA Fine-Tuner */}
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
              
              {/* Left Column: HITL Review Queue Preview (7 cols) */}
              <div className="xl:col-span-7 p-4 rounded-lg bg-[#12121a] border border-[#272738] flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-center justify-between pb-2 mb-3 border-b border-[#1c1c28]">
                    <div className="flex items-center space-x-2">
                      <ClipboardCheck className="w-4 h-4 text-[#818cf8]" />
                      <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                        Human-in-the-Loop Review Queue
                      </h3>
                    </div>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40 font-semibold">
                      5.0% Stratified Sample (99.4% CI)
                    </span>
                  </div>

                  {/* Sample Card */}
                  <div className="p-3 rounded bg-[#0e0e13] border border-[#272738] space-y-2">
                    <div className="flex justify-between items-center text-[11px] font-mono">
                      <span className="text-[#818cf8]">Sample #84,291 · AI Kosh GST Statute</span>
                      <span className="text-[#10b981]">Fidelity: 0.988</span>
                    </div>

                    <div className="text-xs text-white bg-[#0a0a0f] p-2 rounded border border-[#1c1c28] font-mono">
                      <span className="text-[#94a3b8] block mb-1">Q: How does Section 16(4) of the CGST Act intersect with annual return filing reconciliation?</span>
                      <span className="text-[#10b981]">A: Under Section 16(4), registered persons cannot claim input tax credit after 30th November following the end of financial year...</span>
                    </div>

                    {/* Keyboard Shortcuts Linear Badges */}
                    <div className="flex flex-wrap gap-2 pt-1">
                      <button className="px-2.5 py-1 rounded bg-[#10b981]/15 hover:bg-[#10b981]/25 border border-[#10b981]/40 text-[#10b981] text-xs font-mono flex items-center gap-1.5 transition-colors">
                        <kbd className="px-1 py-0.2 rounded bg-[#0a0a0f] text-[10px]">A</kbd>
                        <span>Approve & Tag</span>
                      </button>
                      <button className="px-2.5 py-1 rounded bg-[#f43f5e]/15 hover:bg-[#f43f5e]/25 border border-[#f43f5e]/40 text-[#f43f5e] text-xs font-mono flex items-center gap-1.5 transition-colors">
                        <kbd className="px-1 py-0.2 rounded bg-[#0a0a0f] text-[10px]">R</kbd>
                        <span>Reject & Quarantine</span>
                      </button>
                      <button className="px-2.5 py-1 rounded bg-[#f59e0b]/15 hover:bg-[#f59e0b]/25 border border-[#f59e0b]/40 text-[#f59e0b] text-xs font-mono flex items-center gap-1.5 transition-colors">
                        <kbd className="px-1 py-0.2 rounded bg-[#0a0a0f] text-[10px]">E</kbd>
                        <span>Edit Branch</span>
                      </button>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-[#1c1c28] flex justify-between items-center text-[11px] font-mono text-[#94a3b8]">
                  <span>Pending in Queue: <strong className="text-white">{reviewCount || 218} items</strong></span>
                  <Link href="/review" className="text-[#818cf8] hover:underline flex items-center gap-1">
                    <span>Open Full Review Queue</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              </div>

              {/* Right Column: Quick LoRA Fine-Tuner Launcher (5 cols) */}
              <div className="xl:col-span-5 p-4 rounded-lg bg-[#12121a] border border-[#272738] flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-center justify-between pb-2 mb-3 border-b border-[#1c1c28]">
                    <div className="flex items-center space-x-2">
                      <Cpu className="w-4 h-4 text-[#10b981]" />
                      <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                        PEFT / LoRA Fine-Tune Launcher
                      </h3>
                    </div>
                    <span className="text-[10px] font-mono text-[#10b981] bg-[#10b981]/20 px-2 py-0.5 rounded border border-[#10b981]/40">
                      Unsloth GPU Ready
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    {/* Model Selector */}
                    <div>
                      <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1">Base Model</label>
                      <select className="w-full bg-[#0a0a0f] border border-[#272738] rounded p-1.5 text-xs font-mono text-white focus:outline-none">
                        <option>HuggingFaceTB/SmolLM2-1.7B-Instruct</option>
                        <option>meta-llama/Llama-3-8B-Instruct</option>
                        <option>mistralai/Mistral-7B-v0.3</option>
                      </select>
                    </div>

                    {/* Hyperparameters Grid */}
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div className="p-2 rounded bg-[#0e0e13] border border-[#1c1c28]">
                        <span className="text-[#94a3b8] text-[10px] block">LoRA Rank (r)</span>
                        <span className="text-white font-bold">16 (Alpha=32)</span>
                      </div>
                      <div className="p-2 rounded bg-[#0e0e13] border border-[#1c1c28]">
                        <span className="text-[#94a3b8] text-[10px] block">Epochs</span>
                        <span className="text-white font-bold">3 · lr=2e-4</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="pt-2 border-t border-[#1c1c28]">
                  <Link href="/finetune">
                    <Button className="w-full bg-[#10b981] hover:bg-[#34d399] text-black font-mono font-bold text-xs h-8 shadow-sm glow-emerald flex items-center justify-center gap-1.5">
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>Start LoRA Training Run</span>
                    </Button>
                  </Link>
                </div>
              </div>
            </div>

          </div>
        </main>
      </div>
    </div>
  )
}
