'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Server, Activity, Zap, DollarSign, Clock, AlertTriangle,
  CheckCircle2, RefreshCw, Loader2, Play, XCircle, ShieldAlert,
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
import { api } from '@/lib/api/client'

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
  if (s === 'available' || s === 'healthy') return 'text-emerald-700 font-bold'
  if (s === 'degraded') return 'text-amber-700 font-bold'
  return 'text-rose-700 font-bold'
}

export default function ProvidersPage() {
  const [providers, setProviders] = useState<Provider[]>([])
  const [circuitBreakers, setCircuitBreakers] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState<string | null>(null)
  const [filter, setFilter] = useState('all')
  const { toasts, push } = useToast()

  const fetchAll = useCallback(async () => {
    try {
      const [prov, cb] = await Promise.all([
        api.getProviders().catch(() => [] as Provider[]),
        api.getCircuitBreakers().catch(() => ({} as Record<string, string>)),
      ])
      setProviders(Array.isArray(prov) ? prov : [])
      setCircuitBreakers(cb || {})
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
    try {
      const res = await api.testProvider(name)
      push(`${name}: ${res?.success ? 'reachable ✓' : 'unreachable ✗'}`, res?.success)
    } catch {
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
            'pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-full border shadow-lg text-xs font-semibold animate-slide-in',
            t.ok ? 'bg-emerald-900 text-white border-emerald-700'
                 : 'bg-rose-900 text-white border-rose-700',
          )}>
            {t.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" /> : <XCircle className="h-3.5 w-3.5 shrink-0 text-rose-400" />}
            {t.msg}
          </div>
        ))}
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E6E0] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-bold uppercase tracking-wider">
              LLM &amp; API Router
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">
              Provider Management
            </h1>
          </div>
          <p className="text-xs text-[#55635B]">
            Live health telemetry, latency profiles, and cost routing for AI model providers
          </p>
        </div>
        <Button variant="outline" size="sm" className="rounded-full border-[#D1D8CE] text-[#1B3B2B] hover:bg-[#E8ECE6]" onClick={fetchAll} disabled={loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#1B3B2B]', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Stat cards */}
      {!loading && providers.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Active', value: `${activeCount}/${providers.length}`, icon: CheckCircle2, color: 'text-emerald-700', bg: 'bg-[#E8ECE6]' },
            { label: 'Avg Latency', value: avgLatency ? `${avgLatency}ms` : '—', icon: Clock, color: 'text-[#1B3B2B]', bg: 'bg-[#E8ECE6]' },
            { label: 'Cost Today', value: `$${totalCost.toFixed(3)}`, icon: DollarSign, color: 'text-[#1B3B2B]', bg: 'bg-[#E8ECE6]' },
            { label: 'CB Open', value: cbOpen, icon: ShieldAlert, color: cbOpen > 0 ? 'text-rose-700' : 'text-emerald-700', bg: cbOpen > 0 ? 'bg-rose-100' : 'bg-[#E8ECE6]' },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <Card key={label} className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
              <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-[#55635B] font-mono uppercase">{label}</p>
                  <p className={clsx('text-2xl font-bold font-mono mt-0.5', color)}>{value}</p>
                </div>
                <div className={clsx('h-9 w-9 rounded-xl flex items-center justify-center border border-[#D1D8CE]', bg)}>
                  <Icon className={clsx('h-4.5 w-4.5', color)} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Tabs defaultValue="providers">
        <TabsList className="bg-[#E8ECE6] rounded-full border border-[#D1D8CE]">
          <TabsTrigger value="providers" className="rounded-full">Providers</TabsTrigger>
          <TabsTrigger value="latency" className="rounded-full">Latency Profile</TabsTrigger>
          <TabsTrigger value="circuit-breakers" className="rounded-full">Circuit Breakers</TabsTrigger>
        </TabsList>

        {/* Providers tab */}
        <TabsContent value="providers" className="mt-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-[#55635B] font-mono text-xs gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-[#1B3B2B]" /> Loading providers…
            </div>
          ) : providers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-[#55635B] bg-white rounded-2xl border border-[#E2E6E0]">
              <Server className="h-10 w-10 text-[#809085]" />
              <p className="text-xs font-mono">No providers configured. Add API keys to <code className="bg-[#E8ECE6] text-[#1B3B2B] px-1.5 py-0.5 rounded">.env</code></p>
              <Button variant="outline" size="sm" className="rounded-full border-[#D1D8CE] text-[#1B3B2B]" onClick={fetchAll}><RefreshCw className="h-3.5 w-3.5 mr-1" />Retry</Button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger className="w-36 h-8 text-xs rounded-full border-[#D1D8CE] bg-white text-[#1B3B2B]"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All ({providers.length})</SelectItem>
                    <SelectItem value="healthy">Healthy</SelectItem>
                    <SelectItem value="degraded">Degraded</SelectItem>
                    <SelectItem value="unhealthy">Unhealthy</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs font-mono text-[#55635B]">{filtered.length} providers</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {filtered.map(p => (
                  <Card key={p.name} className="bg-white border-[#E2E6E0] rounded-2xl card-shadow hover:border-[#D1D8CE] transition-all">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <div className="h-9 w-9 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center text-xs font-bold font-mono text-[#1B3B2B] shrink-0">
                            {p.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-[#1B3B2B] truncate">{p.name.replace(/_/g, ' ')}</p>
                            <p className={clsx('text-[11px] font-mono uppercase', statusVariant(p.status))}>{p.status}</p>
                          </div>
                        </div>
                        <Button
                          variant="ghost" size="sm"
                          className="h-7 text-xs rounded-full border border-[#D1D8CE] text-[#1B3B2B] hover:bg-[#E8ECE6] shrink-0"
                          disabled={testing === p.name}
                          onClick={() => handleTest(p.name)}
                        >
                          {testing === p.name
                            ? <Loader2 className="h-3 w-3 animate-spin text-[#1B3B2B]" />
                            : <><Play className="h-3 w-3 mr-1 text-emerald-600 fill-current" />Test</>}
                        </Button>
                      </div>

                      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs bg-[#F6F7F4] p-3 rounded-xl border border-[#E2E6E0]">
                        <div className="flex justify-between">
                          <span className="text-[#55635B] font-mono text-[11px]">Latency</span>
                          <span className="font-mono text-xs font-bold text-[#1B3B2B]">{p.latency_ms ? `${p.latency_ms}ms` : '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#55635B] font-mono text-[11px]">Success</span>
                          <span className="font-mono text-xs font-bold text-[#1B3B2B]">{p.success_rate != null ? `${(p.success_rate * 100).toFixed(1)}%` : '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#55635B] font-mono text-[11px]">Requests</span>
                          <span className="font-mono text-xs text-[#1B3B2B]">{p.requests_today?.toLocaleString() ?? '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-[#55635B] font-mono text-[11px]">Cost today</span>
                          <span className="font-mono text-xs text-[#1B3B2B]">{p.cost_today_usd != null ? `$${p.cost_today_usd.toFixed(4)}` : '—'}</span>
                        </div>
                      </div>

                      {circuitBreakers[p.name] && (
                        <div className={clsx(
                          'text-[11px] font-mono font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 border',
                          circuitBreakers[p.name] === 'open' ? 'bg-rose-100 text-rose-800 border-rose-300' : 'bg-emerald-100 text-emerald-800 border-emerald-300',
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
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]"><CardTitle className="text-sm font-bold text-[#1B3B2B]">Provider Latency (ms)</CardTitle></CardHeader>
            <CardContent className="p-4">
              {latencyData.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-[#55635B] font-mono gap-2 bg-[#F6F7F4] rounded-xl border border-[#E2E6E0]">
                  <Clock className="h-8 w-8 text-[#809085]" />
                  <p className="text-xs font-bold text-[#1B3B2B]">No latency data — run a dataset job first</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={latencyData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E6E0" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="#55635B" />
                    <YAxis tick={{ fontSize: 10 }} stroke="#55635B" unit="ms" />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#FFFFFF', border: '1px solid #E2E6E0', borderRadius: 12, fontSize: 12 }}
                      formatter={(v: any) => [`${v}ms`, 'Latency']}
                    />
                    <Bar dataKey="latency" radius={[6, 6, 0, 0]}>
                      {latencyData.map((entry, i) => (
                        <Cell key={i} fill={entry.latency! > 1000 ? '#E11D48' : entry.latency! > 500 ? '#D97706' : '#1B3B2B'} />
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
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#E2E6E0]"><CardTitle className="text-sm font-bold text-[#1B3B2B]">Circuit Breaker States</CardTitle></CardHeader>
            <CardContent className="p-4">
              {Object.keys(circuitBreakers).length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-[#55635B] font-mono gap-2 bg-[#F6F7F4] rounded-xl border border-[#E2E6E0]">
                  <ShieldAlert className="h-8 w-8 text-[#809085]" />
                  <p className="text-xs font-bold text-[#1B3B2B]">No circuit breaker data available</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {Object.entries(circuitBreakers).map(([name, state]) => (
                    <div key={name} className="flex items-center justify-between p-3 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0]">
                      <span className="text-xs font-bold text-[#1B3B2B]">{name.replace(/_/g, ' ')}</span>
                      <span className={clsx(
                        'text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full border',
                        state === 'closed' && 'bg-emerald-100 text-emerald-800 border-emerald-300',
                        state === 'open' && 'bg-rose-100 text-rose-800 border-rose-300',
                        state === 'half_open' && 'bg-amber-100 text-amber-800 border-amber-300',
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
      </Tabs>
    </div>
  )
}
