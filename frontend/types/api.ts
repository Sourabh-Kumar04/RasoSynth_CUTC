// RasoDataset-Agent - Type Definitions

// ============================================
// Base Types
// ============================================

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type DatasetFormat = 'jsonl' | 'parquet' | 'csv' | 'arrow'
export type DataModality = 'text' | 'image' | 'audio' | 'video' | 'code' | 'multimodal'
export type QualityLevel = 'high' | 'medium' | 'low'
export type ProviderName = 'gemini' | 'nvidia' | 'claude' | 'openai' | 'huggingface' | 'xai' | 'ollama'

// ============================================
// Dataset Types
// ============================================

export interface DatasetMetadata {
  id: string
  name: string
  description: string
  modality: DataModality
  format: DatasetFormat
  size: number
  recordCount: number
  qualityLevel: QualityLevel
  createdAt: string
  updatedAt: string
  tags: string[]
  source: string
  checksum: string
}

export interface DatasetRecord {
  id: string
  data: Record<string, unknown>
  metadata: {
    quality: number
    source: string
    validated: boolean
    processingSteps: string[]
  }
}

export interface DatasetFilter {
  modality?: DataModality
  format?: DatasetFormat
  quality?: QualityLevel
  tags?: string[]
  dateFrom?: string
  dateTo?: string
  search?: string
}

// ============================================
// Job Types
// ============================================

export interface Job {
  id: string
  name: string
  status: JobStatus
  progress: number
  createdAt: string
  updatedAt: string
  startedAt?: string
  completedAt?: string
  estimatedCompletion?: string
  error?: string
  retryCount: number
  maxRetries: number
  dataset?: DatasetMetadata
  config: JobConfig
  metrics: JobMetrics
}

export interface JobConfig {
  modality: DataModality
  targetSize: number
  providers: ProviderName[]
  qualityLevel: QualityLevel
  constraints: Constraint[]
  syntheticAugmentation: boolean
  filteringEnabled: boolean
}

export interface JobMetrics {
  recordsProcessed: number
  recordsGenerated: number
  recordsFiltered: number
  cost: number
  latencyMs: number
  providerCalls: Record<ProviderName, number>
}

export interface JobProgress {
  jobId: string
  stage: string
  progress: number
  recordsProcessed: number
  estimatedCompletion: string
  currentProvider?: ProviderName
  messages: string[]
}

// ============================================
// Constraint Types
// ============================================

export type ConstraintType = 'min_length' | 'max_length' | 'required_fields' | 'quality_threshold' | 'language' | 'topic' | 'format'

export interface Constraint {
  type: ConstraintType
  value: string | number | string[]
  scope: 'global' | 'field' | 'record'
  enabled: boolean
}

// ============================================
// Provider Types
// ============================================

export type ProviderStatus = 'healthy' | 'degraded' | 'unhealthy' | 'disabled'
export type CircuitState = 'closed' | 'open' | 'half_open'

export interface Provider {
  id: ProviderName
  name: string
  status: ProviderStatus
  circuitState: CircuitState
  latencyMs: {
    p50: number
    p95: number
    p99: number
  }
  costPer1k: number
  rateLimit: {
    used: number
    max: number
    resetAt: string
  }
  capabilities: string[]
  models: string[]
  isEnabled: boolean
  healthCheck: {
    lastChecked: string
    successRate: number
  }
}

export interface ProviderMetrics {
  provider: ProviderName
  totalRequests: number
  successfulRequests: number
  failedRequests: number
  avgLatencyMs: number
  cost: number
  errorRate: number
}

// ============================================
// Orchestration Types
// ============================================

export interface WorkflowStep {
  id: string
  name: string
  type: 'discovery' | 'extraction' | 'filtering' | 'construction' | 'export'
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  startedAt?: string
  completedAt?: string
  durationMs?: number
  recordsIn: number
  recordsOut: number
  error?: string
  children?: WorkflowStep[]
}

export interface Workflow {
  id: string
  jobId: string
  steps: WorkflowStep[]
  totalDurationMs: number
  status: JobStatus
  startedAt: string
  completedAt?: string
}

export interface OrchestrationEvent {
  type: 'step_start' | 'step_complete' | 'step_error' | 'progress' | 'provider_call' | 'retry' | 'circuit_open' | 'circuit_close'
  timestamp: string
  jobId: string
  stepId?: string
  data: Record<string, unknown>
}

// ============================================
// Observability Types
// ============================================

export interface MetricPoint {
  timestamp: string
  value: number
}

export interface MetricsSnapshot {
  timestamp: string
  requests: {
    total: number
    success: number
    failed: number
    latencyP50: number
    latencyP95: number
    latencyP99: number
  }
  jobs: {
    pending: number
    running: number
    completed: number
    failed: number
  }
  providers: Record<ProviderName, ProviderMetrics>
  queue: {
    depth: number
    processing: number
    scheduled: number
  }
  system: {
    cpuPercent: number
    memoryPercent: number
    diskPercent: number
  }
}

export interface Trace {
  id: string
  operationName: string
  startTime: string
  endTime: string
  durationMs: number
  status: 'ok' | 'error'
  service: string
  spans: TraceSpan[]
  attributes: Record<string, string>
}

export interface TraceSpan {
  id: string
  name: string
  startTime: string
  durationMs: number
  status: 'ok' | 'error'
  attributes: Record<string, string>
}

// ============================================
// API Response Types
// ============================================

export interface PaginatedResponse<T> {
  data: T[]
  pagination: {
    page: number
    pageSize: number
    total: number
    hasMore: boolean
  }
}

export interface APIError {
  code: string
  message: string
  details?: Record<string, unknown>
}

export interface StreamEvent {
  type: string
  timestamp: string
  data: unknown
}

// ============================================
// UI State Types
// ============================================

export interface SidebarState {
  collapsed: boolean
  activeSection: string
}

export interface CommandPaletteItem {
  id: string
  label: string
  description?: string
  icon?: string
  shortcut?: string
  action: () => void
  category: string
}
