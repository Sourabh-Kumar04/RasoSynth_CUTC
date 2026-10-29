'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Server, Activity, Zap, DollarSign, Clock, AlertTriangle,
  CheckCircle2, RefreshCw, Loader2, Play, XCircle, ShieldAlert,
  ArrowRight, ArrowRightLeft, Shield, Sliders, History,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge, StatusBadge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  BarChart, Bar, ResponsiveContainer, Tooltip, CartesianGrid, XAxis, YAxis, Cell,
} from 'recharts'
import { api, MigrationRecord, FailoverStats } from '@/lib/api/client'

interface Provider {
  name: string
  status: 'available' | 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  latency_ms?: number
  cost_per_token?: number
  requests_today?: number
  tokens_today?: number
  cost_today_usd?: number
  success_rate?: number
}

interface Toast { id: number; msg: string; ok: boolean }

function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])
  let n = 0
  const push = (msg: string, ok = true) => {
    const id = ++n
    setToasts(p => [...p, { id, msg, ok }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3000)
  }
  return { toasts, push }
}

function statusVariant(s: string) {
  if (s === 'available' || s === 'healthy') return 'text-emerald-400 font-bold'
  if (s === 'degraded') return 'text-amber-400 font-bold'
  return 'text-rose-400 font-bold'
}

