'use client'

import { useState, useEffect } from 'react'
import { api, HealthStatus, ProviderMetrics } from '@/lib/api/client'
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock,
  Database,
  Server,
  Shield,
  Zap,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface ProviderHealthProps {
  className?: string
}

export function HealthMonitor({ className }: ProviderHealthProps) {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null)
  const [metrics, setMetrics] = useState<Record<string, ProviderMetrics>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchHealth() {
      try {
        const [readyData, metricsData] = await Promise.all([
          api.getHealthReady().catch(() => null),
          api.getProviderHealthMetrics().catch(() => ({ metrics: {} }))
        ])

        setHealthStatus(readyData)
        setMetrics(metricsData?.metrics || {})
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch health')
      } finally {
        setLoading(false)
      }
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 30000) // Poll every 30s
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <Card className={className}>
        <CardContent className="p-6">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 animate-spin" />
            <span>Loading health status...</span>
          </div>
        </CardContent>
      </Card>
    )
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-500'
      case 'degraded': return 'bg-yellow-500'
      case 'unhealthy': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle2 className="h-4 w-4 text-green-500" />
      case 'degraded': return <AlertCircle className="h-4 w-4 text-yellow-500" />
      case 'unhealthy': return <AlertCircle className="h-4 w-4 text-red-500" />
      default: return <Clock className="h-4 w-4 text-gray-500" />
    }
  }

  const getCircuitBreakerColor = (state: string) => {
    switch (state) {
      case 'closed': return 'bg-green-500'
      case 'open': return 'bg-red-500'
      case 'half-open': return 'bg-yellow-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Activity className="h-5 w-5" />
          System Health
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="overview">
          <TabsList className="w-full">
            <TabsTrigger value="overview" className="flex-1">Overview</TabsTrigger>
            <TabsTrigger value="providers" className="flex-1">Providers</TabsTrigger>
            <TabsTrigger value="circuit" className="flex-1">Circuit Breakers</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4">
            <div className="space-y-4">
              {/* Overall Status */}
              <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
                <div className="flex items-center gap-2">
                  {getStatusIcon(healthStatus?.status || 'unknown')}
                  <span className="font-medium">Overall Status</span>
                </div>
                <Badge variant={healthStatus?.status === 'healthy' ? 'default' : 'destructive'}>
                  {healthStatus?.status || 'unknown'}
                </Badge>
              </div>

              {/* Infrastructure */}
              <div className="grid grid-cols-2 gap-3">
                <div className="flex items-center gap-2 p-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">Database</span>
                  {healthStatus?.database ? (
                    <CheckCircle2 className="h-3 w-3 text-green-500 ml-auto" />
                  ) : (
                    <AlertCircle className="h-3 w-3 text-red-500 ml-auto" />
                  )}
                </div>
                <div className="flex items-center gap-2 p-2">
                  <Server className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">Redis</span>
                  {healthStatus?.redis ? (
                    <CheckCircle2 className="h-3 w-3 text-green-500 ml-auto" />
                  ) : (
                    <AlertCircle className="h-3 w-3 text-red-500 ml-auto" />
                  )}
                </div>
              </div>

              {/* Active Providers */}
              <div>
                <h4 className="text-sm font-medium mb-2">Active Providers</h4>
                <div className="flex flex-wrap gap-2">
                  {healthStatus?.providers && Object.entries(healthStatus.providers).map(([name, info]) => (
                    <Badge key={name} variant="outline" className="gap-1">
                      <span className={`h-2 w-2 rounded-full ${getStatusColor(info.status)}`} />
                      {name}
                    </Badge>
                  ))}
                  {!healthStatus?.providers && (
                    <span className="text-sm text-muted-foreground">No provider data</span>
                  )}
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="providers" className="mt-4">
            <div className="space-y-3">
              {Object.entries(metrics).map(([provider, data]) => (
                <div key={provider} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium">{provider}</span>
                    <Badge variant={data.success_rate > 0.9 ? 'default' : 'destructive'}>
                      {Math.round(data.success_rate * 100)}% success
                    </Badge>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-sm">
                    <div>
                      <span className="text-muted-foreground">Requests</span>
                      <p className="font-medium">{data.total_requests}</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Avg Latency</span>
                      <p className="font-medium">{data.avg_latency_ms.toFixed(0)}ms</p>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Fallbacks</span>
                      <p className="font-medium">{data.fallback_count}</p>
                    </div>
                  </div>
                </div>
              ))}

              {Object.keys(metrics).length === 0 && (
                <p className="text-center text-muted-foreground py-4">No provider metrics available</p>
              )}
            </div>
          </TabsContent>

          <TabsContent value="circuit" className="mt-4">
            <div className="space-y-3">
              {healthStatus?.circuit_breakers && Object.entries(healthStatus.circuit_breakers).map(([provider, state]) => (
                <div key={provider} className="flex items-center justify-between p-3 border rounded-lg">
                  <div className="flex items-center gap-2">
                    <Shield className="h-4 w-4" />
                    <span className="font-medium">{provider}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`h-3 w-3 rounded-full ${getCircuitBreakerColor(state)}`} />
                    <span className="text-sm capitalize">{state}</span>
                  </div>
                </div>
              ))}

              {(!healthStatus?.circuit_breakers || Object.keys(healthStatus.circuit_breakers).length === 0) && (
                <p className="text-center text-muted-foreground py-4">All circuit breakers closed</p>
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

export function ProviderHealthBadge({ status }: { status: string }) {
  const colors = {
    healthy: 'bg-green-500',
    degraded: 'bg-yellow-500',
    unhealthy: 'bg-red-500',
    unknown: 'bg-gray-500',
  }

  return (
    <span className={`inline-flex h-2 w-2 rounded-full ${colors[status as keyof typeof colors] || colors.unknown}`} />
  )
}