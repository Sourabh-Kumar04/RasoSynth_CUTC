'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
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
  Play
} from 'lucide-react'
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
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadDashboardData() {
      setIsLoading(true)
      setError(null)
      try {
        const [healthRes, datasetsRes, finetuneRes, reviewRes] = await Promise.allSettled([
          api.getHealth(),
          api.getJobs({ limit: 5 }),
          api.listFineTuneJobs(),
          api.getReviewQueue()
        ])

        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (datasetsRes.status === 'fulfilled' && datasetsRes.value?.data) {
          setDatasetJobs(datasetsRes.value.data.slice(0, 5))
        }
        if (finetuneRes.status === 'fulfilled' && finetuneRes.value?.jobs) {
          setFinetuneJobs(finetuneRes.value.jobs.slice(0, 5))
        }
        if (reviewRes.status === 'fulfilled' && Array.isArray(reviewRes.value)) {
          setReviewCount(reviewRes.value.length)
        }
      } catch (err: any) {
        console.error('Failed to load dashboard data:', err)
        setError('Failed to refresh live telemetry')
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboardData()
    const interval = setInterval(loadDashboardData, 12000)
    return () => clearInterval(interval)
  }, [])

  const activeFTJobs = finetuneJobs.filter((j) => j.status === 'running' || j.status === 'pending')
  const completedFTJobs = finetuneJobs.filter((j) => j.status === 'completed')

  return (
    <div className="min-h-screen bg-[#F6F7F4] text-[#1B3B2B] flex flex-col">
      <TopNav />
      <div className="flex-1 flex w-full">
        <Sidebar />
        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8">
          <div className="w-full max-w-7xl mx-auto space-y-6">
          {/* Top Banner Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#E2E6E0] pb-5">
            <div>
              <div className="flex items-center gap-2.5 mb-1.5">
                <span className="px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-mono text-[10px] font-bold uppercase tracking-wider">
                  AI Synthesis Engine
                </span>
                <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">
                  Engineering Command Center
                </h1>
              </div>
              <p className="text-xs text-[#55635B]">
                Synthetic dataset orchestration, fine-tuning adapter lifecycle & HITL review pipeline
              </p>
            </div>

            <div className="flex items-center gap-2.5">
              <Button
                data-tour="launch-studio-btn"
                size="sm"
                className="bg-[#1B3B2B] hover:bg-[#142D21] text-white font-medium gap-2 shadow-xs rounded-full text-xs"
                onClick={() => router.push('/studio')}
              >
                <Zap className="h-4 w-4 text-emerald-400 fill-current" />
                Launch Preset Workflow
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-[#D1D8CE] bg-white text-[#1B3B2B] hover:bg-[#F0F3EE] rounded-full text-xs"
                onClick={() => router.push('/finetune')}
              >
                <Cpu className="h-4 w-4 mr-1.5 text-[#1B3B2B]" />
                Fine-Tune Studio
              </Button>
            </div>
          </div>

          {/* HITL Review Alert Banner */}
          {reviewCount > 0 && (
            <Card className="border-amber-300 bg-amber-50/80 rounded-2xl">
              <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-xl bg-[#1B3B2B] flex items-center justify-center font-bold text-white shadow-xs font-mono text-xs">
                    {reviewCount}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-[#1B3B2B]">
                      Human-In-The-Loop (HITL) Inspection Required
                    </p>
                    <p className="text-xs text-[#55635B]">
                      {reviewCount} dataset sample{reviewCount > 1 ? 's are' : ' is'} awaiting quality inspection before training export.
                    </p>
                  </div>
                </div>
                <Button
                  size="sm"
                  className="bg-[#1B3B2B] hover:bg-[#142D21] text-white font-medium text-xs gap-1.5 shrink-0 rounded-full"
                  onClick={() => router.push('/review')}
                >
                  <ClipboardCheck className="h-3.5 w-3.5 text-emerald-400" />
                  Review Pending Items
                </Button>
              </CardContent>
            </Card>
          )}



          {/* Telemetry Stat Overview Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="border-[#E2E6E0] bg-white hover:border-[#D1D8CE] transition-all rounded-2xl card-shadow">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <Database className="h-5 w-5 text-[#1B3B2B]" />
                </div>
                <div>
                  <p className="text-[11px] text-[#55635B] font-mono uppercase tracking-wider">
                    Total Datasets
                  </p>
                  <p className="text-2xl font-bold font-mono text-[#1B3B2B]">{datasetJobs.length}</p>
                </div>
              </CardContent>
            </Card>

            <Card className="border-[#E2E6E0] bg-white hover:border-[#D1D8CE] transition-all rounded-2xl card-shadow">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <Cpu className="h-5 w-5 text-[#1B3B2B]" />
                </div>
                <div>
                  <p className="text-[11px] text-[#55635B] font-mono uppercase tracking-wider">
                    Active Training Runs
                  </p>
                  <p className="text-2xl font-bold font-mono text-[#1B3B2B]">{activeFTJobs.length}</p>
                </div>
              </CardContent>
            </Card>

            <Card className="border-[#E2E6E0] bg-white hover:border-[#D1D8CE] transition-all rounded-2xl card-shadow">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <ShieldCheck className="h-5 w-5 text-[#1B3B2B]" />
                </div>
                <div>
                  <p className="text-[11px] text-[#55635B] font-mono uppercase tracking-wider">
                    Completed Adapters
                  </p>
                  <p className="text-2xl font-bold font-mono text-[#1B3B2B]">{completedFTJobs.length}</p>
                </div>
              </CardContent>
            </Card>

            <Card className="border-[#E2E6E0] bg-white hover:border-[#D1D8CE] transition-all rounded-2xl card-shadow">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="h-10 w-10 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                  <Server className="h-5 w-5 text-[#1B3B2B]" />
                </div>
                <div>
                  <p className="text-[11px] text-[#55635B] font-mono uppercase tracking-wider">
                    Backend Status
                  </p>
                  <p className="text-sm font-bold font-mono text-emerald-700 flex items-center gap-1.5 mt-1">
                    <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                    {health?.status === 'healthy' ? 'ONLINE (100%)' : 'ONLINE (DEMO)'}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Main Grid Section */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Active Model Fine-Tuning Runs */}
            <Card className="lg:col-span-2 border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader className="pb-3 border-b border-[#E2E6E0]">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold flex items-center gap-2 text-[#1B3B2B]">
                    <Cpu className="h-4 w-4 text-[#1B3B2B]" />
                    Fine-Tuning Experiments & Adapter Training
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full gap-1"
                    onClick={() => router.push('/finetune')}
                  >
                    <span>View All Jobs</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-4 space-y-3">
                {finetuneJobs.length === 0 ? (
                  <div className="p-8 text-center border border-dashed border-[#D1D8CE] rounded-xl">
                    <Cpu className="h-8 w-8 mx-auto text-[#809085] mb-2" />
                    <p className="text-xs text-[#55635B] font-mono">No active fine-tuning jobs.</p>
                    <Button
                      size="sm"
                      className="mt-3 bg-[#1B3B2B] hover:bg-[#142D21] text-white font-medium text-xs rounded-full"
                      onClick={() => router.push('/finetune')}
                    >
                      Start Model Fine-Tuning
                    </Button>
                  </div>
                ) : (
                  finetuneJobs.slice(0, 4).map((job) => (
                    <div
                      key={job.id}
                      className="p-3.5 rounded-xl border border-[#E2E6E0] bg-[#F6F7F4] hover:bg-white hover:border-[#D1D8CE] transition-all flex flex-col md:flex-row md:items-center justify-between gap-3"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-[#1B3B2B]">
                            {job.output_model_name || job.id}
                          </span>
                          <Badge variant="outline" className="text-[10px] font-mono border-[#D1D8CE] text-[#1B3B2B] bg-white rounded-full">
                            {job.base_model}
                          </Badge>
                        </div>
                        <p className="text-[11px] text-[#55635B] font-mono">
                          Epoch {job.current_epoch} / {job.total_epochs} • Loss: {job.train_loss !== null ? job.train_loss.toFixed(4) : 'N/A'}
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="w-32 space-y-1">
                          <div className="flex justify-between text-[10px] font-mono">
                            <span className="text-[#55635B]">Progress</span>
                            <span className="text-[#1B3B2B] font-bold">{(job.progress ?? 0).toFixed(0)}%</span>
                          </div>
                          <Progress value={job.progress ?? 0} className="h-1.5 bg-[#E8ECE6]" />
                        </div>
                        <Badge
                          className={`text-[10px] font-mono capitalize rounded-full ${
                            job.status === 'completed'
                              ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                              : job.status === 'running'
                              ? 'bg-amber-100 text-amber-800 border-amber-300 animate-pulse'
                              : 'bg-[#E8ECE6] text-[#55635B]'
                          }`}
                        >
                          {job.status}
                        </Badge>
                      </div>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Preset Workflow Quick Launcher */}
            <Card className="col-span-1 border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader className="pb-3 border-b border-[#E2E6E0]">
                <CardTitle className="text-base font-semibold flex items-center gap-2 text-[#1B3B2B]">
                  <Zap className="h-4 w-4 text-[#1B3B2B]" />
                  Preset Workflow Launcher
                </CardTitle>
                <CardDescription className="text-xs text-[#55635B]">
                  Instant 1-click dataset generation templates
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4 space-y-2.5">
                {[
                  { title: '🩺 Medical Diagnostics SFT', type: 'Clinical SFT', size: 500 },
                  { title: '🐍 Python Concurrency Bench', type: 'Code Synthetics', size: 1000 },
                  { title: '⚖️ Legal Compliance Reasoning', type: 'Legal SFT', size: 750 },
                  { title: '📊 Financial Market Sentiment', type: 'Finance SFT', size: 1000 }
                ].map((preset) => (
                  <div
                    key={preset.title}
                    className="p-2.5 rounded-xl border border-[#E2E6E0] bg-[#F6F7F4] hover:bg-white hover:border-[#D1D8CE] transition-all flex items-center justify-between cursor-pointer"
                    onClick={() => router.push('/studio')}
                  >
                    <div>
                      <p className="text-xs font-semibold text-[#1B3B2B]">{preset.title}</p>
                      <p className="text-[10px] font-mono text-[#55635B]">
                        {preset.size} records • {preset.type}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-6 px-2.5 text-[10px] bg-[#E8ECE6] text-[#1B3B2B] hover:bg-[#1B3B2B] hover:text-white font-bold rounded-full transition-colors"
                    >
                      Launch ⚡
                    </Button>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          {/* Recent Datasets Table Overview */}
          <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow overflow-hidden">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold flex items-center gap-2 text-[#1B3B2B]">
                  <Database className="h-4 w-4 text-[#1B3B2B]" />
                  Recent Synthetic Dataset Runs
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full gap-1"
                  onClick={() => router.push('/datasets')}
                >
                  <span>Explore All Datasets</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="p-0 overflow-x-auto">
              <div className="divide-y divide-[#E2E6E0] min-w-[500px]">
                {datasetJobs.length === 0 ? (
                  <div className="p-8 text-center">
                    <Database className="h-8 w-8 mx-auto text-[#809085] mb-2" />
                    <p className="text-xs text-[#55635B] font-mono">No datasets available.</p>
                  </div>
                ) : (
                  datasetJobs.map((ds) => (
                    <div key={ds.id} className="p-4 flex items-center justify-between hover:bg-[#F6F7F4] transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                          <Database className="h-4 w-4 text-[#1B3B2B]" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-[#1B3B2B] font-mono">{ds.target_domain || ds.id}</p>
                          <p className="text-[11px] text-[#55635B] font-mono">
                            {ds.samples_generated || 0} samples • Format: {ds.output_format || 'jsonl'}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <div className="w-28 hidden sm:block">
                          <Progress value={ds.progress || 100} className="h-1.5 bg-[#E8ECE6]" />
                        </div>
                        <Badge className="text-[10px] font-mono uppercase bg-emerald-100 text-emerald-800 border-emerald-300 rounded-full">
                          {ds.status || 'completed'}
                        </Badge>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
          </div>
        </main>
      </div>
    </div>
  )
}
