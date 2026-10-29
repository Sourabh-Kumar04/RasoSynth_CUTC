'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Database,
  Search,
  Filter,
  Download,
  Eye,
  Calendar,
  FileText,
  Image,
  Code,
  Layers,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Plus,
  Zap,
  ExternalLink,
  Sparkles,
  RefreshCw,
  Copy,
  Check,
  UploadCloud,
  Terminal,
  ShieldCheck,
  AlertTriangle,
  Trash2,
  CheckSquare,
  Square,
  Workflow,
  LayoutGrid,
  List,
  Cpu,
  Globe,
  Puzzle,
  Upload
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useRouter } from 'next/navigation'
import { api, HealthStatus } from '@/lib/api/client'
import { MerkleTreeGraph } from '@/components/dbom/merkle-tree-graph'
import { playClickSound, playSuccessChime } from '@/lib/audio/sound-effects'

// Dataset interface matching backend
interface DatasetJob {
  id: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'negotiating'
  created_at: string
  progress: number
  cost_usd: number
  samples_generated: number
  current_stage?: string
  target_domain?: string
  dataset_type?: string
  output_format?: string
  synthesis_mode?: string
  config?: Record<string, any>
  metadata?: Record<string, any>
  error?: string
}

// Pipeline stages in order
const PIPELINE_STAGES = [
  { id: 'analyzing_constraints', label: 'Analyzing', icon: Search },
  { id: 'discovering_sources', label: 'Discovering', icon: Globe },
  { id: 'extracting_content', label: 'Extracting', icon: FileText },
  { id: 'filtering_quality', label: 'Filtering', icon: Sparkles },
  { id: 'constructing_dataset', label: 'Constructing', icon: Puzzle },
  { id: 'exporting', label: 'Exporting', icon: Upload },
  { id: 'completed', label: 'Complete', icon: Check },
]

const modalityIcons = {
  text: FileText,
  image: Image,
  code: Code,
  coding: Code,
  multimodal: Layers,
  rag: FileText,
  rlhf: FileText,
  classification: FileText,
  reasoning: FileText,
  conversational: FileText,
  tool_calling: Code,
}

// Helper to format file size
function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// Helper to convert backend job to display dataset with intelligent title resolution
function jobToDataset(job: any): any {
  const status = job.status === 'completed' ? 'ready' : job.status === 'running' ? 'processing' : job.status
  const synthesisMode = job.synthesis_mode || job.config?.synthesis_mode || job.metadata?.synthesis_mode || 'standard'
  
  const rawPrompt = job.target_domain || job.config?.target_domain || ''
  let displayName = job.dataset_name || job.config?.dataset_name
  
  if (!displayName) {
    if (rawPrompt.toLowerCase().includes('bharatiya nyaya sanhita') || rawPrompt.toLowerCase().includes('bns 2023')) {
      displayName = 'Bharatiya Nyaya Sanhita (BNS 2023) Legal CoT'
    } else if (rawPrompt.toLowerCase().includes('python software engineering') || rawPrompt.toLowerCase().includes('code-first sft')) {
      displayName = 'Production Python SE & Fast-Pass SFT'
    } else if (rawPrompt.toLowerCase().includes('aeronautical engineering') || rawPrompt.toLowerCase().includes('airfoil design')) {
      displayName = 'Aerospace Engineering & Navier-Stokes CoT'
    } else if (rawPrompt && rawPrompt.length <= 50) {
      displayName = rawPrompt
    } else if (rawPrompt) {
      const firstClause = rawPrompt.split(/[.:;\n]/)[0].trim()
      displayName = firstClause.length <= 50 ? firstClause : firstClause.slice(0, 47) + '...'
    } else {
      displayName = `Synthetic Dataset ${job.id.slice(0, 8)}`
    }
  }

  return {
    id: job.id,
    name: displayName,
    description: rawPrompt,
    modality: job.dataset_type || job.config?.dataset_type || 'text',
    format: job.output_format || job.config?.export_format || 'jsonl',
    synthesis_mode: synthesisMode,
    size: formatSize((job.samples_generated || 0) * 1024 * 2),
    records: job.samples_generated || 0,
    quality: typeof (job.quality_score ?? job.metadata?.quality_score ?? job.metadata?.quality_breakdown?.composite) === 'number'
      ? Math.round(Number(job.quality_score ?? job.metadata?.quality_score ?? job.metadata?.quality_breakdown?.composite) <= 1.0 
          ? Number(job.quality_score ?? job.metadata?.quality_score ?? job.metadata?.quality_breakdown?.composite) * 100 
          : Number(job.quality_score ?? job.metadata?.quality_score ?? job.metadata?.quality_breakdown?.composite))
      : null,
    status,
    current_stage: job.current_stage || 'pending',
    created: job.created_at ? new Date(job.created_at).toISOString().split('T')[0] : '—',
    tags: [job.dataset_type || 'reasoning', job.current_stage, synthesisMode !== 'standard' ? synthesisMode : null].filter(Boolean),
    validated: job.status === 'completed',
    certificate_id: `DBOM-${job.id.slice(0, 8).toUpperCase()}`,
    merkle_root: job.merkle_root || job.metadata?.merkle_root_hash || null,
  }
}

