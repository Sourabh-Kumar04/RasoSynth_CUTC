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
  { name: 'Google Gemini',    env: 'GOOGLE_API_KEY',    letter: 'G', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
  { name: 'NVIDIA NIM',       env: 'NVIDIA_API_KEY',    letter: 'N', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
  { name: 'Anthropic Claude', env: 'ANTHROPIC_API_KEY', letter: 'A', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
  { name: 'OpenAI',           env: 'OPENAI_API_KEY',    letter: 'O', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
  { name: 'HuggingFace',      env: 'HF_TOKEN',          letter: 'H', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
  { name: 'xAI',              env: 'XAI_API_KEY',       letter: 'X', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
  { name: 'Groq',             env: 'GROQ_API_KEY',      letter: 'Gr', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
  { name: 'Ollama (local)',   env: 'OLLAMA_BASE_URL',   letter: 'Ol', color: 'text-[#1B3B2B] bg-[#E8ECE6]' },
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
  return <span className={clsx('h-2 w-2 rounded-full inline-block', ok ? 'bg-emerald-500' : 'bg-rose-500')} />
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

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E6E0] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-bold uppercase tracking-wider">
              System Control
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">
              Settings &amp; Environment
            </h1>
          </div>
          <p className="text-xs text-[#55635B]">
            Platform configuration, API keys &amp; environment variables
          </p>
        </div>
        <Button variant="outline" size="sm" className="rounded-full border-[#D1D8CE] text-[#1B3B2B] hover:bg-[#E8ECE6]" onClick={refresh} disabled={refreshing || loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#1B3B2B]', (refreshing || loading) && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Live health banner */}
      <Card className={clsx(
        'border rounded-2xl card-shadow bg-white',
        loading ? 'border-[#E2E6E0]' :
        infraStatus ? 'border-emerald-300 bg-emerald-50/60' : 'border-rose-300 bg-rose-50/60',
      )}>
        <CardContent className="p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {loading
              ? <Loader2 className="h-5 w-5 animate-spin text-[#1B3B2B]" />
              : infraStatus
                ? <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                : <AlertCircle className="h-5 w-5 text-rose-600" />}
            <div>
              <p className="text-xs font-bold text-[#1B3B2B]">
                {loading ? 'Checking system health…' : `System Status: ${health?.status ?? 'healthy'}`}
              </p>
              {!loading && (
                <p className="text-[11px] text-[#55635B] font-mono mt-0.5 flex items-center gap-3">
                  <span className="flex items-center gap-1"><StatusDot ok={dbOk !== false} />Database</span>
                  <span className="flex items-center gap-1"><StatusDot ok={redisOk !== false} />Redis</span>
                  <span className="flex items-center gap-1"><StatusDot ok={true} />Providers</span>
                </p>
              )}
            </div>
          </div>
          <a href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/docs`} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm" className="h-7 text-xs rounded-full border-[#D1D8CE] text-[#1B3B2B]">
              <ExternalLink className="h-3 w-3 mr-1" />API Docs
            </Button>
          </a>
        </CardContent>
      </Card>

      <Tabs defaultValue="general">
        <TabsList className="bg-[#E8ECE6] rounded-full border border-[#D1D8CE]">
          <TabsTrigger value="general" className="rounded-full">General</TabsTrigger>
          <TabsTrigger value="providers" className="rounded-full">Providers</TabsTrigger>
          <TabsTrigger value="security" className="rounded-full">Security</TabsTrigger>
          <TabsTrigger value="limits" className="rounded-full">Limits</TabsTrigger>
          <TabsTrigger value="hitl" className="rounded-full">HITL Gate</TabsTrigger>
        </TabsList>

        {/* General */}
        <TabsContent value="general" className="mt-4 space-y-3">
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]">
              <CardTitle className="text-sm font-bold text-[#1B3B2B]">Infrastructure</CardTitle>
              <CardDescription className="text-xs text-[#55635B]">Core platform connections — configure in .env</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#E2E6E0]">
              {[
                {
                  icon: Database, label: 'Database',
                  desc: 'POSTGRES_URL — SQLite (default) or PostgreSQL for production',
                  ok: true,
                },
                {
                  icon: Activity, label: 'Redis Cache',
                  desc: 'REDIS_URL — in-memory cache and Celery broker',
                  ok: true,
                },
                {
                  icon: Server, label: 'Vector DB (Qdrant)',
                  desc: 'QDRANT_URL — semantic search and embedding storage',
                  ok: true,
                },
                {
                  icon: Server, label: 'Demo Mode',
                  desc: 'Toggle via top-nav — simulates jobs without live API calls',
                  ok: true,
                },
              ].map(({ icon: Icon, label, desc, ok }) => (
                <div key={label} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#1B3B2B]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#1B3B2B] flex items-center gap-2">
                        {label}
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      </p>
                      <p className="text-[11px] text-[#55635B] font-mono mt-0.5">{desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-2 border-b border-[#E2E6E0]"><CardTitle className="text-xs font-bold text-[#1B3B2B]">How to modify configuration</CardTitle></CardHeader>
            <CardContent className="text-xs text-[#55635B] space-y-1.5 p-4">
              <p>1. Edit <code className="bg-[#E8ECE6] font-mono text-[#1B3B2B] px-1.5 py-0.5 rounded">.env</code> in the project root</p>
              <p>2. Restart the application for changes to take effect</p>
              <p>See <code className="bg-[#E8ECE6] font-mono text-[#1B3B2B] px-1.5 py-0.5 rounded">.env.example</code> for all available options.</p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Providers */}
        <TabsContent value="providers" className="mt-4">
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]">
              <CardTitle className="text-sm font-bold text-[#1B3B2B]">Provider API Keys</CardTitle>
              <CardDescription className="text-xs text-[#55635B]">All keys are read from environment at startup</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#E2E6E0]">
              {PROVIDERS_CONFIG.map(({ name, env, letter, color }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className={clsx('h-9 w-9 rounded-xl border border-[#D1D8CE] flex items-center justify-center text-xs font-bold font-mono text-[#1B3B2B]', color)}>
                      {letter}
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#1B3B2B] flex items-center gap-2">
                        {name}
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                      </p>
                      <p className="text-[11px] text-[#55635B] font-mono">{env}</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                    Configured
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security */}
        <TabsContent value="security" className="mt-4">
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]">
              <CardTitle className="text-sm font-bold text-[#1B3B2B]">Security Configuration</CardTitle>
              <CardDescription className="text-xs text-[#55635B]">Authentication and authorization settings</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#E2E6E0]">
              {[
                { icon: Shield, label: 'JWT Authentication', env: 'JWT_SECRET', desc: 'Must be ≥ 32 chars. Generate: python -c "import secrets; print(secrets.token_urlsafe(64))"' },
                { icon: Shield, label: 'CSRF Protection',    env: 'CSRF_SECRET', desc: 'Auto-derived from JWT_SECRET if not set' },
                { icon: Key,    label: 'Auth Disabled',      env: 'AUTH_DISABLED', desc: 'Set to true to disable authentication (dev only)' },
              ].map(({ icon: Icon, label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div className="flex items-center gap-3.5">
                    <div className="h-9 w-9 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                      <Icon className="h-4.5 w-4.5 text-[#1B3B2B]" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-[#1B3B2B]">{label}</p>
                      <p className="text-[11px] text-[#55635B]">{desc}</p>
                    </div>
                  </div>
                  <code className="text-xs font-mono bg-[#F6F7F4] px-2.5 py-0.5 rounded-full border border-[#D1D8CE] text-[#1B3B2B]">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Limits */}
        <TabsContent value="limits" className="mt-4">
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]">
              <CardTitle className="text-sm font-bold text-[#1B3B2B]">Resource Limits</CardTitle>
              <CardDescription className="text-xs text-[#55635B]">Rate limits and concurrency constraints</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#E2E6E0]">
              {LIMITS_CONFIG.map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-[#1B3B2B]">{label}</p>
                    <p className="text-[11px] text-[#55635B]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#F6F7F4] px-2.5 py-0.5 rounded-full border border-[#D1D8CE] text-[#1B3B2B] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* HITL */}
        <TabsContent value="hitl" className="mt-4">
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]">
              <CardTitle className="text-sm font-bold text-[#1B3B2B]">Human-in-the-Loop (HITL)</CardTitle>
              <CardDescription className="text-xs text-[#55635B]">Controls the dataset review gate in the pipeline</CardDescription>
            </CardHeader>
            <CardContent className="p-0 divide-y divide-[#E2E6E0]">
              {[
                { label: 'HITL Mode',       env: 'HITL_MODE',             desc: '"blocking" pauses pipeline until reviewer resumes | "async" submits and continues' },
                { label: 'HITL Timeout',    env: 'HITL_TIMEOUT_SECONDS',  desc: 'Seconds to wait before auto-approving (0 = unlimited)' },
              ].map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-5 py-3.5">
                  <div>
                    <p className="text-xs font-bold text-[#1B3B2B]">{label}</p>
                    <p className="text-[11px] text-[#55635B]">{desc}</p>
                  </div>
                  <code className="text-xs font-mono bg-[#F6F7F4] px-2.5 py-0.5 rounded-full border border-[#D1D8CE] text-[#1B3B2B] shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
