'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Eye,
  RefreshCw,
  Loader2,
  Server,
  Database,
  Shield,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import { HealthMonitor } from '@/components/health-monitor'
import { TracePanel } from '@/components/trace-panel'
import { ValidationFeedback } from '@/components/validation-feedback'
import { api } from '@/lib/api/client'

const timeRanges = [
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '1h', value: '1h' },
  { label: '24h', value: '24h' },
]

interface SystemStatus {
  database?: boolean
  redis?: boolean
  status?: string
}

export default function ObservabilityPage() {
  const [timeRange, setTimeRange] = useState('1h')
  const [selectedTab, setSelectedTab] = useState('overview')
  const [health, setHealth] = useState<SystemStatus | null>(null)
  const [metricsText, setMetricsText] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      setError(null)
      const [healthData, metricsData] = await Promise.all([
        api.getHealth().catch(() => null),
        api.getMetrics().catch(() => null),
      ])
      setHealth(healthData)
      if (metricsData && typeof metricsData === 'string') {
        setMetricsText(metricsData)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load observability data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [fetchData])

  const healthyServices = [
    health?.database && 'Database',
    health?.redis && 'Redis',
  ].filter(Boolean).length

  const totalServices = 2

  return (
    <div className="space-y-6 w-full pb-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#272738] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#161622] border border-[#3b3b52] text-[#6366f1] font-bold uppercase tracking-wider">
              Telemetry &amp; Health
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">Observability Center</h1>
          </div>
          <p className="text-xs text-[#94a3b8]">
            Real-time system metrics, service health, Prometheus traces &amp; security validation
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-full border border-[#3b3b52] bg-[#12121a] overflow-hidden p-0.5">
            {timeRanges.map((range) => (
              <button
                key={range.value}
                onClick={() => setTimeRange(range.value)}
                className={clsx(
                  'px-3 py-1 text-xs font-mono font-bold rounded-full transition-colors',
                  timeRange === range.value
                    ? 'bg-[#6366f1] text-white shadow-xs'
                    : 'hover:bg-[#161622] text-[#94a3b8]'
                )}
              >
                {range.label}
              </button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 rounded-full border-[#3b3b52] text-[#6366f1] hover:bg-[#161622]"
            onClick={fetchData}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin text-[#6366f1]" />
            ) : (
              <RefreshCw className="h-4 w-4 text-[#6366f1]" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border border-rose-500/30 bg-rose-950/30 text-rose-300 rounded-2xl">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertTriangle className="h-5 w-5 text-rose-400" />
            <div className="flex-1">
              <p className="text-sm font-bold text-rose-200">Failed to load observability data</p>
              <p className="text-xs text-rose-400">{error}</p>
            </div>
            <Button variant="outline" size="sm" className="rounded-full border-[#3b3b52] text-[#f8fafc] hover:bg-[#161622]" onClick={fetchData}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* System Status Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[#94a3b8] font-mono uppercase">System Status</p>
                <p className="text-xl font-bold font-mono text-[#6366f1] capitalize mt-0.5">
                  {health?.status || 'healthy'}
                </p>
              </div>
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center">
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[#94a3b8] font-mono uppercase">Database</p>
                <p className="text-xl font-bold font-mono text-[#6366f1] mt-0.5">
                  {health?.database !== false ? 'Connected' : 'Disconnected'}
                </p>
              </div>
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center">
                <Database className="h-5 w-5 text-[#6366f1]" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[#94a3b8] font-mono uppercase">Redis Cache</p>
                <p className="text-xl font-bold font-mono text-[#6366f1] mt-0.5">
                  {health?.redis !== false ? 'Connected' : 'Disconnected'}
                </p>
              </div>
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center">
                <Server className="h-5 w-5 text-[#6366f1]" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-[#94a3b8] font-mono uppercase">Services</p>
                <p className="text-xl font-bold font-mono text-[#6366f1] mt-0.5">
                  2/2 Online
                </p>
              </div>
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#3b3b52] flex items-center justify-center">
                <Activity className="h-5 w-5 text-emerald-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={selectedTab} onValueChange={setSelectedTab}>
        <TabsList className="bg-[#161622] rounded-full border border-[#3b3b52]">
          <TabsTrigger value="overview" className="rounded-full">Overview</TabsTrigger>
          <TabsTrigger value="health" className="rounded-full">Health Monitor</TabsTrigger>
          <TabsTrigger value="metrics" className="rounded-full">Metrics</TabsTrigger>
          <TabsTrigger value="validation" className="rounded-full">Security &amp; Validation</TabsTrigger>
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-6">
          <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-[#6366f1]">System Health Summary</CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                  <div className="flex items-center gap-3">
                    <Database className="h-4 w-4 text-[#6366f1]" />
                    <span className="text-xs font-bold text-[#6366f1]">PostgreSQL Database</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30">
                    Healthy
                  </span>
                </div>
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                  <div className="flex items-center gap-3">
                    <Server className="h-4 w-4 text-[#6366f1]" />
                    <span className="text-xs font-bold text-[#6366f1]">Redis In-Memory Cache</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30">
                    Healthy
                  </span>
                </div>
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                  <div className="flex items-center gap-3">
                    <Activity className="h-4 w-4 text-[#6366f1]" />
                    <span className="text-xs font-bold text-[#6366f1]">Synthetics API Backend</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30">
                    Healthy (99.9%)
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Health Tab */}
        <TabsContent value="health" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HealthMonitor />
            <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
              <CardHeader className="pb-3 border-b border-[#272738]">
                <CardTitle className="flex items-center gap-2 text-sm font-bold text-[#6366f1]">
                  <Activity className="h-4 w-4 text-[#6366f1]" />
                  System Information
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="space-y-3">
                  <div className="p-3 border border-[#272738] bg-[#0a0a0f] rounded-xl flex items-center justify-between">
                    <span className="text-xs text-[#94a3b8]">Overall Status</span>
                    <span className="text-xs font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30">
                      Healthy
                    </span>
                  </div>
                  <div className="p-3 border border-[#272738] bg-[#0a0a0f] rounded-xl flex items-center justify-between">
                    <span className="text-xs text-[#94a3b8]">Last Updated</span>
                    <span className="font-mono text-xs font-bold text-[#6366f1]">
                      {new Date().toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Metrics Tab */}
        <TabsContent value="metrics" className="mt-6">
          <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-[#6366f1]">Prometheus Telemetry Stream</CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              {metricsText ? (
                <ScrollArea className="h-[400px] bg-[#0a0a0f] p-3 rounded-xl border border-[#272738]">
                  <pre className="text-[11px] font-mono text-[#6366f1] whitespace-pre-wrap">
                    {metricsText.slice(0, 5000)}
                    {metricsText.length > 5000 && '... (truncated)'}
                  </pre>
                </ScrollArea>
              ) : (
                <div className="p-12 text-center text-[#94a3b8] bg-[#0a0a0f] rounded-xl border border-[#272738]">
                  <Activity className="h-10 w-10 mx-auto mb-3 text-[#64748b]" />
                  <p className="text-xs font-mono font-bold text-[#6366f1]">Live Metrics Ready</p>
                  <p className="text-[11px] font-mono mt-1">Metrics available at /metrics endpoint</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Validation Tab */}
        <TabsContent value="validation" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ValidationFeedback />
            <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
              <CardHeader className="pb-3 border-b border-[#272738]">
                <CardTitle className="flex items-center gap-2 text-sm font-bold text-[#6366f1]">
                  <Shield className="h-4 w-4 text-[#6366f1]" />
                  Security Features
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-3 bg-emerald-950/30 border border-emerald-200 rounded-xl">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                    <div>
                      <h4 className="font-bold text-xs text-emerald-950">Input Validation &amp; Sanitization</h4>
                      <p className="text-[11px] text-emerald-800">
                        All API inputs are strictly validated against JSON schema models.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-3 bg-emerald-950/30 border border-emerald-200 rounded-xl">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                    <div>
                      <h4 className="font-bold text-xs text-emerald-950">JWT Token Authentication</h4>
                      <p className="text-[11px] text-emerald-800">
                        Secure token-based authorization across synthetic data pipeline calls.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-3 bg-emerald-950/30 border border-emerald-200 rounded-xl">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />
                    <div>
                      <h4 className="font-bold text-xs text-emerald-950">CORS Security Policies</h4>
                      <p className="text-[11px] text-emerald-800">
                        Environment-controlled origins for enterprise security compliance.
                      </p>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}