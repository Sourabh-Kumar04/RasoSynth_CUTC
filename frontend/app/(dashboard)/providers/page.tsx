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

const STATUS_COLOR: Record<string, string> = {
  available: '#22c55e', healthy: '#22c55e',
  degraded: '#f59e0b', unhealthy: '#ef4444', unknown: '#6b7280',
}

function statusVariant(s: string) {
  if (s === 'available' || s === 'healthy') return 'text-green-400'
  if (s === 'degraded') return 'text-yellow-400'
  return 'text-red-400'
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

  const activeCount = providers.filter(p => p.status !== 'unhealthy' && p.status !== 'unknown').length
  const avgLatency = (() => {
    const with_lat = providers.filter(p => p.latency_ms)
    return with_lat.length ? Math.round(with_lat.reduce((s, p) => s + (p.latency_ms ?? 0), 0) / with_lat.length) : 0
  })()
  const totalCost = providers.reduce((s, p) => s + (p.cost_today_usd ?? 0), 0)
  const cbOpen = Object.values(circuitBreakers).filter(v => v === 'open').length

  const latencyData = providers
    .filter(p => p.latency_ms)
    .map(p => ({ name: p.name.replace(/_/g, ' '), latency: p.latency_ms }))

  return (
    <div className="space-y-5 animate-fade-in">

      {/* Toasts */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className={clsx(
            'pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium animate-slide-in',
            t.ok ? 'bg-green-950/95 border-green-600/40 text-green-200'
                 : 'bg-red-950/95 border-red-600/40 text-red-200',
          )}>
            {t.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0" /> : <XCircle className="h-3.5 w-3.5 shrink-0" />}
            {t.msg}
          </div>
        ))}
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Server className="h-5 w-5 text-orange-400" />Provider Management
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Live status and metrics for all configured AI providers
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
          <RefreshCw className={clsx('h-3.5 w-3.5 mr-1', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Stat cards */}
      {!loading && providers.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Active', value: `${activeCount}/${providers.length}`, icon: CheckCircle2, color: 'text-green-400', bg: 'bg-green-500/10' },
            { label: 'Avg Latency', value: avgLatency ? `${avgLatency}ms` : '—', icon: Clock, color: 'text-blue-400', bg: 'bg-blue-500/10' },
            { label: 'Cost Today', value: `$${totalCost.toFixed(3)}`, icon: DollarSign, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
            { label: 'CB Open', value: cbOpen, icon: ShieldAlert, color: cbOpen > 0 ? 'text-red-400' : 'text-green-400', bg: cbOpen > 0 ? 'bg-red-500/10' : 'bg-green-500/10' },
          ].map(({ label, value, icon: Icon, color, bg }) => (
            <Card key={label} className="bg-surface/40 border-border">
              <CardContent className="pt-3 pb-3 px-4 flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className={clsx('text-xl font-bold mt-0.5', color)}>{value}</p>
                </div>
                <div className={clsx('h-9 w-9 rounded-lg flex items-center justify-center', bg)}>
                  <Icon className={clsx('h-4.5 w-4.5', color)} />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Tabs defaultValue="providers">
        <TabsList>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="latency">Latency</TabsTrigger>
          <TabsTrigger value="circuit-breakers">Circuit Breakers</TabsTrigger>
        </TabsList>

        {/* Providers tab */}
        <TabsContent value="providers" className="mt-4 space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
              <Loader2 className="h-5 w-5 animate-spin" /> Loading providers…
            </div>
          ) : providers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
              <Server className="h-10 w-10 opacity-30" />
              <p className="text-sm">No providers configured. Add API keys to <code className="bg-surface px-1 rounded">.env</code></p>
              <Button variant="outline" size="sm" onClick={fetchAll}><RefreshCw className="h-3.5 w-3.5 mr-1" />Retry</Button>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger className="w-36 h-8 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All ({providers.length})</SelectItem>
                    <SelectItem value="healthy">Healthy</SelectItem>
                    <SelectItem value="degraded">Degraded</SelectItem>
                    <SelectItem value="unhealthy">Unhealthy</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs text-muted-foreground">{filtered.length} providers</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {filtered.map(p => (
                  <Card key={p.name} className="bg-surface/40 border-border hover:border-orange-500/40 transition-colors">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2.5">
                          <div className="h-9 w-9 rounded-lg bg-orange-500/10 flex items-center justify-center text-sm font-bold text-orange-400 shrink-0">
                            {p.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{p.name.replace(/_/g, ' ')}</p>
                            <p className={clsx('text-xs font-medium', statusVariant(p.status))}>{p.status}</p>
                          </div>
                        </div>
                        <Button
                          variant="ghost" size="sm"
                          className="h-7 text-xs shrink-0"
                          disabled={testing === p.name}
                          onClick={() => handleTest(p.name)}
                        >
                          {testing === p.name
                            ? <Loader2 className="h-3 w-3 animate-spin" />
                            : <><Play className="h-3 w-3 mr-1" />Test</>}
                        </Button>
                      </div>

                      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Latency</span>
                          <span className="font-mono">{p.latency_ms ? `${p.latency_ms}ms` : '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Success</span>
                          <span className="font-mono">{p.success_rate != null ? `${(p.success_rate * 100).toFixed(1)}%` : '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Requests</span>
                          <span className="font-mono">{p.requests_today?.toLocaleString() ?? '—'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Cost today</span>
                          <span className="font-mono">{p.cost_today_usd != null ? `$${p.cost_today_usd.toFixed(4)}` : '—'}</span>
                        </div>
                      </div>

                      {circuitBreakers[p.name] && (
                        <div className={clsx(
                          'text-xs px-2 py-1 rounded flex items-center gap-1.5',
                          circuitBreakers[p.name] === 'open' ? 'bg-red-500/10 text-red-400' : 'bg-green-500/10 text-green-400',
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
          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2"><CardTitle className="text-sm">Provider Latency (ms)</CardTitle></CardHeader>
            <CardContent>
              {latencyData.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-2">
                  <Clock className="h-8 w-8 opacity-30" />
                  <p className="text-sm">No latency data — run a job first</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={latencyData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                    <YAxis tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" unit="ms" />
                    <Tooltip
                      contentStyle={{ backgroundColor: 'hsl(var(--surface))', border: '1px solid hsl(var(--border))', borderRadius: 6, fontSize: 12 }}
                      formatter={(v: any) => [`${v}ms`, 'Latency']}
                    />
                    <Bar dataKey="latency" radius={[4, 4, 0, 0]}>
                      {latencyData.map((entry, i) => (
                        <Cell key={i} fill={entry.latency! > 1000 ? '#ef4444' : entry.latency! > 500 ? '#f59e0b' : '#22c55e'} />
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
          <Card className="bg-surface/40 border-border">
            <CardHeader className="pb-2"><CardTitle className="text-sm">Circuit Breaker States</CardTitle></CardHeader>
            <CardContent>
              {Object.keys(circuitBreakers).length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-muted-foreground gap-2">
                  <ShieldAlert className="h-8 w-8 opacity-30" />
                  <p className="text-sm">No circuit breaker data available</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {Object.entries(circuitBreakers).map(([name, state]) => (
                    <div key={name} className="flex items-center justify-between p-3 rounded-lg bg-background/50 border border-border/40">
                      <span className="text-sm font-medium">{name.replace(/_/g, ' ')}</span>
                      <span className={clsx(
                        'text-xs px-2 py-0.5 rounded-full border font-medium',
                        state === 'closed' && 'bg-green-500/15 text-green-300 border-green-500/30',
                        state === 'open' && 'bg-red-500/15 text-red-300 border-red-500/30',
                        state === 'half_open' && 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
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
