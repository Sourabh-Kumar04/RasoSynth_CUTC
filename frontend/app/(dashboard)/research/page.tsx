'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Beaker,
  TrendingUp,
  Clock,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Loader2,
  BookOpen,
  Sparkles,
  Target,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { api } from '@/lib/api/client'

interface ResearchStatus {
  enabled?: boolean
  last_research?: string
  research_history?: string[]
  cached_techniques?: string[]
  status?: string
}

export default function ResearchPage() {
  const [researchStatus, setResearchStatus] = useState<ResearchStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [activeTab, setActiveTab] = useState('status')

  const fetchResearchStatus = useCallback(async () => {
    try {
      setError(null)
      const data = await api.getResearchStatus().catch(() => null)
      setResearchStatus(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load research status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchResearchStatus()
    const interval = setInterval(fetchResearchStatus, 60000) // Poll every minute
    return () => clearInterval(interval)
  }, [fetchResearchStatus])

  const handleTriggerResearch = async () => {
    setTriggering(true)
    try {
      await api.triggerResearch({})
      await fetchResearchStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger research')
    } finally {
      setTriggering(false)
    }
  }

  // Empty state when research is disabled or not available
  if (!loading && !researchStatus?.enabled && researchStatus?.status === 'disabled') {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Research & Optimization</h1>
            <p className="text-sm text-muted-foreground">
              Autonomous research and technique optimization
            </p>
          </div>
        </div>
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Beaker className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">Research System Disabled</h3>
            <p className="text-sm text-muted-foreground mb-4 text-center max-w-md">
              The autonomous research loop is currently disabled. Enable it in your configuration to allow the system to discover and apply new techniques.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Empty state when no research data
  if (!loading && !researchStatus) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">Research & Optimization</h1>
            <p className="text-sm text-muted-foreground">
              Autonomous research and technique optimization
            </p>
          </div>
        </div>
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Beaker className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">No Research Data</h3>
            <p className="text-sm text-muted-foreground mb-4 text-center max-w-md">
              Run a dataset generation job to enable research and optimization features.
            </p>
            <Button variant="outline" onClick={fetchResearchStatus}>
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
          <h1 className="text-2xl font-semibold">Research & Optimization</h1>
          <p className="text-sm text-muted-foreground">
            Autonomous research and technique optimization
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={handleTriggerResearch}
            disabled={triggering}
          >
            {triggering ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {triggering ? 'Running...' : 'Run Research'}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={fetchResearchStatus}
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
            <AlertCircle className="h-5 w-5 text-destructive" />
            <div className="flex-1">
              <p className="text-sm font-medium">Error</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={fetchResearchStatus}>
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
            <p className="text-sm text-muted-foreground">Loading research status...</p>
          </CardContent>
        </Card>
      )}

      {/* Research Status Cards */}
      {!loading && researchStatus && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Status</p>
                    <p className="text-2xl font-semibold capitalize">
                      {researchStatus.status || 'idle'}
                    </p>
                  </div>
                  <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center">
                    {researchStatus.status === 'running' ? (
                      <Loader2 className="h-5 w-5 text-accent animate-spin" />
                    ) : (
                      <Beaker className="h-5 w-5 text-accent" />
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Last Research</p>
                    <p className="text-2xl font-semibold">
                      {researchStatus.last_research
                        ? new Date(researchStatus.last_research).toLocaleDateString()
                        : 'Never'}
                    </p>
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
                    <p className="text-xs text-muted-foreground">Cached Techniques</p>
                    <p className="text-2xl font-semibold">
                      {researchStatus.cached_techniques?.length || 0}
                    </p>
                  </div>
                  <div className="h-10 w-10 rounded-lg bg-success/10 flex items-center justify-center">
                    <Target className="h-5 w-5 text-success" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="status">Status</TabsTrigger>
              <TabsTrigger value="techniques">Techniques</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>

            {/* Status Tab */}
            <TabsContent value="status" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Research System Overview</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-4 rounded-lg bg-surface/50">
                      <div className="flex items-center gap-3">
                        <Beaker className="h-5 w-5 text-accent" />
                        <div>
                          <p className="font-medium">Autonomous Research Loop</p>
                          <p className="text-xs text-muted-foreground">
                            Continuously discovers and applies new optimization techniques
                          </p>
                        </div>
                      </div>
                      <Badge variant={researchStatus.enabled ? 'success' : 'secondary'}>
                        {researchStatus.enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between p-4 rounded-lg bg-surface/50">
                      <div className="flex items-center gap-3">
                        <TrendingUp className="h-5 w-5 text-success" />
                        <div>
                          <p className="font-medium">Technique Discovery</p>
                          <p className="text-xs text-muted-foreground">
                            Finds optimal provider configurations through experimentation
                          </p>
                        </div>
                      </div>
                      <Badge variant="outline">
                        {researchStatus.cached_techniques?.length || 0} techniques
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between p-4 rounded-lg bg-surface/50">
                      <div className="flex items-center gap-3">
                        <BookOpen className="h-5 w-5 text-info" />
                        <div>
                          <p className="font-medium">Research History</p>
                          <p className="text-xs text-muted-foreground">
                            Tracks previous research cycles and their outcomes
                          </p>
                        </div>
                      </div>
                      <Badge variant="outline">
                        {researchStatus.research_history?.length || 0} cycles
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Techniques Tab */}
            <TabsContent value="techniques" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Cached Techniques</CardTitle>
                </CardHeader>
                <CardContent>
                  {researchStatus.cached_techniques && researchStatus.cached_techniques.length > 0 ? (
                    <div className="space-y-2">
                      {researchStatus.cached_techniques.map((technique, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-3 rounded-lg bg-surface/50"
                        >
                          <div className="flex items-center gap-3">
                            <Sparkles className="h-4 w-4 text-accent" />
                            <span className="font-mono text-sm">{technique}</span>
                          </div>
                          <CheckCircle2 className="h-4 w-4 text-success" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-8 text-center text-muted-foreground">
                      <Target className="h-10 w-10 mx-auto mb-3 text-muted-foreground/50" />
                      <p>No techniques discovered yet</p>
                      <p className="text-xs mt-1">Run research to discover optimization techniques</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* History Tab */}
            <TabsContent value="history" className="mt-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Research History</CardTitle>
                </CardHeader>
                <CardContent>
                  {researchStatus.research_history && researchStatus.research_history.length > 0 ? (
                    <div className="space-y-2">
                      {researchStatus.research_history.map((entry, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between p-3 rounded-lg bg-surface/50"
                        >
                          <div className="flex items-center gap-3">
                            <Clock className="h-4 w-4 text-muted-foreground" />
                            <span className="text-sm">{entry}</span>
                          </div>
                          <CheckCircle2 className="h-4 w-4 text-success" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-8 text-center text-muted-foreground">
                      <Clock className="h-10 w-10 mx-auto mb-3 text-muted-foreground/50" />
                      <p>No research history yet</p>
                      <p className="text-xs mt-1">Run research to start building history</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  )
}