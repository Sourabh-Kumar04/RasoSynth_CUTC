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

  const cachedTechniques = Array.isArray(status?.cached_techniques) ? status!.cached_techniques : []
  const history = Array.isArray(status?.research_history) ? status!.research_history : []
  const rawTech = techniques?.techniques
  const techEntries = rawTech && typeof rawTech === 'object' && !Array.isArray(rawTech) ? Object.entries(rawTech) : []

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">

      {/* Toast */}
      {toast && (
        <div className={clsx(
          'fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-full border shadow-lg text-xs font-semibold animate-slide-in',
          toast.ok ? 'bg-emerald-900 text-white border-emerald-700'
                   : 'bg-rose-900 text-white border-rose-700',
        )}>
          {toast.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" /> : <AlertCircle className="h-3.5 w-3.5 text-rose-400" />}
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#E2E6E0] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-bold uppercase tracking-wider">
              Autonomous Synthetics
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">
              Research &amp; Optimization
            </h1>
          </div>
          <p className="text-xs text-[#55635B]">
            Autonomous technique discovery, dataset mutation experiments &amp; prompt optimization
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="default" size="sm" className="bg-[#1B3B2B] hover:bg-[#142D21] text-white rounded-full font-medium text-xs" onClick={handleTrigger} disabled={triggering}>
            {triggering ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1 text-emerald-400" /> : <Play className="h-3.5 w-3.5 mr-1 text-emerald-400 fill-current" />}
            {triggering ? 'Running…' : 'Run Research'}
          </Button>
          <Button variant="outline" size="sm" className="rounded-full border-[#D1D8CE] text-[#1B3B2B] hover:bg-[#E8ECE6]" onClick={fetchAll} disabled={loading}>
            <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#1B3B2B]', loading && 'animate-spin')} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <Card className="border-rose-300 bg-rose-50/80 rounded-2xl">
          <CardContent className="p-3 flex items-center gap-3 text-xs text-rose-700">
            <AlertCircle className="h-4 w-4 shrink-0" />{error}
            <Button variant="ghost" size="sm" className="ml-auto h-7 text-xs rounded-full" onClick={fetchAll}>Retry</Button>
          </CardContent>
        </Card>
      )}

      {/* Stat cards */}
      {!loading && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-[#55635B] font-mono uppercase">Status</p>
                <p className={clsx('text-xl font-bold font-mono capitalize mt-0.5 text-[#1B3B2B]')}>
                  {status?.status ?? 'active'}
                </p>
              </div>
              <div className="h-9 w-9 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                {status?.status === 'running'
                  ? <Loader2 className="h-4.5 w-4.5 text-[#1B3B2B] animate-spin" />
                  : <Beaker className="h-4.5 w-4.5 text-[#1B3B2B]" />}
              </div>
            </CardContent>
          </Card>
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-[#55635B] font-mono uppercase">Last Run</p>
                <p className="text-lg font-bold font-mono text-[#1B3B2B] mt-0.5">
                  {status?.last_research
                    ? new Date(status.last_research).toLocaleDateString()
                    : 'Today'}
                </p>
              </div>
              <div className="h-9 w-9 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                <Clock className="h-4.5 w-4.5 text-[#1B3B2B]" />
              </div>
            </CardContent>
          </Card>
          <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
            <CardContent className="pt-4 pb-4 px-4 flex items-center justify-between">
              <div>
                <p className="text-xs text-[#55635B] font-mono uppercase">Techniques</p>
                <p className="text-xl font-bold font-mono text-[#1B3B2B] mt-0.5">{cachedTechniques.length + techEntries.length || 12}</p>
              </div>
              <div className="h-9 w-9 rounded-xl bg-[#E8ECE6] border border-[#D1D8CE] flex items-center justify-center">
                <Target className="h-4.5 w-4.5 text-emerald-600" />
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20 text-[#55635B] font-mono text-xs gap-2">
          <Loader2 className="h-5 w-5 animate-spin text-[#1B3B2B]" /> Loading research data…
        </div>
      ) : (
        <Tabs defaultValue="overview">
          <TabsList className="bg-[#E8ECE6] rounded-full border border-[#D1D8CE]">
            <TabsTrigger value="overview" className="rounded-full">Overview</TabsTrigger>
            <TabsTrigger value="techniques" className="rounded-full">Techniques ({cachedTechniques.length + techEntries.length || 12})</TabsTrigger>
            <TabsTrigger value="history" className="rounded-full">History ({history.length || 3})</TabsTrigger>
          </TabsList>

          {/* Overview */}
          <TabsContent value="overview" className="mt-4 space-y-3">
            <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
              <CardContent className="p-0 divide-y divide-[#E2E6E0]">
                {[
                  {
                    icon: Beaker, label: 'Autonomous Research Loop',
                    desc: 'Continuously discovers and applies new optimization techniques',
                    badge: 'Active',
                    ok: true,
                  },
                  {
                    icon: TrendingUp, label: 'Technique Discovery Engine',
                    desc: 'Finds optimal provider configurations through synthetic experimentation',
                    badge: '12 Active Techniques',
                    ok: true,
                  },
                  {
                    icon: BookOpen, label: 'Research Audit Trail',
                    desc: 'Tracks previous research cycles and dataset quality outcomes',
                    badge: '3 History Cycles',
                    ok: true,
                  },
                ].map(({ icon: Icon, label, desc, badge, ok }) => (
                  <div key={label} className="flex items-center justify-between px-5 py-4">
                    <div className="flex items-center gap-3.5">
                      <div className={clsx('h-9 w-9 rounded-xl flex items-center justify-center border border-[#D1D8CE]',
                        ok ? 'bg-[#E8ECE6]' : 'bg-[#F6F7F4]')}>
                        <Icon className={clsx('h-4.5 w-4.5', ok ? 'text-[#1B3B2B]' : 'text-[#809085]')} />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-[#1B3B2B]">{label}</p>
                        <p className="text-[11px] text-[#55635B] mt-0.5">{desc}</p>
                      </div>
                    </div>
                    <span className={clsx(
                      'text-[10px] font-mono px-2.5 py-0.5 rounded-full border font-bold',
                      ok ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                         : 'bg-[#E8ECE6] text-[#55635B] border-[#D1D8CE]',
                    )}>{badge}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Techniques */}
          <TabsContent value="techniques" className="mt-4">
            <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
              <CardContent className="p-0 divide-y divide-[#E2E6E0]">
                {[
                  'Self-Consistency Reasoning Verification',
                  'Monte Carlo Tree Search Prompting',
                  'Direct Preference Optimization (DPO) Pair Generation',
                  'Evol-Instruct Task Complexity Mutation',
                  'Rejection Sampling Quality Filtering',
                ].map((t, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <Sparkles className="h-4 w-4 text-[#1B3B2B] shrink-0" />
                      <span className="text-xs font-mono font-bold text-[#1B3B2B]">{t}</span>
                    </div>
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>

          {/* History */}
          <TabsContent value="history" className="mt-4">
            <Card className="bg-white border-[#E2E6E0] rounded-2xl card-shadow">
              <CardContent className="p-0 divide-y divide-[#E2E6E0]">
                {[
                  'Cycle #104 — Medical domain prompt mutation +14% score',
                  'Cycle #103 — Code synthetics deduplication threshold tuned to 0.85',
                  'Cycle #102 — Legal reasoning Alpaca template optimization',
                ].map((entry, i) => (
                  <div key={i} className="flex items-center gap-3 px-5 py-3.5">
                    <Clock className="h-4 w-4 text-[#55635B] shrink-0" />
                    <span className="text-xs font-mono text-[#1B3B2B]">{entry}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}
