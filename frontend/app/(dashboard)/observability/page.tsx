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
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
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
      // Metrics endpoint returns Prometheus format, store as text
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
    const interval = setInterval(fetchData, 30000) // Poll every 30s
    return () => clearInterval(interval)
  }, [fetchData])

  // Calculate some derived metrics from health
  const healthyServices = [
    health?.database && 'Database',
    health?.redis && 'Redis',
  ].filter(Boolean).length

  const totalServices = 2 // Database + Redis

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Observability</h1>
          <p className="text-sm text-muted-foreground">
            System metrics, traces, and monitoring
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-border overflow-hidden">
            {timeRanges.map((range) => (
              <button
                key={range.value}
                onClick={() => setTimeRange(range.value)}
                className={clsx(
                  'px-3 py-1.5 text-xs font-medium transition-colors',
                  timeRange === range.value
                    ? 'bg-accent text-white'
                    : 'hover:bg-surface-hover'
                )}
              >
                {range.label}
              </button>
            ))}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={fetchData}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
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
              <p className="text-sm font-medium">Failed to load observability data</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={fetchData}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* System Status Cards - Real data from health endpoint */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">System Status</p>
                <p className="text-2xl font-semibold capitalize">
                  {health?.status || 'unknown'}
                </p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center">
                {health?.status === 'healthy' ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : (
                  <AlertTriangle className="h-5 w-5 text-warning" />
                )}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Database</p>
                <p className="text-2xl font-semibold">
                  {health?.database ? 'Connected' : 'Disconnected'}
                </p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-success/10 flex items-center justify-center">
                <Database className="h-5 w-5 text-success" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Redis Cache</p>
                <p className="text-2xl font-semibold">
                  {health?.redis ? 'Connected' : 'Disconnected'}
                </p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-success/10 flex items-center justify-center">
                <Server className="h-5 w-5 text-success" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Services</p>
                <p className="text-2xl font-semibold">
                  {healthyServices}/{totalServices}
                </p>
              </div>
              <div className="h-10 w-10 rounded-lg bg-info/10 flex items-center justify-center">
                <Activity className="h-5 w-5 text-info" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={selectedTab} onValueChange={setSelectedTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="health">Health</TabsTrigger>
          <TabsTrigger value="metrics">Metrics</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-6">
          {!loading && health ? (
            <div className="grid grid-cols-12 gap-6">
              {/* System Status */}
              <Card className="col-span-6">
                <CardHeader>
                  <CardTitle className="text-sm">System Health</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between p-3 rounded bg-surface/50">
                      <div className="flex items-center gap-3">
                        <Database className="h-4 w-4 text-muted-foreground" />
                        <span>Database</span>
                      </div>
                      <Badge variant={health.database ? 'success' : 'destructive'}>
                        {health.database ? 'Healthy' : 'Down'}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded bg-surface/50">
                      <div className="flex items-center gap-3">
                        <Server className="h-4 w-4 text-muted-foreground" />
                        <span>Redis</span>
                      </div>
                      <Badge variant={health.redis ? 'success' : 'destructive'}>
                        {health.redis ? 'Healthy' : 'Down'}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Status Note */}
              <Card className="col-span-6">
                <CardHeader>
                  <CardTitle className="text-sm">About Observability</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3 text-sm text-muted-foreground">
                    <p>
                      This page shows real system health data from the /health endpoint.
                      Detailed metrics, traces, and logs require additional observability infrastructure.
                    </p>
                    <p>
                      The system provides Prometheus metrics at /metrics for integration
                      with external monitoring systems.
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : (
            <Card>
              <CardContent className="p-8 flex flex-col items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-accent mb-4" />
                <p className="text-sm text-muted-foreground">Loading system status...</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Health Tab */}
        <TabsContent value="health" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HealthMonitor />
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Activity className="h-5 w-5" />
                  System Information
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Overall Status</span>
                      <Badge variant={health?.status === 'healthy' ? 'success' : 'warning'}>
                        {health?.status || 'unknown'}
                      </Badge>
                    </div>
                  </div>
                  <div className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Last Updated</span>
                      <span className="font-mono text-sm">
                        {new Date().toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Metrics Tab */}
        <TabsContent value="metrics" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Prometheus Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              {metricsText ? (
                <ScrollArea className="h-[400px]">
                  <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap">
                    {metricsText.slice(0, 5000)}
                    {metricsText.length > 5000 && '... (truncated)'}
                  </pre>
                </ScrollArea>
              ) : (
                <div className="p-8 text-center text-muted-foreground">
                  <Activity className="h-10 w-10 mx-auto mb-3 text-muted-foreground/50" />
                  <p>No metrics available</p>
                  <p className="text-xs mt-1">Metrics available at /metrics endpoint</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Validation Tab */}
        <TabsContent value="validation" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ValidationFeedback />
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Shield className="h-5 w-5" />
                  Security Features
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-start gap-3 p-3 bg-success/10 border border-success/20 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-success mt-0.5" />
                    <div>
                      <h4 className="font-medium text-success">Input Validation</h4>
                      <p className="text-sm text-muted-foreground">
                        All API inputs are validated and sanitized
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-3 bg-success/10 border border-success/20 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-success mt-0.5" />
                    <div>
                      <h4 className="font-medium text-success">JWT Authentication</h4>
                      <p className="text-sm text-muted-foreground">
                        Secure token-based authentication
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-3 bg-success/10 border border-success/20 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-success mt-0.5" />
                    <div>
                      <h4 className="font-medium text-success">CORS Configuration</h4>
                      <p className="text-sm text-muted-foreground">
                        Environment-based origin control
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