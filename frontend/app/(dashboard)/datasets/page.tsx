'use client'

import { useState, useEffect, useCallback } from 'react'
import {
  Database,
  Search,
  Filter,
  Download,
  Eye,
  MoreHorizontal,
  Calendar,
  FileText,
  Image,
  Code,
  Layers,
  ChevronDown,
  CheckCircle2,
  AlertCircle,
  X,
  ArrowUpDown,
  Loader2,
  Plus,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useRouter } from 'next/navigation'

// API client import
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
    size: formatSize(job.samples_generated * 1024 * 2), // Rough estimate
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
          setRecordsError(null)
          const data = await api.getJobRecords(selectedDataset, 10)
          setRecords(data.records || [])
        } catch (e: any) {
          console.error('Failed to fetch dataset records:', e)
          setRecordsError(e.message || 'Failed to fetch records')
        } finally {
          setRecordsLoading(false)
        }
      }
      fetchRecords()
    } else {
      setRecords([])
    }
  }, [selectedDataset])

  // Fetch jobs from API
  const fetchJobs = useCallback(async () => {
    try {
      setError(null)

      // Check health first
      try {
        const health = await api.getHealth()
        setHealthStatus(health as HealthStatus)
      } catch (e) {
        console.warn('Health check failed:', e)
      }

      // Fetch jobs
      const response = await api.getJobs({ limit: 50 })
      const jobs = response.data || []

      // Convert jobs to datasets for display
      const mappedDatasets = jobs.map(jobToDataset)
      setDatasets(mappedDatasets)
    } catch (err: any) {
      console.error('Failed to fetch jobs:', err)
      setError(err.message || 'Failed to load datasets')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Initial fetch and polling
  useEffect(() => {
    fetchJobs()

    // Poll for updates every 10 seconds
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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dataset Explorer</h1>
          <p className="text-sm text-muted-foreground">
            Browse, validate, and export generated datasets
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" className="gap-2" onClick={() => router.push('/studio')}>
            <Plus className="h-4 w-4" />
            New Dataset
          </Button>
        </div>
      </div>

      {/* Error State */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <div className="flex-1">
              <p className="text-sm font-medium">Connection Error</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
            <Button variant="outline" size="sm" onClick={fetchJobs}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Loading State */}
      {isLoading && datasets.length === 0 && (
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-accent mb-4" />
            <p className="text-sm text-muted-foreground">Loading datasets...</p>
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      {!isLoading && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center">
                <Database className="h-5 w-5 text-accent" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total Datasets</p>
                <p className="text-xl font-semibold">{datasets.length}</p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-lg bg-success/10 flex items-center justify-center">
                <CheckCircle2 className="h-5 w-5 text-success" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Validated</p>
                <p className="text-xl font-semibold">
                  {datasets.filter((ds) => ds.validated).length}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-lg bg-info/10 flex items-center justify-center">
                <Layers className="h-5 w-5 text-info" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total Records</p>
                <p className="text-xl font-semibold">
                  {datasets.reduce((acc, ds) => acc + ds.records, 0).toLocaleString()}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 flex items-center gap-4">
              <div className="h-10 w-10 rounded-lg bg-warning/10 flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-warning" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Processing</p>
                <p className="text-xl font-semibold">
                  {datasets.filter((ds) => ds.status === 'processing').length}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search datasets..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select value={modalityFilter} onValueChange={setModalityFilter}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Modality" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Modalities</SelectItem>
            <SelectItem value="text">Text</SelectItem>
            <SelectItem value="image">Image</SelectItem>
            <SelectItem value="code">Code</SelectItem>
            <SelectItem value="multimodal">Multimodal</SelectItem>
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="ready">Ready</SelectItem>
            <SelectItem value="processing">Processing</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v: any) => setSortBy(v)}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Sort by" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="created">Created Date</SelectItem>
            <SelectItem value="name">Name</SelectItem>
            <SelectItem value="size">Size</SelectItem>
            <SelectItem value="quality">Quality</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Empty State */}
      {!isLoading && datasets.length === 0 && !error && (
        <Card>
          <CardContent className="p-12 flex flex-col items-center justify-center">
            <Database className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">No datasets yet</h3>
            <p className="text-sm text-muted-foreground mb-6 text-center max-w-md">
              Create your first dataset by describing what you need in the Studio.
              The AI will autonomously generate high-quality training data.
            </p>
            <Button className="gap-2" onClick={() => router.push('/studio')}>
              <Plus className="h-4 w-4" />
              Create Your First Dataset
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Dataset Table */}
      {datasets.length > 0 && (
      <Card>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[300px]">Dataset</TableHead>
              <TableHead>Modality</TableHead>
              <TableHead>Format</TableHead>
              <TableHead className="text-right">Size</TableHead>
              <TableHead className="text-right">Records</TableHead>
              <TableHead>Quality</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Validated</TableHead>
              <TableHead className="w-[200px] text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredDatasets.map((dataset) => {
              const ModalityIcon = modalityIcons[dataset.modality as keyof typeof modalityIcons] || FileText
              return (
                <TableRow
                  key={dataset.id}
                  className={clsx(
                    'cursor-pointer',
                    selectedDataset === dataset.id && 'bg-accent/5'
                  )}
                  onClick={() => setSelectedDataset(dataset.id)}
                >
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded bg-surface flex items-center justify-center">
                        <Database className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="font-medium">{dataset.name}</p>
                        <p className="text-xs text-muted-foreground">{dataset.id}</p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5">
                      <ModalityIcon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm capitalize">{dataset.modality}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {dataset.format}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {dataset.size}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {dataset.records.toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Progress value={dataset.quality} className="w-16 h-1.5" />
                      <span className="text-sm font-mono">{dataset.quality}%</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        dataset.status === 'ready' ? 'success' : 'secondary'
                      }
                      className="capitalize"
                    >
                      {dataset.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {dataset.validated ? (
                      <CheckCircle2 className="h-4 w-4 text-success" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-warning" />
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 justify-end">
                      {/* View button - expands preview panel */}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedDataset(dataset.id)
                        }}
                        title="View dataset details and records preview"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      {/* Format selector dropdown */}
                      <Select
                        value={downloadFormat[dataset.id] || 'jsonl'}
                        onValueChange={(val) =>
                          setDownloadFormat((prev) => ({ ...prev, [dataset.id]: val }))
                        }
                      >
                        <SelectTrigger className="h-8 w-[68px] text-xs px-2">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="json">JSON</SelectItem>
                          <SelectItem value="jsonl">JSONL</SelectItem>
                        </SelectContent>
                      </Select>
                      {/* Download button with loading spinner */}
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 gap-1 text-xs px-2"
                        disabled={downloadingIds.has(dataset.id) || dataset.status !== 'ready'}
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDownload(dataset.id, downloadFormat[dataset.id] || 'jsonl')
                        }}
                      >
                        {downloadingIds.has(dataset.id) ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Download className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </Card>
      )}

      {/* Selected Dataset Details */}
      {selected && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">{selected.name}</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setSelectedDataset(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Pipeline Stages */}
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">Pipeline Progress</p>
                <div className="flex items-center gap-1">
                  {PIPELINE_STAGES.map((stage, index) => {
                    const currentStageIndex = PIPELINE_STAGES.findIndex(
                      s => s.id === selected.status || (selected.status === 'processing' && s.id === selected.current_stage)
                    )
                    const isCompleted = index < currentStageIndex
                    const isCurrent = index === currentStageIndex || (selected.status === 'processing' && stage.id === selected.current_stage)

                    return (
                      <div key={stage.id} className="flex items-center">
                        <div
                          className={clsx(
                            'flex items-center justify-center w-8 h-8 rounded-full text-xs font-medium',
                            isCompleted && 'bg-success/20 text-success',
                            isCurrent && selected.status !== 'ready' ? 'bg-accent/20 text-accent' : 'bg-surface text-muted-foreground',
                            !isCompleted && !isCurrent && 'bg-surface text-muted-foreground'
                          )}
                        >
                          {isCompleted ? '✓' : stage.icon}
                        </div>
                        {index < PIPELINE_STAGES.length - 1 && (
                          <div
                            className={clsx(
                              'w-8 h-0.5',
                              isCompleted ? 'bg-success/30' : 'bg-border'
                            )}
                          />
                        )}
                      </div>
                    )
                  })}
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Start</span>
                  <span>Complete</span>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-4 gap-4">
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Progress</p>
                  <p className="text-sm font-mono">{Math.round(selected.quality)}%</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Samples</p>
                  <p className="text-sm font-mono">{selected.records.toLocaleString()}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Created</p>
                  <p className="text-sm">{selected.created}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">ID</p>
                  <p className="text-sm font-mono text-xs">{selected.id.slice(0, 12)}...</p>
                </div>
              </div>

              {/* Tags */}
              {selected.tags.length > 0 && (
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Tags</p>
                  <div className="flex flex-wrap gap-1">
                    {selected.tags.map((tag: string) => (
                      <Badge key={tag} variant="secondary" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Records Preview */}
              <div className="space-y-2 border-t pt-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold">Dataset Records Preview (First 10 records)</p>
                  {records.length > 0 && (
                    <span className="text-xs text-muted-foreground">{records.length} records retrieved</span>
                  )}
                </div>

                {recordsLoading ? (
                  <div className="p-8 flex items-center justify-center bg-surface/50 rounded border border-dashed">
                    <Loader2 className="h-5 w-5 animate-spin text-accent mr-2" />
                    <span className="text-xs text-muted-foreground">Loading preview records...</span>
                  </div>
                ) : recordsError ? (
                  <div className="p-4 bg-destructive/10 rounded border border-destructive/20 text-xs text-destructive">
                    Failed to load preview: {recordsError}
                  </div>
                ) : records.length === 0 ? (
                  <div className="p-8 text-center bg-surface/50 rounded border border-dashed text-xs text-muted-foreground">
                    No preview records available. Ensure pipeline has completed and exported files successfully.
                  </div>
                ) : (
                  <div className="max-h-[350px] overflow-y-auto space-y-3 rounded-lg border bg-surface/30 p-3">
                    {records.map((rec, i) => (
                      <div key={i} className="p-3 bg-surface rounded border text-xs space-y-2 hover:border-accent/40 transition">
                        <div className="flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                          <span>Record #{i + 1}</span>
                          {rec.difficulty_tier !== undefined && (
                            <Badge variant="outline" className="text-[9px] px-1 py-0 font-mono">
                              Tier {rec.difficulty_tier}
                            </Badge>
                          )}
                        </div>
                        {rec.instruction || rec.prompt ? (
                          <div className="space-y-1">
                            <p className="font-semibold text-accent">Prompt / Instruction:</p>
                            <p className="bg-surface/80 p-2 rounded text-muted-foreground max-w-full overflow-x-auto whitespace-pre-wrap font-sans leading-relaxed">
                              {rec.instruction || rec.prompt}
                            </p>
                          </div>
                        ) : null}
                        {rec.response || rec.output ? (
                          <div className="space-y-1">
                            <p className="font-semibold text-success">Response / Output:</p>
                            <p className="bg-surface/80 p-2 rounded text-muted-foreground max-w-full overflow-x-auto whitespace-pre-wrap font-sans leading-relaxed">
                              {rec.response || rec.output}
                            </p>
                          </div>
                        ) : null}
                        {!rec.instruction && !rec.prompt && !rec.response && !rec.output ? (
                          <pre className="text-[11px] font-mono text-muted-foreground bg-surface/80 p-2 rounded overflow-x-auto whitespace-pre">
                            {JSON.stringify(rec, null, 2)}
                          </pre>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Download Action with format selector */}
              {selected.status === 'ready' && (
                <div className="pt-4 flex items-center justify-end gap-2">
                  <div className="flex items-center gap-2 mr-auto">
                    <span className="text-xs text-muted-foreground">Download as:</span>
                    <Select
                      value={downloadFormat[selected.id] || 'jsonl'}
                      onValueChange={(val) =>
                        setDownloadFormat((prev) => ({ ...prev, [selected.id]: val }))
                      }
                    >
                      <SelectTrigger className="h-8 w-28 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="json">JSON (.json)</SelectItem>
                        <SelectItem value="jsonl">JSONL (.jsonl)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button
                    size="sm"
                    className="gap-2 bg-success hover:bg-success/90 text-white"
                    disabled={downloadingIds.has(selected.id)}
                    onClick={() =>
                      handleDownload(selected.id, downloadFormat[selected.id] || 'jsonl')
                    }
                  >
                    {downloadingIds.has(selected.id) ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Downloading...
                      </>
                    ) : (
                      <>
                        <Download className="h-4 w-4" />
                        Download Dataset
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
