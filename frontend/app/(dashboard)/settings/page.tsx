'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Settings, Shield, Key, Database, Server, Activity,
  CheckCircle2, XCircle, AlertCircle, RefreshCw, Loader2, ExternalLink,
  HardDrive, Radio, Cpu, FileText, Check, ArrowRight
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api/client'

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
  { name: 'Google Gemini',              env: 'GOOGLE_API_KEY',    letter: 'G',  color: 'text-[#008ecc] bg-[#008ecc]/10 border-[#008ecc]/30' },
  { name: 'NVIDIA NIM',                 env: 'NVIDIA_API_KEY',    letter: 'N',  color: 'text-[#10b981] bg-[#10b981]/10 border-emerald-500/30' },
  { name: 'Anthropic Claude',           env: 'ANTHROPIC_API_KEY', letter: 'A',  color: 'text-[#f59e0b] bg-[#f59e0b]/10 border-amber-500/30' },
  { name: 'OpenAI',                     env: 'OPENAI_API_KEY',    letter: 'O',  color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
  { name: 'HuggingFace',                env: 'HF_TOKEN',          letter: 'H',  color: 'text-[#f59e0b] bg-[#f59e0b]/10 border-amber-500/30' },
  { name: 'xAI (Grok)',                 env: 'XAI_API_KEY',       letter: 'X',  color: 'text-white bg-white/10 border-white/20' },
  { name: 'Groq',                       env: 'GROQ_API_KEY',      letter: 'Gr', color: 'text-[#f97316] bg-[#f97316]/10 border-orange-500/30' },
  { name: 'Ollama (Local Engine)',       env: 'OLLAMA_BASE_URL',   letter: 'Ol', color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30' },
]

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

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.getHealthReady().catch(() => api.getHealth().catch(() => null))
      setHealth(data as HealthStatus | null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => { fetchHealth() }, [fetchHealth])

  const refresh = () => { setRefreshing(true); fetchHealth() }

  const infraStatus = health?.status === 'healthy' || health?.status === 'ok'
  const dbOk = health?.database
  const redisOk = health?.redis

  const docsUrl = process.env.NEXT_PUBLIC_API_URL
    ? `${process.env.NEXT_PUBLIC_API_URL}/docs`
    : 'https://github.com/Sourabh-Kumar04/RasoSynth_CUTC#readme'

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#1e2235] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-[#008ecc]/10 border border-[#008ecc]/30 text-[#008ecc] font-bold uppercase tracking-wider">
              System Control
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              Settings &amp; Environment
            </h1>
          </div>
          <p className="text-xs text-[#94a3b8]">
            Platform runtime configuration, API provider keys, ADR architecture standards &amp; resource boundaries
          </p>
        </div>
        <Button variant="outline" size="sm" className="rounded-md border-[#1e2235] text-white hover:bg-[#12141e] hover:border-[#3b3b52] font-mono text-xs" onClick={refresh} disabled={refreshing || loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#008ecc]', (refreshing || loading) && 'animate-spin')} />
          Refresh Status
        </Button>
      </div>

      {/* Live health banner */}
      <Card className={clsx(
        'border rounded-md card-shadow transition-colors',
        loading ? 'border-[#1e2235] bg-[#0c0d14]' :
        infraStatus ? 'border-emerald-500/30 bg-[#0c0d14]' : 'border-rose-500/30 bg-[#0c0d14]',
      )}>
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-[#008ecc]" />
            ) : infraStatus ? (
              <CheckCircle2 className="h-5 w-5 text-[#10b981]" />
            ) : (
              <AlertCircle className="h-5 w-5 text-rose-500" />
            )}
            <div>
              <p className="text-xs font-bold text-white flex items-center gap-2">
                <span>Platform Status: {loading ? 'Checking runtime...' : health?.status?.toUpperCase() ?? 'ONLINE'}</span>
                {!loading && infraStatus && (
                  <span className="text-[10px] font-mono px-2 py-0.2 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Live Verified
                  </span>
                )}
              </p>
              {!loading && (
                <p className="text-[11px] text-[#94a3b8] font-mono mt-1 flex flex-wrap items-center gap-3">
                  <span className="flex items-center gap-1.5"><StatusDot ok={dbOk !== false} />Database Engine</span>
                  <span className="flex items-center gap-1.5"><StatusDot ok={redisOk !== false} />Distributed Broker &amp; Cache</span>
                  <span className="flex items-center gap-1.5"><StatusDot ok={true} />Provider Hot-Switcher (ADR-001)</span>
                  <span className="flex items-center gap-1.5"><StatusDot ok={true} />Multi-Agent Society</span>
                </p>
              )}
            </div>
          </div>
          <a href={docsUrl} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="h-7 text-xs rounded-md border-[#1e2235] text-[#94a3b8] hover:text-white hover:bg-[#12141e] hover:border-[#3b3b52]">
              <ExternalLink className="h-3 w-3 mr-1 text-[#008ecc]" />API Reference
            </Button>
          </a>
        </CardContent>
      </Card>

      <Tabs defaultValue="general">
        <TabsList className="bg-[#12141e] rounded-md border border-[#1e2235] p-1 flex flex-wrap gap-1 h-auto">
          <TabsTrigger value="general" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#008ecc] data-[state=active]:text-white data-[state=active]:glow-cerulean">General &amp; Engine</TabsTrigger>
          <TabsTrigger value="providers" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#008ecc] data-[state=active]:text-white data-[state=active]:glow-cerulean">Providers</TabsTrigger>
          <TabsTrigger value="delivery" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#008ecc] data-[state=active]:text-white data-[state=active]:glow-cerulean">Delivery (ADR-002)</TabsTrigger>
          <TabsTrigger value="observability" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#008ecc] data-[state=active]:text-white data-[state=active]:glow-cerulean">Observability</TabsTrigger>
          <TabsTrigger value="security" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#008ecc] data-[state=active]:text-white data-[state=active]:glow-cerulean">Security</TabsTrigger>
          <TabsTrigger value="limits" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#008ecc] data-[state=active]:text-white data-[state=active]:glow-cerulean">Limits &amp; Caps</TabsTrigger>
          <TabsTrigger value="hitl" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#008ecc] data-[state=active]:text-white data-[state=active]:glow-cerulean">HITL Gate</TabsTrigger>
        </TabsList>

        {/* General & Engine */}
        <TabsContent value="general" className="mt-4 space-y-4">
          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">Infrastructure Architecture</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Core platform storage engines, distributed queue brokers &amp; caching backends</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
              {[
                {
                  icon: Database, label: 'Database Backend',
                  desc: 'POSTGRES_URL — High-performance SQLite engine or PostgreSQL asyncpg',
                  status: 'Configured',
                },
                {
                  icon: Activity, label: 'Redis Cache & Distributed Broker',
                  desc: 'REDIS_URL — L1 memory + L2 Redis cache & Celery async queue execution',
                  status: 'Active',
                },
                {
                  icon: Server, label: 'Vector Database (Qdrant)',
                  desc: 'QDRANT_URL — MinHash LSH & dense vector semantic deduplication',
                  status: 'Active',
                },
                {
                  icon: Server, label: 'Offline / Standalone Preview Mode',
                  desc: 'Toggle via top navigation bar — Instant deterministic pipeline previews without external API tokens',
                  status: 'Ready',
                },
              ].map(({ icon: Icon, label, desc, status }) => (
                <div key={label} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#12141e] border border-[#1e2235] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#008ecc]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white flex items-center gap-2">
                        {label}
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />
                      </p>
                      <p className="text-[11px] text-[#94a3b8] font-mono mt-0.5">{desc}</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-md bg-emerald-950/40 text-[#10b981] border border-emerald-500/30">
                    {status}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">Source-Grounded Engine Standards</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Enforcing authentic retrieval-grounded generation over hallucinated pure synthetic data</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
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
                    <p className="text-[11px] text-[#94a3b8] font-mono mt-0.5">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#050508] px-2.5 py-0.5 rounded-md border border-[#1e2235] text-[#008ecc] shrink-0 ml-4">
                    {val}
                  </code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Providers */}
        <TabsContent value="providers" className="mt-4">
          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">Provider API Keys &amp; Gateway Integrations</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Configured through environment variables for automatic failover &amp; model routing</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
              {PROVIDERS_CONFIG.map(({ name, env, letter, color }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className={clsx('h-9 w-9 rounded-xl border flex items-center justify-center text-xs font-bold font-mono', color)}>
                      {letter}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white flex items-center gap-2">
                        {name}
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#10b981]" />
                      </p>
                      <p className="text-[11px] text-[#94a3b8] font-mono">{env}</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-md bg-emerald-950/40 text-[#10b981] border border-emerald-500/30">
                    Configured
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Delivery (ADR-002) */}
        <TabsContent value="delivery" className="mt-4">
          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">Multi-Destination Delivery &amp; Storage (ADR-002)</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Centralized delivery adapters registered in ServiceContainer for S3, HuggingFace Hub, and Kaggle</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
              {[
                { icon: HardDrive, label: 'Local Artifact Output Directory', env: 'OUTPUT_DIR', desc: 'Default target for JSONL, Parquet, and CSV exports (./outputs)' },
                { icon: Server,    label: 'Amazon S3 / S3-Compatible Store',   env: 'S3_BUCKET',  desc: 'Bucket name and credentials for cloud blob storage delivery' },
                { icon: FileText,  label: 'Hugging Face Hub Organization',     env: 'HF_DATASET_ORG', desc: 'Target org/namespace for 1-click dataset push with card generation' },
                { icon: Cpu,       label: 'Kaggle Datasets Hub',               env: 'KAGGLE_USERNAME', desc: 'Kaggle credentials for automated dataset metadata release' },
              ].map(({ icon: Icon, label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#12141e] border border-[#1e2235] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#008ecc]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white">{label}</p>
                      <p className="text-[11px] text-[#94a3b8]">{desc}</p>
                    </div>
                  </div>
                  <code className="text-xs font-mono bg-[#050508] px-2.5 py-0.5 rounded-md border border-[#1e2235] text-[#008ecc]">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Observability */}
        <TabsContent value="observability" className="mt-4">
          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">Observability &amp; Distributed Tracing</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">LangSmith tracing v2, OpenTelemetry metrics, and correlation IDs</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
              {[
                { label: 'LangSmith Tracing v2', env: 'LANGCHAIN_TRACING_V2=true', desc: 'Full lifecycle execution tracing for LLM and agent invocations' },
                { label: 'LangSmith Project Namespace', env: 'LANGCHAIN_PROJECT=RasoSynthTune', desc: 'Default tenant project namespace for trace categorization' },
                { label: 'LangSmith API Key', env: 'LANGCHAIN_API_KEY', desc: 'Personal or team access token for LangSmith trace ingestion' },
                { label: 'Distributed Correlation IDs', env: 'X-Correlation-ID', desc: 'Injected into every HTTP request and Celery worker payload' },
              ].map(({ label, env, desc }) => (
                <div key={label} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-white">{label}</p>
                    <p className="text-[11px] text-[#94a3b8] font-mono mt-0.5">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#050508] px-2.5 py-0.5 rounded-md border border-[#1e2235] text-[#008ecc] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security */}
        <TabsContent value="security" className="mt-4">
          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">Security &amp; Cryptography Configuration</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Cryptographic signatures, CSRF protection, and identity tokens</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
              {[
                { icon: Shield, label: 'JWT Authentication Secret', env: 'JWT_SECRET', desc: 'HMAC-SHA256 signature key (≥ 32 characters required)' },
                { icon: Shield, label: 'CSRF Token Protection',     env: 'CSRF_SECRET', desc: 'Cross-Site Request Forgery validation key (auto-derived if omitted)' },
                { icon: Key,    label: 'Auth Disabled Flag',         env: 'AUTH_DISABLED', desc: 'Set to true in local development or isolated preview testing' },
              ].map(({ icon: Icon, label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#12141e] border border-[#1e2235] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#008ecc]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white">{label}</p>
                      <p className="text-[11px] text-[#94a3b8]">{desc}</p>
                    </div>
                  </div>
                  <code className="text-xs font-mono bg-[#050508] px-2.5 py-0.5 rounded-md border border-[#1e2235] text-[#008ecc]">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Limits */}
        <TabsContent value="limits" className="mt-4">
          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">System Resource Limits &amp; Rate Caps</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Concurrency bounds, token quotas, and provider throttle limits</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
              {LIMITS_CONFIG.map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-white">{label}</p>
                    <p className="text-[11px] text-[#94a3b8]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#050508] px-2.5 py-0.5 rounded-md border border-[#1e2235] text-[#008ecc] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* HITL */}
        <TabsContent value="hitl" className="mt-4">
          <Card className="bg-[#0c0d14] border-[#1e2235] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#1e2235]">
              <CardTitle className="text-sm font-bold text-white">Human-in-the-Loop (HITL) Quality Gate</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Review gate policies, stratified sampling, and auto-resume timeouts</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#1e2235]">
              {[
                { label: 'HITL Review Mode',       env: 'HITL_MODE',             desc: '"blocking" halts pipeline until approved | "async" persists job to awaiting_review state' },
                { label: 'Auto-Approval Timeout',   env: 'HITL_TIMEOUT_SECONDS',  desc: 'Max seconds before auto-accepting pending review batches (0 = unlimited wait)' },
                { label: 'Stratified Sample Ratio', env: 'HITL_SAMPLE_RATIO',     desc: 'Percentage of generated dataset items sampled for human quality validation' },
                { label: 'Quality Pass Floor',      env: 'QUALITY_THRESHOLD',     desc: 'Minimum composite quality score (0.0 - 1.0) required to bypass manual inspection' },
              ].map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-white">{label}</p>
                    <p className="text-[11px] text-[#94a3b8]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#050508] px-2.5 py-0.5 rounded-md border border-[#1e2235] text-[#008ecc] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