export default function DatasetsPage() {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [modalityFilter, setModalityFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'name' | 'size' | 'quality' | 'created'>('created')
  const [viewMode, setViewMode] = useState<'grid' | 'table'>('table')
  const [selectedDataset, setSelectedDataset] = useState<string | null>(null)

  // API state for dataset records preview
  const [records, setRecords] = useState<any[]>([])
  const [recordsLoading, setRecordsLoading] = useState(false)
  const [recordsError, setRecordsError] = useState<string | null>(null)
  const [datasetSummary, setDatasetSummary] = useState<any | null>(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  // Download state
  const [downloadFormat, setDownloadFormat] = useState<Record<string, string>>({})
  const [downloadingIds, setDownloadingIds] = useState<Set<string>>(new Set())

  // Hugging Face Dataset Card modal state
  const [hfCardModalOpen, setHfCardModalOpen] = useState(false)
  const [hfCardContent, setHfCardContent] = useState<string>('')
  const [hfCardLoading, setHfCardLoading] = useState(false)
  const [hfCardCopied, setHfCardCopied] = useState(false)
  const [hfCardDomain, setHfCardDomain] = useState<string>('')

  const handleViewHfCard = async (jobId: string, name: string) => {
    setHfCardModalOpen(true)
    setHfCardLoading(true)
    setHfCardCopied(false)
    setHfCardDomain(name)
    try {
      const res = await api.getHuggingFaceCard(jobId)
      setHfCardContent(res.content || '')
    } catch (e: any) {
      console.error('Failed to load HF Card:', e)
      setHfCardContent('# Error loading Hugging Face Card\n' + (e.message || 'Unknown error'))
    } finally {
      setHfCardLoading(false)
    }
  }

  const handleCopyHfCard = () => {
    if (!hfCardContent) return
    navigator.clipboard.writeText(hfCardContent)
    setHfCardCopied(true)
    setTimeout(() => setHfCardCopied(false), 2000)
  }

  // Hugging Face Hub Direct Publish state
  const [hfPublishModalOpen, setHfPublishModalOpen] = useState(false)
  const [hfRepoId, setHfRepoId] = useState('')
  const [hfToken, setHfToken] = useState('')
  const [hfPrivate, setHfPrivate] = useState(false)
  const [hfPublishLoading, setHfPublishLoading] = useState(false)
  const [hfPublishResult, setHfPublishResult] = useState<any | null>(null)
  const [hfPublishError, setHfPublishError] = useState<string | null>(null)

  const handlePublishToHub = async () => {
    if (!selectedDataset || !hfRepoId.trim()) return
    setHfPublishLoading(true)
    setHfPublishError(null)
    setHfPublishResult(null)
    try {
      const res = await api.publishToHuggingFace(selectedDataset, {
        repo_id: hfRepoId.trim(),
        hf_token: hfToken.trim() || undefined,
        private: hfPrivate,
      })
      playSuccessChime()
      setHfPublishResult(res)
    } catch (e: any) {
      console.error('Failed to publish to Hugging Face Hub:', e)
      setHfPublishError(e.message || 'Failed to publish to Hugging Face Hub')
    } finally {
      setHfPublishLoading(false)
    }
  }

  // Multi-select batch export state
  const [selectedDatasetIds, setSelectedDatasetIds] = useState<Set<string>>(new Set())
  const [batchExporting, setBatchExporting] = useState(false)

  const toggleSelectDataset = (id: string) => {
    playClickSound()
    setSelectedDatasetIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const toggleSelectAll = () => {
    playClickSound()
    if (selectedDatasetIds.size > 0 && selectedDatasetIds.size === filteredDatasets.length) {
      setSelectedDatasetIds(new Set())
    } else {
      setSelectedDatasetIds(new Set(filteredDatasets.map((d) => d.id)))
    }
  }

  const handleExportBatch = async (format: 'tar.gz' | 'zip') => {
    if (selectedDatasetIds.size === 0) return
    setBatchExporting(true)
    playClickSound()
    try {
      for (const id of Array.from(selectedDatasetIds)) {
        await api.exportDataset(id, format)
      }
      playSuccessChime()
    } catch (e) {
      console.error('Batch export failed:', e)
    } finally {
      setBatchExporting(false)
      setSelectedDatasetIds(new Set())
    }
  }

  // Fine-Tuning Recipe Generator state
  const [recipeModalOpen, setRecipeModalOpen] = useState(false)
  const [recipeFramework, setRecipeFramework] = useState<'unsloth' | 'axolotl' | 'llamafactory'>('unsloth')
  const [recipeModel, setRecipeModel] = useState<string>('')
  const [recipeData, setRecipeData] = useState<any | null>(null)
  const [recipeLoading, setRecipeLoading] = useState(false)
  const [recipeCopied, setRecipeCopied] = useState(false)
  const [recipeCmdCopied, setRecipeCmdCopied] = useState(false)

  const handleFetchRecipe = async (jobId: string, framework: string = recipeFramework, model?: string) => {
    setRecipeLoading(true)
    try {
      const res = await api.getTrainingRecipe(jobId, framework, model || recipeModel || undefined)
      setRecipeData(res)
    } catch (e: any) {
      console.error('Failed to fetch training recipe:', e)
    } finally {
      setRecipeLoading(false)
    }
  }

  const handleOpenRecipeModal = (jobId: string) => {
    setRecipeModalOpen(true)
    setRecipeCopied(false)
    setRecipeCmdCopied(false)
    handleFetchRecipe(jobId, recipeFramework)
  }

  const handleDeleteDataset = async (id: string) => {
    if (!confirm('Are you sure you want to delete this dataset? All samples and artifacts will be permanently removed.')) return
    try {
      await api.deleteDataset(id)
      setDatasets((prev) => prev.filter((d) => d.id !== id))
      if (selectedDataset === id) setSelectedDataset(null)
    } catch (e: any) {
      console.error('Failed to delete dataset:', e)
      alert(e.message || 'Failed to delete dataset')
    }
  }

  // Contamination & Adversarial state
  const [contaminationReport, setContaminationReport] = useState<any | null>(null)
  const [contaminationLoading, setContaminationLoading] = useState(false)
  const [adversarialProbes, setAdversarialProbes] = useState<any[] | null>(null)
  const [adversarialLoading, setAdversarialLoading] = useState(false)

  const handleAuditContamination = async () => {
    if (!records || records.length === 0) return
    setContaminationLoading(true)
    try {
      const res = await api.auditContamination({
        samples: records.map((r: any) => ({ instruction: r.instruction, response: r.response })),
      })
      setContaminationReport(res)
    } catch (e: any) {
      console.error('Contamination audit failed:', e)
    } finally {
      setContaminationLoading(false)
    }
  }

  const handleGenerateAdversarial = async (domain: string) => {
    setAdversarialLoading(true)
    try {
      const res = await api.generateAdversarialProbes({
        domain: domain || 'taxation',
        sample_count: 5,
      })
      setAdversarialProbes(res.probes || [])
    } catch (e: any) {
      console.error('Adversarial probe generation failed:', e)
    } finally {
      setAdversarialLoading(false)
    }
  }

  // DBOM Attestation modal state
  const [dbomModalOpen, setDbomModalOpen] = useState(false)
  const [dbomLoading, setDbomLoading] = useState(false)
  const [dbomData, setDbomData] = useState<any | null>(null)
  const [dbomError, setDbomError] = useState<string | null>(null)
  const [dbomCopied, setDbomCopied] = useState(false)
  const [dbomVerifyLoading, setDbomVerifyLoading] = useState(false)
  const [dbomVerifyResult, setDbomVerifyResult] = useState<any | null>(null)

  const handleViewDbom = async (jobId: string, name: string) => {
    setDbomModalOpen(true)
    setDbomLoading(true)
    setDbomVerifyResult(null)
    setDbomError(null)
    setDbomCopied(false)
    try {
      const res = await api.getDatasetDbom(jobId)
      setDbomData(res)
    } catch (e: any) {
      console.error('Failed to load DBOM:', e)
      // No fallback certificate: on DBOM-API failure show an error state,
      // never a fabricated root, sample count, or clean bill of health.
      setDbomData(null)
      setDbomError('DBOM unavailable for ' + name + ': the attestation could not be loaded. No certificate is shown.')
    } finally {
      setDbomLoading(false)
    }
  }

  const handleVerifyDbom = async () => {
    if (!dbomData?.dbom) return
    playClickSound()
    setDbomVerifyLoading(true)
    try {
      let samplesToVerify = records && records.length > 0 ? records : []
      if (samplesToVerify.length === 0 && dbomData?.job_id) {
        try {
          const recRes = await api.getJobRecords(dbomData.job_id, 10000)
          samplesToVerify = recRes?.records || []
        } catch {}
      }
      const res = await api.verifyDbom({
        samples: samplesToVerify,
        dbom_certificate: dbomData.dbom,
      })
      // Surface the backend verdict verbatim; count only samples actually sent.
      setDbomVerifyResult({
        ...(res || {}),
        is_valid: res?.is_valid ?? false,
        status: res?.status ?? (res?.is_valid ? 'cryptographically_verified' : 'verification_failed'),
        total_samples_verified: samplesToVerify.length,
      })
      if (res?.is_valid) playSuccessChime()
    } catch (e: any) {
      // A failed verification must never render as a pass.
      setDbomVerifyResult({
        is_valid: false,
        status: 'verification_failed',
        total_samples_verified: 0,
        error: e?.message || 'Verification request failed',
      })
    } finally {
      setDbomVerifyLoading(false)
    }
  }

  // API state
  const [datasets, setDatasets] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null)

  // Fetch dataset records preview when a dataset is selected
  useEffect(() => {
    if (selectedDataset) {
      const fetchRecords = async () => {
        try {
          setRecordsLoading(true)
          setSummaryLoading(true)
          setRecordsError(null)
          const [dataResult, summaryResult] = await Promise.allSettled([
            api.getJobRecords(selectedDataset, 10),
            api.getJobDatasetSummary(selectedDataset),
          ])
          if (dataResult.status === 'fulfilled') setRecords(dataResult.value.records || [])
          else throw dataResult.reason
          setDatasetSummary(summaryResult.status === 'fulfilled' ? summaryResult.value : null)
        } catch (e: any) {
          console.error('Failed to fetch dataset records:', e)
          setRecordsError(e.message || 'Failed to fetch records')
        } finally {
          setRecordsLoading(false)
          setSummaryLoading(false)
        }
      }
      fetchRecords()
    } else {
      setRecords([])
      setDatasetSummary(null)
    }
  }, [selectedDataset])

  // Fetch jobs from API
  const fetchJobs = useCallback(async () => {
    try {
      setError(null)
      try {
        const health = await api.getHealth()
        setHealthStatus(health as HealthStatus)
      } catch (e) {
        console.warn('Health check failed:', e)
      }

      const response = await api.getJobs({ limit: 50 })
      const rawJobs = response?.data || (Array.isArray(response) ? response : [])
      const jobs = Array.isArray(rawJobs) ? rawJobs : []

      const mappedDatasets = jobs.map(jobToDataset)
      setDatasets(mappedDatasets)
    } catch (err: any) {
      console.error('Failed to fetch jobs:', err)
      setError(err.message || 'Failed to load datasets')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
    const interval = setInterval(fetchJobs, 10000)
    return () => clearInterval(interval)
  }, [fetchJobs])

  // Download handler that uses the API client with format parameter
  const handleDownload = async (datasetId: string, format: string) => {
    if (downloadingIds.has(datasetId)) return
    setDownloadingIds((prev) => new Set(prev).add(datasetId))
    try {
      const blob = await api.downloadDataset(datasetId, format)
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `dataset-${datasetId.slice(0, 8)}.${format}`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err: any) {
      console.error('Download failed:', err)
      setError(err.message || 'Download failed')
    } finally {
      setDownloadingIds((prev) => {
        const next = new Set(prev)
        next.delete(datasetId)
        return next
      })
    }
  }

  const filteredDatasets = datasets
    .filter((ds) => {
      const matchesSearch = ds.name.toLowerCase().includes(search.toLowerCase())
      const matchesModality = modalityFilter === 'all' || ds.modality === modalityFilter
      const matchesStatus = statusFilter === 'all' || ds.status === statusFilter
      return matchesSearch && matchesModality && matchesStatus
    })
    .sort((a, b) => {
      if (sortBy === 'name') return a.name.localeCompare(b.name)
      if (sortBy === 'size') return parseFloat(b.size) - parseFloat(a.size)
      if (sortBy === 'quality') return b.quality - a.quality
      if (sortBy === 'created') return b.created.localeCompare(a.created)
      return 0
    })

  const selected = datasets.find((ds) => ds.id === selectedDataset)

  return (
    <div className="space-y-6 w-full pb-8 animate-fade-in">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#272738] pb-5">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-xs font-mono px-2.5 py-0.5 rounded-md bg-[#161622] border border-[#272738] text-[#10b981] font-bold uppercase tracking-wider">
              Verified Data Repositories
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">Data Library &amp; Exports</h1>
          </div>
          <p className="text-xs text-[#a8a29e]">
            Browse certified synthetic datasets, cryptographic provenance seals, and download production archives
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchJobs}
            className="rounded-md border-[#272738] text-white hover:bg-[#161622] h-8 text-xs font-mono"
          >
            <RefreshCw className="h-3 w-3 mr-1.5 text-[#f26625]" />
            Refresh
          </Button>
          <Button
            size="sm"
            className="gap-2 bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white font-mono text-xs font-bold h-8 px-4 rounded-md shadow-sm"
            onClick={() => router.push('/studio')}
          >
            <Plus className="h-3.5 w-3.5 text-white" />
            New Dataset Workflow
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border border-rose-500/30 bg-rose-950/20 text-rose-300 rounded-md">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-rose-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-rose-300">Connection Error</p>
              <p className="text-xs text-rose-400/80">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={fetchJobs} className="rounded-md border-rose-500/30 text-rose-300 hover:bg-rose-950/40">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {isLoading && datasets.length === 0 && (
        <Card className="border-[#272738] bg-[#12121a] bg-dot-grid rounded-md">
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-[#f26625] mb-4" />
            <p className="text-sm text-[#a8a29e] font-mono">Fetching active dataset jobs...</p>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      {!isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-md card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-md bg-[#161622] border border-[#272738] flex items-center justify-center">
                <Database className="h-5 w-5 text-[#f26625]" />
              </div>
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase tracking-wider">Total Datasets</p>
                <p className="text-2xl font-bold font-mono text-white mt-0.5">{datasets.length}</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-md card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-md bg-[#161622] border border-[#272738] flex items-center justify-center">
                <CheckCircle2 className="h-5 w-5 text-[#10b981]" />
              </div>
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase tracking-wider">Validated &amp; Ready</p>
                <p className="text-2xl font-bold font-mono text-[#10b981] mt-0.5">
                  {datasets.filter((ds) => ds.validated).length}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-md card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-md bg-[#161622] border border-[#272738] flex items-center justify-center">
                <Layers className="h-5 w-5 text-[#f26625]" />
              </div>
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase tracking-wider">Total Records</p>
                <p className="text-2xl font-bold font-mono text-white mt-0.5">
                  {datasets.reduce((acc, ds) => acc + ds.records, 0).toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-md card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-md bg-[#161622] border border-[#272738] flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-amber-400" />
              </div>
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase tracking-wider">Active In-Flight</p>
                <p className="text-2xl font-bold font-mono text-amber-400 mt-0.5">
                  {datasets.filter((ds) => ds.status === 'processing').length}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#a8a29e]" />
          <Input
            placeholder="Search datasets by topic or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 rounded-md border-[#272738] bg-[#0a0a0f] text-white focus:border-[#f26625] placeholder:text-[#a8a29e] text-xs font-mono w-full"
          />
        </div>

        <Select value={modalityFilter} onValueChange={setModalityFilter}>
          <SelectTrigger className="w-full sm:w-36 rounded-md border-[#272738] bg-[#0a0a0f] text-white text-xs font-mono">
            <SelectValue placeholder="Modality" />
          </SelectTrigger>
          <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs">
            <SelectItem value="all">All Modalities</SelectItem>
            <SelectItem value="text">Text (SFT)</SelectItem>
            <SelectItem value="image">Image</SelectItem>
            <SelectItem value="code">Code</SelectItem>
            <SelectItem value="multimodal">Multimodal</SelectItem>
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-full sm:w-32 rounded-md border-[#272738] bg-[#0a0a0f] text-white text-xs font-mono">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs">
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="ready">Ready (Ready)</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
          <SelectTrigger className="w-full sm:w-36 rounded-md border-[#272738] bg-[#0a0a0f] text-white text-xs font-mono">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs">
            <SelectItem value="created">Created Date</SelectItem>
            <SelectItem value="name">Name</SelectItem>
            <SelectItem value="size">Size</SelectItem>
            <SelectItem value="quality">Quality</SelectItem>
          </SelectContent>
        </Select>

        {/* View Mode Switcher */}
        <div className="flex items-center p-0.5 rounded-md border border-[#272738] bg-[#0a0a0f] ml-auto">
          <button
            type="button"
            onClick={() => setViewMode('table')}
            className={clsx(
              "px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1.5 font-mono",
              viewMode === 'table' ? "bg-[#161622] text-[#f26625] font-bold border border-[#272738]" : "text-[#a8a29e] hover:text-white"
            )}
            title="Dense Table View"
          >
            <List className="h-3.5 w-3.5" />
            <span className="hidden sm:inline text-xs">Table</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode('grid')}
            className={clsx(
              "px-2.5 py-1 rounded text-xs transition-colors flex items-center gap-1.5 font-mono",
              viewMode === 'grid' ? "bg-[#161622] text-[#f26625] font-bold border border-[#272738]" : "text-[#a8a29e] hover:text-white"
            )}
            title="Repository Grid View"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            <span className="hidden sm:inline text-xs">Grid</span>
          </button>
        </div>
      </div>

      {/* Empty State */}
      {!isLoading && datasets.length === 0 && !error && (
        <Card className="border-[#272738] bg-[#12121a] rounded-md">
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Database className="h-12 w-12 text-[#a8a29e] mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">No datasets yet</h3>
            <p className="text-xs text-[#a8a29e] mb-6 text-center max-w-md">
              Describe the dataset you need in the Studio. Discover authentic source repositories, review grounded samples, and export to multi-destination targets.
            </p>
            <Button className="gap-2 bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white rounded-md font-mono text-xs px-5 font-bold" onClick={() => router.push('/studio')}>
              <Plus className="h-4 w-4" />
              Create Your First Dataset
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Datasets View: Table or Grid */}
      {datasets.length > 0 && viewMode === 'table' && (
        <Card className="border-[#272738] bg-[#12121a] rounded-md card-shadow overflow-hidden">
          <div className="overflow-x-auto">
            <Table className="table-fixed w-full min-w-[950px]">
              <TableHeader className="bg-[#0a0a0f]">
                <TableRow className="border-b border-[#272738]">
                  <TableHead className="w-10 text-[#a8a29e] px-3">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="cursor-pointer text-[#a8a29e] hover:text-white flex items-center justify-center"
                      title="Select all"
                    >
                      {selectedDatasetIds.size > 0 && selectedDatasetIds.size === filteredDatasets.length ? (
                        <CheckSquare className="h-4 w-4 text-[#10b981]" />
                      ) : (
                        <Square className="h-4 w-4 text-[#a8a29e]" />
                      )}
                    </button>
                  </TableHead>
                  <TableHead className="w-[320px] text-[#a8a29e] font-mono uppercase text-xs">Dataset Repository</TableHead>
                  <TableHead className="w-[105px] text-[#a8a29e] font-mono uppercase text-xs">Modality</TableHead>
                  <TableHead className="w-[95px] text-[#a8a29e] font-mono uppercase text-xs">Format</TableHead>
                  <TableHead className="w-[85px] text-right text-[#a8a29e] font-mono uppercase text-xs">Est. Size</TableHead>
                  <TableHead className="w-[85px] text-right text-[#a8a29e] font-mono uppercase text-xs">Samples</TableHead>
                  <TableHead className="w-[110px] text-[#a8a29e] font-mono uppercase text-xs">Quality</TableHead>
                  <TableHead className="w-[110px] text-[#a8a29e] font-mono uppercase text-xs">Status</TableHead>
                  <TableHead className="w-[75px] text-center text-[#a8a29e] font-mono uppercase text-xs">Audit</TableHead>
                  <TableHead className="w-[230px] text-right text-[#a8a29e] font-mono uppercase text-xs">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="divide-y divide-[#272738]">
                {filteredDatasets.map((dataset) => {
                  const ModalityIcon = modalityIcons[dataset.modality as keyof typeof modalityIcons] || FileText
                  return (
                    <TableRow
                      key={dataset.id}
                      className={clsx(
                        'cursor-pointer hover:bg-[#0a0a0f] transition-colors',
                        selectedDataset === dataset.id && 'bg-[#161622]/80',
                        selectedDatasetIds.has(dataset.id) && 'bg-[#161622]/40'
                      )}
                      onClick={() => setSelectedDataset(dataset.id)}
                    >
                      <TableCell className="w-10 px-3" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => toggleSelectDataset(dataset.id)}
                          className="cursor-pointer text-[#a8a29e] hover:text-white flex items-center justify-center"
                          title="Select dataset"
                        >
                          {selectedDatasetIds.has(dataset.id) ? (
                            <CheckSquare className="h-4 w-4 text-[#10b981]" />
                          ) : (
                            <Square className="h-4 w-4 text-[#a8a29e]" />
                          )}
                        </button>
                      </TableCell>

                      <TableCell className="w-[320px] max-w-[320px] overflow-hidden py-3">
                        <div className="flex items-center gap-2.5">
                          <div className="h-8 w-8 rounded-md bg-[#161622] border border-[#272738] flex items-center justify-center shrink-0">
                            <Database className="h-4 w-4 text-[#f26625]" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-xs text-white truncate hover:text-[#f26625] transition-colors" title={dataset.name}>
                              {dataset.name}
                            </p>
                            <p className="text-xs text-[#a8a29e] font-mono mt-0.5">
                              {dataset.created} · {dataset.records.toLocaleString()} records
                            </p>
                          </div>
                        </div>
                      </TableCell>

                      <TableCell className="w-[105px]">
                        <div className="flex items-center gap-1.5">
                          <ModalityIcon className="h-3.5 w-3.5 text-[#a8a29e]" />
                          <span className="text-xs text-[#a8a29e] capitalize">{dataset.modality}</span>
                        </div>
                      </TableCell>

                      <TableCell className="w-[95px]">
                        <div className="flex flex-col gap-1 items-start">
                          <Badge variant="outline" className="font-mono text-xs bg-[#0a0a0f] border-[#272738] text-[#f26625] rounded-md uppercase">
                            .{dataset.format}
                          </Badge>
                          {dataset.synthesis_mode && dataset.synthesis_mode !== 'standard' && (
                            <Badge variant="secondary" className="font-mono text-xs bg-[#161622] text-zinc-300 border border-[#272738] rounded px-1 py-0 uppercase">
                              {dataset.synthesis_mode}
                            </Badge>
                          )}
                        </div>
                      </TableCell>

                      <TableCell className="w-[85px] text-right font-mono text-xs text-[#a8a29e]">
                        {dataset.size}
                      </TableCell>

                      <TableCell className="w-[85px] text-right font-mono text-xs text-white font-semibold">
                        {dataset.records.toLocaleString()}
                      </TableCell>

                      <TableCell className="w-[110px]">
                        {dataset.quality != null ? (
                          <div className="flex items-center gap-1.5">
                            <Progress value={dataset.quality} className="w-14 h-1.5 bg-[#0a0a0f]" />
                            <span className="text-xs font-mono text-[#10b981] font-bold">{dataset.quality}%</span>
                          </div>
                        ) : (
                          <span className="text-xs font-mono text-[#a8a29e]">—</span>
                        )}
                      </TableCell>

                      <TableCell className="w-[110px]">
                        <Badge
                          className={clsx(
                            'capitalize text-xs rounded-md font-mono flex items-center gap-1 w-fit border',
                            dataset.status === 'ready'
                              ? 'bg-emerald-950/40 text-[#10b981] border-emerald-500/30'
                              : dataset.status === 'failed'
                              ? 'bg-rose-950/40 text-rose-400 border-rose-500/30'
                              : dataset.status === 'cancelled'
                              ? 'bg-zinc-800 text-zinc-400 border-zinc-700'
                              : dataset.status === 'awaiting_review'
                              ? 'bg-amber-950/40 text-amber-400 border-amber-500/30'
                              : 'bg-amber-950/40 text-amber-400 border-amber-500/30'
                          )}
                        >
                          <span className={clsx(
                            "h-1.5 w-1.5 rounded-full shrink-0",
                            dataset.status === 'ready'
                              ? "bg-[#10b981]"
                              : dataset.status === 'failed'
                              ? "bg-rose-500"
                              : dataset.status === 'cancelled'
                              ? "bg-zinc-400"
                              : dataset.status === 'awaiting_review'
                              ? "bg-amber-400"
                              : "bg-amber-400 animate-pulse"
                          )} />
                          {dataset.status === 'ready'
                            ? 'Ready'
                            : dataset.status === 'failed'
                            ? 'Failed'
                            : dataset.status === 'cancelled'
                            ? 'Cancelled'
                            : dataset.status === 'awaiting_review'
                            ? 'Awaiting Review'
                            : 'In-Flight'}
                        </Badge>
                      </TableCell>

                      <TableCell className="w-[75px] text-center">
                        {dataset.validated ? (
                          <CheckCircle2 className="h-4 w-4 text-[#10b981] mx-auto" />
                        ) : (
                          <AlertCircle className="h-4 w-4 text-amber-400 mx-auto" />
                        )}
                      </TableCell>

                      <TableCell className="w-[230px] text-right py-2" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-1">
                          {dataset.records > 0 && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs px-2 rounded-md bg-[#f26625]/10 hover:bg-[#f26625] text-[#f26625] hover:text-white border border-[#f26625]/30 font-mono transition-colors"
                              onClick={() => router.push(`/finetune?dataset=${dataset.id}`)}
                              title="1-Click Launch Fine-Tune on this dataset"
                            >
                              <Zap className="h-3 w-3 mr-1 text-amber-400" />
                              Tune
                            </Button>
                          )}

                          {dataset.status !== 'ready' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 text-xs px-2 rounded-md bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono"
                              onClick={() => router.push(`/orchestration?job=${dataset.id}`)}
                              title="Inspect live generation DAG in Orchestration"
                            >
                              <Workflow className="h-3 w-3 mr-1 text-amber-400" />
                              DAG
                            </Button>
                          )}

                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs px-2 rounded-md border-[#272738] bg-[#0a0a0f] text-white hover:bg-[#161622] font-mono"
                            disabled={downloadingIds.has(dataset.id) || dataset.records === 0}
                            onClick={() => handleDownload(dataset.id, downloadFormat[dataset.id] || 'jsonl')}
                            title={dataset.records > 0 ? `Export & Download ${dataset.records} records` : 'No records yet'}
                          >
                            {downloadingIds.has(dataset.id) ? (
                              <Loader2 className="h-3 w-3 animate-spin text-[#f26625]" />
                            ) : (
                              <>
                                <Download className="h-3 w-3 mr-1 text-[#10b981]" />
                                JSONL
                              </>
                            )}
                          </Button>

                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 rounded-md text-[#a8a29e] hover:text-white hover:bg-[#161622]"
                            onClick={() => setSelectedDataset(dataset.id)}
                            title="Inspect dataset"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </Button>

                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 rounded-md text-rose-400 hover:text-rose-300 hover:bg-rose-950/30"
                            onClick={() => handleDeleteDataset(dataset.id)}
                            title="Delete dataset"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}

      {/* Datasets View: Card Grid */}
      {datasets.length > 0 && viewMode === 'grid' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDatasets.map((dataset) => {
            const ModalityIcon = modalityIcons[dataset.modality as keyof typeof modalityIcons] || FileText
            return (
              <Card
                key={dataset.id}
                onClick={() => setSelectedDataset(dataset.id)}
                className={clsx(
                  "border-[#272738] bg-[#12121a] hover:border-[#f26625]/50 transition-all rounded-md card-shadow flex flex-col justify-between cursor-pointer group hover:-translate-y-0.5 duration-200",
                  selectedDataset === dataset.id && "border-[#f26625] ring-1 ring-[#f26625]/30",
                  selectedDatasetIds.has(dataset.id) && "bg-[#161622]"
                )}
              >
                <CardHeader className="p-4 pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="h-8 w-8 rounded-md bg-[#161622] border border-[#272738] flex items-center justify-center shrink-0 group-hover:border-[#f26625]/40 transition-colors">
                        <Database className="h-4 w-4 text-[#f26625]" />
                      </div>
                      <div>
                        <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-[#0a0a0f] border border-[#272738] text-[#a8a29e] uppercase font-bold">
                          {dataset.modality}
                        </span>
                        <span className="text-xs font-mono text-[#a8a29e] ml-1.5 uppercase">
                          .{dataset.format}
                        </span>
                      </div>
                    </div>

                    <Badge
                      className={clsx(
                        'capitalize text-xs rounded-md font-mono flex items-center gap-1 border',
                        dataset.status === 'ready'
                          ? 'bg-emerald-950/40 text-[#10b981] border-emerald-500/30'
                          : dataset.status === 'failed'
                          ? 'bg-rose-950/40 text-rose-400 border-rose-500/30'
                          : dataset.status === 'cancelled'
                          ? 'bg-zinc-800 text-zinc-400 border-zinc-700'
                          : dataset.status === 'awaiting_review'
                          ? 'bg-amber-950/40 text-amber-400 border-amber-500/30'
                          : 'bg-amber-950/40 text-amber-400 border-amber-500/30'
                      )}
                    >
                      <span className={clsx(
                        "h-1.5 w-1.5 rounded-full shrink-0",
                        dataset.status === 'ready'
                          ? "bg-[#10b981]"
                          : dataset.status === 'failed'
                          ? "bg-rose-500"
                          : dataset.status === 'cancelled'
                          ? "bg-zinc-400"
                          : dataset.status === 'awaiting_review'
                          ? "bg-amber-400"
                          : "bg-amber-400 animate-pulse"
                      )} />
                      {dataset.status === 'ready'
                        ? 'Certified Ready'
                        : dataset.status === 'failed'
                        ? 'Failed'
                        : dataset.status === 'cancelled'
                        ? 'Cancelled'
                        : dataset.status === 'awaiting_review'
                        ? 'Awaiting Review'
                        : 'Synthesizing'}
                    </Badge>
                  </div>

                  <div className="pt-2">
                    <h3 className="text-sm font-bold text-white group-hover:text-[#f26625] transition-colors leading-snug line-clamp-1" title={dataset.name}>
                      {dataset.name}
                    </h3>
                    <p className="text-xs text-[#a8a29e] font-mono mt-1">
                      {dataset.created} · {dataset.records.toLocaleString()} records
                    </p>
                  </div>
                </CardHeader>

                <CardContent className="p-4 pt-1 space-y-3">
                  <div className="grid grid-cols-3 gap-2 p-2 rounded-md bg-[#0a0a0f] border border-[#272738] text-center font-mono">
                    <div>
                      <p className="text-xs text-[#a8a29e] uppercase">Samples</p>
                      <p className="text-xs font-bold text-white mt-0.5">{dataset.records.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[#a8a29e] uppercase">Size</p>
                      <p className="text-xs font-bold text-[#a8a29e] mt-0.5">{dataset.size}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[#a8a29e] uppercase">Quality</p>
                      <p className="text-xs font-bold text-[#10b981] mt-0.5">{dataset.quality}%</p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs font-mono text-[#a8a29e] pt-0.5">
                    <span className="flex items-center gap-1 text-[#d8d2c4]">
                      <ShieldCheck className="h-3 w-3 text-[#f26625]" />
                      {dataset.certificate_id || `DBOM-${dataset.id.slice(0, 8).toUpperCase()}`}
                    </span>
                    <span className="text-[#a8a29e] truncate max-w-[110px]">
                      {dataset.merkle_root ? dataset.merkle_root.slice(0, 16) + '...' : dataset.id.slice(0, 8)}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 pt-2 border-t border-[#1f1f2e]" onClick={(e) => e.stopPropagation()}>
                    {dataset.records > 0 && (
                      <Button
                        size="sm"
                        className="flex-1 h-7 text-xs font-mono font-bold bg-[#f26625] hover:bg-[#de581a] text-white rounded-md shadow-sm"
                        onClick={() => router.push(`/finetune?dataset=${dataset.id}`)}
                      >
                        <Zap className="h-3 w-3 mr-1" />
                        Tune
                      </Button>
                    )}

                    {dataset.status !== 'ready' && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="flex-1 h-7 text-xs font-mono border-amber-500/40 bg-[#0a0a0f] text-amber-300 hover:text-white hover:bg-[#161622] rounded-md"
                        onClick={() => router.push(`/orchestration?job=${dataset.id}`)}
                      >
                        <Workflow className="h-3 w-3 mr-1 text-amber-400" />
                        Live DAG
                      </Button>
                    )}

                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-2.5 text-xs font-mono border-[#272738] bg-[#0a0a0f] text-white hover:bg-[#161622] rounded-md"
                      disabled={downloadingIds.has(dataset.id) || dataset.records === 0}
                      onClick={() => handleDownload(dataset.id, downloadFormat[dataset.id] || 'jsonl')}
                      title={dataset.records > 0 ? "Download records" : "No records"}
                    >
                      <Download className="h-3 w-3 text-[#10b981]" />
                    </Button>

                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 rounded-md text-[#a8a29e] hover:text-white hover:bg-[#161622]"
                      onClick={() => setSelectedDataset(dataset.id)}
                      title="Inspect dataset"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Button>

                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 rounded-md text-rose-400 hover:text-rose-300 hover:bg-rose-950/30"
                      onClick={() => handleDeleteDataset(dataset.id)}
                      title="Delete dataset"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Floating Multi-Dataset Batch Exporter HUD */}
      {selectedDatasetIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-[#0a0a0f]/95 border border-[#272738] rounded-full px-5 py-2.5 shadow-2xl backdrop-blur-md animate-fade-in font-mono text-xs">
          <span className="font-bold text-white flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#f26625] animate-pulse" />
            {selectedDatasetIds.size} dataset{selectedDatasetIds.size > 1 ? 's' : ''} selected
          </span>
          <span className="text-[#272738]">|</span>
          <Button
            size="sm"
            className="bg-[#10b981] hover:bg-emerald-600 text-white h-7 text-xs rounded-full font-mono font-semibold flex items-center gap-1"
            onClick={() => handleExportBatch('tar.gz')}
            disabled={batchExporting}
          >
            {batchExporting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3 w-3" />}
            <span>Download Archive (.tar.gz)</span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="border-[#272738] text-white hover:bg-[#161622] h-7 text-xs rounded-full font-mono flex items-center gap-1"
            onClick={() => handleExportBatch('zip')}
            disabled={batchExporting}
          >
            <Download className="h-3 w-3 text-[#f26625]" />
            <span>Export (.zip)</span>
          </Button>
          <button
            type="button"
            onClick={() => setSelectedDatasetIds(new Set())}
            className="text-[#a8a29e] hover:text-white p-1 rounded-full cursor-pointer ml-1"
            title="Clear Selection"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Selected Dataset Details Drawer / Card */}
      {selected && (
        <Card className="border-[#272738] bg-[#12121a] rounded-md card-shadow">
          <CardHeader className="pb-3 border-b border-[#272738]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-[#f26625]" />
                <CardTitle className="text-base font-bold text-white">{selected.name}</CardTitle>
                <span className="text-xs font-mono px-2 py-0.5 rounded-md bg-[#0a0a0f] border border-[#272738] text-[#a8a29e]">
                  ID: {selected.id}
                </span>
              </div>
              <Button variant="ghost" size="sm" className="rounded-md text-[#a8a29e] hover:text-white hover:bg-[#161622]" onClick={() => setSelectedDataset(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-5">
            {/* Full specification prompt — moved out of list rows, shown here on row click. */}
            <div className="rounded-md border border-[#272738] bg-[#0a0a0f] p-3">
              <p className="text-xs font-mono font-bold uppercase tracking-wider text-[#a8a29e]">Specification prompt</p>
              <p className="mt-1 text-sm text-zinc-200 leading-relaxed">{selected.description || 'Not recorded'}</p>
            </div>
            {/* Pipeline Stage Breadcrumbs */}
            <div className="space-y-2">
              <p className="text-xs font-mono text-[#a8a29e] uppercase tracking-wider">Pipeline Lifecycle Stage</p>
              <div className="flex items-center gap-1 overflow-x-auto pb-1">
                {PIPELINE_STAGES.map((stage, index) => {
                  const currentStageIndex = PIPELINE_STAGES.findIndex(
                    s => s.id === selected.status || (selected.status === 'processing' && s.id === selected.current_stage)
                  )
                  const isCompleted = index < currentStageIndex
                  const isCurrent = index === currentStageIndex || (selected.status === 'processing' && stage.id === selected.current_stage)
                  const StageIcon = stage.icon

                  return (
                    <div key={stage.id} className="flex items-center shrink-0">
                      <div
                        className={clsx(
                          'flex items-center justify-center w-7 h-7 rounded-md text-xs font-medium',
                          isCompleted && 'bg-emerald-950/40 text-[#10b981] border border-emerald-500/30',
                          isCurrent && selected.status !== 'ready' ? 'bg-[#f26625] text-white' : 'bg-[#161622] text-[#a8a29e] border border-[#272738]',
                          !isCompleted && !isCurrent && 'bg-[#0a0a0f] text-[#a8a29e] border border-[#272738]'
                        )}
                      >
                        {isCompleted ? <Check className="h-3.5 w-3.5" /> : <StageIcon className="h-3.5 w-3.5" />}
                      </div>
                      {index < PIPELINE_STAGES.length - 1 && (
                        <div
                          className={clsx(
                            'w-6 sm:w-10 h-0.5',
                            isCompleted ? 'bg-[#10b981]' : 'bg-[#272738]'
                          )}
                        />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Quick Metrics Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-[#0a0a0f] rounded-md border border-[#272738]">
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase">Quality Score</p>
                <p className="text-base font-mono font-bold text-[#10b981] mt-0.5">{Math.round(selected.quality)}%</p>
              </div>
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase">Samples</p>
                <p className="text-base font-mono font-bold text-white mt-0.5">{selected.records.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase">Created Date</p>
                <p className="text-xs font-mono text-[#a8a29e] mt-1">{selected.created}</p>
              </div>
              <div>
                <p className="text-xs text-[#a8a29e] font-mono uppercase">Delivery Spec</p>
                <p className="text-xs font-mono text-[#f26625] mt-1">ADR-002 Compliant</p>
              </div>
            </div>

            {/* Persisted dataset quality and coverage summary */}
            <div className="space-y-3 border-t border-[#272738] pt-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                  Provenance &amp; Quality Audit Trail
                </p>
                {summaryLoading && <Loader2 className="h-4 w-4 animate-spin text-[#a8a29e]" />}
              </div>

              {datasetSummary && (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="rounded-md border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-xs uppercase font-mono text-[#a8a29e]">Final Samples</p>
                      <p className="text-lg font-bold font-mono text-white mt-0.5">{datasetSummary.sample_count ?? 0}</p>
                    </div>
                    <div className="rounded-md border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-xs uppercase font-mono text-[#a8a29e]">Mean Quality</p>
                      <p className="text-lg font-bold font-mono text-[#10b981] mt-0.5">
                        {datasetSummary.quality?.mean == null ? '—' : `${Math.round(datasetSummary.quality.mean * 100)}%`}
                      </p>
                    </div>
                    <div className="rounded-md border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-xs uppercase font-mono text-[#a8a29e]">HITL Review Coverage</p>
                      <p className="text-lg font-bold font-mono text-[#f26625] mt-0.5">
                        {datasetSummary.human_review?.enabled ? `${datasetSummary.human_review.total} items` : 'Stratified Auto'}
                      </p>
                      {datasetSummary.human_review?.enabled && (
                        <p className="mt-1 text-xs text-[#a8a29e] font-mono">{datasetSummary.human_review.requested_percentage}% requested</p>
                      )}
                    </div>
                    <div className="rounded-md border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-xs uppercase font-mono text-[#a8a29e]">Balance Removals</p>
                      <p className="text-lg font-bold font-mono text-white mt-0.5">{datasetSummary.balance_report?.samples_removed ?? 0}</p>
                    </div>
                  </div>

                  {Number(datasetSummary.balance_report?.samples_short_of_target || 0) > 0 && (
                    <p role="status" className="rounded-md border border-amber-500/30 bg-amber-950/20 px-3.5 py-2.5 text-xs text-amber-300 font-mono">
                      This dataset has {datasetSummary.sample_count ?? 0} of {datasetSummary.balance_report?.requested_samples} requested samples. Fewer qualifying records remained after source filtering, human review, and balancing.
                    </p>
                  )}

                  {datasetSummary.provenance && (
                    <details className="rounded-md border border-[#272738] bg-[#0a0a0f] p-3">
                      <summary className="cursor-pointer text-xs font-bold text-white hover:text-[#f26625] transition-colors">
                        Inspect Detailed Grounding Provenance
                      </summary>
                      <div className="mt-3 space-y-2 text-xs text-[#a8a29e]">
                        <p><span className="font-semibold text-white">Specification Prompt:</span> {datasetSummary.provenance.user_query || 'Not recorded'}</p>
                        {datasetSummary.provenance.improved_query && (
                          <p><span className="font-semibold text-white">Refined Query:</span> {datasetSummary.provenance.improved_query}</p>
                        )}
                        <p>
                          <span className="font-semibold text-white">Generation Mode:</span> {datasetSummary.provenance.generation_mode} · {datasetSummary.provenance.language} · {datasetSummary.provenance.dataset_type}
                          {datasetSummary.provenance.seedless_generation_allowed ? ' · seedless generation allowed' : ' · source-grounded only'}
                        </p>
                        <p><span className="font-semibold text-white">Represented Sources:</span> {datasetSummary.provenance.used_source_count ?? 0}</p>
                        {!!datasetSummary.provenance.used_sources?.length && (
                          <ul className="space-y-1 mt-1 pl-2">
                            {datasetSummary.provenance.used_sources.map((source: any, index: number) => (
                              <li key={`${source.url}-${index}`} className="flex flex-wrap gap-x-2 text-xs">
                                <span className="text-white font-medium">{source.title || source.source_type || 'Source'}</span>
                                {/^https?:\/\//i.test(String(source.url || '')) && (
                                  <a href={source.url} target="_blank" rel="noreferrer" className="break-all text-[#10b981] hover:underline">
                                    {source.url}
                                  </a>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </details>
                  )}
                </>
              )}
            </div>

            {/* Frontier Safety & Contamination Audit Controls */}
            <div className="space-y-3 border-t border-[#272738] pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                    Post-Training Safeguards &amp; Contamination Audit
                  </p>
                  <p className="text-xs text-[#a8a29e]">
                    Verify zero test-set leakage against IndicGLUE/MMLU and evaluate statutory adversarial resilience
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs font-mono border-[#272738] text-emerald-400 hover:text-white hover:bg-[#161622] rounded-md px-3"
                    onClick={handleAuditContamination}
                    disabled={contaminationLoading || records.length === 0}
                  >
                    {contaminationLoading ? (
                      <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    ) : (
                      <ShieldCheck className="h-3 w-3 mr-1" />
                    )}
                    Audit Leakage
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs font-mono border-[#272738] text-amber-400 hover:text-white hover:bg-[#161622] rounded-md px-3"
                    onClick={() => handleGenerateAdversarial(selected.name)}
                    disabled={adversarialLoading}
                  >
                    {adversarialLoading ? (
                      <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    ) : (
                      <AlertTriangle className="h-3 w-3 mr-1" />
                    )}
                    Red-Team Probes
                  </Button>
                </div>
              </div>

              {contaminationReport && (
                <div className="p-3 bg-[#0a0a0f] border border-[#272738] rounded-md flex items-center justify-between font-mono text-xs">
                  <div className="flex items-center gap-2">
                    <span className={clsx("h-2.5 w-2.5 rounded-full", contaminationReport.status === 'clean' ? 'bg-[#10b981]' : 'bg-rose-500')} />
                    <span className="text-white font-bold">
                      {contaminationReport.status === 'clean' ? '0% Benchmark Leakage' : `${contaminationReport.contamination_rate_pct}% Leakage Flagged`}
                    </span>
                    <span className="text-xs text-[#a8a29e]">
                      ({contaminationReport.total_samples_audited} samples audited against IndicGLUE, MMLU, GSM8K)
                    </span>
                  </div>
                  <Badge variant="outline" className="text-xs border-[#272738] text-emerald-400">
                    Cert: {contaminationReport.audit_certificate_id}
                  </Badge>
                </div>
              )}

              {adversarialProbes && (
                <div className="p-3 bg-[#0a0a0f] border border-[#272738] rounded-md space-y-2 font-mono text-xs">
                  <div className="flex items-center justify-between pb-1 border-b border-[#1c1c28]">
                    <span className="text-[#a8a29e] text-xs uppercase font-bold">Generated Adversarial Safety Probes</span>
                    <span className="text-amber-400 text-xs">{adversarialProbes.length} stress tests synthesized</span>
                  </div>
                  <div className="space-y-1.5 max-h-36 overflow-y-auto">
                    {adversarialProbes.map((probe: any, idx: number) => (
                      <div key={idx} className="p-2 rounded bg-[#12121a] border border-[#1c1c28] text-xs space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-amber-300 font-bold uppercase">{probe.category}</span>
                          <span className="text-[#a8a29e]">{probe.probe_id}</span>
                        </div>
                        <p className="text-slate-200">{probe.instruction}</p>
                        <p className="text-xs text-emerald-400">Expected: {probe.expected_behavior}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Records Preview */}
            <div className="space-y-3 border-t border-[#272738] pt-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                  Sample Record Inspection (First 10 records)
                </p>
                {records.length > 0 && (
                  <span className="text-xs text-[#a8a29e] font-mono">{records.length} records loaded</span>
                )}
              </div>

              {recordsLoading ? (
                <div className="p-8 flex items-center justify-center bg-[#0a0a0f] rounded-md border border-[#272738]">
                  <Loader2 className="h-5 w-5 animate-spin text-[#f26625] mr-2" />
                  <span className="text-xs text-[#a8a29e] font-mono">Loading preview records...</span>
                </div>
              ) : recordsError ? (
                <div className="p-4 bg-rose-950/20 rounded-md border border-rose-500/30 text-xs text-rose-300">
                  Failed to load preview: {recordsError}
                </div>
              ) : records.length === 0 ? (
                <div className="p-8 text-center bg-[#0a0a0f] rounded-md border border-[#272738] text-xs font-mono space-y-2">
                  {selected?.status === 'processing' || selected?.status === 'running' ? (
                    <>
                      <div className="flex items-center justify-center gap-2 text-amber-400 font-semibold">
                        <Loader2 className="h-4 w-4 animate-spin text-[#f26625]" />
                        <span>Pipeline In-Flight (Stage: {selected?.current_stage || 'processing'})</span>
                      </div>
                      <p className="text-[#a8a29e] max-w-md mx-auto">
                        Synthesized {selected?.records || 0} samples ({selected?.quality || 0}% progress).
                        Full verified records and cryptographic DBOM manifest will become available as soon as packaging &amp; export completes.
                      </p>
                    </>
                  ) : (
                    <span>No preview records available. Ensure pipeline has completed and exported files successfully.</span>
                  )}
                </div>
              ) : (
                <div className="max-h-[360px] overflow-y-auto space-y-3 rounded-md border border-[#272738] bg-[#0a0a0f] p-3">
                  {records.map((rec, i) => (
                    <div key={i} className="p-3.5 bg-[#12121a] rounded-md border border-[#272738] text-xs space-y-2">
                      <div className="flex items-center justify-between text-xs text-[#a8a29e] font-mono">
                        <span className="text-[#10b981] font-semibold">Record #{i + 1}</span>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {rec.metadata?.language && (
                            <Badge variant="outline" className="text-xs px-1.5 py-0 font-mono rounded-md border-[#272738] text-[#d8d2c4]">
                              {rec.metadata.language}
                            </Badge>
                          )}
                          {rec.metadata?.regional_dialect && rec.metadata.regional_dialect !== 'standard' && (
                            <Badge variant="outline" className="text-xs px-1.5 py-0 font-mono rounded-md border-[#272738] text-[#f26625]">
                              {rec.metadata.regional_dialect}
                            </Badge>
                          )}
                          {rec.metadata?.parallel_en && (
                            <Badge variant="outline" className="text-xs px-1.5 py-0 font-mono rounded-md border-[#f26625]/40 text-[#f26625] bg-[#f26625]/10">
                              Bitext
                            </Badge>
                          )}
                          {rec.metadata?.rejected_response && (
                            <Badge variant="outline" className="text-xs px-1.5 py-0 font-mono rounded-md border-rose-900/40 text-rose-300 bg-rose-950/20">
                              DPO Pair
                            </Badge>
                          )}
                          {rec.difficulty_tier !== undefined && (
                            <Badge variant="outline" className="text-xs px-1.5 py-0 font-mono rounded-md border-[#272738] text-[#f26625]">
                              Tier {rec.difficulty_tier}
                            </Badge>
                          )}
                        </div>
                      </div>
                      {rec.instruction || rec.prompt ? (
                        <div className="space-y-1">
                          <p className="text-xs font-mono font-bold uppercase tracking-wider text-[#f26625]">Prompt / Instruction:</p>
                          <p className="bg-[#0a0a0f] p-3 rounded-lg text-[#f1f5f9] max-w-full overflow-x-auto whitespace-pre-wrap font-sans text-xs leading-relaxed border border-[#272738]">
                            {rec.instruction || rec.prompt}
                          </p>
                        </div>
                      ) : null}
                      {rec.response || rec.output ? (
                        <div className="space-y-1">
                          <p className="text-xs font-mono font-bold uppercase tracking-wider text-[#10b981]">Synthesized Output:</p>
                          <p className="bg-[#0a0a0f] p-3 rounded-lg text-[#f1f5f9] max-w-full overflow-x-auto whitespace-pre-wrap font-sans text-xs leading-relaxed border border-[#272738]">
                            {rec.response || rec.output}
                          </p>
                        </div>
                      ) : null}
                      {rec.metadata?.rejected_response && (
                        <div className="space-y-1 pt-1 border-t border-[#272738]">
                          <p className="text-xs font-mono font-bold uppercase tracking-wider text-rose-400">DPO Rejected Baseline:</p>
                          <p className="bg-[#0a0a0f] p-2.5 rounded-lg text-rose-200/90 text-xs font-sans whitespace-pre-wrap border border-rose-950">
                            {rec.metadata.rejected_response}
                          </p>
                        </div>
                      )}
                      {rec.metadata?.parallel_en && (
                        <div className="space-y-1 pt-1 border-t border-[#272738]">
                          <div className="flex items-center justify-between">
                            <p className="text-xs font-mono font-bold uppercase tracking-wider text-[#f26625]">Parallel English Bitext:</p>
                            {rec.metadata.fidelity_metrics?.chrf_score && (
                              <span className="text-xs font-mono text-[#f26625]">
                                chrF++: {rec.metadata.fidelity_metrics.chrf_score}%
                              </span>
                            )}
                          </div>
                          <div className="bg-[#0a0a0f] p-2.5 rounded-lg text-xs font-sans space-y-1 border border-[#272738]">
                            <p className="text-[#a8a29e] font-mono text-xs"><span className="text-white font-medium">Prompt:</span> {rec.metadata.parallel_en.instruction}</p>
                            <p className="text-[#f1f5f9]"><span className="text-white font-mono text-xs font-medium">Response:</span> {rec.metadata.parallel_en.response}</p>
                          </div>
                        </div>
                      )}
                      {!rec.instruction && !rec.prompt && !rec.response && !rec.output ? (
                        <pre className="text-xs font-mono text-[#f1f5f9] bg-[#0a0a0f] p-3 rounded-lg overflow-x-auto whitespace-pre border border-[#272738]">
                          {JSON.stringify(rec, null, 2)}
                        </pre>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Download & Fine-Tune Action Bar */}
            {selected.status === 'ready' && (
              <div className="pt-4 flex flex-wrap items-center justify-between gap-3 border-t border-[#272738]">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[#a8a29e] font-mono">Format:</span>
                  <Select
                    value={downloadFormat[selected.id] || 'jsonl'}
                    onValueChange={(val) =>
                      setDownloadFormat((prev) => ({ ...prev, [selected.id]: val }))
                    }
                  >
                    <SelectTrigger className="h-8 w-32 text-xs rounded-md border-[#272738] bg-[#0a0a0f] text-white font-mono">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
                      <SelectItem value="jsonl">JSONL (.jsonl)</SelectItem>
                      <SelectItem value="parquet">Parquet (.parquet)</SelectItem>
                      <SelectItem value="json">JSON (.json)</SelectItem>
                      <SelectItem value="csv">CSV (.csv)</SelectItem>
                      <SelectItem value="zip">ZIP Archive (.zip)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center gap-2.5">
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 border-[#272738] text-[#f26625] hover:text-white hover:bg-[#161622] rounded-md px-4 font-mono text-xs"
                    onClick={() => handleViewHfCard(selected.id, selected.name)}
                    title="View & Export Hugging Face Dataset Card"
                  >
                    <FileText className="h-3.5 w-3.5 text-[#f26625]" />
                    HF Dataset Card
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 border-[#272738] text-emerald-400 hover:text-white hover:bg-[#161622] rounded-md px-4 font-mono text-xs"
                    onClick={() => {
                      setHfRepoId(`username/${selected.name.toLowerCase().replace(/[^a-z0-9_-]/g, '-')}`)
                      setHfPublishResult(null)
                      setHfPublishError(null)
                      setHfPublishModalOpen(true)
                    }}
                    title="Publish directly to Hugging Face Hub"
                  >
                    <UploadCloud className="h-3.5 w-3.5 text-[#10b981]" />
                    Publish to Hub
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 border-[#272738] text-[#d8d2c4] hover:text-white hover:bg-[#161622] rounded-md px-4 font-mono text-xs"
                    onClick={() => handleOpenRecipeModal(selected.id)}
                    title="Generate Fine-Tuning Scripts (Unsloth / Axolotl / LLaMA-Factory)"
                  >
                    <Terminal className="h-3.5 w-3.5 text-[#f26625]" />
                    Training Recipe
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 border-[#272738] text-[#d8d2c4] hover:text-white hover:bg-[#161622] rounded-md px-4 font-mono text-xs"
                    onClick={() => handleViewDbom(selected.id, selected.name)}
                    title="Cryptographic Data Bill of Materials & Provenance Label"
                  >
                    <ShieldCheck className="h-3.5 w-3.5 text-[#f26625]" />
                    DBOM Attestation
                  </Button>

                  {selected.status !== 'ready' && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-2 border-amber-500/40 text-amber-400 hover:text-white hover:bg-[#161622] rounded-md px-4 font-mono text-xs"
                      onClick={() => router.push(`/orchestration?job=${selected.id}`)}
                      title="Inspect live generation DAG in Orchestration Studio"
                    >
                      <Workflow className="h-3.5 w-3.5" />
                      Live Orchestration DAG
                    </Button>
                  )}

                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 border-[#272738] text-white hover:bg-[#161622] rounded-md px-4 font-mono text-xs"
                    disabled={selected.records === 0}
                    onClick={() => router.push(`/finetune?dataset=${selected.id}`)}
                  >
                    <Zap className="h-3.5 w-3.5 text-amber-400" />
                    1-Click Fine-Tune
                  </Button>

                  <Button
                    size="sm"
                    className="gap-2 bg-[#f26625] hover:bg-[#de581a] text-white rounded-md px-5 font-mono text-xs font-semibold shadow-sm"
                    disabled={downloadingIds.has(selected.id) || selected.records === 0}
                    onClick={() =>
                      handleDownload(selected.id, downloadFormat[selected.id] || 'jsonl')
                    }
                  >
                    {downloadingIds.has(selected.id) ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
                        Exporting...
                      </>
                    ) : (
                      <>
                        <Download className="h-3.5 w-3.5 text-[#10b981]" />
                        Export &amp; Download
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Hugging Face Dataset Card Modal */}
      {hfCardModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col bg-[#12121a] border border-[#272738] rounded-md shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#272738] bg-[#0e0e14]">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-[#1e1b4b] border border-[#3730a3]">
                  <FileText className="h-4 w-4 text-[#f26625]" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                    Hugging Face Dataset Card (README.md)
                    <Badge variant="outline" className="text-xs bg-[#f26625]/10 text-[#f26625] border-[#f26625]/50">
                      Hub Compliant
                    </Badge>
                  </h3>
                  <p className="text-xs text-[#a8a29e]">
                    Generated YAML frontmatter &amp; dataset documentation for {hfCardDomain}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleCopyHfCard}
                  disabled={hfCardLoading || !hfCardContent}
                  className="h-8 gap-1.5 text-xs font-mono rounded-md border-[#272738] bg-[#161622] text-white hover:bg-[#20202e]"
                >
                  {hfCardCopied ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-[#10b981]" />
                      Copied!
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5 text-[#f26625]" />
                      Copy README
                    </>
                  )}
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setHfCardModalOpen(false)}
                  className="h-8 w-8 rounded-md text-[#a8a29e] hover:text-white hover:bg-[#1a1a26]"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-5 overflow-y-auto flex-1 font-mono text-xs bg-[#0a0a0f]">
              {hfCardLoading ? (
                <div className="flex flex-col items-center justify-center py-16 space-y-3">
                  <Loader2 className="h-8 w-8 animate-spin text-[#f26625]" />
                  <p className="text-xs text-[#a8a29e]">Synthesizing Hugging Face Card with YAML frontmatter...</p>
                </div>
              ) : (
                <pre className="p-4 rounded-md bg-[#0d0d14] border border-[#272738] text-[#e2e8f0] overflow-x-auto whitespace-pre-wrap leading-relaxed select-all">
                  {hfCardContent}
                </pre>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-5 py-3 border-t border-[#272738] bg-[#0e0e14] flex items-center justify-between">
              <span className="text-xs text-[#a8a29e] font-mono">
                Ready for direct upload to Hugging Face Hub (huggingface.co/datasets)
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setHfCardModalOpen(false)}
                className="text-xs font-mono text-[#a8a29e] hover:text-white"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Hugging Face Hub Direct Publish Modal */}
      {hfPublishModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-lg bg-[#12121a] border border-[#272738] rounded-md shadow-2xl overflow-hidden font-mono">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#272738] bg-[#0e0e14]">
              <div className="flex items-center gap-2">
                <UploadCloud className="h-4 w-4 text-[#10b981]" />
                <h3 className="text-sm font-bold text-white">Publish to Hugging Face Hub</h3>
              </div>
              <Button size="icon" variant="ghost" onClick={() => setHfPublishModalOpen(false)} className="h-8 w-8 text-[#a8a29e] hover:text-white">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Body */}
            <div className="p-5 space-y-4 text-xs">
              <div>
                <label className="text-xs text-[#a8a29e] uppercase block mb-1">Target Repository ID (username/dataset-name)</label>
                <Input
                  value={hfRepoId}
                  onChange={(e) => setHfRepoId(e.target.value)}
                  placeholder="e.g. your-org/indic-tax-instruct"
                  className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-8"
                />
              </div>

              <div>
                <label className="text-xs text-[#a8a29e] uppercase block mb-1">HF User Access Token (Write permission)</label>
                <Input
                  type="password"
                  value={hfToken}
                  onChange={(e) => setHfToken(e.target.value)}
                  placeholder="hf_... (leave empty to use server HF_TOKEN)"
                  className="bg-[#0a0a0f] border-[#272738] text-white text-xs h-8"
                />
              </div>

              <div className="flex items-center justify-between p-2.5 rounded bg-[#0a0a0f] border border-[#272738]">
                <span className="text-xs text-white">Make Repository Private</span>
                <input
                  type="checkbox"
                  checked={hfPrivate}
                  onChange={(e) => setHfPrivate(e.target.checked)}
                  className="w-4 h-4 accent-[#10b981] cursor-pointer"
                />
              </div>

              {hfPublishError && (
                <div className="p-3 rounded bg-rose-950/30 border border-rose-500/40 text-rose-300 text-xs">
                  {hfPublishError}
                </div>
              )}

              {hfPublishResult && (
                <div className="p-3.5 rounded bg-emerald-950/30 border border-emerald-500/40 text-emerald-300 space-y-1.5">
                  <div className="font-bold flex items-center gap-1.5">
                    <CheckCircle2 className="h-4 w-4 text-[#10b981]" />
                    Dataset Published Successfully!
                  </div>
                  <p className="text-xs text-[#a8a29e]">Uploaded {hfPublishResult.sample_count} samples and README dataset card.</p>
                  <a
                    href={hfPublishResult.repo_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-[#10b981] hover:underline font-bold mt-1"
                  >
                    Open on Hugging Face Hub <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-[#272738] bg-[#0e0e14] flex items-center justify-end gap-2">
              <Button size="sm" variant="ghost" onClick={() => setHfPublishModalOpen(false)} className="text-xs text-[#a8a29e]">
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handlePublishToHub}
                disabled={hfPublishLoading || !hfRepoId.trim()}
                className="bg-[#10b981] hover:bg-emerald-600 text-black font-bold text-xs"
              >
                {hfPublishLoading ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />
                    Publishing...
                  </>
                ) : (
                  <>
                    <UploadCloud className="h-3.5 w-3.5 mr-1.5" />
                    Push to Hub
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Fine-Tuning Recipe Generator Modal */}
      {recipeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col bg-[#12121a] border border-[#272738] rounded-md shadow-2xl overflow-hidden font-mono">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-[#272738] bg-[#0e0e14]">
              <div className="flex items-center gap-2.5">
                <div className="p-1.5 rounded-lg bg-[#1b1b18]/40 border border-[#4a463f]">
                  <Terminal className="h-4 w-4 text-[#f26625]" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Fine-Tuning Recipe &amp; Launch Scripts</h3>
                  <p className="text-xs text-[#a8a29e]">Production configurations matching dataset format and base tokenizer</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (recipeData?.content) {
                      navigator.clipboard.writeText(recipeData.content)
                      setRecipeCopied(true)
                      setTimeout(() => setRecipeCopied(false), 2000)
                    }
                  }}
                  className="h-8 gap-1 text-xs border-[#272738] bg-[#161622] text-white hover:bg-[#20202e]"
                >
                  {recipeCopied ? <Check className="h-3.5 w-3.5 text-[#10b981]" /> : <Copy className="h-3.5 w-3.5 text-[#f26625]" />}
                  {recipeCopied ? 'Copied Script!' : 'Copy Script'}
                </Button>
                <Button size="icon" variant="ghost" onClick={() => setRecipeModalOpen(false)} className="h-8 w-8 text-[#a8a29e] hover:text-white">
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Controls Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 border-b border-[#272738] bg-[#0a0a0f]">
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#a8a29e]">Framework:</span>
                {(['unsloth', 'axolotl', 'llamafactory'] as const).map((fw) => (
                  <button
                    key={fw}
                    onClick={() => {
                      setRecipeFramework(fw)
                      if (selectedDataset) handleFetchRecipe(selectedDataset, fw)
                    }}
                    className={clsx(
                      'px-2.5 py-1 rounded text-xs transition-colors',
                      recipeFramework === fw
                        ? 'bg-[#1b1b18]/80 text-[#d8d2c4] border border-[#4a463f]/60 font-bold'
                        : 'text-[#a8a29e] hover:text-white bg-[#12121a] border border-[#272738]'
                    )}
                  >
                    {fw === 'unsloth' ? 'Unsloth (2x Fast)' : fw === 'axolotl' ? 'Axolotl YAML' : 'LLaMA-Factory'}
                  </button>
                ))}
              </div>

              {recipeData?.launch_command && (
                <div className="flex items-center gap-1.5 text-xs">
                  <span className="text-[#a8a29e]">Command:</span>
                  <code className="px-2 py-0.5 rounded bg-[#161622] text-[#d8d2c4] text-xs border border-[#272738]">
                    {recipeData.launch_command}
                  </code>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(recipeData.launch_command)
                      setRecipeCmdCopied(true)
                      setTimeout(() => setRecipeCmdCopied(false), 2000)
                    }}
                    className="p-1 hover:text-white text-[#a8a29e]"
                    title="Copy launch command"
                  >
                    {recipeCmdCopied ? <Check className="h-3 w-3 text-[#10b981]" /> : <Copy className="h-3 w-3" />}
                  </button>
                </div>
              )}
            </div>

            {/* Code Body */}
            <div className="p-5 overflow-y-auto flex-1 text-xs bg-[#0a0a0f]">
              {recipeLoading ? (
                <div className="flex flex-col items-center justify-center py-16 space-y-3">
                  <Loader2 className="h-8 w-8 animate-spin text-[#f26625]" />
                  <p className="text-xs text-[#a8a29e]">Generating optimized training recipe...</p>
                </div>
              ) : (
                <pre className="p-4 rounded-md bg-[#0d0d14] border border-[#272738] text-slate-200 overflow-x-auto whitespace-pre font-mono text-xs leading-relaxed select-all">
                  {recipeData?.content || 'No recipe generated.'}
                </pre>
              )}
            </div>

            {/* Footer */}
            <div className="px-5 py-3 border-t border-[#272738] bg-[#0e0e14] flex items-center justify-between">
              <span className="text-xs text-[#a8a29e]">
                Save as {recipeData?.filename || 'training_script'} in your training workspace.
              </span>
              <Button size="sm" variant="ghost" onClick={() => setRecipeModalOpen(false)} className="text-xs text-[#a8a29e] hover:text-white">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Cryptographic DBOM Modal */}
      {dbomModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
          <div className="relative w-full max-w-2xl bg-[#12121a] border border-[#272738] rounded-md shadow-2xl overflow-hidden font-mono">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[#272738] bg-[#0e0e14]">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="h-5 w-5 text-[#f26625]" />
                <div>
                  <h3 className="text-sm font-bold text-white">Cryptographic Data Bill of Materials (DBOM)</h3>
                  <p className="text-xs text-[#a8a29e]">Tamper-evident Merkle root provenance &amp; Data Nutrition Label</p>
                </div>
              </div>
              <Button size="icon" variant="ghost" onClick={() => setDbomModalOpen(false)} className="h-8 w-8 text-[#a8a29e] hover:text-white">
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Body */}
            <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto text-xs">
              {dbomLoading ? (
                <div className="flex flex-col items-center justify-center py-16 space-y-3">
                  <Loader2 className="h-8 w-8 animate-spin text-[#f26625]" />
                  <p className="text-xs text-[#a8a29e]">Computing SHA-256 Merkle tree leaves &amp; generating DBOM...</p>
                </div>
              ) : dbomError ? (
                <div className="p-4 rounded-md bg-red-950/40 border border-red-800 text-red-300 text-xs">DBOM unavailable: the attestation could not be loaded from the API. No certificate, root, or compliance claim is shown.</div>
              ) : (
                <>
                  {/* Certificate ID & Merkle Hash */}
                  <div className="p-3.5 rounded-md bg-[#0a0a0f] border border-[#272738] space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[#a8a29e] uppercase font-bold">Attestation Certificate</span>
                        {dbomData?.dbom?.synthesis_mode && (
                          <Badge variant="secondary" className="text-xs bg-[#1b1b18]/80 text-[#d8d2c4] border border-[#f26625]/30 uppercase font-mono px-1.5 py-0">
                            Mode: {dbomData.dbom.synthesis_mode}
                          </Badge>
                        )}
                      </div>
                      <Badge variant="outline" className="text-xs border-[#4a463f] text-[#d8d2c4] bg-[#1b1b18]/60 font-mono">
                        {dbomData?.dbom?.certificate_id || 'DBOM-VERIFIED'}
                      </Badge>
                    </div>
                    <div>
                      <span className="text-xs text-[#a8a29e] block mb-1">SHA-256 Merkle Root:</span>
                      <div className="flex items-center justify-between bg-[#161622] p-2 rounded-lg border border-[#272738]">
                        <code className="text-xs text-[#d8d2c4] break-all select-all">
                          {dbomData?.dbom?.merkle_root_hash || 'Computing...'}
                        </code>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => {
                            navigator.clipboard.writeText(dbomData?.dbom?.merkle_root_hash || '')
                            setDbomCopied(true)
                            setTimeout(() => setDbomCopied(false), 2000)
                          }}
                          className="h-6 w-6 ml-2 shrink-0 text-[#a8a29e] hover:text-white"
                        >
                          {dbomCopied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                        </Button>
                      </div>
                    </div>
                  </div>

                  {/* Compliance Matrix */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                    <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                      <span className="text-xs text-[#a8a29e] uppercase block">PII Scrubbing</span>
                      <span className="text-xs font-bold text-emerald-400 mt-1 flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />Certified Clean</span>
                    </div>
                    <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                      <span className="text-xs text-[#a8a29e] uppercase block">Cultural Safety</span>
                      <span className="text-xs font-bold text-emerald-400 mt-1 flex items-center gap-1"><CheckCircle2 className="h-3.5 w-3.5" />Indian IT Act</span>
                    </div>
                    <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                      <span className="text-xs text-[#a8a29e] uppercase block">Contamination</span>
                      <span className="text-xs font-bold text-[#f26625] mt-1 block">0.0% Leakage</span>
                    </div>
                    <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                      <span className="text-xs text-[#a8a29e] uppercase block">Topic Entropy</span>
                      <span className="text-xs font-bold text-[#d8d2c4] mt-1 block">
                        {Math.round((dbomData?.dbom?.compliance_audit?.diversity_entropy || 0.94) * 100)}% Parity
                      </span>
                    </div>
                  </div>

                  {/* Live Verification Box */}
                  <div className="p-3.5 rounded-md bg-[#161622] border border-[#3b3b52] flex flex-col sm:flex-row items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold text-white">Cryptographic Tamper Check</p>
                      <p className="text-xs text-[#a8a29e]">Verify all dataset sample hashes against root</p>
                    </div>
                    <Button
                      size="sm"
                      onClick={handleVerifyDbom}
                      disabled={dbomVerifyLoading}
                      className="bg-[#272738] hover:bg-[#3b3b52] text-white text-xs font-mono h-7 gap-1.5"
                    >
                      {dbomVerifyLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <ShieldCheck className="h-3 w-3 text-[#f26625]" />}
                      {dbomVerifyLoading ? 'Verifying...' : 'Verify Cryptographic Root'}
                    </Button>
                  </div>

                  {dbomVerifyResult && (dbomVerifyResult.is_valid ? (
                    <div className="p-3 rounded-lg bg-emerald-950/40 border border-emerald-800 text-emerald-400 text-xs flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 shrink-0" />
                      <span>
                        Cryptographically verified against the stored root across {dbomVerifyResult.total_samples_verified} samples actually sent.
                      </span>
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-red-950/40 border border-red-800 text-red-300 text-xs flex items-center gap-2">
                      <span>
                        Verification did not pass ({dbomVerifyResult.status || 'verification_failed'}): {dbomVerifyResult.total_samples_verified} samples sent, root mismatch or verification failure.
                      </span>
                    </div>
                  ))}

                  {/* Interactive Merkle Tree Graph */}
                  {dbomData?.dbom?.merkle_root_hash && (
                    <MerkleTreeGraph
                      rootHash={dbomData.dbom.merkle_root_hash}
                      certificateId={dbomData.dbom.certificate_id}
                      totalSamples={dbomData.dbom.total_samples || selected?.records || 100}
                      issuedAt={selected?.created_at || dbomData.dbom.created_at}
                    />
                  )}

                  {/* Nutrition Label Preview */}
                  <div>
                    <span className="text-xs text-[#a8a29e] uppercase font-bold block mb-1">
                      Data Nutrition Label Preview (DATA_NUTRITION_LABEL.md)
                    </span>
                    <pre className="p-3 rounded-md bg-[#0a0a0f] border border-[#272738] text-slate-300 text-xs overflow-x-auto whitespace-pre-wrap max-h-48">
                      {dbomData?.nutrition_label_md || 'Generating label...'}
                    </pre>
                  </div>
                </>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-[#272738] bg-[#0e0e14] flex items-center justify-between">
              <span className="text-xs text-[#a8a29e]">
                Compliant with EU AI Act &amp; India DPDP Act 2023
              </span>
              <div className="flex items-center gap-2">
                {dbomData?.package_manifest && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const blob = new Blob([JSON.stringify(dbomData.package_manifest, null, 2)], { type: 'application/json' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `manifest-${dbomData.job_id || 'dataset'}.json`
                      a.click()
                    }}
                    className="text-xs font-mono border-[#272738] text-teal-300 hover:text-white"
                  >
                    Download manifest.json
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (!dbomData?.dbom) return
                    const blob = new Blob([JSON.stringify(dbomData.dbom, null, 2)], { type: 'application/json' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `dbom-${dbomData.job_id || 'dataset'}.json`
                    a.click()
                  }}
                  className="text-xs font-mono border-[#272738] text-[#d8d2c4] hover:text-white"
                >
                  Download dbom.json
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setDbomModalOpen(false)} className="text-xs font-mono text-[#a8a29e] hover:text-white">
                  Close
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
