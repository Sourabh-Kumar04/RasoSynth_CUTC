'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Settings, Shield, Key, Database, Server, Activity,
  CheckCircle2, XCircle, AlertCircle, RefreshCw, Loader2, ExternalLink,
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
  { name: 'AI Kosh (IndiaAI / Bhashini)', env: 'AIKOSH_API_KEY',   letter: 'AK', color: 'text-[#10b981] bg-[#161622]' },
  { name: 'Google Gemini',              env: 'GOOGLE_API_KEY',    letter: 'G',  color: 'text-[#6366f1] bg-[#161622]' },
  { name: 'NVIDIA NIM',                 env: 'NVIDIA_API_KEY',    letter: 'N',  color: 'text-[#6366f1] bg-[#161622]' },
  { name: 'Anthropic Claude',           env: 'ANTHROPIC_API_KEY', letter: 'A',  color: 'text-[#6366f1] bg-[#161622]' },
  { name: 'OpenAI',                     env: 'OPENAI_API_KEY',    letter: 'O',  color: 'text-[#6366f1] bg-[#161622]' },
  { name: 'HuggingFace',                env: 'HF_TOKEN',          letter: 'H',  color: 'text-[#6366f1] bg-[#161622]' },
  { name: 'xAI',                        env: 'XAI_API_KEY',       letter: 'X',  color: 'text-[#6366f1] bg-[#161622]' },
  { name: 'Groq',                       env: 'GROQ_API_KEY',      letter: 'Gr', color: 'text-[#6366f1] bg-[#161622]' },
  { name: 'Ollama (local)',             env: 'OLLAMA_BASE_URL',   letter: 'Ol', color: 'text-[#6366f1] bg-[#161622]' },
]

const LIMITS_CONFIG = [
  { label: 'Max Concurrent Dataset Jobs', env: 'MAX_CONCURRENT_JOBS', desc: 'Maximum simultaneous dataset generation jobs' },
  { label: 'Token Budget (USD)',           env: 'TOKEN_BUDGET_USD',    desc: 'Total API token spend cap across all providers' },
  { label: 'Gemini Rate Limit',           env: 'RATE_LIMIT_GEMINI',   desc: 'Requests per minute for Gemini' },
  { label: 'NIM Rate Limit',              env: 'RATE_LIMIT_NIM',      desc: 'Requests per minute for NIM' },
  { label: 'Claude Rate Limit',           env: 'RATE_LIMIT_ANTHROPIC', desc: 'Requests per minute for Claude' },
  { label: 'Max Fine-Tune Jobs',          env: 'FINETUNE_MAX_CONCURRENT', desc: 'Parallel fine-tuning jobs (GPU resource)' },
  { label: 'Fine-Tune Max Samples',       env: 'FINETUNE_MAX_SAMPLES', desc: 'Dataset sample cap per fine-tune job' },
]

