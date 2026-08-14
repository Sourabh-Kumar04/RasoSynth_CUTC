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
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge, StatusBadge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  CartesianGrid,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '@/lib/api/client'

// Provider types from backend
interface ProviderStatusData {
  name: string
  status: 'available' | 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  latency_ms?: number
  cost_per_token?: number
  requests_today?: number
  tokens_today?: number
  cost_today_usd?: number
  success_rate?: number
}

interface HealthData {
  status: string
  providers?: Record<string, any>
  database?: boolean
  redis?: boolean
}

export default function ProvidersPage() {
  const [providers, setProviders] = useState<ProviderStatusData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')

  const fetchData = useCallback(async () => {
    try {
      setError(null)
      const providersData = await api.getProviders().catch(() => [] as ProviderStatusData[])
      setProviders(providersData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load provider data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Poll every 30s
    return () => clearInterval(interval)
  }, [fetchData])

  // Calculate derived stats
  const activeProviders = providers.filter(p => p.status !== 'unhealthy' && p.status !== 'unknown')
  const avgLatency = providers.length > 0
    ? Math.round(providers.reduce((acc, p) => acc + (p.latency_ms || 0), 0) / providers.filter(p => p.latency_ms).length)
    : 0
  const totalCost = providers.reduce((acc, p) => acc + (p.cost_today_usd || 0), 0)

  const filteredProviders = providers.filter((p) => {
    if (filter === 'all') return true
    if (filter === 'healthy') return p.status === 'available' || p.status === 'healthy'
    if (filter === 'degraded') return p.status === 'degraded'
    if (filter === 'unhealthy') return p.status === 'unhealthy' || p.status === 'unknown'
    return true
  })

  const selected = providers.find((p) => p.name === selectedProvider)

  // Build latency chart data from real provider latency
  const latencyData = providers.map(p => ({
    name: p.name,
    latency: p.latency_ms || 0,
  }))

  // Empty state when no providers
  if (!loading && providers.length === 0 && !error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Provider Management</h1>
            <p className="text-sm text-muted-foreground">
              Monitor and configure AI provider connections
            </p>
          </div>
        </div>
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Server className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">No Providers Configured</h3>
            <p className="text-sm text-muted-foreground mb-4 text-center max-w-md">
              Configure API keys in your environment to enable providers.
              The system supports Google Gemini, NVIDIA NIM, Anthropic Claude, OpenAI, and more.
            </p>
            <Button variant="outline" onClick={fetchData}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Provider Management</h1>
          <p className="text-sm text-muted-foreground">
            Monitor and configure AI provider connections
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-2" onClick={fetchData} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertTriangle className="h-5 w-5 text-destructive" />
            <div className="flex-1">
              <p className="text-sm font-medium">Failed to load providers</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={fetchData}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {loading && (
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-accent mb-4" />
            <p className="text-sm text-muted-foreground">Loading providers...</p>
          </CardContent>
        </Card>
      )}

      {/* Overview Stats - Only show when we have data */}
      {!loading && providers.length > 0 && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Active Providers</p>
                  <p className="text-2xl font-semibold">{activeProviders.length}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-success/10 flex items-center justify-center">
                  <CheckCircle2 className="h-5 w-5 text-success" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Total Providers</p>
                  <p className="text-2xl font-semibold">{providers.length}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Server className="h-5 w-5 text-accent" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Avg Latency</p>
                  <p className="text-2xl font-semibold">{avgLatency > 0 ? `${avgLatency}ms` : '-'}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-info/10 flex items-center justify-center">
                  <Clock className="h-5 w-5 text-info" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">Cost Today</p>
                  <p className="text-2xl font-semibold">${totalCost.toFixed(2)}</p>
                </div>
                <div className="h-10 w-10 rounded-lg bg-warning/10 flex items-center justify-center">
                  <DollarSign className="h-5 w-5 text-warning" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="providers">
        <TabsList>
          <TabsTrigger value="providers">All Providers</TabsTrigger>
          <TabsTrigger value="latency">Latency</TabsTrigger>
        </TabsList>

        {/* All Providers */}
        <TabsContent value="providers" className="mt-6">
          {!loading && providers.length > 0 ? (
            <>
              <div className="flex items-center gap-4 mb-4">
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Providers</SelectItem>
                    <SelectItem value="healthy">Healthy</SelectItem>
                    <SelectItem value="degraded">Degraded</SelectItem>
                    <SelectItem value="unhealthy">Unhealthy</SelectItem>
                  </SelectContent>
                </Select>
                <span className="text-xs text-muted-foreground">
                  {filteredProviders.length} providers
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {filteredProviders.map((provider) => (
                  <Card
                    key={provider.name}
                    className={clsx(
                      'cursor-pointer transition-all',
                      selectedProvider === provider.name && 'border-accent'
                    )}
                    onClick={() => setSelectedProvider(provider.name === selectedProvider ? null : provider.name)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div
                            className={clsx(
                              'h-10 w-10 rounded-lg flex items-center justify-center font-bold',
                              (provider.status === 'available' || provider.status === 'healthy') && 'bg-success/10 text-success',
                              provider.status === 'degraded' && 'bg-warning/10 text-warning',
                              (provider.status === 'unhealthy' || provider.status === 'unknown') && 'bg-error/10 text-error'
                            )}
                          >
                            {provider.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <h3 className="font-medium">{provider.name}</h3>
                            <div className="flex items-center gap-2 mt-0.5">
                              <StatusBadge status={provider.status === 'available' ? 'healthy' : provider.status} />
                                                          </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-mono">
                            {provider.cost_per_token ? `$${provider.cost_per_token.toFixed(3)}/1k` : '-'}
                          </p>
                          <p className="text-xs text-muted-foreground">per 1k tokens</p>
                        </div>
                      </div>

                      {/* Metrics */}
                      <div className="grid grid-cols-2 gap-4 mb-4">
                        <div className="text-center">
                          <p className="text-xs text-muted-foreground">Latency</p>
                          <p className="font-mono font-medium">
                            {provider.latency_ms ? `${provider.latency_ms}ms` : '-'}
                          </p>
                        </div>
                        <div className="text-center">
                          <p className="text-xs text-muted-foreground">Success Rate</p>
                          <p className="font-mono font-medium">
                            {provider.success_rate ? `${(provider.success_rate * 100).toFixed(1)}%` : '-'}
                          </p>
                        </div>
                      </div>

                      {/* Requests Today */}
                      {provider.requests_today !== undefined && (
                        <div className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-muted-foreground">Requests Today</span>
                            <span className="font-mono">{provider.requests_today.toLocaleString()}</span>
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          ) : (
            !loading && (
              <Card>
                <CardContent className="p-8 flex flex-col items-center justify-center text-center">
                  <Activity className="h-10 w-10 text-muted-foreground/50 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    No provider data available
                  </p>
                </CardContent>
              </Card>
            )
          )}
        </TabsContent>

        {/* Latency Analysis */}
        <TabsContent value="latency" className="mt-6">
          {latencyData.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Provider Latency (ms)</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={latencyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} stroke="#606070" />
                    <YAxis tick={{ fontSize: 10 }} stroke="#606070" />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1a1a24',
                        border: '1px solid #2a2a3a',
                        borderRadius: '6px',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="latency"
                      stroke="#6366f1"
                      strokeWidth={2}
                      dot={{ fill: '#6366f1' }}
                      name="Latency (ms)"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-8 flex flex-col items-center justify-center text-center">
                <Clock className="h-10 w-10 text-muted-foreground/50 mb-3" />
                <p className="text-sm text-muted-foreground">
                  No latency data available
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}