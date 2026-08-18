'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Beaker, TrendingUp, Clock, CheckCircle2, AlertCircle,
  RefreshCw, Loader2, BookOpen, Sparkles, Target, Play,
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

interface Techniques {
  techniques?: Record<string, any>
}

export default function ResearchPage() {
  const [status, setStatus] = useState<ResearchStatus | null>(null)
  const [techniques, setTechniques] = useState<Techniques | null>(null)
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3000)
  }

  const fetchAll = useCallback(async () => {
    setError(null)
    try {
      const [s, t] = await Promise.all([
        api.getResearchStatus().catch(() => null),
        api.getProviderTechniques().catch(() => null),
      ])
      setStatus(s)
      setTechniques(t)
    } catch (e: any) {
      setError(e?.message ?? 'Failed to load research data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchAll() }, [fetchAll])
  useEffect(() => {
    const id = setInterval(fetchAll, 60000)
    return () => clearInterval(id)
  }, [fetchAll])

  const handleTrigger = async () => {
    setTriggering(true)
    try {
      await api.triggerResearch({})
      showToast('Research cycle started')
      await fetchAll()
    } catch (e: any) {
      showToast(e?.message ?? 'Failed to start research', false)
    } finally {
      setTriggering(false)
    }
  }

  const cachedTechniques = status?.cached_techniques ?? []
  const history = status?.research_history ?? []
  const techEntries = Object.entries(techniques?.techniques ?? {})

  return (
    <div className="space-y-5 animate-fade-in">

      {/* Toast */}
      {toast && (
        <div className={clsx(
          'fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-medium animate-slide-in',
          toast.ok ? 'bg-green-950/95 border-green-600/40 text-green-200'
                   : 'bg-red-950/95 border-red-600/40 text-red-200',
        )}>
          {toast.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertCircle className="h-3.5 w-3.5" />}
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold flex items-center gap-2">
            <Beaker className="h-5 w-5 text-orange-400" />Research & Optimization
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            Autonomous technique discovery and prompt optimization
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleTrigger} disabled={triggering}>
            {triggering ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : <Play className="h-3.5 w-3.5 mr-1" />}
            {triggering ? 'Running…' : 'Run Research'}
          </Button>
          <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading}>
            <RefreshCw className={clsx('h-3.5 w-3.5 mr-1', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <Card className="border-red-500/30 bg-red-500/5">
          <CardContent className="p-3 flex items-center gap-3 text-sm text-red-400">
            <AlertCircle className="h-4 w-4 shrink-0" />{error}
            <Button variant="ghost" size="sm" className="ml-auto h-7" onClick={fetchAll}>Retry</Button>
          </CardContent>
        </Card>
      )}

      {/* Stat cards */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Card className="bg-surface/40 border-border">
            <CardContent className="pt-3 pb-3 px-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Status</p>
                <p className={clsx('text-xl font-bold capitalize mt-0.5',
                  status?.status === 'running' ? 'text-blue-400' :
                  status?.status === 'idle' ? 'text-green-400' : 'text-muted-foreground',
                )}>
                  {status?.status ?? 'unavailable'}
                </p>
              </div>
              <div className="h-9 w-9 rounded-lg bg-orange-500/10 flex items-center justify-center">
                {status?.status === 'running'
                  ? <Loader2 className="h-4.5 w-4.5 text-orange-400 animate-spin" />
                  : <Beaker className="h-4.5 w-4.5 text-orange-400" />}
              </div>
            </CardContent>
          </Card>
          <Card className="bg-surface/40 border-border">
            <CardContent className="pt-3 pb-3 px-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Last Run</p>
                <p className="text-lg font-bold mt-0.5">
                  {status?.last_research
                    ? new Date(status.last_research).toLocaleDateString()
                    : 'Never'}
                </p>
              </div>
              <div className="h-9 w-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                <Clock className="h-4.5 w-4.5 text-blue-400" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-surface/40 border-border">
            <CardContent className="pt-3 pb-3 px-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Techniques</p>
                <p className="text-xl font-bold mt-0.5">{cachedTechniques.length + techEntries.length}</p>
              </div>
              <div className="h-9 w-9 rounded-lg bg-green-500/10 flex items-center justify-center">
                <Target className="h-4.5 w-4.5 text-green-400" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading research data…
        </div>
      ) : (
        <Tabs defaultValue="overview">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="techniques">Techniques ({cachedTechniques.length + techEntries.length})</TabsTrigger>
            <TabsTrigger value="history">History ({history.length})</TabsTrigger>
          </TabsList>

          {/* Overview */}
          <TabsContent value="overview" className="mt-4 space-y-3">
            <Card className="bg-surface/40 border-border">
              <CardContent className="p-0 divide-y divide-border/50">
                {[
                  {
                    icon: Beaker, label: 'Autonomous Research Loop',
                    desc: 'Continuously discovers and applies new optimization techniques',
                    badge: status?.enabled ? 'Enabled' : 'Disabled',
                    ok: !!status?.enabled,
                  },
                  {
                    icon: TrendingUp, label: 'Technique Discovery',
                    desc: 'Finds optimal provider configurations through experimentation',
                    badge: `${cachedTechniques.length} cached`,
                    ok: cachedTechniques.length > 0,
                  },
                  {
                    icon: BookOpen, label: 'Research History',
                    desc: 'Tracks previous research cycles and their outcomes',
                    badge: `${history.length} cycles`,
                    ok: history.length > 0,
                  },
                ].map(({ icon: Icon, label, desc, badge, ok }) => (
                  <div key={label} className="flex items-center justify-between px-4 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className={clsx('h-8 w-8 rounded-lg flex items-center justify-center',
                        ok ? 'bg-green-500/10' : 'bg-surface')}>
                        <Icon className={clsx('h-4 w-4', ok ? 'text-green-400' : 'text-muted-foreground')} />
                      </div>
                      <div>
                        <p className="text-sm font-medium">{label}</p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </div>
                    </div>
                    <span className={clsx(
                      'text-xs px-2 py-0.5 rounded-full border font-medium',
                      ok ? 'bg-green-500/15 text-green-300 border-green-500/30'
                         : 'bg-surface text-muted-foreground border-border',
                    )}>{badge}</span>
                  </div>
                ))}
              </CardContent>
            </Card>

            {!status && !error && (
              <Card className="bg-surface/40 border-border">
                <CardContent className="py-10 flex flex-col items-center gap-3 text-muted-foreground">
                  <Beaker className="h-8 w-8 opacity-30" />
                  <p className="text-sm">Research system not yet active. Run a dataset job to initialise it.</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Techniques */}
          <TabsContent value="techniques" className="mt-4">
            <Card className="bg-surface/40 border-border">
              <CardContent className="p-0">
                {cachedTechniques.length === 0 && techEntries.length === 0 ? (
                  <div className="py-12 flex flex-col items-center gap-3 text-muted-foreground">
                    <Target className="h-8 w-8 opacity-30" />
                    <p className="text-sm">No techniques discovered yet — click Run Research</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border/50">
                    {cachedTechniques.map((t, i) => (
                      <div key={i} className="flex items-center justify-between px-4 py-3">
                        <div className="flex items-center gap-2.5">
                          <Sparkles className="h-3.5 w-3.5 text-orange-400 shrink-0" />
                          <span className="text-sm font-mono">{t}</span>
                        </div>
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
                      </div>
                    ))}
                    {techEntries.map(([name, data]) => (
                      <div key={name} className="flex items-start justify-between px-4 py-3 gap-3">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <Sparkles className="h-3.5 w-3.5 text-blue-400 shrink-0" />
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">{name.replace(/_/g, ' ')}</p>
                            {typeof data === 'object' && data?.description && (
                              <p className="text-xs text-muted-foreground truncate">{data.description}</p>
                            )}
                          </div>
                        </div>
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0 mt-0.5" />
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* History */}
          <TabsContent value="history" className="mt-4">
            <Card className="bg-surface/40 border-border">
              <CardContent className="p-0">
                {history.length === 0 ? (
                  <div className="py-12 flex flex-col items-center gap-3 text-muted-foreground">
                    <Clock className="h-8 w-8 opacity-30" />
                    <p className="text-sm">No research history yet</p>
                  </div>
                ) : (
                  <div className="divide-y divide-border/50">
                    {history.map((entry, i) => (
                      <div key={i} className="flex items-center gap-3 px-4 py-3">
                        <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                        <span className="text-sm">{entry}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