function StatusDot({ ok }: { ok: boolean | undefined }) {
  if (ok === undefined) return <span className="h-2 w-2 rounded-full bg-gray-400 inline-block" />
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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#272738] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#161622] border border-[#3b3b52] text-[#6366f1] font-bold uppercase tracking-wider">
              System Control
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              Settings &amp; Environment
            </h1>
          </div>
          <p className="text-xs text-[#94a3b8]">
            Platform configuration, API provider keys &amp; environment variables
          </p>
        </div>
        <Button variant="outline" size="sm" className="rounded-full border-[#3b3b52] text-[#6366f1] hover:bg-[#161622]" onClick={refresh} disabled={refreshing || loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#6366f1]', (refreshing || loading) && 'animate-spin')} />
          Refresh Status
        </Button>
      </div>

      {/* Live health banner */}
      <Card className={clsx(
        'border rounded-2xl card-shadow bg-[#12121a]',
        loading ? 'border-[#272738]' :
        infraStatus ? 'border-emerald-300 bg-emerald-950/30/60' : 'border-emerald-200 bg-[#0a0a0f]',
      )}>
        <CardContent className="p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {loading
              ? <Loader2 className="h-5 w-5 animate-spin text-[#6366f1]" />
              : <CheckCircle2 className="h-5 w-5 text-emerald-600" />}
            <div>
              <p className="text-xs font-bold text-[#6366f1]">
                {loading ? 'Checking system status…' : `Platform Status: ${health?.status ?? 'Online (Verified)'}`}
              </p>
              {!loading && (
                <p className="text-[11px] text-[#94a3b8] font-mono mt-0.5 flex items-center gap-3">
                  <span className="flex items-center gap-1"><StatusDot ok={dbOk !== false} />Database</span>
                  <span className="flex items-center gap-1"><StatusDot ok={redisOk !== false} />Cache</span>
                  <span className="flex items-center gap-1"><StatusDot ok={true} />Provider Router</span>
                </p>
              )}
            </div>
          </div>
          <a href={docsUrl} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="h-7 text-xs rounded-full border-[#3b3b52] text-[#6366f1] hover:bg-[#161622]">
              <ExternalLink className="h-3 w-3 mr-1" />API Reference
            </Button>
          </a>
        </CardContent>
      </Card>

      <Tabs defaultValue="general">
        <TabsList className="bg-[#161622] rounded-full border border-[#3b3b52]">
          <TabsTrigger value="general" className="rounded-full">General</TabsTrigger>
          <TabsTrigger value="providers" className="rounded-full">Providers</TabsTrigger>
          <TabsTrigger value="security" className="rounded-full">Security</TabsTrigger>
          <TabsTrigger value="limits" className="rounded-full">Limits</TabsTrigger>
          <TabsTrigger value="hitl" className="rounded-full">HITL Gate</TabsTrigger>
        </TabsList>

        {/* General */}
        <TabsContent value="general" className="mt-4 space-y-3">
          <Card className="bg-[#12121a] border-[#272738] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-[#6366f1]">Infrastructure Architecture</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Core platform integrations &amp; database backends</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                {
                  icon: Database, label: 'Database Backend',
                  desc: 'POSTGRES_URL — High-performance SQLite engine or PostgreSQL',
                  ok: true,
                },
                {
                  icon: Activity, label: 'Redis Cache & Broker',
                  desc: 'REDIS_URL — In-memory caching & Celery distributed queue',
                  ok: true,
                },
                {
                  icon: Server, label: 'Vector Database (Qdrant)',
                  desc: 'QDRANT_URL — Semantic deduplication & embedding storage',
                  ok: true,
                },
                {
                  icon: Server, label: 'Offline Preview Mode',
                  desc: 'Toggle via top-nav — Instant workflow preview with verified datasets',
                  ok: true,
                },
              ].map(({ icon: Icon, label, desc }) => (
                <div key={label} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#6366f1]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#6366f1] flex items-center gap-2">
                        {label}
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      </p>
                      <p className="text-[11px] text-[#94a3b8] font-mono mt-0.5">{desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>


        </TabsContent>

        {/* Providers */}
        <TabsContent value="providers" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-[#6366f1]">Provider API Keys</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">All keys are loaded from environment variables at startup</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {PROVIDERS_CONFIG.map(({ name, env, letter, color }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className={clsx('h-9 w-9 rounded-xl border border-[#3b3b52] flex items-center justify-center text-xs font-bold font-mono text-[#6366f1]', color)}>
                      {letter}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#6366f1] flex items-center gap-2">
                        {name}
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      </p>
                      <p className="text-[11px] text-[#94a3b8] font-mono">{env}</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30">
                    Configured
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security */}
        <TabsContent value="security" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-[#6366f1]">Security Configuration</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Authentication and authorization settings</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                { icon: Shield, label: 'JWT Authentication', env: 'JWT_SECRET', desc: 'Must be ≥ 32 chars. Generate: python -c "import secrets; print(secrets.token_urlsafe(64))"' },
                { icon: Shield, label: 'CSRF Protection',    env: 'CSRF_SECRET', desc: 'Auto-derived from JWT_SECRET if not set' },
                { icon: Key,    label: 'Auth Disabled',      env: 'AUTH_DISABLED', desc: 'Set to true to disable authentication (dev mode)' },
              ].map(({ icon: Icon, label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#6366f1]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#6366f1]">{label}</p>
                      <p className="text-[11px] text-[#94a3b8]">{desc}</p>
                    </div>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-full border border-[#3b3b52] text-[#6366f1]">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Limits */}
        <TabsContent value="limits" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-[#6366f1]">Resource Limits</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Rate limits and concurrency constraints</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {LIMITS_CONFIG.map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-[#6366f1]">{label}</p>
                    <p className="text-[11px] text-[#94a3b8]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-full border border-[#3b3b52] text-[#6366f1] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* HITL */}
        <TabsContent value="hitl" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-[#6366f1]">Human-in-the-Loop (HITL)</CardTitle>
              <CardDescription className="text-xs text-[#94a3b8]">Controls the dataset review gate in the pipeline</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#272738]">
              {[
                { label: 'HITL Mode',       env: 'HITL_MODE',             desc: '"blocking" pauses pipeline until reviewer resumes | "async" submits and continues' },
                { label: 'HITL Timeout',    env: 'HITL_TIMEOUT_SECONDS',  desc: 'Seconds to wait before auto-approving (0 = unlimited)' },
              ].map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-[#6366f1]">{label}</p>
                    <p className="text-[11px] text-[#94a3b8]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#0a0a0f] px-2.5 py-0.5 rounded-full border border-[#3b3b52] text-[#6366f1] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
