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
  error?: string
}

// Pipeline stages in order
const PIPELINE_STAGES = [
  { id: 'analyzing_constraints', label: 'Analyzing', icon: '🔍' },
  { id: 'discovering_sources', label: 'Discovering', icon: '🌐' },
  { id: 'extracting_content', label: 'Extracting', icon: '📄' },
  { id: 'filtering_quality', label: 'Filtering', icon: '✨' },
  { id: 'constructing_dataset', label: 'Constructing', icon: '🧩' },
  { id: 'exporting', label: 'Exporting', icon: '📤' },
  { id: 'completed', label: 'Complete', icon: '✓' },
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

// Helper to convert backend job to display dataset
function jobToDataset(job: DatasetJob): any {
  const status = job.status === 'completed' ? 'ready' : job.status === 'running' ? 'processing' : job.status
  return {
    id: job.id,
    name: job.target_domain || `Dataset ${job.id.slice(0, 8)}`,
    modality: job.dataset_type || 'text',
    format: job.output_format || 'jsonl',
    size: formatSize(job.samples_generated * 1024 * 2),
    records: job.samples_generated || 0,
    quality: Math.round(job.progress * 100),
    status,
    current_stage: job.current_stage || 'pending',
    created: new Date(job.created_at).toISOString().split('T')[0],
    tags: [job.dataset_type, job.current_stage].filter(Boolean),
    validated: job.status === 'completed',
  }
}

export default function DatasetsPage() {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [modalityFilter, setModalityFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<'name' | 'size' | 'quality' | 'created'>('created')
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
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#161622] border border-[#272738] text-[#10b981] font-bold uppercase tracking-wider">
              Source-Grounded Repositories
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white font-display">Dataset Explorer</h1>
          </div>
          <p className="text-xs text-[#94a3b8]">
            Curated source discovery, quality review, balanced datasets &amp; multi-destination delivery (ADR-002)
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchJobs}
            className="rounded-full border-[#272738] text-white hover:bg-[#161622] h-8 text-xs font-mono"
          >
            <RefreshCw className="h-3 w-3 mr-1.5 text-[#6366f1]" />
            Refresh
          </Button>
          <Button
            size="sm"
            className="gap-2 bg-[#6366f1] hover:bg-[#818cf8] text-white font-mono text-xs font-semibold h-8 px-4 rounded-full shadow-sm glow-indigo"
            onClick={() => router.push('/studio')}
          >
            <Plus className="h-3.5 w-3.5 text-[#10b981]" />
            New Dataset Workflow
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border border-rose-500/30 bg-rose-950/20 text-rose-300 rounded-2xl">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-rose-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-rose-300">Connection Error</p>
              <p className="text-xs text-rose-400/80">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={fetchJobs} className="rounded-full border-rose-500/30 text-rose-300 hover:bg-rose-950/40">
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {isLoading && datasets.length === 0 && (
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl">
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-[#6366f1] mb-4" />
            <p className="text-sm text-[#94a3b8] font-mono">Fetching active dataset jobs...</p>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      {!isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-2xl card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center">
                <Database className="h-5 w-5 text-[#6366f1]" />
              </div>
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase tracking-wider">Total Datasets</p>
                <p className="text-2xl font-bold font-mono text-white mt-0.5">{datasets.length}</p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-2xl card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center">
                <CheckCircle2 className="h-5 w-5 text-[#10b981]" />
              </div>
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase tracking-wider">Validated &amp; Ready</p>
                <p className="text-2xl font-bold font-mono text-[#10b981] mt-0.5">
                  {datasets.filter((ds) => ds.validated).length}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-2xl card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center">
                <Layers className="h-5 w-5 text-indigo-400" />
              </div>
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase tracking-wider">Total Records</p>
                <p className="text-2xl font-bold font-mono text-white mt-0.5">
                  {datasets.reduce((acc, ds) => acc + ds.records, 0).toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-[#272738] bg-[#12121a] hover:border-[#3b3b52] transition-all rounded-2xl card-shadow">
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-amber-400" />
              </div>
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase tracking-wider">Active In-Flight</p>
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
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#94a3b8]" />
          <Input
            placeholder="Search datasets by topic or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10 rounded-full border-[#272738] bg-[#0a0a0f] text-white focus:border-[#6366f1] placeholder:text-[#64748b] text-xs font-mono w-full"
          />
        </div>

        <Select value={modalityFilter} onValueChange={setModalityFilter}>
          <SelectTrigger className="w-full sm:w-36 rounded-full border-[#272738] bg-[#0a0a0f] text-white text-xs font-mono">
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
          <SelectTrigger className="w-full sm:w-32 rounded-full border-[#272738] bg-[#0a0a0f] text-white text-xs font-mono">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs">
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="ready">Ready (Ready)</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
          <SelectTrigger className="w-full sm:w-36 rounded-full border-[#272738] bg-[#0a0a0f] text-white text-xs font-mono">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs">
            <SelectItem value="created">Created Date</SelectItem>
            <SelectItem value="name">Name</SelectItem>
            <SelectItem value="size">Size</SelectItem>
            <SelectItem value="quality">Quality</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Empty State */}
      {!isLoading && datasets.length === 0 && !error && (
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl">
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Database className="h-12 w-12 text-[#64748b] mb-4" />
            <h3 className="text-lg font-bold text-white mb-2">No datasets yet</h3>
            <p className="text-xs text-[#94a3b8] mb-6 text-center max-w-md">
              Describe the dataset you need in the Studio. Discover authentic source repositories, review grounded samples, and export to multi-destination targets.
            </p>
            <Button className="gap-2 bg-[#6366f1] hover:bg-[#818cf8] text-white rounded-full font-mono text-xs px-5" onClick={() => router.push('/studio')}>
              <Plus className="h-4 w-4" />
              Create Your First Dataset
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Dataset Table */}
      {datasets.length > 0 && (
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow overflow-hidden">
          <Table>
            <TableHeader className="bg-[#0a0a0f]">
              <TableRow className="border-b border-[#272738]">
                <TableHead className="w-[300px] text-[#94a3b8] font-mono uppercase text-[10px]">Dataset Repository</TableHead>
                <TableHead className="text-[#94a3b8] font-mono uppercase text-[10px]">Modality</TableHead>
                <TableHead className="text-[#94a3b8] font-mono uppercase text-[10px]">Format</TableHead>
                <TableHead className="text-right text-[#94a3b8] font-mono uppercase text-[10px]">Est. Size</TableHead>
                <TableHead className="text-right text-[#94a3b8] font-mono uppercase text-[10px]">Samples</TableHead>
                <TableHead className="text-[#94a3b8] font-mono uppercase text-[10px]">Quality</TableHead>
                <TableHead className="text-[#94a3b8] font-mono uppercase text-[10px]">Status</TableHead>
                <TableHead className="text-[#94a3b8] font-mono uppercase text-[10px]">Validated</TableHead>
                <TableHead className="w-[240px] text-right text-[#94a3b8] font-mono uppercase text-[10px]">Actions</TableHead>
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
                      selectedDataset === dataset.id && 'bg-[#161622]/80'
                    )}
                    onClick={() => setSelectedDataset(dataset.id)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-xl bg-[#161622] border border-[#272738] flex items-center justify-center shrink-0">
                          <Database className="h-4 w-4 text-[#6366f1]" />
                        </div>
                        <div>
                          <p className="font-semibold text-xs text-white truncate max-w-[220px]">{dataset.name}</p>
                          <p className="text-[10px] text-[#94a3b8] font-mono">{dataset.id.slice(0, 16)}...</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        <ModalityIcon className="h-3.5 w-3.5 text-[#94a3b8]" />
                        <span className="text-xs text-[#94a3b8] capitalize">{dataset.modality}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono text-[10px] bg-[#0a0a0f] border-[#272738] text-indigo-300 rounded-full">
                        {dataset.format}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs text-[#94a3b8]">
                      {dataset.size}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs text-white font-semibold">
                      {dataset.records.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Progress value={dataset.quality} className="w-16 h-1.5 bg-[#0a0a0f]" />
                        <span className="text-xs font-mono text-[#10b981] font-bold">{dataset.quality}%</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={clsx(
                          'capitalize text-[10px] rounded-full font-mono',
                          dataset.status === 'ready'
                            ? 'bg-emerald-950/40 text-[#10b981] border border-emerald-500/30'
                            : 'bg-amber-950/40 text-amber-400 border border-amber-500/30'
                        )}
                      >
                        {dataset.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {dataset.validated ? (
                        <CheckCircle2 className="h-4 w-4 text-[#10b981]" />
                      ) : (
                        <AlertCircle className="h-4 w-4 text-amber-400" />
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5 justify-end" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 rounded-full text-[#94a3b8] hover:text-white hover:bg-[#161622]"
                          onClick={() => setSelectedDataset(dataset.id)}
                          title="View dataset details and records preview"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Select
                          value={downloadFormat[dataset.id] || 'jsonl'}
                          onValueChange={(val) =>
                            setDownloadFormat((prev) => ({ ...prev, [dataset.id]: val }))
                          }
                        >
                          <SelectTrigger className="h-8 w-[76px] text-[11px] px-2 rounded-full border-[#272738] bg-[#0a0a0f] text-white font-mono">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-[#12121a] border-[#272738] text-white text-xs font-mono">
                            <SelectItem value="jsonl">JSONL</SelectItem>
                            <SelectItem value="parquet">Parquet</SelectItem>
                            <SelectItem value="json">JSON</SelectItem>
                            <SelectItem value="csv">CSV</SelectItem>
                            <SelectItem value="zip">ZIP</SelectItem>
                          </SelectContent>
                        </Select>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8 gap-1 text-xs px-2.5 rounded-full border-[#272738] text-white hover:bg-[#161622] hover:border-[#3b3b52]"
                          disabled={downloadingIds.has(dataset.id) || dataset.status !== 'ready'}
                          onClick={() =>
                            handleDownload(dataset.id, downloadFormat[dataset.id] || 'jsonl')
                          }
                          title="Export & Download"
                        >
                          {downloadingIds.has(dataset.id) ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#6366f1]" />
                          ) : (
                            <Download className="h-3.5 w-3.5 text-[#10b981]" />
                          )}
                        </Button>
                        {dataset.status === 'ready' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 text-xs px-2.5 rounded-full text-indigo-400 hover:text-white hover:bg-[#161622] font-mono"
                            onClick={() => router.push(`/finetune?dataset=${dataset.id}`)}
                            title="1-Click Launch Fine-Tune"
                          >
                            <Zap className="h-3.5 w-3.5 text-amber-400 mr-1" />
                            Tune
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Selected Dataset Details Drawer / Card */}
      {selected && (
        <Card className="border-[#272738] bg-[#12121a] rounded-2xl card-shadow">
          <CardHeader className="pb-3 border-b border-[#272738]">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-[#6366f1]" />
                <CardTitle className="text-base font-bold text-white">{selected.name}</CardTitle>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#0a0a0f] border border-[#272738] text-[#94a3b8]">
                  ID: {selected.id}
                </span>
              </div>
              <Button variant="ghost" size="sm" className="rounded-full text-[#94a3b8] hover:text-white hover:bg-[#161622]" onClick={() => setSelectedDataset(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-6 space-y-5">
            {/* Pipeline Stage Breadcrumbs */}
            <div className="space-y-2">
              <p className="text-[10px] font-mono text-[#94a3b8] uppercase tracking-wider">Pipeline Lifecycle Stage</p>
              <div className="flex items-center gap-1 overflow-x-auto pb-1">
                {PIPELINE_STAGES.map((stage, index) => {
                  const currentStageIndex = PIPELINE_STAGES.findIndex(
                    s => s.id === selected.status || (selected.status === 'processing' && s.id === selected.current_stage)
                  )
                  const isCompleted = index < currentStageIndex
                  const isCurrent = index === currentStageIndex || (selected.status === 'processing' && stage.id === selected.current_stage)

                  return (
                    <div key={stage.id} className="flex items-center shrink-0">
                      <div
                        className={clsx(
                          'flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium',
                          isCompleted && 'bg-emerald-950/40 text-[#10b981] border border-emerald-500/30',
                          isCurrent && selected.status !== 'ready' ? 'bg-[#6366f1] text-white' : 'bg-[#161622] text-[#94a3b8] border border-[#272738]',
                          !isCompleted && !isCurrent && 'bg-[#0a0a0f] text-[#64748b] border border-[#272738]'
                        )}
                      >
                        {isCompleted ? '✓' : stage.icon}
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
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-[#0a0a0f] rounded-xl border border-[#272738]">
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase">Quality Score</p>
                <p className="text-base font-mono font-bold text-[#10b981] mt-0.5">{Math.round(selected.quality)}%</p>
              </div>
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase">Samples</p>
                <p className="text-base font-mono font-bold text-white mt-0.5">{selected.records.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase">Created Date</p>
                <p className="text-xs font-mono text-[#94a3b8] mt-1">{selected.created}</p>
              </div>
              <div>
                <p className="text-[10px] text-[#94a3b8] font-mono uppercase">Delivery Spec</p>
                <p className="text-xs font-mono text-indigo-300 mt-1">ADR-002 Compliant</p>
              </div>
            </div>

            {/* Persisted dataset quality and coverage summary */}
            <div className="space-y-3 border-t border-[#272738] pt-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                  Provenance &amp; Quality Audit Trail
                </p>
                {summaryLoading && <Loader2 className="h-4 w-4 animate-spin text-[#94a3b8]" />}
              </div>

              {datasetSummary && (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="rounded-xl border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-[10px] uppercase font-mono text-[#94a3b8]">Final Samples</p>
                      <p className="text-lg font-bold font-mono text-white mt-0.5">{datasetSummary.sample_count ?? 0}</p>
                    </div>
                    <div className="rounded-xl border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-[10px] uppercase font-mono text-[#94a3b8]">Mean Quality</p>
                      <p className="text-lg font-bold font-mono text-[#10b981] mt-0.5">
                        {datasetSummary.quality?.mean == null ? '—' : `${Math.round(datasetSummary.quality.mean * 100)}%`}
                      </p>
                    </div>
                    <div className="rounded-xl border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-[10px] uppercase font-mono text-[#94a3b8]">HITL Review Coverage</p>
                      <p className="text-lg font-bold font-mono text-indigo-300 mt-0.5">
                        {datasetSummary.human_review?.enabled ? `${datasetSummary.human_review.total} items` : 'Stratified Auto'}
                      </p>
                      {datasetSummary.human_review?.enabled && (
                        <p className="mt-1 text-[10px] text-[#94a3b8] font-mono">{datasetSummary.human_review.requested_percentage}% requested</p>
                      )}
                    </div>
                    <div className="rounded-xl border border-[#272738] bg-[#0a0a0f] p-3">
                      <p className="text-[10px] uppercase font-mono text-[#94a3b8]">Balance Removals</p>
                      <p className="text-lg font-bold font-mono text-white mt-0.5">{datasetSummary.balance_report?.samples_removed ?? 0}</p>
                    </div>
                  </div>

                  {Number(datasetSummary.balance_report?.samples_short_of_target || 0) > 0 && (
                    <p role="status" className="rounded-xl border border-amber-500/30 bg-amber-950/20 px-3.5 py-2.5 text-xs text-amber-300 font-mono">
                      This dataset has {datasetSummary.sample_count ?? 0} of {datasetSummary.balance_report?.requested_samples} requested samples. Fewer qualifying records remained after source filtering, human review, and balancing.
                    </p>
                  )}

                  {datasetSummary.provenance && (
                    <details className="rounded-xl border border-[#272738] bg-[#0a0a0f] p-3">
                      <summary className="cursor-pointer text-xs font-bold text-white hover:text-indigo-300 transition-colors">
                        Inspect Detailed Grounding Provenance
                      </summary>
                      <div className="mt-3 space-y-2 text-xs text-[#94a3b8]">
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
                              <li key={`${source.url}-${index}`} className="flex flex-wrap gap-x-2 text-[11px]">
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

            {/* Records Preview */}
            <div className="space-y-3 border-t border-[#272738] pt-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                  Sample Record Inspection (First 10 records)
                </p>
                {records.length > 0 && (
                  <span className="text-xs text-[#94a3b8] font-mono">{records.length} records loaded</span>
                )}
              </div>

              {recordsLoading ? (
                <div className="p-8 flex items-center justify-center bg-[#0a0a0f] rounded-xl border border-[#272738]">
                  <Loader2 className="h-5 w-5 animate-spin text-[#6366f1] mr-2" />
                  <span className="text-xs text-[#94a3b8] font-mono">Loading preview records...</span>
                </div>
              ) : recordsError ? (
                <div className="p-4 bg-rose-950/20 rounded-xl border border-rose-500/30 text-xs text-rose-300">
                  Failed to load preview: {recordsError}
                </div>
              ) : records.length === 0 ? (
                <div className="p-8 text-center bg-[#0a0a0f] rounded-xl border border-[#272738] text-xs text-[#94a3b8] font-mono">
                  No preview records available. Ensure pipeline has completed and exported files successfully.
                </div>
              ) : (
                <div className="max-h-[360px] overflow-y-auto space-y-3 rounded-2xl border border-[#272738] bg-[#0a0a0f] p-3">
                  {records.map((rec, i) => (
                    <div key={i} className="p-3.5 bg-[#12121a] rounded-xl border border-[#272738] text-xs space-y-2">
                      <div className="flex items-center justify-between text-[10px] text-[#94a3b8] font-mono">
                        <span className="text-[#10b981] font-semibold">Record #{i + 1}</span>
                        <div className="flex items-center gap-1.5 flex-wrap">
                          {rec.metadata?.language && (
                            <Badge variant="outline" className="text-[9px] px-1.5 py-0 font-mono rounded-full border-[#272738] text-purple-300">
                              {rec.metadata.language}
                            </Badge>
                          )}
                          {rec.metadata?.regional_dialect && rec.metadata.regional_dialect !== 'standard' && (
                            <Badge variant="outline" className="text-[9px] px-1.5 py-0 font-mono rounded-full border-[#272738] text-indigo-300">
                              {rec.metadata.regional_dialect}
                            </Badge>
                          )}
                          {rec.metadata?.parallel_en && (
                            <Badge variant="outline" className="text-[9px] px-1.5 py-0 font-mono rounded-full border-indigo-900/40 text-indigo-300 bg-indigo-950/20">
                              Bitext
                            </Badge>
                          )}
                          {rec.metadata?.rejected_response && (
                            <Badge variant="outline" className="text-[9px] px-1.5 py-0 font-mono rounded-full border-rose-900/40 text-rose-300 bg-rose-950/20">
                              DPO Pair
                            </Badge>
                          )}
                          {rec.difficulty_tier !== undefined && (
                            <Badge variant="outline" className="text-[9px] px-1.5 py-0 font-mono rounded-full border-[#272738] text-indigo-300">
                              Tier {rec.difficulty_tier}
                            </Badge>
                          )}
                        </div>
                      </div>
                      {rec.instruction || rec.prompt ? (
                        <div className="space-y-1">
                          <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-400">Prompt / Instruction:</p>
                          <p className="bg-[#0a0a0f] p-3 rounded-lg text-[#f1f5f9] max-w-full overflow-x-auto whitespace-pre-wrap font-sans text-xs leading-relaxed border border-[#272738]">
                            {rec.instruction || rec.prompt}
                          </p>
                        </div>
                      ) : null}
                      {rec.response || rec.output ? (
                        <div className="space-y-1">
                          <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#10b981]">Synthesized Output:</p>
                          <p className="bg-[#0a0a0f] p-3 rounded-lg text-[#f1f5f9] max-w-full overflow-x-auto whitespace-pre-wrap font-sans text-xs leading-relaxed border border-[#272738]">
                            {rec.response || rec.output}
                          </p>
                        </div>
                      ) : null}
                      {rec.metadata?.rejected_response && (
                        <div className="space-y-1 pt-1 border-t border-[#272738]">
                          <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-rose-400">DPO Rejected Baseline:</p>
                          <p className="bg-[#0a0a0f] p-2.5 rounded-lg text-rose-200/90 text-xs font-sans whitespace-pre-wrap border border-rose-950">
                            {rec.metadata.rejected_response}
                          </p>
                        </div>
                      )}
                      {rec.metadata?.parallel_en && (
                        <div className="space-y-1 pt-1 border-t border-[#272738]">
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-indigo-400">Parallel English Bitext:</p>
                            {rec.metadata.fidelity_metrics?.chrf_score && (
                              <span className="text-[9px] font-mono text-indigo-300">
                                chrF++: {rec.metadata.fidelity_metrics.chrf_score}%
                              </span>
                            )}
                          </div>
                          <div className="bg-[#0a0a0f] p-2.5 rounded-lg text-xs font-sans space-y-1 border border-[#272738]">
                            <p className="text-[#94a3b8] font-mono text-[11px]"><span className="text-white font-medium">Prompt:</span> {rec.metadata.parallel_en.instruction}</p>
                            <p className="text-[#f1f5f9]"><span className="text-white font-mono text-[11px] font-medium">Response:</span> {rec.metadata.parallel_en.response}</p>
                          </div>
                        </div>
                      )}
                      {!rec.instruction && !rec.prompt && !rec.response && !rec.output ? (
                        <pre className="text-[11px] font-mono text-[#f1f5f9] bg-[#0a0a0f] p-3 rounded-lg overflow-x-auto whitespace-pre border border-[#272738]">
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
                  <span className="text-xs text-[#94a3b8] font-mono">Format:</span>
                  <Select
                    value={downloadFormat[selected.id] || 'jsonl'}
                    onValueChange={(val) =>
                      setDownloadFormat((prev) => ({ ...prev, [selected.id]: val }))
                    }
                  >
                    <SelectTrigger className="h-8 w-32 text-xs rounded-full border-[#272738] bg-[#0a0a0f] text-white font-mono">
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
                    className="gap-2 border-[#272738] text-white hover:bg-[#161622] rounded-full px-4 font-mono text-xs"
                    onClick={() => router.push(`/finetune?dataset=${selected.id}`)}
                  >
                    <Zap className="h-3.5 w-3.5 text-amber-400" />
                    1-Click Fine-Tune
                  </Button>

                  <Button
                    size="sm"
                    className="gap-2 bg-[#6366f1] hover:bg-[#818cf8] text-white rounded-full px-5 font-mono text-xs font-semibold shadow-sm glow-indigo"
                    disabled={downloadingIds.has(selected.id)}
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
    </div>
  )
}
