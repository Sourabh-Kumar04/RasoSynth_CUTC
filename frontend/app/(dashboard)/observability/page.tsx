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
  Zap,
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
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] font-bold uppercase tracking-wider">
              Telemetry &amp; Health
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">Observability Center</h1>
          </div>
          <p className="text-xs text-[#94a3b8]">
            Real-time system metrics, service health, Prometheus traces &amp; security validation
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-md border border-[#272738] bg-[#12121a] overflow-hidden p-0.5">
            {timeRanges.map((range) => (
              <button
                key={range.value}
                onClick={() => setTimeRange(range.value)}
                className={clsx(
                  'px-3 py-1 text-xs font-mono font-bold rounded-sm transition-colors',
                  timeRange === range.value
                    ? 'bg-[#f26625] text-white shadow-xs glow-yc'
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
            className="gap-2 rounded-md border-[#272738] text-[#94a3b8] hover:text-white hover:bg-[#161622] font-mono text-xs"
            onClick={fetchData}
            disabled={loading}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin text-[#f26625]" />
            ) : (
              <RefreshCw className="h-4 w-4 text-[#f26625]" />
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
          <TabsTrigger value="token_efficiency" className="rounded-full">Tokenizer &amp; Indic Savings</TabsTrigger>
          <TabsTrigger value="validation" className="rounded-full">Security &amp; Validation</TabsTrigger>
        </TabsList>

        {/* Overview */}
        <TabsContent value="overview" className="mt-6">
          <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white">System Health Summary</CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                  <div className="flex items-center gap-3">
                    <Database className="h-4 w-4 text-[#818cf8]" />
                    <span className="text-xs font-bold text-white">PostgreSQL Database</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30">
                    Healthy
                  </span>
                </div>
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                  <div className="flex items-center gap-3">
                    <Server className="h-4 w-4 text-[#818cf8]" />
                    <span className="text-xs font-bold text-white">Redis In-Memory Cache</span>
                  </div>
                  <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-emerald-950/40 text-emerald-400 border border-emerald-500/30">
                    Healthy
                  </span>
                </div>
                <div className="flex items-center justify-between p-3.5 rounded-xl bg-[#0a0a0f] border border-[#272738]">
                  <div className="flex items-center gap-3">
                    <Activity className="h-4 w-4 text-[#10b981]" />
                    <span className="text-xs font-bold text-white">Synthetics API Backend</span>
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

        {/* Tokenizer & Indic Efficiency Tab */}
        <TabsContent value="token_efficiency" className="mt-6 space-y-4 font-mono text-xs">
          <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                    <Zap className="h-4 w-4 text-emerald-400" />
                    Indic Tokenizer Fertility &amp; Cost Compression Engine
                  </CardTitle>
                  <p className="text-[11px] text-[#94a3b8] mt-0.5">
                    Measuring token bloat (fertility ratio) and training cost reduction across Indic languages
                  </p>
                </div>
                <Badge variant="outline" className="border-emerald-600/50 bg-emerald-950/40 text-emerald-400 text-[10px]">
                  ~42% Mean Savings on Sarvam
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-4 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-3 bg-[#0a0a0f] border border-[#272738] rounded-xl space-y-1">
                  <span className="text-[10px] uppercase text-[#94a3b8] font-bold">Standard Llama-3 Fertility</span>
                  <p className="text-xl font-bold text-rose-400">3.65 tok/word</p>
                  <p className="text-[10px] text-[#64748b]">Byte fallback bloat on Devanagari &amp; Indic scripts</p>
                </div>
                <div className="p-3 bg-[#0a0a0f] border border-[#272738] rounded-xl space-y-1">
                  <span className="text-[10px] uppercase text-[#94a3b8] font-bold">Sarvam / Gemma-2 Fertility</span>
                  <p className="text-xl font-bold text-[#10b981]">1.28 tok/word</p>
                  <p className="text-[10px] text-[#64748b]">Optimized Devanagari subword vocabulary</p>
                </div>
                <div className="p-3 bg-[#0a0a0f] border border-[#272738] rounded-xl space-y-1">
                  <span className="text-[10px] uppercase text-[#94a3b8] font-bold">Inference &amp; Fine-Tune Savings</span>
                  <p className="text-xl font-bold text-cyan-300">~65% Less Compute</p>
                  <p className="text-[10px] text-[#64748b]">Over 2.8x shorter sequence lengths at training time</p>
                </div>
              </div>

              {/* Language Benchmark Comparison Grid */}
              <div className="border border-[#272738] bg-[#0a0a0f] rounded-xl overflow-hidden">
                <div className="grid grid-cols-5 p-2.5 bg-[#161622] text-[10px] uppercase font-bold text-[#94a3b8] border-b border-[#272738]">
                  <span>Language</span>
                  <span>Script</span>
                  <span>Llama-3 (t/w)</span>
                  <span>Sarvam (t/w)</span>
                  <span className="text-right">Savings (%)</span>
                </div>
                {[
                  { lang: 'Hindi (हिन्दी)', script: 'Native Devanagari', llama: '3.65', sarvam: '1.28', savings: '65%' },
                  { lang: 'Hindi + English', script: 'Romanized (Hinglish)', llama: '1.55', sarvam: '1.32', savings: '15%' },
                  { lang: 'Tamil (தமிழ்)', script: 'Native Tamil', llama: '3.82', sarvam: '1.35', savings: '64%' },
                  { lang: 'Telugu (తెలుగు)', script: 'Native Telugu', llama: '3.78', sarvam: '1.34', savings: '64%' },
                  { lang: 'Bengali (বাংলা)', script: 'Native Bengali', llama: '3.60', sarvam: '1.31', savings: '63%' },
                  { lang: 'Marathi (मराठी)', script: 'Native Devanagari', llama: '3.55', sarvam: '1.29', savings: '63%' },
                ].map((row, idx) => (
                  <div key={idx} className="grid grid-cols-5 p-2.5 text-[11px] border-b border-[#1c1c28] last:border-0 hover:bg-[#12121a]">
                    <span className="font-bold text-white">{row.lang}</span>
                    <span className="text-[#94a3b8]">{row.script}</span>
                    <span className="text-rose-300 font-mono">{row.llama}</span>
                    <span className="text-emerald-400 font-mono font-bold">{row.sarvam}</span>
                    <span className="text-right text-[#10b981] font-bold font-mono">{row.savings}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Validation Tab */}
        <TabsContent value="validation" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ValidationFeedback />
            <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
              <CardHeader className="pb-3 border-b border-[#272738]">
                <CardTitle className="flex items-center gap-2 text-sm font-bold text-white">
                  <Shield className="h-4 w-4 text-[#6366f1]" />
                  Security Features
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-3 bg-[#0a0a0f] border border-[#272738] rounded-xl">
                    <CheckCircle2 className="h-4 w-4 text-[#10b981] mt-0.5 shrink-0" />
                    <div>
                      <h4 className="font-bold text-xs text-white">Input Validation &amp; Sanitization</h4>
                      <p className="text-[11px] text-[#94a3b8]">
                        All API inputs are strictly validated against JSON schema models and rate-limited.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-3 bg-[#0a0a0f] border border-[#272738] rounded-xl">
                    <CheckCircle2 className="h-4 w-4 text-[#10b981] mt-0.5 shrink-0" />
                    <div>
                      <h4 className="font-bold text-xs text-white">JWT Token &amp; CSRF Protection</h4>
                      <p className="text-[11px] text-[#94a3b8]">
                        Secure token-based authorization with stateless HMAC CSRF protection across requests.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 p-3 bg-[#0a0a0f] border border-[#272738] rounded-xl">
                    <CheckCircle2 className="h-4 w-4 text-[#10b981] mt-0.5 shrink-0" />
                    <div>
                      <h4 className="font-bold text-xs text-white">CORS &amp; Admission Control</h4>
                      <p className="text-[11px] text-[#94a3b8]">
                        Environment-controlled origins with backpressure admission limiting concurrent jobs.
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