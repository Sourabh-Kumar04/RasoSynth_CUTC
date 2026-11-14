'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Server,
  Activity,
  Zap,
  DollarSign,
  Clock,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Loader2,
  Play,
  XCircle,
  ShieldAlert,
  ArrowRight,
  ArrowRightLeft,
  Shield,
  Sliders,
  History,
  ChevronUp,
  ChevronDown,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
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
      push(`${name.replace(/_/g, ' ')}: ${isSuccess ? 'reachable ✓' : 'unreachable ✗'} (${lat}ms)`, isSuccess)
    } catch {
      const lat = Math.round(performance.now() - start)
      setTestResults(prev => ({
        ...prev,
        [name]: { ok: false, latency: lat, msg: 'Test request failed' }
      }))
      push(`${name.replace(/_/g, ' ')}: test failed`, false)
    } finally {
      setTesting(null)
    }
  }

  const handleMovePriority = (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1
    if (targetIndex < 0 || targetIndex >= providers.length) return
    const reordered = [...providers]
    const item = reordered[index]
    reordered[index] = reordered[targetIndex]
    reordered[targetIndex] = item
    setProviders(reordered)
    push(`Routing Priority Updated: ${item.name.replace(/_/g, ' ')} is now #${targetIndex + 1}`, true)
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
            Manage foundational LLM providers, cascading priority failover routing, and circuit breaker health.
          </p>
        </div>
        <Button variant="outline" size="sm" className="rounded-md border-[#272738] text-[#a8a29e] hover:text-white hover:bg-[#161622] font-mono text-xs" onClick={fetchAll} disabled={loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#f26625]', loading && 'animate-spin')} />
          Refresh Providers
        </Button>
      </div>

      {/* Stat cards */}
      {!loading && providers.length > 0 && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Active Providers', value: `${activeCount}/${providers.length}`, icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-[#161622]' },
              { label: 'Avg Latency', value: avgLatency ? `${avgLatency}ms` : '—', icon: Clock, color: 'text-[#f26625]', bg: 'bg-[#161622]' },
              { label: 'Cost Today', value: `$${totalCost.toFixed(3)}`, icon: DollarSign, color: 'text-[#f26625]', bg: 'bg-[#161622]' },
              { label: 'Circuit Breakers Open', value: cbOpen, icon: ShieldAlert, color: cbOpen > 0 ? 'text-rose-400' : 'text-emerald-400', bg: cbOpen > 0 ? 'bg-rose-950/40' : 'bg-emerald-950/30' },
            ].map(({ label, value, icon: Icon, color, bg }) => (
              <Card key={label} className="bg-[#12121a]/90 backdrop-blur-sm border-[#272738] rounded-xl card-shadow">
                <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-[#a8a29e] font-mono uppercase tracking-wider">{label}</p>
                    <p className={clsx('text-2xl font-bold font-mono mt-0.5 tracking-tight', color)}>{value}</p>
                  </div>
                  <div className={clsx('h-9 w-9 rounded-lg flex items-center justify-center border border-white/5', bg)}>
                    <Icon className={clsx('h-4.5 w-4.5', color)} />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Budget Cap Control Banner */}
          <div className="p-3.5 rounded-xl bg-[#12121a] border border-[#272738] flex flex-wrap items-center justify-between gap-3 text-xs font-mono">
            <div className="flex items-center gap-3">
              <span className="text-[#a8a29e] uppercase text-xs font-bold">API Spending Cap:</span>
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
              <span className="text-xs text-[#a8a29e]">Adjust Budget:</span>
              <input
                type="number"
                min={1}
                max={1000}
                value={budgetCap}
                onChange={(e) => setBudgetCap(Number(e.target.value))}
                className="w-20 bg-[#0a0a0f] border border-[#272738] rounded px-2 py-0.5 text-xs font-mono text-white"
              />
              <span className="text-xs text-emerald-400">Budget Guard Active</span>
            </div>
          </div>
        </div>
      )}

      <Tabs defaultValue="providers">
        <TabsList className="bg-[#161622] rounded-md border border-[#272738] p-1 flex flex-wrap gap-1 h-auto">
          <TabsTrigger value="providers" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white">
            Configured Providers &amp; Priority
          </TabsTrigger>
          <TabsTrigger value="latency" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white">
            Latency Profiles
          </TabsTrigger>
          <TabsTrigger value="circuit-breakers" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white">
            Circuit Breaker States
          </TabsTrigger>
          <TabsTrigger value="failover" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white">
            Failover Audit Log
          </TabsTrigger>
        </TabsList>

        {/* Providers Tab */}
        <TabsContent value="providers" className="mt-4 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-[#a8a29e] font-mono text-xs gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-[#f26625]" /> Loading providers…
            </div>
          ) : providers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-[#a8a29e] bg-[#12121a] rounded-md border border-[#272738]">
              <Server className="h-10 w-10 text-[#a8a29e]" />
              <p className="text-xs font-mono">No providers configured. Add API keys in Settings or .env</p>
              <Button variant="outline" size="sm" className="rounded-md border-[#3b3b52] text-[#f26625]" onClick={fetchAll}>
                <RefreshCw className="h-3.5 w-3.5 mr-1" />Retry
              </Button>
            </div>
          ) : (
            <>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div className="flex items-center gap-3">
                  <Select value={filter} onValueChange={setFilter}>
                    <SelectTrigger className="w-36 h-8 text-xs rounded-md border-[#272738] bg-[#12121a] text-white">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
                      <SelectItem value="all">All ({providers.length})</SelectItem>
                      <SelectItem value="healthy">Healthy</SelectItem>
                      <SelectItem value="degraded">Degraded</SelectItem>
                      <SelectItem value="unhealthy">Unhealthy</SelectItem>
                    </SelectContent>
                  </Select>
                  <span className="text-xs font-mono text-[#a8a29e]">{filtered.length} providers displayed</span>
                </div>
                <p className="text-xs font-mono text-[#a8a29e]">
                  Use the <span className="text-white font-bold">▲ ▼ buttons</span> to reorder cascading failover priority.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {filtered.map((p, idx) => {
                  const isFirst = idx === 0
                  const isLast = idx === filtered.length - 1

                  return (
                    <Card key={p.name} className="bg-[#12121a] border-[#272738] rounded-md card-shadow hover:border-[#3b3b52] transition-all flex flex-col justify-between">
                      <CardContent className="p-4 space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-2.5">
                            <div className="h-9 w-9 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center text-xs font-bold font-mono text-[#f26625] shrink-0">
                              {p.name.slice(0, 2).toUpperCase()}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <p className="text-xs font-bold text-white truncate">{p.name.replace(/_/g, ' ')}</p>
                                <span className={clsx(
                                  "px-1.5 py-0.2 rounded text-[10px] font-mono font-bold border",
                                  idx === 0
                                    ? "bg-emerald-950/40 text-emerald-400 border-emerald-500/30"
                                    : "bg-[#161622] text-[#f26625] border-[#272738]"
                                )}>
                                  Priority #{idx + 1} {idx === 0 ? '(Primary)' : '(Fallback)'}
                                </span>
                              </div>
                              <p className={clsx('text-xs font-mono uppercase mt-0.5', statusVariant(p.status))}>{p.status}</p>
                            </div>
                          </div>

                          {/* Priority Reordering Controls */}
                          <div className="flex items-center gap-1 shrink-0">
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={isFirst}
                              onClick={() => handleMovePriority(idx, 'up')}
                              className="h-7 w-7 rounded border border-[#272738] text-zinc-400 hover:text-white hover:bg-[#1f1f2e] disabled:opacity-30"
                              title="Move priority up"
                            >
                              <ChevronUp className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              disabled={isLast}
                              onClick={() => handleMovePriority(idx, 'down')}
                              className="h-7 w-7 rounded border border-[#272738] text-zinc-400 hover:text-white hover:bg-[#1f1f2e] disabled:opacity-30"
                              title="Move priority down"
                            >
                              <ChevronDown className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs bg-[#0a0a0f] p-3 rounded-xl border border-[#272738]">
                          <div className="flex justify-between">
                            <span className="text-[#a8a29e] font-mono text-xs">Latency</span>
                            <span className="font-mono text-xs font-bold text-[#f26625]">{p.latency_ms ? `${p.latency_ms}ms` : '—'}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-[#a8a29e] font-mono text-xs">Success Rate</span>
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

                        <div className="pt-1">
                          <Button
                            variant="outline"
                            size="sm"
                            className="w-full h-7 text-xs rounded-md border-[#272738] bg-[#0a0a0f] hover:bg-[#161622] text-zinc-300 font-mono"
                            disabled={testing === p.name}
                            onClick={() => handleTest(p.name)}
                          >
                            {testing === p.name ? (
                              <Loader2 className="h-3 w-3 animate-spin text-[#f26625] mr-1" />
                            ) : (
                              <Play className="h-3 w-3 mr-1 text-emerald-400 fill-current" />
                            )}
                            Test Endpoint Reachability
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  )
                })}
              </div>
            </>
          )}
        </TabsContent>

        {/* Latency Chart */}
        <TabsContent value="latency" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-[#f26625]" />
                Provider Latency Profiles (ms)
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              {latencyData.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-[#a8a29e] font-mono gap-2 bg-[#0a0a0f] rounded-xl border border-[#272738]">
                  <Clock className="h-8 w-8 text-[#a8a29e]" />
                  <p className="text-xs font-bold text-[#f26625]">No latency data recorded yet</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={latencyData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#272738" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="#a8a29e" />
                    <YAxis tick={{ fontSize: 10 }} stroke="#a8a29e" unit="ms" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#12121a', border: '1px solid #272738', borderRadius: 8, fontSize: 12, color: '#fff' }}
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

        {/* Circuit Breakers */}
        <TabsContent value="circuit-breakers" className="mt-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Shield className="w-4 h-4 text-[#f26625]" />
                Provider Circuit Breaker Protections
              </CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">
                Automatic backoff and quarantine states guarding against provider rate limiting or HTTP 5xx failures.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-4">
              {Object.keys(circuitBreakers).length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-[#a8a29e] font-mono gap-2 bg-[#0a0a0f] rounded-xl border border-[#272738]">
                  <ShieldAlert className="h-8 w-8 text-emerald-400" />
                  <p className="text-xs font-bold text-white">All circuit breakers closed and operating nominally.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {Object.entries(circuitBreakers).map(([name, state]) => (
                    <div key={name} className="flex items-center justify-between p-3 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                      <span className="text-xs font-bold text-white">{name.replace(/_/g, ' ')}</span>
                      <span className={clsx(
                        'text-xs font-mono font-bold px-2.5 py-0.5 rounded-md border',
                        state === 'closed' && 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30',
                        state === 'open' && 'bg-rose-950/40 text-rose-400 border-rose-500/30',
                        state === 'half_open' && 'bg-amber-950/40 text-amber-400 border-amber-500/30',
                      )}>
                        {state.toUpperCase()}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Failover History Audit Log */}
        <TabsContent value="failover" className="mt-4 space-y-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738] flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                  <History className="h-4 w-4 text-[#f26625]" />
                  Automatic Failover &amp; Migration Audit Log
                </CardTitle>
                <CardDescription className="text-xs text-[#a8a29e]">
                  Recorded automatic migrations and state-preserved transitions across provider outages
                </CardDescription>
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
                        <th className="pb-2">Run ID</th>
                        <th className="pb-2">Transition</th>
                        <th className="pb-2">Reason / Trigger</th>
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
                          <td className="py-2.5 text-[#a8a29e]">{m.failure_type || 'failover_cascade'}</td>
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