export default function ProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [circuitBreakers, setCircuitBreakers] = useState<Record<string, string>>({})
  const [failoverStats, setFailoverStats] = useState<FailoverStats | null>(null)
  const [failoverHistory, setFailoverHistory] = useState<MigrationRecord[]>([])
  const [switchJobId, setSwitchJobId] = useState('')
  const [switchTargetProvider, setSwitchTargetProvider] = useState('google_gemini')
  const [switchCheckpoint, setSwitchCheckpoint] = useState(true)
  const [switching, setSwitching] = useState(false)
  const [failoverJobId, setFailoverJobId] = useState('')
  const [failoverReason, setFailoverReason] = useState('Manual latency spike mitigation')
  const [triggeringFailover, setTriggeringFailover] = useState(false)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { ok: boolean; latency: number; msg: string }>>({})
  const [budgetCap, setBudgetCap] = useState(50.00)
  const [filter, setFilter] = useState('all')
  const { toasts, push } = useToast()

  const fetchAll = useCallback(async () => {
    try {
      const [prov, cb, foStats, foHist] = await Promise.all([
        api.getProviders().catch(() => [] as Provider[]),
        api.getCircuitBreakers().catch(() => ({} as Record<string, string>)),
        api.getFailoverStats().catch(() => null),
        api.getFailoverHistory().catch(() => ({ migrations: [], total_count: 0, failure_stats: {} })),
      ])
      const rawProv = Array.isArray(prov) ? prov : []
      // Deduplicate Anthropic / Anthropic Claude
      const map = new Map<string, Provider>()
      for (const p of rawProv) {
        const key = p.name.toLowerCase().replace(/[-_\s]/g, '')
        if (key === 'anthropic') {
          if (!map.has('anthropicclaude')) {
            map.set('anthropicclaude', { ...p, name: 'anthropic_claude' })
          }
        } else if (key === 'anthropicclaude') {
          map.set('anthropicclaude', p)
        } else {
          map.set(key, p)
        }
      }
      setProviders(Array.from(map.values()))
      setCircuitBreakers(cb || {})
      setFailoverStats(foStats)
      setFailoverHistory(foHist?.migrations || [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    const id = setInterval(fetchAll, 30000)
    return () => clearInterval(id)
  }, [fetchAll])

  const handleSwitchProvider = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!switchJobId.trim()) {
      push('Please enter a Job ID to switch provider', false)
      return
    }
    setSwitching(true)
    try {
      const res = await api.switchProvider({
        job_id: switchJobId.trim(),
        new_provider: switchTargetProvider,
        create_checkpoint: switchCheckpoint,
      })
      if (res.success) {
        push(res.message || `Switched to ${switchTargetProvider}`, true)
        fetchAll()
      } else {
        push(res.message || 'Switch failed', false)
      }
    } catch (err: any) {
      push(err?.message || 'Switch provider request failed', false)
    } finally {
      setSwitching(false)
    }
  }

  const handleTriggerFailover = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!failoverJobId.trim()) {
      push('Please enter a Job ID for failover', false)
      return
    }
    setTriggeringFailover(true)
    try {
      const res = await api.triggerFailover({
        job_id: failoverJobId.trim(),
        reason: failoverReason.trim(),
      })
      if (res.success) {
        push(res.message || `Failover completed to ${res.to_provider}`, true)
        fetchAll()
      } else {
        push(res.message || 'Failover failed', false)
      }
    } catch (err: any) {
      push(err?.message || 'Failover request failed', false)
    } finally {
      setTriggeringFailover(false)
    }
  }

  const handleTest = async (name: string) => {
    setTesting(name)
    const start = performance.now()
    try {
      const res = await api.testProvider(name)
      const lat = Math.round(performance.now() - start)
      const isSuccess = Boolean(res?.success)
      setTestResults(prev => ({
        ...prev,
        [name]: { ok: isSuccess, latency: lat, msg: res?.message || (isSuccess ? 'Reachable' : 'Key missing or unreachable') }
      }))
      push(`${name}: ${isSuccess ? 'reachable ✓' : 'unreachable ✗'} (${lat}ms)`, isSuccess)
    } catch {
      const lat = Math.round(performance.now() - start)
      setTestResults(prev => ({
        ...prev,
        [name]: { ok: false, latency: lat, msg: 'Test request failed' }
      }))
      push(`${name}: test failed`, false)
    } finally {
      setTesting(null)
    }
  }

  const filtered = providers.filter(p => {
    if (filter === 'healthy') return p.status === 'available' || p.status === 'healthy'
    if (filter === 'degraded') return p.status === 'degraded'
    if (filter === 'unhealthy') return p.status === 'unhealthy' || p.status === 'unknown'
    return true
  })

  const safeProviders = Array.isArray(providers) ? providers : []
  const activeCount = safeProviders.filter(p => p.status === 'available' || p.status === 'healthy').length
  const avgLatency = (() => {
    const with_lat = safeProviders.filter(p => p.latency_ms != null && p.latency_ms > 0)
    return with_lat.length ? Math.round(with_lat.reduce((s, p) => s + (p.latency_ms ?? 0), 0) / with_lat.length) : 0
  })()
  const totalCost = safeProviders.reduce((s, p) => s + (p.cost_today_usd ?? 0), 0)
  const cbOpen = Object.values(circuitBreakers).filter(v => v === 'open').length

  const latencyData = safeProviders
    .filter(p => p.latency_ms)
    .map(p => ({ name: p.name.replace(/_/g, ' '), latency: p.latency_ms }))

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">

      {/* Toasts */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className={clsx(
            'pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-md border shadow-lg text-xs font-semibold animate-slide-in',
            t.ok ? 'bg-emerald-900 text-white border-emerald-700'
                 : 'bg-rose-900 text-white border-rose-700',
          )}>
            {t.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" /> : <XCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />}
            {t.msg}
          </div>
        ))}
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#272738] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-xs font-mono px-2 py-0.5 rounded-sm bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] font-bold uppercase tracking-wider">
              Model Routing &amp; Resilience
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              AI Providers &amp; Failover
            </h1>
          </div>
          <p className="text-xs text-[#a8a29e]">
            Multi-provider health monitoring, token cost tracking, circuit breaker states &amp; live session migration
          </p>
        </div>
        <Button variant="outline" size="sm" className="rounded-md border-[#272738] text-[#a8a29e] hover:text-white hover:bg-[#161622] font-mono text-xs" onClick={fetchAll} disabled={loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#f26625]', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Stat cards */}
      {!loading && providers.length > 0 && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Active', value: `${activeCount}/${providers.length}`, icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-[#161622]' },
              { label: 'Avg Latency', value: avgLatency ? `${avgLatency}ms` : '—', icon: Clock, color: 'text-[#f26625]', bg: 'bg-[#161622]' },
              { label: 'Cost Today', value: `$${totalCost.toFixed(3)}`, icon: DollarSign, color: 'text-[#f26625]', bg: 'bg-[#161622]' },
              { label: 'CB Open', value: cbOpen, icon: ShieldAlert, color: cbOpen > 0 ? 'text-rose-400' : 'text-emerald-400', bg: cbOpen > 0 ? 'bg-rose-950/40' : 'bg-emerald-950/30' },
            ].map(({ label, value, icon: Icon, color, bg }) => (
              <Card key={label} className="bg-[#12121a]/90 backdrop-blur-sm border-[#272738] rounded-xl card-shadow glow-card-hover group">
                <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-[#a8a29e] font-mono uppercase tracking-wider">{label}</p>
                    <p className={clsx('text-2xl font-bold font-mono mt-0.5 tnum tracking-tight', color)}>{value}</p>
                  </div>
                  <div className={clsx('h-9 w-9 rounded-lg flex items-center justify-center border border-white/5 transition-transform group-hover:scale-110', bg)}>
                    <Icon className={clsx('h-4.5 w-4.5', color)} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Budget Cap Control Banner */}
          <div className="p-3.5 rounded-xl bg-[#12121a] border border-[#272738] flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-3">
              <span className="text-[#a8a29e] uppercase text-xs font-bold">Demo Spending Cap:</span>
              <div className="flex items-center gap-1.5">
                <span className="text-white font-bold">${totalCost.toFixed(3)}</span>
                <span className="text-zinc-500">/</span>
                <span className="text-[#f26625] font-bold">${budgetCap.toFixed(2)} limit</span>
              </div>
              <div className="w-28 bg-[#161622] h-2 rounded-full overflow-hidden border border-[#272738]">
                <div className="bg-[#f26625] h-full" style={{ width: `${Math.min(100, (totalCost / budgetCap) * 100)}%` }} />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#a8a29e]">Adjust Cap:</span>
              <input
                type="number"
                min={1}
                max={1000}
                value={budgetCap}
                onChange={(e) => setBudgetCap(Number(e.target.value))}
                className="w-20 bg-[#0a0a0f] border border-[#272738] rounded px-2 py-0.5 text-xs font-mono text-white"
              />
              <span className="text-xs text-emerald-400">Circuit Breaker Enabled</span>
            </div>
          </div>
        </div>
      )}

      <Tabs defaultValue="providers">
        <TabsList className="bg-[#161622] rounded-md border border-[#272738] p-1 flex flex-wrap gap-1 h-auto">
          <TabsTrigger value="providers" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Providers</TabsTrigger>
          <TabsTrigger value="latency" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Latency Profile</TabsTrigger>
          <TabsTrigger value="circuit-breakers" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Circuit Breakers</TabsTrigger>
          <TabsTrigger value="failover" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white data-[state=active]">Failover &amp; Hot-Switch</TabsTrigger>
        </TabsList>

        {/* Providers tab */}
        <TabsContent value="providers" className="mt-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-[#a8a29e] font-mono text-xs gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-[#f26625]" /> Loading providers…
            </div>
          ) : providers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-[#a8a29e] bg-[#12121a] rounded-md border border-[#272738]">
              <Server className="h-10 w-10 text-[#a8a29e]" />
              <p className="text-xs font-mono">No providers configured. Add API keys to <code className="bg-[#161622] text-[#f26625] px-1.5 py-0.5 rounded">.env</code></p>
              <Button variant="outline" size="sm" className="rounded-md border-[#3b3b52] text-[#f26625]" onClick={fetchAll}><RefreshCw className="h-3.5 w-3.5 mr-1" />Retry</Button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger className="w-36 h-8 text-xs rounded-md border-[#3b3b52] bg-[#12121a] text-[#f26625]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All ({providers.length})</SelectItem>
                    <SelectItem value="healthy">Healthy</SelectItem>
                    <SelectItem value="degraded">Degraded</SelectItem>
                    <SelectItem value="unhealthy">Unhealthy</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs font-mono text-[#a8a29e]">{filtered.length} providers</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {filtered.map((p, idx) => (
                  <Card key={p.name} className="bg-[#12121a] border-[#272738] rounded-md card-shadow hover:border-[#3b3b52] transition-all">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center text-xs font-bold font-mono text-[#f26625] shrink-0">
                            {p.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <p className="text-xs font-bold text-white truncate">{p.name.replace(/_/g, ' ')}</p>
                              <span className="px-1.5 py-0.2 rounded bg-[#161622] text-[#f26625] border border-[#272738] text-xs font-mono font-bold">
                                Priority #{idx + 1}
                              </span>
                            </div>
                            <p className={clsx('text-xs font-mono uppercase mt-0.5', statusVariant(p.status))}>{p.status}</p>
                          </div>
                        </div>
                        <Button
                          variant="ghost" size="sm"
                          className="h-7 text-xs rounded-md border border-[#3b3b52] text-[#f26625] hover:bg-[#161622] shrink-0"
                          disabled={testing === p.name}
                          onClick={() => handleTest(p.name)}
                        >
                          {testing === p.name
                            ? <Loader2 className="h-3 w-3 animate-spin text-[#f26625]" />
                            : <><Play className="h-3 w-3 mr-1 text-emerald-400 fill-current" />Test</>}
                        </Button>
                      </div>

                      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs bg-[#0a0a0f] p-3 rounded-xl border border-[#272738]">
                        <div className="flex justify-between">
                          <span className="text-[#a8a29e] font-mono text-xs">Latency</span>
                          <span className="font-mono text-xs font-bold text-[#f26625]">{p.latency_ms ? `${p.latency_ms}ms` : '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#a8a29e] font-mono text-xs">Success</span>
                          <span className="font-mono text-xs font-bold text-zinc-300">
                            {p.requests_today && p.requests_today > 0 && p.success_rate != null
                              ? `${(p.success_rate * 100).toFixed(1)}%`
                              : testResults[p.name]?.ok
                              ? 'Verified'
                              : 'Not tested'}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#a8a29e] font-mono text-xs">Requests</span>
                          <span className="font-mono text-xs text-[#f26625]">{p.requests_today?.toLocaleString() ?? '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#a8a29e] font-mono text-xs">Cost today</span>
                          <span className="font-mono text-xs text-[#f26625]">{p.cost_today_usd != null ? `$${p.cost_today_usd.toFixed(4)}` : '—'}</span>
                        </div>
                      </div>

                      {/* Inline Test Result Feedback */}
                      {testResults[p.name] && (
                        <div className={clsx(
                          'text-xs font-mono px-2 py-1 rounded-md flex items-center justify-between border',
                          testResults[p.name].ok
                            ? 'bg-emerald-950/40 text-emerald-300 border-emerald-500/40'
                            : 'bg-rose-950/40 text-rose-300 border-rose-500/40'
                        )}>
                          <span>{testResults[p.name].ok ? '✓ Reachable' : '✗ Unreachable'}</span>
                          <span>{testResults[p.name].latency}ms latency</span>
                        </div>
                      )}

                      {circuitBreakers[p.name] && (
                        <div className={clsx(
                          'text-xs font-mono font-bold px-2.5 py-1 rounded-md flex items-center gap-1.5 border',
                          circuitBreakers[p.name] === 'open' ? 'bg-rose-950/40 text-rose-400 border-rose-500/30' : 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30',
                        )}>
                          <ShieldAlert className="h-3 w-3 shrink-0" />
                          Circuit breaker: {circuitBreakers[p.name]}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          )}
        </TabsContent>

        {/* Latency chart */}
        <TabsContent value="latency" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]"><CardTitle className="text-sm font-bold text-[#f26625]">Provider Latency (ms)</CardTitle></CardHeader>
            <CardContent className="p-4">
              {latencyData.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-[#a8a29e] font-mono gap-2 bg-[#0a0a0f] rounded-xl border border-[#272738]">
                  <Clock className="h-8 w-8 text-[#a8a29e]" />
                  <p className="text-xs font-bold text-[#f26625]">No latency data — run a dataset job first</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={latencyData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#272738" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="#a8a29e" />
                    <YAxis tick={{ fontSize: 10 }} stroke="#a8a29e" unit="ms" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #272738', borderRadius: 12, fontSize: 12 }}
                      formatter={(v: any) => [`${v}ms`, 'Latency']}
                    />
                    <Bar dataKey="latency" radius={[6, 6, 0, 0]}>
                      {latencyData.map((entry, i) => (
                        <Cell key={i} fill={entry.latency! > 1000 ? '#E11D48' : entry.latency! > 500 ? '#D97706' : '#f26625'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Circuit breakers */}
        <TabsContent value="circuit-breakers" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]"><CardTitle className="text-sm font-bold text-[#f26625]">Circuit Breaker States</CardTitle></CardHeader>
            <CardContent className="p-4">
              {Object.keys(circuitBreakers).length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-[#a8a29e] font-mono gap-2 bg-[#0a0a0f] rounded-xl border border-[#272738]">
                  <ShieldAlert className="h-8 w-8 text-[#a8a29e]" />
                  <p className="text-xs font-bold text-[#f26625]">No circuit breaker data available</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {Object.entries(circuitBreakers).map(([name, state]) => (
                    <div key={name} className="flex items-center justify-between p-3 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                      <span className="text-xs font-bold text-[#f26625]">{name.replace(/_/g, ' ')}</span>
                      <span className={clsx(
                        'text-xs font-mono font-bold px-2.5 py-0.5 rounded-md border',
                        state === 'closed' && 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30',
                        state === 'open' && 'bg-rose-950/40 text-rose-400 border-rose-500/30',
                        state === 'half_open' && 'bg-amber-950/40 text-amber-400 border-amber-500/30',
                      )}>
                        {state}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Failover & Hot-Switch tab */}
        <TabsContent value="failover" className="mt-4 space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Manual Provider Hot-Switcher */}
            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardHeader className="pb-3 border-b border-[#272738]">
                <div className="flex items-center gap-2">
                  <ArrowRightLeft className="h-4 w-4 text-[#f26625]" />
                  <CardTitle className="text-sm font-bold text-white">Manual Provider Hot-Switcher (ADR-001)</CardTitle>
                </div>
                <p className="text-xs text-[#a8a29e] mt-1 font-mono">
                  Migrate an in-flight synthesis job to a target model provider with an atomic state checkpoint.
                </p>
              </CardHeader>
              <CardContent className="p-4">
                <form onSubmit={handleSwitchProvider} className="space-y-4">
                  <div>
                    <label className="text-xs font-mono text-[#a8a29e] block mb-1">In-Flight Job ID</label>
                    <input
                      type="text"
                      placeholder="e.g. medical-sft-v1-verified or UUID"
                      value={switchJobId}
                      onChange={e => setSwitchJobId(e.target.value)}
                      className="w-full h-9 px-3 rounded-lg bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-white placeholder-[#a8a29e] focus:outline-none focus:border-[#f26625]"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-mono text-[#a8a29e] block mb-1">Target Provider</label>
                    <Select value={switchTargetProvider} onValueChange={setSwitchTargetProvider}>
                      <SelectTrigger className="w-full h-9 text-xs rounded-lg border-[#272738] bg-[#0a0a0f] text-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="google_gemini">Google Gemini (Gemini 2.5 Flash / Pro)</SelectItem>
                        <SelectItem value="openai">OpenAI (GPT-4o / GPT-4o-mini)</SelectItem>
                        <SelectItem value="anthropic">Anthropic (Claude 3.5 Sonnet)</SelectItem>
                        <SelectItem value="groq">Groq (Llama-3.3-70B Ultra-Fast)</SelectItem>
                        <SelectItem value="deepseek">DeepSeek (V3 / R1 Reasoning)</SelectItem>
                        <SelectItem value="nvidia_nim">NVIDIA NIM (Llama-3-70B)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="flex items-center gap-2 text-xs font-mono text-[#a8a29e]">
                    <input
                      type="checkbox"
                      id="ckpt-switch"
                      checked={switchCheckpoint}
                      onChange={e => setSwitchCheckpoint(e.target.checked)}
                      className="rounded border-[#272738] text-[#f26625] focus:ring-0"
                    />
                    <label htmlFor="ckpt-switch" className="cursor-pointer">
                      Persist pipeline state checkpoint before switching
                    </label>
                  </div>

                  <Button
                    type="submit"
                    disabled={switching}
                    className="w-full rounded-xl bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-bold font-mono h-9"
                  >
                    {switching ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <ArrowRightLeft className="h-3.5 w-3.5 mr-1.5" />}
                    Hot-Switch Active Provider
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* Trigger Manual Failover */}
            <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
              <CardHeader className="pb-3 border-b border-[#272738]">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-amber-400" />
                  <CardTitle className="text-sm font-bold text-white">Trigger Automatic Failover Migration</CardTitle>
                </div>
                <p className="text-xs text-[#a8a29e] mt-1 font-mono">
                  Simulate or trigger AutomaticFailoverEngine to cascade to the next healthiest provider.
                </p>
              </CardHeader>
              <CardContent className="p-4">
                <form onSubmit={handleTriggerFailover} className="space-y-4">
                  <div>
                    <label className="text-xs font-mono text-[#a8a29e] block mb-1">Target Job ID</label>
                    <input
                      type="text"
                      placeholder="e.g. medical-sft-v1-verified"
                      value={failoverJobId}
                      onChange={e => setFailoverJobId(e.target.value)}
                      className="w-full h-9 px-3 rounded-lg bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-white placeholder-[#a8a29e] focus:outline-none focus:border-amber-500"
                    />
                  </div>

                  <div>
                    <label className="text-xs font-mono text-[#a8a29e] block mb-1">Failure Reason / Simulated Trigger</label>
                    <input
                      type="text"
                      value={failoverReason}
                      onChange={e => setFailoverReason(e.target.value)}
                      className="w-full h-9 px-3 rounded-lg bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                    />
                  </div>

                  <div className="p-3 rounded-xl bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-[#a8a29e] space-y-1">
                    <p className="text-white font-bold">Failover Protocol Rules:</p>
                    <p>• Circuit breaker updates automatically on repeated error triggers</p>
                    <p>• Intermediate constructed samples are saved to checkpoint storage</p>
                    <p>• Priority cascade selects next available healthy provider</p>
                  </div>

                  <Button
                    type="submit"
                    disabled={triggeringFailover}
                    variant="outline"
                    className="w-full rounded-xl border-amber-500/40 text-amber-400 hover:bg-amber-950/20 text-xs font-bold font-mono h-9"
                  >
                    {triggeringFailover ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <ShieldAlert className="h-3.5 w-3.5 mr-1.5" />}
                    Simulate / Trigger Failover
                  </Button>
                </form>
              </CardContent>
            </Card>

          </div>

          {/* Failover History Table */}
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738] flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                  <History className="h-4 w-4 text-[#f26625]" />
                  Provider Migration &amp; Failover History
                </CardTitle>
                <p className="text-xs text-[#a8a29e] mt-0.5 font-mono">
                  Recorded failovers and hot-switches with preserved checkpoint references
                </p>
              </div>
              <Badge variant="outline" className="font-mono text-xs border-[#272738] text-[#10b981]">
                {failoverHistory.length} Recorded Migrations
              </Badge>
            </CardHeader>
            <CardContent className="p-4">
              {failoverHistory.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-[#a8a29e] font-mono gap-2 bg-[#0a0a0f] rounded-xl border border-[#272738]">
                  <CheckCircle2 className="h-7 w-7 text-emerald-400" />
                  <p className="text-xs text-white">Zero failover migrations recorded — all providers operating stably.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead>
                      <tr className="border-b border-[#272738] text-[#a8a29e] text-xs uppercase">
                        <th className="pb-2">Migration ID</th>
                        <th className="pb-2">Job ID</th>
                        <th className="pb-2">Transition</th>
                        <th className="pb-2">Reason / Failure</th>
                        <th className="pb-2">Checkpoint ID</th>
                        <th className="pb-2">Status</th>
                        <th className="pb-2 text-right">Timestamp</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#272738]">
                      {failoverHistory.map(m => (
                        <tr key={m.migration_id} className="hover:bg-[#161622]/50">
                          <td className="py-2.5 text-white font-bold">{m.migration_id.slice(0, 8)}...</td>
                          <td className="py-2.5 text-[#a8a29e]">{m.job_id}</td>
                          <td className="py-2.5">
                            <span className="text-rose-400 font-semibold">{m.from_provider}</span>
                            <span className="text-[#a8a29e] mx-1.5">→</span>
                            <span className="text-emerald-400 font-semibold">{m.to_provider}</span>
                          </td>
                          <td className="py-2.5 text-[#a8a29e]">{m.failure_type || 'manual_switch'}</td>
                          <td className="py-2.5 text-[#f26625]">{m.checkpoint_id || 'ckpt-auto'}</td>
                          <td className="py-2.5">
                            <span className={clsx(
                              'text-xs px-2 py-0.5 rounded-md font-bold uppercase border',
                              m.success ? 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30' : 'bg-rose-950/40 text-rose-400 border-rose-500/30'
                            )}>
                              {m.success ? 'Success' : 'Failed'}
                            </span>
                          </td>
                          <td className="py-2.5 text-right text-[#a8a29e]">
                            {new Date(m.timestamp).toLocaleTimeString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
