'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Settings, Shield, Key, Database, Server, Activity,
  CheckCircle2, XCircle, AlertCircle, RefreshCw, Loader2, ExternalLink,
  HardDrive, Radio, Cpu, FileText, Check, ArrowRight, Cloud, Zap
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api/client'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'

interface HealthStatus {
  status: string
  service?: string
  database?: boolean
  redis?: boolean
  providers?: Record<string, { status: string; latency_ms?: number }>
  circuit_breakers?: Record<string, string>
}

const PROVIDERS_CONFIG = [
  { name: 'AI Kosh (IndiaAI / Bhashini)', env: 'AIKOSH_API_KEY',   letter: 'AK', color: 'text-[#10b981] bg-[#10b981]/10 border-emerald-500/30' },
  { name: 'Google Gemini (1.5 / 2.0)',    env: 'GEMINI_API_KEY',    letter: 'G',  color: 'text-[#f26625] bg-[#f26625]/10 border-[#f26625]/30' },
  { name: 'Groq Cloud (Llama-3.3-70B)',   env: 'GROQ_API_KEY',      letter: 'Gr', color: 'text-[#f97316] bg-[#f97316]/10 border-orange-500/30' },
  { name: 'DeepSeek (R1 / V3)',           env: 'DEEPSEEK_API_KEY',  letter: 'DS', color: 'text-[#f26625] bg-[#f26625]/10 border-[#f26625]/30' },
  { name: 'OpenRouter Aggregator',        env: 'OPENROUTER_API_KEY',letter: 'OR', color: 'text-[#f26625] bg-[#f26625]/10 border-[#f26625]/30' },
  { name: 'Together AI (DeepSeek R1)',    env: 'TOGETHER_API_KEY',  letter: 'TG', color: 'text-[#f26625] bg-[#f26625]/10 border-[#f26625]/30' },
  { name: 'HuggingFace Hub Token',        env: 'HF_TOKEN',          letter: 'HF', color: 'text-[#f59e0b] bg-[#f59e0b]/10 border-amber-500/30' },
  { name: 'Ollama (Local Engine)',        env: 'OLLAMA_BASE_URL',   letter: 'Ol', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  { name: 'NVIDIA NIM Microservices',     env: 'NVIDIA_API_KEY',    letter: 'N',  color: 'text-[#a8a29e] bg-[#1b1b18] border-[#4a463f]' },
  { name: 'Anthropic Claude 3.5',         env: 'ANTHROPIC_API_KEY', letter: 'A',  color: 'text-[#a8a29e] bg-[#1b1b18] border-[#4a463f]' },
  { name: 'OpenAI (GPT-4o)',              env: 'OPENAI_API_KEY',    letter: 'O',  color: 'text-[#a8a29e] bg-[#1b1b18] border-[#4a463f]' },
]

// P0: provider "configured" status is verified against the backend
// GET /providers list — never hardcoded. Backend router names map to the
// UI rows below; a row with no backend counterpart is "not reported",
// not "configured". When the backend is unreachable every row is unknown.
const BACKEND_PROVIDER_TO_ENV: Record<string, string> = {
  google_gemini: 'GEMINI_API_KEY',
  groq: 'GROQ_API_KEY',
  deepseek: 'DEEPSEEK_API_KEY',
  openrouter: 'OPENROUTER_API_KEY',
  together: 'TOGETHER_API_KEY',
  nvidia_nim: 'NVIDIA_API_KEY',
  anthropic: 'ANTHROPIC_API_KEY',
  openai: 'OPENAI_API_KEY',
  huggingface: 'HF_TOKEN',
  ollama: 'OLLAMA_BASE_URL',
}

const LIMITS_CONFIG = [
  { label: 'Max Concurrent Dataset Jobs', env: 'MAX_CONCURRENT_JOBS', desc: 'Maximum simultaneous dataset generation pipelines' },
  { label: 'Max Job Queue Size',          env: 'MAX_JOB_QUEUE_SIZE',   desc: 'Queue buffer cap before backpressure rejects new pipeline jobs' },
  { label: 'Token Budget Cap (USD)',      env: 'TOKEN_BUDGET_USD',    desc: 'Total API token spend limit across all external providers' },
  { label: 'Gemini Rate Limit',           env: 'RATE_LIMIT_GEMINI',   desc: 'Requests per minute cap for Gemini 1.5/2.0' },
  { label: 'NVIDIA NIM Rate Limit',       env: 'RATE_LIMIT_NIM',      desc: 'Requests per minute for hosted NIM microservices' },
  { label: 'Claude Rate Limit',           env: 'RATE_LIMIT_ANTHROPIC', desc: 'Requests per minute for Claude 3.5 Sonnet' },
  { label: 'Fine-Tune Concurrency',       env: 'FINETUNE_MAX_CONCURRENT', desc: 'Parallel fine-tuning worker sessions (GPU resource bound)' },
  { label: 'Fine-Tune Max Samples',       env: 'FINETUNE_MAX_SAMPLES', desc: 'Dataset sample ceiling per single fine-tune run' },
]

function StatusDot({ ok }: { ok: boolean | undefined }) {
  if (ok === undefined) return <span className="h-2 w-2 rounded-full bg-gray-500 inline-block" />
  return <span className={clsx('h-2 w-2 rounded-full inline-block', ok ? 'bg-emerald-400' : 'bg-rose-500')} />
}

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const [computeConfig, setComputeConfig] = useState<{
    modal_configured: boolean
    runpod_configured: boolean
    hf_configured: boolean
    modal_token_id_masked: string | null
    runpod_key_masked: string | null
    hf_token_masked: string | null
    available_targets: string[]
  } | null>(null)
  // Backend-reported providers (null = backend unreachable / not loaded yet).
  const [backendProviders, setBackendProviders] = useState<{ name: string }[] | null>(null)
  const [modalTokenId, setModalTokenId] = useState('')
  const [modalTokenSecret, setModalTokenSecret] = useState('')
  const [runpodApiKey, setRunpodApiKey] = useState('')
  const [hfToken, setHfToken] = useState('')
  const [savingCompute, setSavingCompute] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.getHealthReady().catch(() => api.getHealth().catch(() => null))
      setHealth(data as HealthStatus | null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchComputeSettings = useCallback(async () => {
    try {
      const res = await api.getComputeSettings()
      setComputeConfig(res)
    } catch (e) {
      console.warn('Failed to fetch compute settings', e)
    }
  }, [])

  const fetchBackendProviders = useCallback(async () => {
    try {
      const res = await api.getProviders()
      setBackendProviders(Array.isArray(res) ? res : [])
    } catch (e) {
      console.warn('Failed to fetch backend providers', e)
      setBackendProviders(null)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    fetchComputeSettings()
    fetchBackendProviders()
  }, [fetchHealth, fetchComputeSettings, fetchBackendProviders])

  const refresh = () => {
    setRefreshing(true)
    fetchHealth()
    fetchComputeSettings()
  }

  const handleSaveCompute = async (e: React.FormEvent) => {
    e.preventDefault()
    playClickSound()
    setSavingCompute(true)
    setSaveSuccess(false)
    try {
      await api.updateComputeSettings({
        modal_token_id: modalTokenId || undefined,
        modal_token_secret: modalTokenSecret || undefined,
        runpod_api_key: runpodApiKey || undefined,
        hf_token: hfToken || undefined,
      })
      playSuccessChime()
      setSaveSuccess(true)
      fetchComputeSettings()
      setModalTokenId('')
      setModalTokenSecret('')
      setRunpodApiKey('')
      setHfToken('')
      setTimeout(() => setSaveSuccess(false), 3000)
    } catch (err) {
      console.error('Failed to update compute settings', err)
    } finally {
      setSavingCompute(false)
    }
  }

  const infraStatus = health?.status === 'healthy' || health?.status === 'ok'
  const dbOk = health?.database
  const redisOk = health?.redis

  const docsUrl = process.env.NEXT_PUBLIC_API_URL
    ? `${process.env.NEXT_PUBLIC_API_URL}/docs`
    : 'https://github.com/Sourabh-Kumar04/RasoSynth_CUTC#readme'

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#272738] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-xs font-mono px-2 py-0.5 rounded-sm bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] font-bold uppercase tracking-wider">
              System Control
            </span>
            <span className="text-xs font-mono px-2 py-0.5 rounded-sm bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 font-bold">
              Standalone Local Container Active
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              System Status &amp; Configuration
            </h1>
          </div>

        </div>
        <div className="flex items-center gap-2">
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#161622] border border-[#272738] text-xs font-mono text-[#a8a29e]">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            Supabase Cloud Pooler (AWS SG)
          </span>
          <Button variant="outline" size="sm" className="rounded-md border-[#272738] text-white hover:bg-[#161622] hover:border-[#3b3b52] font-mono text-xs" onClick={refresh} disabled={refreshing || loading}>
            <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#f26625]', (refreshing || loading) && 'animate-spin')} />
            Refresh Status
          </Button>
        </div>
      </div>

      {/* Live health banner */}
      <Card className={clsx(
        'border rounded-md card-shadow transition-colors',
        loading ? 'border-[#272738] bg-[#12121a]' :
        infraStatus ? 'border-emerald-500/30 bg-[#12121a]' : 'border-rose-500/30 bg-[#12121a]',
      )}>
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-[#f26625]" />
            ) : infraStatus ? (
              <CheckCircle2 className="h-5 w-5 text-[#10b981]" />
            ) : (
              <AlertCircle className="h-5 w-5 text-rose-500" />
            )}
            <div>
              <p className="text-xs font-bold text-white flex items-center gap-2">
                <span>Platform Status: {loading ? 'Checking runtime...' : health?.status?.toUpperCase() ?? 'UNKNOWN'}</span>
                {!loading && infraStatus && (
                  <span className="text-xs font-mono px-2 py-0.2 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Live Verified
                  </span>
                )}
              </p>
              {!loading && (
                <p className="text-xs text-[#a8a29e] font-mono mt-1 flex flex-wrap items-center gap-3">
                  <span className="flex items-center gap-1.5"><StatusDot ok={dbOk !== false} />Database Engine</span>
                  <span className="flex items-center gap-1.5"><StatusDot ok={redisOk !== false} />Distributed Broker &amp; Cache</span>
                  <span className="flex items-center gap-1.5"><StatusDot ok={true} />Provider Hot-Switcher (ADR-001)</span>
                  <span className="flex items-center gap-1.5"><StatusDot ok={true} />Multi-Agent Society</span>
                </p>
              )}
            </div>
          </div>
          <a href={docsUrl} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="h-7 text-xs rounded-md border-[#272738] text-[#a8a29e] hover:text-white hover:bg-[#161622] hover:border-[#3b3b52]">
              <ExternalLink className="h-3 w-3 mr-1 text-[#f26625]" />API Reference
            </Button>
          </a>
        </CardContent>
      </Card>

      <Tabs defaultValue="general">
        <TabsList className="bg-[#161622] rounded-md border border-[#272738] p-1 flex flex-wrap gap-1 h-auto">
          <TabsTrigger value="general" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">General &amp; Engine</TabsTrigger>
          <TabsTrigger value="compute" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active] flex items-center gap-1.5">
            <Cloud className="w-3.5 h-3.5" />
            Cloud Compute &amp; GPUs
          </TabsTrigger>
          <TabsTrigger value="providers" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Providers</TabsTrigger>
          <TabsTrigger value="delivery" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Delivery (ADR-002)</TabsTrigger>
          <TabsTrigger value="observability" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Observability</TabsTrigger>
          <TabsTrigger value="security" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Security</TabsTrigger>
          <TabsTrigger value="limits" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Limits &amp; Caps</TabsTrigger>
          <TabsTrigger value="hitl" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">HITL Gate</TabsTrigger>
        </TabsList>

        {/* General & Engine */}
        <TabsContent value="general" className="mt-4 space-y-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">Infrastructure Architecture</CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">Core platform storage engines, distributed queue brokers &amp; caching backends</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                {
                  icon: Database, label: 'Database Engine',
                  desc: 'POSTGRES_URL — Database engine connection',
                  status: loading ? 'Checking…' : health?.database === true ? 'Connected' : health?.database === false ? 'Disconnected' : 'Unknown',
                  isOk: health?.database === true,
                },
                {
                  icon: Activity, label: 'Redis Cache & Distributed Broker',
                  desc: 'REDIS_URL — L1 memory + L2 Redis cache',
                  status: loading ? 'Checking…' : health?.redis === true ? 'Active' : health?.redis === false ? 'Standalone' : 'Unknown',
                  isOk: health?.redis === true,
                },
                {
                  icon: Server, label: 'Vector Database & Semantic Index',
                  desc: 'QDRANT_URL / SQLite-VSS — Vector storage status',
                  status: 'Configured Reference',
                  isOk: true,
                },
                {
                  icon: Cpu, label: 'Standalone Local Container Execution Mode',
                  desc: 'Multiprocess worker pool execution target',
                  status: 'Configured',
                  isOk: true,
                },
              ].map(({ icon: Icon, label, desc, status, isOk }) => (
                <div key={label} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#f26625]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white flex items-center gap-2">
                        {label}
                        {isOk && status !== 'Unknown' && <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />}
                      </p>
                      <p className="text-xs text-[#a8a29e] font-mono mt-0.5">{desc}</p>
                    </div>
                  </div>
                  <span className={clsx(
                    "text-xs font-mono font-bold px-2.5 py-0.5 rounded-md border",
                    status === 'Connected' || status === 'Active' ? "bg-emerald-950/40 text-[#10b981] border-emerald-500/30" :
                    status === 'Disconnected' ? "bg-rose-950/40 text-rose-400 border-rose-500/30" :
                    status === 'Standalone' || status === 'Configured' || status === 'Configured Reference' ? "bg-zinc-900 text-[#d8d2c4] border-[#272738]" :
                    "bg-zinc-900 text-[#a8a29e] border-[#272738]"
                  )}>
                    {status}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">Source-Grounded Engine Standards</CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">Enforcing authentic retrieval-grounded generation over hallucinated pure synthetic data</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                {
                  label: 'Default Generation Mode',
                  desc: 'GENERATION_MODE=strict_source — Pure synthetic generation is strictly disabled unless explicitly opted in',
                  val: 'strict_source',
                },
                {
                  label: 'Seedless Generation Guard',
                  desc: 'ALLOW_SEEDLESS_GENERATION=false — Generation without grounded domain reference seeds is rejected',
                  val: 'Disabled (Protected)',
                },
                {
                  label: 'Topological Coverage Planner',
                  desc: 'COVERAGE_PLANNER_ENABLED=true — Plans domain taxonomy distribution prior to LLM extraction calls',
                  val: 'Enabled',
                },
                {
                  label: 'Validation Strictness',
                  desc: 'VALIDATION_STRICTNESS=standard — Syntactic, schema, and semantic sanity checks enforced on all batches',
                  val: 'standard',
                },
              ].map(({ label, desc, val }) => (
                <div key={label} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-white">{label}</p>
                    <p className="text-xs text-[#a8a29e] font-mono mt-0.5">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-md border border-[#272738] text-[#f26625] shrink-0 ml-4">
                    {val}
                  </code>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Seedless Generation Guard Plain Language Explainer */}
          <Card className="bg-[#12121a] border border-[#f26625]/30 rounded-md card-shadow overflow-hidden">
            <div className="bg-[#f26625]/10 border-b border-[#f26625]/20 px-5 py-2.5 flex items-center justify-between">
              <span className="text-xs font-mono font-bold text-[#f26625] uppercase tracking-wider flex items-center gap-2">
                <Shield className="h-4 w-4 text-[#f26625]" />
                Seedless Generation Guard Explainer
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-500/40 text-emerald-400 font-bold">
                ENFORCED (RFC-GROUNDING-01)
              </span>
            </div>
            <CardContent className="p-5 text-xs font-mono space-y-2.5">
              <p className="text-white font-medium leading-relaxed font-sans text-xs">
                <strong>Why does this guard exist?</strong> Pure synthetic text generated without reference seed documents frequently invents fictitious legal sections, fabricated statutory penalties, and hallucinated medical dosages.
              </p>
              <p className="text-[#a8a29e] text-xs leading-relaxed">
                When enabled (<code>ALLOW_SEEDLESS_GENERATION=false</code>), the pipeline strictly requires an authoritative reference corpus (e.g., CGST Act PDFs, medical case studies, or validated codebases) before initiating LLM teacher-forcing. If seed retrieval fails or yields zero matches, generation is automatically halted rather than allowing the model to hallucinate unverified statutory claims from vacuum.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cloud Compute & GPUs */}
        <TabsContent value="compute" className="mt-4 space-y-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Cloud className="w-4 h-4 text-[#f26625]" />
                Cloud GPU Compute Fabric &amp; Serverless Endpoints
              </CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">
                Configure external cloud GPU credentials for offloading QLoRA and SFT fine-tuning jobs (Modal Labs, RunPod Cloud, HuggingFace Hub)
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              <div className="flex items-center justify-between px-5 py-3.5">
                <div className="flex items-center gap-3.5">
                  <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center font-mono font-bold text-xs text-[#f26625]">
                    M
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white flex items-center gap-2">
                      Modal Serverless GPU Fabric (NVIDIA A10G / H100)
                      {computeConfig?.modal_configured && <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />}
                    </p>
                    <p className="text-xs text-[#a8a29e] font-mono mt-0.5">
                      MODAL_TOKEN_ID &amp; MODAL_TOKEN_SECRET — Serverless containerized training
                    </p>
                  </div>
                </div>
                <span className={clsx(
                  'text-xs font-mono font-bold px-2.5 py-0.5 rounded-md border',
                  computeConfig?.modal_configured
                    ? 'bg-emerald-950/40 text-[#10b981] border-emerald-500/30'
                    : 'bg-zinc-900 text-zinc-400 border-zinc-800'
                )}>
                  {computeConfig?.modal_configured ? `Active (${computeConfig.modal_token_id_masked || 'Configured'})` : 'Not Configured'}
                </span>
              </div>

              <div className="flex items-center justify-between px-5 py-3.5">
                <div className="flex items-center gap-3.5">
                  <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center font-mono font-bold text-xs text-[#f26625]">
                    RP
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white flex items-center gap-2">
                      RunPod Cloud GPU Endpoints
                      {computeConfig?.runpod_configured && <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />}
                    </p>
                    <p className="text-xs text-[#a8a29e] font-mono mt-0.5">
                      RUNPOD_API_KEY — On-demand remote worker pods for high-throughput fine-tuning
                    </p>
                  </div>
                </div>
                <span className={clsx(
                  'text-xs font-mono font-bold px-2.5 py-0.5 rounded-md border',
                  computeConfig?.runpod_configured
                    ? 'bg-emerald-950/40 text-[#10b981] border-emerald-500/30'
                    : 'bg-zinc-900 text-zinc-400 border-zinc-800'
                )}>
                  {computeConfig?.runpod_configured ? `Active (${computeConfig.runpod_key_masked || 'Configured'})` : 'Not Configured'}
                </span>
              </div>

              <div className="flex items-center justify-between px-5 py-3.5">
                <div className="flex items-center gap-3.5">
                  <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center font-mono font-bold text-xs text-amber-400">
                    HF
                  </div>
                  <div>
                    <p className="text-xs font-bold text-white flex items-center gap-2">
                      Hugging Face Hub Token (Write / Model Upload)
                      {computeConfig?.hf_configured && <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />}
                    </p>
                    <p className="text-xs text-[#a8a29e] font-mono mt-0.5">
                      HF_TOKEN — Required for pushing trained LoRA weights &amp; dataset cards
                    </p>
                  </div>
                </div>
                <span className={clsx(
                  'text-xs font-mono font-bold px-2.5 py-0.5 rounded-md border',
                  computeConfig?.hf_configured
                    ? 'bg-emerald-950/40 text-[#10b981] border-emerald-500/30'
                    : 'bg-zinc-900 text-zinc-400 border-zinc-800'
                )}>
                  {computeConfig?.hf_configured ? `Active (${computeConfig.hf_token_masked || 'Configured'})` : 'Not Configured'}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Form to update credentials */}
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Key className="w-4 h-4 text-[#f26625]" />
                Update Cloud Compute Credentials
              </CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">
                Credentials are saved to the active runtime environment and persisted for all subsequent cloud fine-tuning jobs.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5">
              <form onSubmit={handleSaveCompute} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-white block">
                      Modal Token ID
                    </label>
                    <input
                      type="text"
                      value={modalTokenId}
                      onChange={(e) => setModalTokenId(e.target.value)}
                      placeholder={computeConfig?.modal_token_id_masked || 'ak-xxxx'}
                      className="w-full px-3 py-2 text-xs font-mono bg-[#0a0a0f] border border-[#272738] rounded-md text-white placeholder-zinc-600 focus:outline-none focus:border-[#f26625]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-white block">
                      Modal Token Secret
                    </label>
                    <input
                      type="password"
                      value={modalTokenSecret}
                      onChange={(e) => setModalTokenSecret(e.target.value)}
                      placeholder="as-xxxx"
                      className="w-full px-3 py-2 text-xs font-mono bg-[#0a0a0f] border border-[#272738] rounded-md text-white placeholder-zinc-600 focus:outline-none focus:border-[#f26625]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-white block">
                      RunPod API Key
                    </label>
                    <input
                      type="password"
                      value={runpodApiKey}
                      onChange={(e) => setRunpodApiKey(e.target.value)}
                      placeholder={computeConfig?.runpod_key_masked || 'rpa_xxxx'}
                      className="w-full px-3 py-2 text-xs font-mono bg-[#0a0a0f] border border-[#272738] rounded-md text-white placeholder-zinc-600 focus:outline-none focus:border-[#f26625]"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-white block">
                      Hugging Face Token
                    </label>
                    <input
                      type="password"
                      value={hfToken}
                      onChange={(e) => setHfToken(e.target.value)}
                      placeholder={computeConfig?.hf_token_masked || 'hf_xxxx'}
                      className="w-full px-3 py-2 text-xs font-mono bg-[#0a0a0f] border border-[#272738] rounded-md text-white placeholder-zinc-600 focus:outline-none focus:border-[#f26625]"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-3 border-t border-[#272738]">
                  <div>
                    {saveSuccess && (
                      <span className="text-xs text-emerald-400 font-mono flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Credentials saved and applied to runtime!
                      </span>
                    )}
                  </div>
                  <Button
                    type="submit"
                    disabled={savingCompute || (!modalTokenId && !modalTokenSecret && !runpodApiKey && !hfToken)}
                    className="bg-[#f26625] hover:bg-[#d9551c] text-white text-xs font-mono px-4 h-8"
                  >
                    {savingCompute ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Zap className="w-3.5 h-3.5 mr-1.5" />
                        Apply &amp; Save Credentials
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Providers */}
        <TabsContent value="providers" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-white">Provider API Keys &amp; Gateway Integrations</CardTitle>
                  <CardDescription className="text-xs text-[#a8a29e]">Environment key detection and failover routing readiness</CardDescription>
                </div>
                <Badge variant="outline" className="text-xs font-mono border-emerald-500/40 text-emerald-400 bg-emerald-950/20">
                  {backendProviders === null
                    ? 'Backend provider status unavailable'
                    : `${PROVIDERS_CONFIG.filter(p => backendProviders.some(b => BACKEND_PROVIDER_TO_ENV[b.name] === p.env)).length} / ${PROVIDERS_CONFIG.length} reported by backend`}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {PROVIDERS_CONFIG.map(({ name, env, letter, color }) => {
                const reported = backendProviders === null
                  ? null
                  : backendProviders.some(b => BACKEND_PROVIDER_TO_ENV[b.name] === env)
                return (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className={clsx('h-9 w-9 rounded-xl border flex items-center justify-center text-xs font-bold font-mono', color)}>
                      {letter}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white flex items-center gap-2">
                        {name}
                        {reported ? (
                          <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />
                        ) : (
                          <span className="w-1.5 h-1.5 rounded-full bg-[#4a463f] inline-block" />
                        )}
                      </p>
                      <p className="text-xs text-[#a8a29e] font-mono">{env}</p>
                    </div>
                  </div>
                  <span className={clsx(
                    'text-xs font-mono font-bold px-2.5 py-0.5 rounded-md border',
                    reported
                      ? 'bg-emerald-950/40 text-[#10b981] border-emerald-500/30'
                      : 'bg-zinc-900 text-zinc-500 border-zinc-800'
                  )}>
                    {reported === null ? 'Unknown (backend unreachable)' : reported ? 'Reported by backend' : 'Not reported by backend'}
                  </span>
                </div>
                )
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Delivery (ADR-002) */}
        <TabsContent value="delivery" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">Multi-Destination Delivery &amp; Storage (ADR-002)</CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">Centralized delivery adapters registered in ServiceContainer for S3, HuggingFace Hub, and Kaggle</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                { icon: HardDrive, label: 'Local Artifact Output Directory', env: 'OUTPUT_DIR', desc: 'Default target for JSONL, Parquet, and CSV exports (./outputs)' },
                { icon: Server,    label: 'Amazon S3 / S3-Compatible Store',   env: 'S3_BUCKET',  desc: 'Bucket name and credentials for cloud blob storage delivery' },
                { icon: FileText,  label: 'Hugging Face Hub Organization',     env: 'HF_DATASET_ORG', desc: 'Target org/namespace for 1-click dataset push with card generation' },
                { icon: Cpu,       label: 'Kaggle Datasets Hub',               env: 'KAGGLE_USERNAME', desc: 'Kaggle credentials for automated dataset metadata release' },
              ].map(({ icon: Icon, label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#f26625]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white">{label}</p>
                      <p className="text-xs text-[#a8a29e]">{desc}</p>
                    </div>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-md border border-[#272738] text-[#f26625]">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Observability */}
        <TabsContent value="observability" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">Observability &amp; Distributed Tracing</CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">LangSmith tracing v2, OpenTelemetry metrics, and correlation IDs</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                { label: 'LangSmith Tracing v2', env: 'LANGCHAIN_TRACING_V2=true', desc: 'Full lifecycle execution tracing for LLM and agent invocations' },
                { label: 'LangSmith Project Namespace', env: 'LANGCHAIN_PROJECT=RasoSynthTune', desc: 'Default tenant project namespace for trace categorization' },
                { label: 'LangSmith API Key', env: 'LANGCHAIN_API_KEY', desc: 'Personal or team access token for LangSmith trace ingestion' },
                { label: 'Distributed Correlation IDs', env: 'X-Correlation-ID', desc: 'Injected into every HTTP request and Celery worker payload' },
              ].map(({ label, env, desc }) => (
                <div key={label} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-white">{label}</p>
                    <p className="text-xs text-[#a8a29e] font-mono mt-0.5">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-md border border-[#272738] text-[#f26625] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security */}
        <TabsContent value="security" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">Security &amp; Cryptography Configuration</CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">Cryptographic signatures, CSRF protection, and identity tokens</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                { icon: Shield, label: 'JWT Authentication Secret', env: 'JWT_SECRET', desc: 'HMAC-SHA256 signature key (≥ 32 characters required)' },
                { icon: Shield, label: 'CSRF Token Protection',     env: 'CSRF_SECRET', desc: 'Cross-Site Request Forgery validation key (auto-derived if omitted)' },
                { icon: Key,    label: 'Auth Disabled Flag',         env: 'AUTH_DISABLED', desc: 'Set to true in local development or isolated preview testing' },
              ].map(({ icon: Icon, label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#f26625]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white">{label}</p>
                      <p className="text-xs text-[#a8a29e]">{desc}</p>
                    </div>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-md border border-[#272738] text-[#f26625]">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Limits */}
        <TabsContent value="limits" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">System Resource Limits &amp; Rate Caps</CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">Concurrency bounds, token quotas, and provider throttle limits</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {LIMITS_CONFIG.map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-white">{label}</p>
                    <p className="text-xs text-[#a8a29e]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-md border border-[#272738] text-[#f26625] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* HITL */}
        <TabsContent value="hitl" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">Human-in-the-Loop (HITL) Quality Gate</CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">Review gate policies, stratified sampling, and auto-resume timeouts</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                { label: 'HITL Review Mode',       env: 'HITL_MODE',             desc: '"blocking" halts pipeline until approved | "async" persists job to awaiting_review state' },
                { label: 'Auto-Approval Timeout',   env: 'HITL_TIMEOUT_SECONDS',  desc: 'Max seconds before auto-accepting pending review batches (0 = unlimited wait)' },
                { label: 'Stratified Sample Ratio', env: 'HITL_SAMPLE_RATIO',     desc: 'Percentage of generated dataset items sampled for human quality validation' },
                { label: 'Quality Pass Floor',      env: 'QUALITY_THRESHOLD',     desc: 'Minimum composite quality score (0.0 - 1.0) required to bypass manual inspection' },
              ].map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-white">{label}</p>
                    <p className="text-xs text-[#a8a29e]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-md border border-[#272738] text-[#f26625] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
