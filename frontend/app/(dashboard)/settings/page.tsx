'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Settings,
  Shield,
  Key,
  Database,
  Server,
  Activity,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Loader2,
  ExternalLink,
  HardDrive,
  Cpu,
  Check,
  Cloud,
  Zap,
  Sliders,
  Gauge,
  Lock,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { api } from '@/lib/api/client'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'

interface HealthStatus {
  status: string
  service?: string
  database?: boolean
  database_engine?: string
  redis?: boolean
  providers?: Record<string, { status: string; latency_ms?: number }>
  circuit_breakers?: Record<string, string>
}

export default function SettingsPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null)

  // 1. General & Storage State
  const [generationMode, setGenerationMode] = useState('strict_source')
  const [seedlessGuard, setSeedlessGuard] = useState(true)
  const [outputDirectory, setOutputDirectory] = useState('outputs')
  const [storageBackend, setStorageBackend] = useState('local')
  const [validationStrictness, setValidationStrictness] = useState('standard')

  // 2. Cloud Compute & GPUs State
  const [computeConfig, setComputeConfig] = useState<{
    modal_configured: boolean
    runpod_configured: boolean
    hf_configured: boolean
    modal_token_id_masked: string | null
    runpod_key_masked: string | null
    hf_token_masked: string | null
    available_targets: string[]
  } | null>(null)
  const [modalTokenId, setModalTokenId] = useState('')
  const [modalTokenSecret, setModalTokenSecret] = useState('')
  const [runpodApiKey, setRunpodApiKey] = useState('')
  const [hfToken, setHfToken] = useState('')
  const [savingCompute, setSavingCompute] = useState(false)

  // 3. Quality & Review Thresholds State
  const [hitlMode, setHitlMode] = useState<'async' | 'blocking'>('async')
  const [qualityThreshold, setQualityThreshold] = useState(0.85)
  const [sampleRatio, setSampleRatio] = useState(0.15)
  const [autoApproveMinutes, setAutoApproveMinutes] = useState(30)
  const [canaryGateEnabled, setCanaryGateEnabled] = useState(true)

  // 4. Rate Limits & Concurrency State
  const [tokenBudgetUsd, setTokenBudgetUsd] = useState(50.0)
  const [maxConcurrentJobs, setMaxConcurrentJobs] = useState(4)
  const [maxQueueSize, setMaxQueueSize] = useState(50)
  const [fineTuneMaxConcurrent, setFineTuneMaxConcurrent] = useState(2)
  const [geminiRpm, setGeminiRpm] = useState(60)
  const [groqRpm, setGroqRpm] = useState(90)
  const [anthropicRpm, setAnthropicRpm] = useState(40)

  // Load persisted user preferences
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('rs_platform_settings')
        if (saved) {
          const parsed = JSON.parse(saved)
          if (parsed.generationMode) setGenerationMode(parsed.generationMode)
          if (parsed.seedlessGuard != null) setSeedlessGuard(parsed.seedlessGuard)
          if (parsed.outputDirectory) setOutputDirectory(parsed.outputDirectory)
          if (parsed.storageBackend) setStorageBackend(parsed.storageBackend)
          if (parsed.validationStrictness) setValidationStrictness(parsed.validationStrictness)
          if (parsed.hitlMode) setHitlMode(parsed.hitlMode)
          if (parsed.qualityThreshold != null) setQualityThreshold(parsed.qualityThreshold)
          if (parsed.sampleRatio != null) setSampleRatio(parsed.sampleRatio)
          if (parsed.autoApproveMinutes != null) setAutoApproveMinutes(parsed.autoApproveMinutes)
          if (parsed.canaryGateEnabled != null) setCanaryGateEnabled(parsed.canaryGateEnabled)
          if (parsed.tokenBudgetUsd != null) setTokenBudgetUsd(parsed.tokenBudgetUsd)
          if (parsed.maxConcurrentJobs != null) setMaxConcurrentJobs(parsed.maxConcurrentJobs)
          if (parsed.maxQueueSize != null) setMaxQueueSize(parsed.maxQueueSize)
          if (parsed.fineTuneMaxConcurrent != null) setFineTuneMaxConcurrent(parsed.fineTuneMaxConcurrent)
          if (parsed.geminiRpm != null) setGeminiRpm(parsed.geminiRpm)
          if (parsed.groqRpm != null) setGroqRpm(parsed.groqRpm)
          if (parsed.anthropicRpm != null) setAnthropicRpm(parsed.anthropicRpm)
        }
      } catch {}
    }
  }, [])

  const persistSettings = useCallback(() => {
    if (typeof window !== 'undefined') {
      const payload = {
        generationMode,
        seedlessGuard,
        outputDirectory,
        storageBackend,
        validationStrictness,
        hitlMode,
        qualityThreshold,
        sampleRatio,
        autoApproveMinutes,
        canaryGateEnabled,
        tokenBudgetUsd,
        maxConcurrentJobs,
        maxQueueSize,
        fineTuneMaxConcurrent,
        geminiRpm,
        groqRpm,
        anthropicRpm,
      }
      localStorage.setItem('rs_platform_settings', JSON.stringify(payload))
    }
  }, [
    generationMode, seedlessGuard, outputDirectory, storageBackend, validationStrictness,
    hitlMode, qualityThreshold, sampleRatio, autoApproveMinutes, canaryGateEnabled,
    tokenBudgetUsd, maxConcurrentJobs, maxQueueSize, fineTuneMaxConcurrent,
    geminiRpm, groqRpm, anthropicRpm,
  ])

  const showNotification = (msg: string) => {
    setSaveSuccessMsg(msg)
    playSuccessChime()
    setTimeout(() => setSaveSuccessMsg(null), 3000)
  }

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.getHealth().catch(() => api.getHealthReady().catch(() => null))
      setHealth(data as HealthStatus | null)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  const fetchComputeSettings = useCallback(async () => {
    try {
      const res = await api.getComputeSettings()
      setComputeConfig(res)
    } catch (e) {
      console.warn('Failed to fetch compute settings', e)
    }
  }, [])

  useEffect(() => {
    fetchHealth()
    fetchComputeSettings()
  }, [fetchHealth, fetchComputeSettings])

  const refresh = () => {
    setRefreshing(true)
    fetchHealth()
    fetchComputeSettings()
  }

  const handleSaveCompute = async (e: React.FormEvent) => {
    e.preventDefault()
    playClickSound()
    setSavingCompute(true)
    try {
      await api.updateComputeSettings({
        modal_token_id: modalTokenId || undefined,
        modal_token_secret: modalTokenSecret || undefined,
        runpod_api_key: runpodApiKey || undefined,
        hf_token: hfToken || undefined,
      })
      showNotification('Cloud compute credentials updated and applied!')
      fetchComputeSettings()
      setModalTokenId('')
      setModalTokenSecret('')
      setRunpodApiKey('')
      setHfToken('')
    } catch (err) {
      console.error('Failed to update compute settings', err)
    } finally {
      setSavingCompute(false)
    }
  }

  const handleSaveGeneral = (e: React.FormEvent) => {
    e.preventDefault()
    playClickSound()
    persistSettings()
    showNotification('General and storage preferences saved!')
  }

  const handleSaveQuality = (e: React.FormEvent) => {
    e.preventDefault()
    playClickSound()
    persistSettings()
    showNotification('Quality and review thresholds applied!')
  }

  const handleSaveLimits = (e: React.FormEvent) => {
    e.preventDefault()
    playClickSound()
    persistSettings()
    showNotification('Resource limits and rate caps updated!')
  }

  const infraStatus = health?.status === 'healthy' || health?.status === 'ok'
  const isDbConnected = health?.database !== false
  const isRedisConnected = health?.redis !== false

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in max-w-7xl mx-auto">
      {/* Toast Notification */}
      {saveSuccessMsg && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 px-4 py-2.5 rounded-md border shadow-lg text-xs font-semibold bg-emerald-950 text-white border-emerald-500/40 animate-slide-in">
          <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
          <span>{saveSuccessMsg}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#272738] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-xs font-mono px-2 py-0.5 rounded-sm bg-[#f26625]/10 border border-[#f26625]/30 text-[#f26625] font-bold uppercase tracking-wider">
              Platform Configuration
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">
              Platform Settings
            </h1>
          </div>
          <p className="text-xs text-[#a8a29e]">
            Configure runtime environments, cloud GPU credentials, quality review gates, and resource concurrency bounds.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            className="rounded-md border-[#272738] text-white hover:bg-[#161622] font-mono text-xs"
            onClick={refresh}
            disabled={refreshing || loading}
          >
            <RefreshCw className={clsx('h-3.5 w-3.5 mr-1 text-[#f26625]', (refreshing || loading) && 'animate-spin')} />
            Refresh Status
          </Button>
        </div>
      </div>

      {/* Runtime Health Ribbon */}
      <Card className="border-[#272738] bg-[#12121a] rounded-md card-shadow">
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 font-mono text-xs">
          <div className="flex items-center gap-3">
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin text-[#f26625]" />
            ) : infraStatus ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
            ) : (
              <AlertCircle className="h-5 w-5 text-amber-400" />
            )}
            <div>
              <p className="text-xs font-bold text-white flex items-center gap-2">
                <span>Platform Engine: {loading ? 'Checking status...' : health?.status?.toUpperCase() ?? 'ACTIVE'}</span>
                {!loading && infraStatus && (
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Live Verified
                  </span>
                )}
              </p>
              <div className="text-[#a8a29e] text-xs mt-1 flex flex-wrap items-center gap-3">
                <span className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${isDbConnected ? 'bg-emerald-400' : 'bg-rose-400'}`} />
                  Primary Database ({health?.database_engine === 'sqlite' ? 'SQLite' : 'PostgreSQL'})
                </span>
                <span className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${isRedisConnected ? 'bg-emerald-400' : 'bg-zinc-500'}`} />
                  Broker &amp; Cache ({isRedisConnected ? 'Redis Connected' : 'In-Memory Ring'})
                </span>
              </div>
            </div>
          </div>
          <a
            href={process.env.NEXT_PUBLIC_API_URL ? `${process.env.NEXT_PUBLIC_API_URL}/docs` : 'https://github.com/Sourabh-Kumar04/RasoSynth_CUTC#readme'}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button variant="outline" size="sm" className="h-7 text-xs rounded-md border-[#272738] text-[#a8a29e] hover:text-white hover:bg-[#161622]">
              <ExternalLink className="h-3 w-3 mr-1 text-[#f26625]" />
              API Documentation
            </Button>
          </a>
        </CardContent>
      </Card>

      {/* 4 Focused Interactive Settings Panels */}
      <Tabs defaultValue="general">
        <TabsList className="bg-[#161622] rounded-md border border-[#272738] p-1 flex flex-wrap gap-1 h-auto">
          <TabsTrigger value="general" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white flex items-center gap-1.5">
            <HardDrive className="w-3.5 h-3.5" />
            General &amp; Storage
          </TabsTrigger>
          <TabsTrigger value="compute" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white flex items-center gap-1.5">
            <Cloud className="w-3.5 h-3.5" />
            Cloud Compute &amp; GPUs
          </TabsTrigger>
          <TabsTrigger value="quality" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5" />
            Quality &amp; Review Thresholds
          </TabsTrigger>
          <TabsTrigger value="limits" className="rounded-sm text-xs font-mono data-[state=active]:bg-[#f26625] data-[state=active]:text-white flex items-center gap-1.5">
            <Gauge className="w-3.5 h-3.5" />
            Rate Limits &amp; Concurrency
          </TabsTrigger>
        </TabsList>

        {/* Panel 1: General & Storage */}
        <TabsContent value="general" className="mt-4 space-y-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-[#f26625]" />
                General System &amp; Grounding Architecture
              </CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">
                Configure data grounding enforcement, artifact export destinations, and storage adapters.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5">
              <form onSubmit={handleSaveGeneral} className="space-y-5 font-mono text-xs">
                {/* Generation Mode Select */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Default Generation Mode</label>
                    <Select value={generationMode} onValueChange={setGenerationMode}>
                      <SelectTrigger className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
                        <SelectItem value="strict_source">Strict Source-Grounded (Recommended)</SelectItem>
                        <SelectItem value="hybrid">Hybrid (Source-Assisted Synthetic)</SelectItem>
                        <SelectItem value="unconstrained">Unconstrained Synthetic</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[11px] text-[#a8a29e]">
                      Strict mode ensures every generated response contains verifiable citations to domain corpus.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Validation Strictness</label>
                    <Select value={validationStrictness} onValueChange={setValidationStrictness}>
                      <SelectTrigger className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
                        <SelectItem value="standard">Standard (Schema + Grammar Validation)</SelectItem>
                        <SelectItem value="strict">Strict (Zero-Tolerance Hallucination Floor)</SelectItem>
                        <SelectItem value="lenient">Lenient (Permissive Output Parser)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[11px] text-[#a8a29e]">
                      Controls how aggressively malformed JSON or ungrounded claims are rejected.
                    </p>
                  </div>
                </div>

                {/* Seedless Generation Guard Toggle */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-[#0a0a0f] border border-[#272738]">
                  <div className="space-y-0.5 max-w-xl">
                    <div className="text-xs font-bold text-white flex items-center gap-2">
                      <span>Seedless Generation Guard</span>
                      <Badge variant="outline" className="border-emerald-500/40 text-emerald-400 text-[10px]">
                        ACTIVE PROTECTION
                      </Badge>
                    </div>
                    <p className="text-[11px] text-[#a8a29e]">
                      Rejects synthetic generation requests when reference domain seeds are absent, preventing hallucinated legal statutes or fictitious medical claims.
                    </p>
                  </div>
                  <Switch checked={seedlessGuard} onCheckedChange={setSeedlessGuard} />
                </div>

                {/* Storage Backend & Output Directory */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-[#1c1c28]">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Storage Destination</label>
                    <Select value={storageBackend} onValueChange={setStorageBackend}>
                      <SelectTrigger className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
                        <SelectItem value="local">Local Filesystem Storage</SelectItem>
                        <SelectItem value="s3">AWS S3 / Compatible Object Store</SelectItem>
                        <SelectItem value="huggingface">Hugging Face Datasets Hub</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Output Directory Path</label>
                    <Input
                      type="text"
                      value={outputDirectory}
                      onChange={(e) => setOutputDirectory(e.target.value)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                      placeholder="outputs"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-3 border-t border-[#272738]">
                  <Button type="submit" className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-bold font-mono h-9 px-5">
                    Save General Settings
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Panel 2: Cloud Compute & GPUs */}
        <TabsContent value="compute" className="mt-4 space-y-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Cloud className="w-4 h-4 text-[#f26625]" />
                Cloud Compute &amp; GPU Execution Providers
              </CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">
                Configure external cloud GPU credentials for offloading QLoRA and SFT fine-tuning jobs (Modal Labs, RunPod Cloud, Hugging Face Hub).
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5 space-y-5 font-mono text-xs">
              {/* Status Badges */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3 rounded-lg bg-[#0a0a0f] border border-[#272738] flex items-center justify-between">
                  <div>
                    <span className="text-white font-bold block">Modal Labs GPU</span>
                    <span className="text-[11px] text-zinc-400">Serverless A10G / H100</span>
                  </div>
                  <Badge variant="outline" className={computeConfig?.modal_configured ? 'border-emerald-500/40 text-emerald-400' : 'border-zinc-700 text-zinc-500'}>
                    {computeConfig?.modal_configured ? 'Configured' : 'Not Configured'}
                  </Badge>
                </div>

                <div className="p-3 rounded-lg bg-[#0a0a0f] border border-[#272738] flex items-center justify-between">
                  <div>
                    <span className="text-white font-bold block">RunPod Cloud</span>
                    <span className="text-[11px] text-zinc-400">On-demand Pod Workers</span>
                  </div>
                  <Badge variant="outline" className={computeConfig?.runpod_configured ? 'border-emerald-500/40 text-emerald-400' : 'border-zinc-700 text-zinc-500'}>
                    {computeConfig?.runpod_configured ? 'Configured' : 'Not Configured'}
                  </Badge>
                </div>

                <div className="p-3 rounded-lg bg-[#0a0a0f] border border-[#272738] flex items-center justify-between">
                  <div>
                    <span className="text-white font-bold block">Hugging Face Hub</span>
                    <span className="text-[11px] text-zinc-400">Model Upload &amp; Releases</span>
                  </div>
                  <Badge variant="outline" className={computeConfig?.hf_configured ? 'border-emerald-500/40 text-emerald-400' : 'border-zinc-700 text-zinc-500'}>
                    {computeConfig?.hf_configured ? 'Configured' : 'Not Configured'}
                  </Badge>
                </div>
              </div>

              {/* Interactive Credentials Update Form */}
              <form onSubmit={handleSaveCompute} className="space-y-4 pt-2 border-t border-[#1c1c28]">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block">Modal Token ID</label>
                    <Input
                      type="text"
                      value={modalTokenId}
                      onChange={(e) => setModalTokenId(e.target.value)}
                      placeholder={computeConfig?.modal_token_id_masked || 'ak-xxxx'}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono placeholder:text-zinc-600"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block">Modal Token Secret</label>
                    <Input
                      type="password"
                      value={modalTokenSecret}
                      onChange={(e) => setModalTokenSecret(e.target.value)}
                      placeholder="as-xxxx"
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono placeholder:text-zinc-600"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block">RunPod API Key</label>
                    <Input
                      type="password"
                      value={runpodApiKey}
                      onChange={(e) => setRunpodApiKey(e.target.value)}
                      placeholder={computeConfig?.runpod_key_masked || 'rpa_xxxx'}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono placeholder:text-zinc-600"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block">Hugging Face Hub Write Token</label>
                    <Input
                      type="password"
                      value={hfToken}
                      onChange={(e) => setHfToken(e.target.value)}
                      placeholder={computeConfig?.hf_token_masked || 'hf_xxxx'}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono placeholder:text-zinc-600"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-3 border-t border-[#272738]">
                  <Button
                    type="submit"
                    disabled={savingCompute || (!modalTokenId && !modalTokenSecret && !runpodApiKey && !hfToken)}
                    className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-bold font-mono h-9 px-5"
                  >
                    {savingCompute ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                        Saving Credentials...
                      </>
                    ) : (
                      <>
                        <Zap className="w-3.5 h-3.5 mr-1.5" />
                        Save Cloud Credentials
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Panel 3: Quality & Review Thresholds */}
        <TabsContent value="quality" className="mt-4 space-y-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Shield className="w-4 h-4 text-[#f26625]" />
                Human-in-the-Loop (HITL) &amp; Automated Quality Floor
              </CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">
                Set inspection thresholds, canary win-rate gates, and sample ratios for dataset validation.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5">
              <form onSubmit={handleSaveQuality} className="space-y-5 font-mono text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">HITL Inspection Mode</label>
                    <Select value={hitlMode} onValueChange={(v: any) => setHitlMode(v)}>
                      <SelectTrigger className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
                        <SelectItem value="async">Asynchronous Review (Persist to Review Queue)</SelectItem>
                        <SelectItem value="blocking">Blocking Gate (Halt Pipeline for Approval)</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-[11px] text-[#a8a29e]">
                      Determines whether generation runs continue or wait when samples require inspection.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">
                      Quality Pass Floor: <span className="text-[#f26625] font-bold">{(qualityThreshold * 100).toFixed(0)}%</span>
                    </label>
                    <Input
                      type="number"
                      step={0.01}
                      min={0.5}
                      max={0.99}
                      value={qualityThreshold}
                      onChange={(e) => setQualityThreshold(parseFloat(e.target.value) || 0.85)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                    />
                    <p className="text-[11px] text-[#a8a29e]">
                      Minimum composite LLM judge score needed to bypass manual inspection.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-[#1c1c28]">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">
                      Stratified Sampling Ratio: <span className="text-[#f26625] font-bold">{(sampleRatio * 100).toFixed(0)}%</span>
                    </label>
                    <Input
                      type="number"
                      step={0.01}
                      min={0.01}
                      max={1.0}
                      value={sampleRatio}
                      onChange={(e) => setSampleRatio(parseFloat(e.target.value) || 0.15)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                    />
                    <p className="text-[11px] text-[#a8a29e]">
                      Percentage of generated records randomly routed for audit.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Auto-Approval Timeout (Minutes)</label>
                    <Input
                      type="number"
                      min={0}
                      max={1440}
                      value={autoApproveMinutes}
                      onChange={(e) => setAutoApproveMinutes(parseInt(e.target.value) || 30)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                    />
                    <p className="text-[11px] text-[#a8a29e]">
                      Minutes before auto-approving pending batches (0 = wait indefinitely).
                    </p>
                  </div>
                </div>

                {/* Canary Gate Switch */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-[#0a0a0f] border border-[#272738]">
                  <div className="space-y-0.5 max-w-xl">
                    <span className="text-xs font-bold text-white block">Canary Win-Rate Validation Gate</span>
                    <p className="text-[11px] text-[#a8a29e]">
                      Prevents fine-tuned model export or dataset release unless automated A/B evaluations exceed 70% win-rate against baseline models.
                    </p>
                  </div>
                  <Switch checked={canaryGateEnabled} onCheckedChange={setCanaryGateEnabled} />
                </div>

                <div className="flex justify-end pt-3 border-t border-[#272738]">
                  <Button type="submit" className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-bold font-mono h-9 px-5">
                    Save Quality Thresholds
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Panel 4: Rate Limits & Concurrency */}
        <TabsContent value="limits" className="mt-4 space-y-4">
          <Card className="bg-[#12121a] border-[#272738] rounded-md card-shadow">
            <CardHeader className="pb-3 border-b border-[#272738]">
              <CardTitle className="text-sm font-bold text-white flex items-center gap-2">
                <Gauge className="w-4 h-4 text-[#f26625]" />
                Resource Limits, Budgets &amp; Concurrency Bounds
              </CardTitle>
              <CardDescription className="text-xs text-[#a8a29e]">
                Protect backend hardware and prevent external LLM API cost overruns with concurrency and rate limits.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-5">
              <form onSubmit={handleSaveLimits} className="space-y-5 font-mono text-xs">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Token Spending Budget Cap ($ USD)</label>
                    <Input
                      type="number"
                      min={1}
                      max={10000}
                      step={1}
                      value={tokenBudgetUsd}
                      onChange={(e) => setTokenBudgetUsd(parseFloat(e.target.value) || 50)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                    />
                    <p className="text-[11px] text-[#a8a29e]">
                      Total external model token spend ceiling before the platform halts synthesis.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Max Concurrent Dataset Jobs</label>
                    <Input
                      type="number"
                      min={1}
                      max={16}
                      value={maxConcurrentJobs}
                      onChange={(e) => setMaxConcurrentJobs(parseInt(e.target.value) || 4)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                    />
                    <p className="text-[11px] text-[#a8a29e]">
                      Maximum simultaneous synthesis pipelines allowed to execute.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-[#1c1c28]">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Job Queue Buffer Cap</label>
                    <Input
                      type="number"
                      min={5}
                      max={200}
                      value={maxQueueSize}
                      onChange={(e) => setMaxQueueSize(parseInt(e.target.value) || 50)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                    />
                    <p className="text-[11px] text-[#a8a29e]">
                      Backpressure threshold before rejecting new pipeline submissions.
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-white block uppercase">Parallel Fine-Tuning Workers</label>
                    <Input
                      type="number"
                      min={1}
                      max={8}
                      value={fineTuneMaxConcurrent}
                      onChange={(e) => setFineTuneMaxConcurrent(parseInt(e.target.value) || 2)}
                      className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-9 font-mono"
                    />
                    <p className="text-[11px] text-[#a8a29e]">
                      Simultaneous QLoRA training worker limit bounded by available GPU memory.
                    </p>
                  </div>
                </div>

                {/* Provider RPM Limits */}
                <div className="pt-2 border-t border-[#1c1c28] space-y-2">
                  <span className="text-xs font-bold text-white block uppercase">Provider Throttle Quotas (Requests / Min)</span>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="p-2.5 rounded bg-[#0a0a0f] border border-[#272738] space-y-1">
                      <span className="text-[11px] text-[#a8a29e] block font-bold">Google Gemini</span>
                      <Input
                        type="number"
                        min={5}
                        max={300}
                        value={geminiRpm}
                        onChange={(e) => setGeminiRpm(parseInt(e.target.value) || 60)}
                        className="bg-[#12121a] border-[#272738] text-white text-xs h-8 font-mono"
                      />
                    </div>
                    <div className="p-2.5 rounded bg-[#0a0a0f] border border-[#272738] space-y-1">
                      <span className="text-[11px] text-[#a8a29e] block font-bold">Groq Cloud</span>
                      <Input
                        type="number"
                        min={5}
                        max={300}
                        value={groqRpm}
                        onChange={(e) => setGroqRpm(parseInt(e.target.value) || 90)}
                        className="bg-[#12121a] border-[#272738] text-white text-xs h-8 font-mono"
                      />
                    </div>
                    <div className="p-2.5 rounded bg-[#0a0a0f] border border-[#272738] space-y-1">
                      <span className="text-[11px] text-[#a8a29e] block font-bold">Anthropic Claude</span>
                      <Input
                        type="number"
                        min={5}
                        max={300}
                        value={anthropicRpm}
                        onChange={(e) => setAnthropicRpm(parseInt(e.target.value) || 40)}
                        className="bg-[#12121a] border-[#272738] text-white text-xs h-8 font-mono"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-end pt-3 border-t border-[#272738]">
                  <Button type="submit" className="bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-bold font-mono h-9 px-5">
                    Save Resource Limits
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
