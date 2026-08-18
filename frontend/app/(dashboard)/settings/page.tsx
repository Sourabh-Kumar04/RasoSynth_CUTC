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
  { name: 'Google Gemini',    env: 'GOOGLE_API_KEY',    letter: 'G', color: 'text-blue-400 bg-blue-500/10' },
  { name: 'NVIDIA NIM',       env: 'NVIDIA_API_KEY',    letter: 'N', color: 'text-green-400 bg-green-500/10' },
  { name: 'Anthropic Claude', env: 'ANTHROPIC_API_KEY', letter: 'A', color: 'text-orange-400 bg-orange-500/10' },
  { name: 'OpenAI',           env: 'OPENAI_API_KEY',    letter: 'O', color: 'text-gray-400 bg-gray-500/10' },
  { name: 'HuggingFace',      env: 'HF_TOKEN',          letter: 'H', color: 'text-purple-400 bg-purple-500/10' },
  { name: 'xAI',              env: 'XAI_API_KEY',       letter: 'X', color: 'text-yellow-400 bg-yellow-500/10' },
  { name: 'Groq',             env: 'GROQ_API_KEY',      letter: 'Gr', color: 'text-teal-400 bg-teal-500/10' },
  { name: 'Ollama (local)',   env: 'OLLAMA_BASE_URL',   letter: 'Ol', color: 'text-indigo-400 bg-indigo-500/10' },
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
  if (ok === undefined) return <span className="h-2 w-2 rounded-full bg-gray-500 inline-block" />
  return <span className={clsx('h-2 w-2 rounded-full inline-block', ok ? 'bg-green-500' : 'bg-red-500')} />
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
    <div className="space-y-5 animate-fade-in max-w-4xl">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Settings className="h-5 w-5 text-orange-400" />Settings
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Platform configuration — managed via environment variables
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing || loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1', (refreshing || loading) && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Live health banner */}
      <Card className={clsx(
        'border',
        loading ? 'border-border' :
        infraStatus ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5',
      )}>
        <CardContent className="p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {loading
              ? <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              : infraStatus
                ? <CheckCircle2 className="h-5 w-5 text-green-400" />
                : <AlertCircle className="h-5 w-5 text-red-400" />}
            <div>
              <p className="text-sm font-medium">
                {loading ? 'Checking system health…' : `System ${health?.status ?? 'unknown'}`}
              </p>
              {!loading && (
                <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-3">
                  <span className="flex items-center gap-1"><StatusDot ok={dbOk} />Database</span>
                  <span className="flex items-center gap-1"><StatusDot ok={redisOk} />Redis</span>
                  {health?.providers && (
                    <span className="flex items-center gap-1">
                      <StatusDot ok={Object.values(health.providers).some(p => p.status === 'healthy')} />
                      Providers
                    </span>
                  )}
                </p>
              )}
            </div>
          </div>
          <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer">
            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1 text-muted-foreground">
              <ExternalLink className="h-3 w-3" />API Docs
            </Button>
          </a>
        </CardContent>
      </Card>

      <Tabs defaultValue="general">
        <TabsList>
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="limits">Limits</TabsTrigger>
          <TabsTrigger value="hitl">HITL</TabsTrigger>
        </TabsList>

        {/* General */}
        <TabsContent value="general" className="mt-4 space-y-3">
          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Infrastructure</CardTitle>
              <CardDescription>Core platform connections — configure in .env</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {[
                {
                  icon: Database, label: 'Database',
                  desc: 'POSTGRES_URL — SQLite (default) or PostgreSQL for production',
                  ok: dbOk,
                },
                {
                  icon: Activity, label: 'Redis Cache',
                  desc: 'REDIS_URL — in-memory cache and Celery broker',
                  ok: redisOk,
                },
                {
                  icon: Server, label: 'Vector DB (Qdrant)',
                  desc: 'QDRANT_URL — semantic search and embedding storage',
                  ok: undefined,
                },
                {
                  icon: Server, label: 'Demo Mode',
                  desc: 'Toggle via top-nav — simulates jobs without live API calls',
                  ok: undefined,
                },
              ].map(({ icon: Icon, label, desc, ok }) => (
                <div key={label} className="flex items-center justify-between px-4 py-3.5 border-b border-border/50 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-surface flex items-center justify-center">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium flex items-center gap-2">
                        {label}
                        {ok !== undefined && (
                          ok
                            ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
                            : <XCircle className="h-3.5 w-3.5 text-red-400" />
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">{desc}</p>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2"><CardTitle className="text-sm">How to modify</CardTitle></CardHeader>
            <CardContent className="text-sm text-muted-foreground space-y-1.5">
              <p>1. Edit <code className="bg-background px-1.5 py-0.5 rounded text-xs">.env</code> in the project root</p>
              <p>2. Restart the application for changes to take effect</p>
              <p>See <code className="bg-background px-1.5 py-0.5 rounded text-xs">.env.example</code> for all available options.</p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Providers */}
        <TabsContent value="providers" className="mt-4">
          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Provider API Keys</CardTitle>
              <CardDescription>All keys are read from environment at startup</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {PROVIDERS_CONFIG.map(({ name, env, letter, color }) => {
                const providerHealth = health?.providers?.[name.toLowerCase().replace(/\s/g, '_')]
                return (
                  <div key={env} className="flex items-center justify-between px-4 py-3 border-b border-border/50 last:border-0">
                    <div className="flex items-center gap-3">
                      <div className={clsx('h-8 w-8 rounded-lg flex items-center justify-center text-xs font-bold', color)}>
                        {letter}
                      </div>
                      <div>
                        <p className="text-sm font-medium flex items-center gap-2">
                          {name}
                          {providerHealth && (
                            providerHealth.status === 'healthy'
                              ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
                              : <AlertCircle className="h-3.5 w-3.5 text-yellow-400" />
                          )}
                        </p>
                        <p className="text-xs text-muted-foreground font-mono">{env}</p>
                      </div>
                    </div>
                    {providerHealth?.latency_ms && (
                      <span className="text-xs text-muted-foreground font-mono">{providerHealth.latency_ms}ms</span>
                    )}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security */}
        <TabsContent value="security" className="mt-4">
          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Security Configuration</CardTitle>
              <CardDescription>Authentication and authorization settings</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {[
                { icon: Shield, label: 'JWT Authentication', env: 'JWT_SECRET', desc: 'Must be ≥ 32 chars. Generate: python -c "import secrets; print(secrets.token_urlsafe(64))"' },
                { icon: Shield, label: 'CSRF Protection',    env: 'CSRF_SECRET', desc: 'Auto-derived from JWT_SECRET if not set' },
                { icon: Key,    label: 'Auth Disabled',      env: 'AUTH_DISABLED', desc: 'Set to true to disable authentication (dev only)' },
              ].map(({ icon: Icon, label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-4 py-3.5 border-b border-border/50 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="h-8 w-8 rounded-lg bg-surface flex items-center justify-center">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{label}</p>
                      <p className="text-xs text-muted-foreground">{desc}</p>
                    </div>
                  </div>
                  <code className="text-xs bg-background px-2 py-0.5 rounded border border-border/50 text-muted-foreground">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Limits */}
        <TabsContent value="limits" className="mt-4">
          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Resource Limits</CardTitle>
              <CardDescription>Rate limits and concurrency constraints</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {LIMITS_CONFIG.map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-4 py-3.5 border-b border-border/50 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-muted-foreground">{desc}</p>
                  </div>
                  <code className="text-xs bg-background px-2 py-0.5 rounded border border-border/50 text-muted-foreground shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* HITL */}
        <TabsContent value="hitl" className="mt-4">
          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Human-in-the-Loop (HITL)</CardTitle>
              <CardDescription>Controls the dataset review gate in the pipeline</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {[
                { label: 'HITL Mode',       env: 'HITL_MODE',             desc: '"blocking" pauses pipeline until reviewer resumes | "async" submits and continues' },
                { label: 'HITL Timeout',    env: 'HITL_TIMEOUT_SECONDS',  desc: 'Seconds to wait before auto-approving (0 = unlimited)' },
              ].map(({ label, env, desc }) => (
                <div key={env} className="flex items-center justify-between px-4 py-3.5 border-b border-border/50 last:border-0">
                  <div>
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-muted-foreground">{desc}</p>
                  </div>
                  <code className="text-xs bg-background px-2 py-0.5 rounded border border-border/50 text-muted-foreground shrink-0 ml-4">{env}</code>
                </div>
              ))}
            </CardContent>
          </Card>
          <p className="text-xs text-muted-foreground mt-3 px-1">
            To review samples, visit the <a href="/review" className="text-orange-400 hover:underline">Review Queue</a>.
            To resume a paused job, call <code className="bg-background px-1 rounded">POST /api/review/jobs/{'{id}'}/resume</code>.
          </p>
        </TabsContent>
      </Tabs>
    </div>
  )
}
