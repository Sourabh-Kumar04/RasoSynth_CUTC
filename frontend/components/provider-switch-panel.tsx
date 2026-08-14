'use client'

import { useState, useEffect } from 'react'
import {
  ArrowLeftRight,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Zap,
  Server,
  Clock,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  ProviderStatus,
  ProviderSwitchRequest,
  ProviderSwitchResponse,
  FailoverHistory,
  FailoverStats,
} from '@/lib/api/client'
import { clsx } from 'clsx'

interface ProviderSwitchPanelProps {
  jobId: string
  providers: ProviderStatus[]
  onSwitch: (request: ProviderSwitchRequest) => Promise<ProviderSwitchResponse>
  currentProvider?: string
  isLoading?: boolean
}

export function ProviderSwitchPanel({
  jobId,
  providers,
  onSwitch,
  currentProvider,
  isLoading = false,
}: ProviderSwitchPanelProps) {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null)
  const [switchResult, setSwitchResult] = useState<ProviderSwitchResponse | null>(null)
  const [isSwitching, setIsSwitching] = useState(false)
  const [createCheckpoint, setCreateCheckpoint] = useState(true)

  const handleSwitch = async () => {
    if (!selectedProvider) return

    setIsSwitching(true)
    try {
      const request: ProviderSwitchRequest = {
        job_id: jobId,
        new_provider: selectedProvider,
        create_checkpoint: createCheckpoint,
      }
      const result = await onSwitch(request)
      setSwitchResult(result)
    } catch (error) {
      console.error('Provider switch failed:', error)
      setSwitchResult({
        success: false,
        message: 'Failed to switch provider',
      })
    } finally {
      setIsSwitching(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Current Provider */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg flex items-center gap-2">
            <Server className="h-5 w-5" />
            Provider Switching
          </CardTitle>
          <CardDescription>Hot-switch to a different provider during execution</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-4">
            <div>
              <div className="text-sm text-muted-foreground">Current Provider</div>
              <div className="font-medium">{currentProvider || 'None'}</div>
            </div>
            <ArrowLeftRight className="h-5 w-5 text-muted-foreground" />
            <div>
              <div className="text-sm text-muted-foreground">Target Provider</div>
              <div className="font-medium">{selectedProvider || 'Select below'}</div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={createCheckpoint}
                onChange={(e) => setCreateCheckpoint(e.target.checked)}
                className="rounded border-input"
              />
              Create checkpoint before switch
            </label>
            <Button
              variant="default"
              onClick={handleSwitch}
              disabled={!selectedProvider || isSwitching}
            >
              {isSwitching ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <ArrowLeftRight className="h-4 w-4 mr-2" />
              )}
              Switch Provider
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Switch Result */}
      {switchResult && (
        <Card className={switchResult.success ? 'border-green-500' : 'border-red-500'}>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              {switchResult.success ? (
                <CheckCircle2 className="h-5 w-5 text-green-500" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500" />
              )}
              <span className={switchResult.success ? 'text-green-500' : 'text-red-500'}>
                {switchResult.message}
              </span>
            </div>
            {switchResult.success && (
              <div className="mt-2 text-sm text-muted-foreground">
                {switchResult.from_provider && (
                  <span>From: {switchResult.from_provider}</span>
                )}
                {switchResult.from_provider && switchResult.to_provider && <span> → </span>}
                {switchResult.to_provider && (
                  <span>To: {switchResult.to_provider}</span>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Available Providers */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Available Providers
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {providers.map((provider) => (
                <div
                  key={provider.name}
                  className={clsx(
                    'flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors',
                    selectedProvider === provider.name
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:bg-muted/50',
                    provider.name === currentProvider && 'opacity-50'
                  )}
                  onClick={() => setSelectedProvider(provider.name)}
                >
                  <div className={clsx(
                    'w-2 h-2 rounded-full',
                    provider.status === 'available' ? 'bg-green-500' : 'bg-yellow-500'
                  )} />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm">{provider.name}</div>
                    {provider.latency_ms && (
                      <div className="text-xs text-muted-foreground">
                        {provider.latency_ms}ms
                      </div>
                    )}
                  </div>
                  {provider.name === currentProvider && (
                    <Badge variant="secondary" className="text-xs">Current</Badge>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

interface FailoverHistoryPanelProps {
  history: FailoverHistory
  stats: FailoverStats | null
  isLoading?: boolean
}

export function FailoverHistoryPanel({ history, stats, isLoading = false }: FailoverHistoryPanelProps) {
  return (
    <div className="space-y-4">
      {/* Stats */}
      {stats && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Failover Statistics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold">{stats.total_migrations}</div>
                <div className="text-xs text-muted-foreground">Total Migrations</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">
                  {Object.keys(stats.circuit_breakers).length}
                </div>
                <div className="text-xs text-muted-foreground">Circuit Breakers</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold">
                  {Object.values(stats.failure_stats).reduce((sum, v) => sum + (v.total || 0), 0)}
                </div>
                <div className="text-xs text-muted-foreground">Total Failures</div>
              </div>
            </div>

            {/* Failure breakdown */}
            <div className="mt-4">
              <div className="text-sm font-medium mb-2">Failure Breakdown</div>
              <div className="space-y-1">
                {Object.entries(stats.failure_stats).map(([provider, failures]) => (
                  <div key={provider} className="flex items-center gap-2 text-sm">
                    <span className="font-medium">{provider}</span>
                    <Badge variant="outline" className="text-xs">
                      {failures.rate_limit || 0} rate limit
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {failures.quota || 0} quota
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {failures.latency || 0} latency
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Migration History */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Migration History
          </CardTitle>
          <CardDescription>{history.total_count} total migrations</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : history.migrations.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No migrations recorded yet
            </div>
          ) : (
            <ScrollArea className="h-[300px]">
              <div className="space-y-2">
                {history.migrations.map((migration) => (
                  <div
                    key={migration.migration_id}
                    className="flex items-center gap-3 p-3 rounded-lg border border-border"
                  >
                    <div className={clsx(
                      'w-2 h-2 rounded-full',
                      migration.success ? 'bg-green-500' : 'bg-red-500'
                    )} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{migration.from_provider}</span>
                        <ArrowLeftRight className="h-3 w-3 text-muted-foreground" />
                        <span className="font-medium text-sm">{migration.to_provider}</span>
                        {migration.failure_type && (
                          <Badge variant="outline" className="text-xs">
                            {migration.failure_type}
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        Job: {migration.job_id} • {new Date(migration.timestamp).toLocaleString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  )
}