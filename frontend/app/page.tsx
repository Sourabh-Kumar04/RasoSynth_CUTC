'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { clsx } from 'clsx'
import {
  Database,
  Cpu,
  FlaskConical,
  Zap,
  ArrowRight,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Sparkles,
  Layers,
  BarChart2,
  Clock,
  Play,
  Scale,
  Plus,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api/client'
import { TopNav } from '@/components/layout/top-nav'
import { Sidebar } from '@/components/layout/sidebar'

export default function OverviewDashboardPage() {
  const router = useRouter()
  const [datasetJobs, setDatasetJobs] = useState<any[]>([])
  const [finetuneJobs, setFinetuneJobs] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [queryInput, setQueryInput] = useState<string>(
    'Synthesize 10,000 multi-turn instruction dialogues from AI Kosh tax rulings & GST statutes with self-correction'
  )
  const [selectedDomain, setSelectedDomain] = useState<string>('Finance & Taxation (AI Kosh)')
  const [evalTab, setEvalTab] = useState<'tuned' | 'base'>('tuned')

  useEffect(() => {
    async function loadDashboardData() {
      setIsLoading(true)
      try {
        const [datasetsRes, finetuneRes] = await Promise.allSettled([
          api.getJobs({ limit: 5 }),
          api.listFineTuneJobs(),
        ])

        if (datasetsRes.status === 'fulfilled') {
          const raw = datasetsRes.value?.data || (Array.isArray(datasetsRes.value) ? datasetsRes.value : [])
          if (Array.isArray(raw)) setDatasetJobs(raw.slice(0, 5))
        }
        if (finetuneRes.status === 'fulfilled') {
          const raw = finetuneRes.value?.jobs || (Array.isArray(finetuneRes.value) ? finetuneRes.value : [])
          if (Array.isArray(raw)) setFinetuneJobs(raw.slice(0, 5))
        }
      } catch (err: any) {
        console.error('Failed to load dashboard data:', err)
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboardData()
    const interval = setInterval(loadDashboardData, 12000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-[#09090b] text-[#f8fafc] flex flex-col font-sans antialiased">
      <TopNav />
      <div className="flex-1 flex w-full">
        <Sidebar />
        <main className="flex-1 min-w-0 p-6 sm:p-8 lg:p-10 space-y-10 max-w-7xl mx-auto">
          
          {/* Hero Section: Spacious, Bold, Minimal YC Aesthetic */}
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-[#22222e] pb-8">
            <div className="space-y-2 max-w-3xl">
              <div className="inline-flex items-center gap-2 px-2.5 py-0.5 rounded-sm bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] text-xs font-mono font-bold tracking-wide">
                <span className="w-1.5 h-1.5 rounded-full bg-[#f26625] animate-pulse" />
                SOVEREIGN FOUNDRY · PROOF-CARRIER SYSTEM
              </div>
              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white font-display">
                Autonomous AI Dataset Synthesis &amp; Fine-Tuning
              </h1>
              <p className="text-sm text-[#94a3b8] leading-relaxed">
                Transform domain knowledge and statutory corpora into audit-grade fine-tuning datasets with cryptographic Merkle proof provenance.
              </p>
            </div>

            <div className="flex items-center gap-3 shrink-0">
              <Link href="/studio">
                <Button className="bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white text-xs font-mono font-bold h-9 px-4 rounded-md shadow-sm glow-yc flex items-center gap-1.5">
                  <Plus className="w-4 h-4" />
                  <span>New Dataset</span>
                </Button>
              </Link>
              <Link href="/finetune">
                <Button variant="outline" className="border-[#272738] bg-[#12121a] hover:bg-[#161622] text-[#cbd5e1] text-xs font-mono h-9 px-4 rounded-md">
                  <Cpu className="w-4 h-4 mr-1.5 text-[#f26625]" />
                  Fine-Tune Studio
                </Button>
              </Link>
            </div>
          </div>

          {/* Quick Intent Launcher: High Signal, Clean Spacing */}
          <div className="p-6 rounded-lg bg-[#111118] border border-[#22222e] space-y-4">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#f26625]" />
                Dataset Specification
              </span>
              <span className="text-[#10b981] flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                Air-Gapped Sovereign Engine Active
              </span>
            </div>

            <textarea
              value={queryInput}
              onChange={(e) => setQueryInput(e.target.value)}
              rows={2}
              className="w-full bg-[#09090b] border border-[#272738] focus:border-[#f26625] rounded-md p-3.5 text-xs font-mono text-white placeholder:text-[#64748b] focus:outline-none transition-colors resize-none leading-relaxed"
              placeholder="Describe your dataset target domain, schema, and quality constraints..."
            />

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
              <div className="flex flex-wrap items-center gap-2 text-xs font-mono">
                <span className="text-[#94a3b8] text-[11px] uppercase tracking-wider">Presets:</span>
                {[
                  { name: 'Finance & GST', domain: 'Finance & Taxation (AI Kosh)', prompt: 'Synthesize 20,000 multi-turn legal and financial audit dialogues from Indian GST statutes and Section 16(4) input-tax-credit reconciliation case studies.' },
                  { name: 'Aerospace & FAR 25', domain: 'Aerospace Engineering & Aerodynamics', prompt: 'Synthesize 15,000 aeronautical engineering QA dialogues based on NASA supercritical airfoil data, transonic Navier-Stokes flow regimes, and FAR Part 25 airworthiness criteria.' },
                  { name: 'Clinical Reasoning', domain: 'Medical Reasoning', prompt: 'Extract step-by-step diagnostic reasoning trajectories from PubMed open clinical case studies with contraindication warnings.' },
                  { name: 'Python Code', domain: 'Python Math & Code', prompt: 'Generate 15,000 competitive programming solutions with test suites and asymptotic time-space analysis.' },
                ].map((preset) => (
                  <button
                    key={preset.name}
                    onClick={() => {
                      setSelectedDomain(preset.domain)
                      setQueryInput(preset.prompt)
                    }}
                    className={clsx(
                      'px-2.5 py-1 rounded-sm text-xs font-mono transition-all border',
                      selectedDomain === preset.domain
                        ? 'bg-[#f26625]/15 border-[#f26625] text-[#f26625] font-semibold'
                        : 'bg-[#09090b] border-[#272738] text-[#94a3b8] hover:text-white hover:border-[#3b3b52]'
                    )}
                  >
                    {preset.name}
                  </button>
                ))}
              </div>

              <Link href={`/studio?prompt=${encodeURIComponent(queryInput)}&domain=${encodeURIComponent(selectedDomain)}`}>
                <Button className="bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white text-xs font-mono font-bold h-8 px-4 rounded-md glow-yc flex items-center gap-1.5">
                  <span>Launch Pipeline</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Button>
              </Link>
            </div>
          </div>

          {/* Core Proof Telemetry: 4 Spacious High-Signal Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            <Card className="bg-[#111118] border-[#22222e] rounded-lg p-5">
              <div className="flex items-center justify-between text-xs font-mono uppercase text-[#94a3b8]">
                <span>Fine-Tuning Delta</span>
                <TrendingUp className="w-4 h-4 text-[#f26625]" />
              </div>
              <div className="mt-3">
                <span className="text-3xl font-extrabold font-mono text-white tnum tracking-tight">+537%</span>
                <span className="text-xs text-emerald-400 font-mono ml-2 font-semibold">chrF Score</span>
              </div>
              <p className="text-[11px] text-[#64748b] mt-1 font-mono">
                54.74 vs 8.59 base model
              </p>
            </Card>

            <Card className="bg-[#111118] border-[#22222e] rounded-lg p-5">
              <div className="flex items-center justify-between text-xs font-mono uppercase text-[#94a3b8]">
                <span>Unit Economics</span>
                <Zap className="w-4 h-4 text-[#10b981]" />
              </div>
              <div className="mt-3">
                <span className="text-3xl font-extrabold font-mono text-white tnum tracking-tight">99.95%</span>
                <span className="text-xs text-emerald-400 font-mono ml-2 font-semibold">Cheaper</span>
              </div>
              <p className="text-[11px] text-[#64748b] mt-1 font-mono">
                $52 vs $100k human labeling
              </p>
            </Card>

            <Card className="bg-[#111118] border-[#22222e] rounded-lg p-5">
              <div className="flex items-center justify-between text-xs font-mono uppercase text-[#94a3b8]">
                <span>Provenance Engine</span>
                <ShieldCheck className="w-4 h-4 text-[#10b981]" />
              </div>
              <div className="mt-3">
                <span className="text-3xl font-extrabold font-mono text-white tnum tracking-tight">302k /s</span>
              </div>
              <p className="text-[11px] text-[#64748b] mt-1 font-mono">
                DBOM SHA-256 Merkle root
              </p>
            </Card>

            <Card className="bg-[#111118] border-[#22222e] rounded-lg p-5">
              <div className="flex items-center justify-between text-xs font-mono uppercase text-[#94a3b8]">
                <span>Citation Adherence</span>
                <Scale className="w-4 h-4 text-cyan-400" />
              </div>
              <div className="mt-3">
                <span className="text-3xl font-extrabold font-mono text-white tnum tracking-tight">100%</span>
              </div>
              <p className="text-[11px] text-[#64748b] mt-1 font-mono">
                Zero hallucinated statutes
              </p>
            </Card>
          </div>

          {/* Empirical Comparison & Live Jobs Split View */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            
            {/* Left 6 Columns: Empirical Model Evaluation */}
            <div className="lg:col-span-6 p-6 rounded-lg bg-[#111118] border border-[#22222e] space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#1c1c24]">
                <div className="flex items-center gap-2">
                  <Scale className="w-4 h-4 text-[#f26625]" />
                  <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                    Empirical Evaluation: Sarvam-2B
                  </h3>
                </div>

                <div className="inline-flex p-0.5 rounded-sm bg-[#09090b] border border-[#272738]">
                  <button
                    onClick={() => setEvalTab('tuned')}
                    className={clsx(
                      'px-2.5 py-1 rounded-xs text-[11px] font-mono font-semibold transition-all',
                      evalTab === 'tuned'
                        ? 'bg-[#f26625] text-white shadow-sm'
                        : 'text-[#94a3b8] hover:text-white'
                    )}
                  >
                    RasoSynth SFT (54.74)
                  </button>
                  <button
                    onClick={() => setEvalTab('base')}
                    className={clsx(
                      'px-2.5 py-1 rounded-xs text-[11px] font-mono font-semibold transition-all',
                      evalTab === 'base'
                        ? 'bg-rose-950/60 text-rose-400 border border-rose-500/30'
                        : 'text-[#94a3b8] hover:text-white'
                    )}
                  >
                    Pretrained Base (8.59)
                  </button>
                </div>
              </div>

              <div className="p-4 rounded-md bg-[#09090b] border border-[#1c1c24] space-y-2 text-xs font-mono">
                <div className="flex justify-between text-[11px] text-[#94a3b8]">
                  <span>Query: GST Input Tax Credit Statutory Requirements</span>
                  <span className={evalTab === 'tuned' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                    {evalTab === 'tuned' ? '100% Grounded Citation' : '0% Statutory Citations'}
                  </span>
                </div>
                <p className="text-xs text-[#cbd5e1] leading-relaxed">
                  {evalTab === 'tuned' ? (
                    'Under Section 16(2) of the CGST Act 2017, a registered taxpayer can claim ITC only upon satisfying five statutory conditions: (1) Possession of tax invoice/debit note; (2) Receipt of goods or services; (3) Tax paid to Government via GSTR-2B; (4) Return filed under Section 39; (5) Supplier paid within 180 days.'
                  ) : (
                    'Under GST laws in India, input tax credit can be claimed by businesses for their taxes. You should check the GST portal or ask a chartered accountant for the exact filing forms and dates.'
                  )}
                </p>
              </div>

              <div className="flex items-center justify-between text-xs font-mono pt-1 text-[#94a3b8]">
                <span>chrF Match: <strong className="text-white">{evalTab === 'tuned' ? '54.74 (+537%)' : '8.59'}</strong></span>
                <span>Token F1: <strong className="text-white">{evalTab === 'tuned' ? '0.404 (+325%)' : '0.095'}</strong></span>
                <Link href="/research" className="text-[#f26625] hover:underline font-semibold flex items-center gap-1">
                  <span>Full Benchmark Audit</span>
                  <ArrowRight className="w-3 h-3" />
                </Link>
              </div>
            </div>

            {/* Right 6 Columns: Recent Workflows & Datasets */}
            <div className="lg:col-span-6 p-6 rounded-lg bg-[#111118] border border-[#22222e] space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#1c1c24]">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-[#f26625]" />
                  <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                    Recent Workflows
                  </h3>
                </div>
                <Link href="/datasets" className="text-xs font-mono text-[#f26625] hover:underline">
                  View All ({datasetJobs.length || 3})
                </Link>
              </div>

              <div className="space-y-2.5">
                {[
                  { name: 'Indic GST QA Benchmark', type: 'SFT · 20,000 rows', status: 'Completed', time: 'Flagship', link: '/datasets' },
                  { name: 'Clinical Medical Reasoning', type: 'Reasoning · 10,000 rows', status: 'Completed', time: 'Flagship', link: '/datasets' },
                  { name: 'Corporate Law Compliance', type: 'SFT · 15,000 rows', status: 'Completed', time: 'Flagship', link: '/datasets' },
                  ...datasetJobs.slice(0, 2).map(j => ({
                    name: j.target_domain || j.id.slice(0, 16),
                    type: `${j.dataset_type || 'sft'} · ${(j.samples_generated || 1000).toLocaleString()} rows`,
                    status: j.status,
                    time: 'Recent',
                    link: `/orchestration?job=${j.id}`
                  }))
                ].slice(0, 4).map((item, idx) => (
                  <Link key={idx} href={item.link}>
                    <div className="flex items-center justify-between p-3 rounded-md bg-[#09090b] border border-[#1c1c24] hover:border-[#f26625]/40 transition-colors cursor-pointer text-xs font-mono">
                      <div>
                        <div className="text-white font-semibold">{item.name}</div>
                        <div className="text-[11px] text-[#64748b]">{item.type}</div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-[10px] px-2 py-0.5 rounded-sm bg-emerald-950/40 text-emerald-400 border border-emerald-500/30 font-medium">
                          {item.status}
                        </span>
                        <ArrowRight className="w-3.5 h-3.5 text-[#64748b]" />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </div>

          </div>

        </main>
      </div>
    </div>
  )
}
