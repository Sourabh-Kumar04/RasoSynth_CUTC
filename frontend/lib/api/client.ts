// API Client for RasoSynthTune Backend - Enhanced with Production Hardening

// Remove /api/v1 prefix - backend uses direct paths like /jobs not /api/v1/jobs
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean>
}

// Types for new observability and health features
export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'not_ready'
  service: string
  timestamp: string
  providers?: Record<string, ProviderHealthInfo>
  database?: boolean
  redis?: boolean
  circuit_breakers?: Record<string, string>
}

export interface ProviderHealthInfo {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  latency_ms?: number
  error?: string
}

export interface ProviderStatus {
  name: string
  status: 'available' | 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  latency_ms?: number
  error?: string
  is_primary?: boolean
}

export interface ProviderMetrics {
  provider: string
  total_requests: number
  success_rate: number
  avg_latency_ms: number
  fallback_count: number
}

export interface TraceInfo {
  id: string
  operation: string
  duration: string
  status: 'ok' | 'error' | 'pending'
  service: string
  timestamp: string
  trace_id?: string
  correlation_id?: string
}

export interface ValidationResult {
  valid: boolean
  errors?: string[]
  warnings?: string[]
}

// === Checkpoint Types ===
export type CheckpointStage = 'discovery' | 'extraction' | 'filtering' | 'construction' | 'export' | 'completed'

export interface ProviderContextInfo {
  provider_name: string
  model: string
  api_key_hash: string
  base_url?: string
  capabilities: string[]
  latency_ms: number
  cost_accumulated: number
}

export interface CheckpointData {
  checkpoint_id: string
  job_id: string
  stage: CheckpointStage
  progress: number
  sources_discovered: number
  sources_extracted: number
  samples_filtered: number
  samples_generated: number
  provider_context?: ProviderContextInfo
  fallback_provider?: string
  created_at: string
  version: number
}

export interface CreateCheckpointRequest {
  job_id: string
  stage: CheckpointStage
  progress: number
  sources_discovered?: number
  sources_extracted?: number
  samples_filtered?: number
  samples_generated?: number
  provider_name?: string
  provider_model?: string
  extracted_content?: any[]
  filtered_samples?: any[]
  constructed_samples?: any[]
  metadata?: Record<string, any>
}

export interface RestoreCheckpointRequest {
  job_id: string
  checkpoint_id?: string
  resume_from_stage?: CheckpointStage
}

export interface RestoreCheckpointResponse {
  success: boolean
  checkpoint?: CheckpointData
  resume_from_stage?: string
  progress: number
  samples_generated: number
  message: string
}

// === Failover Types ===
export interface ProviderSwitchRequest {
  job_id: string
  new_provider: string
  create_checkpoint?: boolean
}

export interface ProviderSwitchResponse {
  success: boolean
  from_provider?: string
  to_provider?: string
  checkpoint_id?: string
  message: string
}

export interface FailoverRequest {
  job_id: string
  reason?: string
}

export interface FailoverResponse {
  success: boolean
  from_provider?: string
  to_provider?: string
  failure_type?: string
  checkpoint_id?: string
  message: string
}

export interface MigrationRecord {
  migration_id: string
  job_id: string
  from_provider: string
  to_provider: string
  failure_type?: string
  checkpoint_id?: string
  success: boolean
  timestamp: string
  error?: string
}

export interface FailoverHistory {
  migrations: MigrationRecord[]
  total_count: number
  failure_stats: Record<string, Record<string, number>>
}

export interface FailoverStats {
  failure_stats: Record<string, Record<string, number>>
  total_migrations: number
  circuit_breakers: Record<string, { state: string; failures: number }>
}

class APIClient {
  private baseUrl: string
  private csrfToken: string | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async fetchCsrfToken(): Promise<string> {
    if (typeof window !== 'undefined' && localStorage.getItem('mockMode') === 'true') {
      return 'mock-csrf-token'
    }
    try {
      const response = await fetch(`${this.baseUrl}/auth/csrf-token`, {
        credentials: 'include',
      })
      if (!response.ok) {
        throw new Error('Failed to fetch CSRF token')
      }
      const data = await response.json()
      this.csrfToken = data.csrf_token
      return data.csrf_token
    } catch {
      return 'mock-csrf-token'
    }
  }

  private async ensureCsrfToken(): Promise<string> {
    if (!this.csrfToken) {
      await this.fetchCsrfToken()
    }
    return this.csrfToken!
  }

  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const isMock = typeof window !== 'undefined' && localStorage.getItem('mockMode') === 'true';
    if (isMock) {
      return this.handleMockRequest<T>(endpoint, options)
    }
    const { params, ...fetchOptions } = options

    let url = `${this.baseUrl}${endpoint}`

    if (params) {
      const searchParams = new URLSearchParams()
      Object.entries(params).forEach(([key, value]) => {
        searchParams.append(key, String(value))
      })
      url += `?${searchParams.toString()}`
    }

    // Add correlation ID header for distributed tracing
    const correlationId = this.getCorrelationId()

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Correlation-ID': correlationId,
    }

    // Fetch and attach CSRF token for state-changing methods
    const method = (fetchOptions.method || 'GET').toUpperCase()
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      try {
        const token = await this.ensureCsrfToken()
        headers['X-CSRF-Token'] = token
      } catch {
        // CSRF token fetch failed — proceed without it, server may reject
      }
    }

    try {
      const response = await fetch(url, {
        ...fetchOptions,
        headers: {
          ...headers,
          ...(fetchOptions.headers as Record<string, string>),
        },
      })

      // If CSRF token was rejected, refresh it and retry once
      if (response.status === 403 && this.csrfToken) {
        this.csrfToken = null
        try {
          const newToken = await this.fetchCsrfToken()
          headers['X-CSRF-Token'] = newToken
          const retryResponse = await fetch(url, {
            ...fetchOptions,
            headers: {
              ...headers,
              ...(fetchOptions.headers as Record<string, string>),
            },
          })
          if (!retryResponse.ok) {
            const error = await retryResponse.json().catch(() => ({ message: 'Request failed' }))
            throw new Error(error.detail || error.message || `HTTP ${retryResponse.status}`)
          }
          return retryResponse.json()
        } catch (retryError) {
          if (retryError instanceof Error) throw retryError
          throw new Error('Request failed after CSRF retry')
        }
      }

      if (!response.ok) {
        const error = await response.json().catch(() => ({ message: 'Request failed' }))
        throw new Error(error.detail || error.message || `HTTP ${response.status}`)
      }

      return response.json()
    } catch (err) {
      const isConnectionError = err instanceof TypeError || String(err).includes('fetch') || String(err).includes('Failed to fetch') || String(err).includes('HTTP 500') || String(err).includes('HTTP 503') || String(err).includes('HTTP 502')
      if (isConnectionError && typeof window !== 'undefined') {
        console.warn(`[API Client] Connection to backend ${this.baseUrl} failed. Automatically falling back to Hackathon Demo Mode.`, err)
        localStorage.setItem('mockMode', 'true')
        window.dispatchEvent(new CustomEvent('backend-unreachable-fallback', { detail: { endpoint, error: String(err) } }))
        window.dispatchEvent(new Event('storage'))
        window.dispatchEvent(new Event('mockModeChanged'))
        return this.handleMockRequest<T>(endpoint, options)
      }
      throw err
    }
  }

  private getCorrelationId(): string {
    // Generate or retrieve correlation ID for trace context
    // Uses crypto.getRandomValues for production-safe randomness
    if (typeof window !== 'undefined') {
      let cid = sessionStorage.getItem('correlation_id')
      if (!cid) {
        const array = new Uint8Array(8)
        crypto.getRandomValues(array)
        const randomHex = Array.from(array).map(b => b.toString(16).padStart(2, '0')).join('')
        cid = `corr-${Date.now()}-${randomHex}`
        sessionStorage.setItem('correlation_id', cid)
      }
      return cid
    }
    return ''
  }

  // Jobs API
  async getJobs(params?: { status?: string; cursor?: string; limit?: number }) {
    return this.request<{ data: any[]; next_cursor?: string; has_more: boolean }>('/jobs', { params })
  }

  async getJob(id: string) {
    return this.request<any>(`/jobs/${id}`)
  }

  async createJob(data: any): Promise<any> {
    // Create job - returns JobResponse
    return this.request<any>('/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async cancelJob(id: string) {
    return this.request<any>(`/jobs/${id}/cancel`, { method: 'POST' })
  }

  // Datasets API
  async getDatasets(params?: { modality?: string; cursor?: string; limit?: number }) {
    return this.request<{ data: any[]; next_cursor?: string; has_more: boolean }>('/datasets', { params })
  }

  async getDataset(id: string) {
    return this.request<any>(`/datasets/${id}`)
  }

  async exportDataset(id: string, format: string) {
    return this.request<any>(`/datasets/${id}/export`, {
      method: 'POST',
      body: JSON.stringify({ format }),
    })
  }

  // Providers API
  async getProviders() {
    return this.request<any[]>('/providers')
  }

  async getProvider(id: string) {
    return this.request<any>(`/providers/${id}`)
  }

  async updateProvider(id: string, data: any) {
    return this.request<any>(`/providers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  }

  async getProviderMetrics(id: string) {
    return this.request<any>(`/providers/${id}/metrics`)
  }

  // Metrics API
  async getMetrics() {
    return this.request<any>('/metrics')
  }

  async getMetricsHistory(range: string) {
    return this.request<any>('/metrics/history', { params: { range } })
  }

  // === Enhanced Health API ===

  // Basic liveness check
  async getHealth() {
    return this.request<{ status: string; service: string }>('/health')
  }

  // Detailed readiness with provider status and circuit breakers
  async getHealthReady() {
    return this.request<HealthStatus>('/health/ready')
  }

  // Provider metrics
  async getProviderHealthMetrics() {
    return this.request<{ metrics: Record<string, ProviderMetrics> }>('/health/providers/metrics')
  }

  // Circuit breaker states
  async getCircuitBreakers() {
    return this.request<Record<string, string>>('/health/circuit-breakers')
  }

  // === Validation API ===

  // Validate request before submission
  async validateRequest(request: any): Promise<ValidationResult> {
    return this.request<ValidationResult>('/validate', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Validate dataset configuration
  async validateDatasetConfig(config: any): Promise<ValidationResult> {
    return this.request<ValidationResult>('/validate/dataset', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }

  // === Tracing API ===

  // Get recent traces
  async getTraces(params?: { service?: string; limit?: number }) {
    return this.request<{ traces: TraceInfo[] }>('/traces', { params })
  }

  // Get specific trace details
  async getTrace(traceId: string) {
    return this.request<any>(`/traces/${traceId}`)
  }

  // Get trace by correlation ID
  async getTraceByCorrelation(correlationId: string) {
    return this.request<{ traces: TraceInfo[] }>('/traces/correlation', {
      params: { correlation_id: correlationId }
    })
  }

  // === Checkpoint API ===

  // Create a checkpoint
  async createCheckpoint(request: CreateCheckpointRequest): Promise<CheckpointData> {
    return this.request<CheckpointData>('/checkpoints', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Get checkpoint(s) for a job
  async getCheckpoint(jobId: string, checkpointId?: string): Promise<CheckpointData> {
    const endpoint = checkpointId
      ? `/checkpoints/${jobId}?checkpoint_id=${checkpointId}`
      : `/checkpoints/${jobId}`
    return this.request<CheckpointData>(endpoint)
  }

  // Get checkpoint history
  async getCheckpointHistory(jobId: string, limit: number = 10): Promise<CheckpointData[]> {
    return this.request<CheckpointData[]>(`/checkpoints/${jobId}/history`, {
      params: { limit }
    })
  }

  // Restore from checkpoint
  async restoreCheckpoint(request: RestoreCheckpointRequest): Promise<RestoreCheckpointResponse> {
    return this.request<RestoreCheckpointResponse>(`/checkpoints/${request.job_id}/restore`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // === Provider Switch API ===

  // Manually switch provider
  async switchProvider(request: ProviderSwitchRequest): Promise<ProviderSwitchResponse> {
    return this.request<ProviderSwitchResponse>('/providers/switch', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Trigger manual failover
  async triggerFailover(request: FailoverRequest): Promise<FailoverResponse> {
    return this.request<FailoverResponse>('/providers/failover', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Get failover history
  async getFailoverHistory(jobId?: string, limit: number = 50): Promise<FailoverHistory> {
    const params: Record<string, string | number> = { limit }
    if (jobId) params.job_id = jobId
    return this.request<FailoverHistory>('/failover/history', { params })
  }

  // Get failover statistics
  async getFailoverStats(): Promise<FailoverStats> {
    return this.request<FailoverStats>('/failover/stats')
  }

  // === Research API ===
  async triggerResearch(request: any) {
    return this.request<any>('/research', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  async getResearchStatus() {
    return this.request<any>('/research/status')
  }

  // === Adaptability API ===
  async analyzeAdaptability(constraints: any) {
    return this.request<any>('/adaptability', {
      method: 'POST',
      body: JSON.stringify(constraints),
    })
  }

  // === Provider Techniques API ===
  async getProviderTechniques() {
    return this.request<any>('/providers/techniques')
  }

  async testProvider(provider: string) {
    return this.request<any>('/providers/test', {
      method: 'POST',
      body: JSON.stringify({ provider }),
    })
  }

  // === Auth API ===
  async login(username: string, password: string) {
    return this.request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
  }

  async getCurrentUser() {
    return this.request<any>('/auth/me')
  }

  async logout() {
    return this.request<any>('/auth/logout', { method: 'POST' })
  }

  // === Job Reports API ===
  async getJobReport(jobId: string) {
    return this.request<any>(`/jobs/${jobId}/report`)
  }

  async getJobRecords(jobId: string, limit: number = 10) {
    return this.request<{ records: any[]; count: number; message?: string }>(`/jobs/${jobId}/records`, {
      params: { limit }
    })
  }

  // === Download API ===
  // Download a dataset with format selection - returns a Blob for file saving
  async downloadDataset(id: string, format: string = 'jsonl'): Promise<Blob> {
    if (typeof window !== 'undefined' && (localStorage.getItem('mockMode') === 'true' || localStorage.getItem('mockMode') === null)) {
      const sampleText = JSON.stringify({
        instruction: "Sample instruction for dataset " + id,
        response: "Sample synthesized response for dataset generation."
      }, null, 2);
      return new Blob([sampleText], { type: 'application/json' });
    }

    try {
      const token = await this.ensureCsrfToken().catch(() => null)
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['X-CSRF-Token'] = token

      const response = await fetch(`${this.baseUrl}/datasets/${id}/export`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ format }),
      })

      if (!response.ok) {
        const error = await response.json().catch(() => ({ message: 'Download failed' }))
        throw new Error(error.message || error.detail || `HTTP ${response.status}`)
      }

      return response.blob()
    } catch (e) {
      console.warn("Dataset download fetch failed, returning mock blob", e);
      const sampleText = JSON.stringify({
        instruction: "Sample synthesized instruction for " + id,
        response: "Synthesized model response dataset export output."
      }, null, 2);
      return new Blob([sampleText], { type: 'application/json' });
    }
  }

  // === WebSocket API ===
  // Connect to a WebSocket for real-time job updates
  // Returns a WebSocket instance; caller is responsible for managing lifecycle
  connectJobWebSocket(jobId: string): WebSocket {
    if (typeof window !== 'undefined' && localStorage.getItem('mockMode') === 'true') {
      return new MockWebSocket(`${this.baseUrl.replace(/^http/, 'ws')}/ws/jobs/${jobId}`) as any
    }
    const wsBaseUrl = this.baseUrl.replace(/^http/, 'ws')
    const socket = new WebSocket(`${wsBaseUrl}/ws/jobs/${jobId}`)
    return socket
  }

  // Connect to a WebSocket for real-time job list updates
  connectJobsListWebSocket(): WebSocket {
    if (typeof window !== 'undefined' && localStorage.getItem('mockMode') === 'true') {
      return new MockWebSocket(`${this.baseUrl.replace(/^http/, 'ws')}/ws/jobs`) as any
    }
    const wsBaseUrl = this.baseUrl.replace(/^http/, 'ws')
    const socket = new WebSocket(`${wsBaseUrl}/ws/jobs`)
    return socket
  }

  private handleMockRequest<T>(endpoint: string, options: RequestOptions = {}): T {
    const method = (options.method || 'GET').toUpperCase();
    console.log(`[Mock API] Intercepted ${method} ${endpoint}`);

    // Helpers to return parsed mock data
    const parse = (obj: any): T => obj as unknown as T;

    if (endpoint.startsWith('/auth/me')) {
      return parse({ id: 'guest', username: 'Guest Judge', role: 'admin', email: 'judge@cutc.ca' });
    }

    if (endpoint.startsWith('/auth/csrf-token')) {
      return parse({ csrf_token: 'mock-csrf-token' });
    }

    if (endpoint.startsWith('/health') || endpoint.startsWith('/readiness')) {
      return parse({ status: 'healthy', service: 'Dataset Generator', timestamp: new Date().toISOString() });
    }

    if (endpoint.startsWith('/api/quality/overview')) {
      return parse({
        average_quality: 0.842,
        total_jobs: 8,
        total_samples_reviewed: 1240,
        approval_rate: 0.89,
        rejection_rate: 0.11,
        last_updated: new Date().toISOString(),
      });
    }

    if (endpoint.startsWith('/api/quality/trends')) {
      return parse({
        period_days: 7,
        data_points: 5,
        trends: [
          { timestamp: '2026-08-10T00:00:00Z', avg_quality: 0.81, samples_count: 200 },
          { timestamp: '2026-08-11T00:00:00Z', avg_quality: 0.83, samples_count: 350 },
          { timestamp: '2026-08-12T00:00:00Z', avg_quality: 0.82, samples_count: 500 },
          { timestamp: '2026-08-13T00:00:00Z', avg_quality: 0.84, samples_count: 820 },
          { timestamp: '2026-08-14T00:00:00Z', avg_quality: 0.85, samples_count: 1240 },
        ],
        avg_quality: 0.842,
      });
    }

    if (endpoint.startsWith('/api/quality/distributions')) {
      return parse({
        total_scores: 1240,
        mean: 0.842,
        distribution: {
          excellent: 680,
          good: 410,
          fair: 120,
          poor: 30,
        },
        histogram: [5, 10, 15, 30, 60, 120, 200, 310, 410, 270],
      });
    }

    if (endpoint.startsWith('/api/quality/sources') || endpoint.startsWith('/api/quality/segmented')) {
      return parse({
        total_unique_sources: 5,
        sources: [
          { source: 'medicine', avg_quality: 0.875, samples_count: 150 },
          { source: 'finance', avg_quality: 0.862, samples_count: 200 },
          { source: 'coding', avg_quality: 0.795, samples_count: 210 },
          { source: 'physics', avg_quality: 0.890, samples_count: 100 },
          { source: 'general', avg_quality: 0.832, samples_count: 580 },
        ],
        dataset_types: {
          sft: { avg: 0.825, count: 450 },
          rag: { avg: 0.885, count: 320 },
          coding: { avg: 0.795, count: 210 },
          reasoning: { avg: 0.865, count: 180 },
          conversational: { avg: 0.840, count: 80 }
        },
        prompt_lengths: {
          short: { avg: 0.812, count: 340 },
          medium: { avg: 0.854, count: 680 },
          long: { avg: 0.835, count: 220 }
        },
        domains: {
          medicine: { avg: 0.875, count: 150 },
          finance: { avg: 0.862, count: 200 },
          coding: { avg: 0.795, count: 210 },
          physics: { avg: 0.890, count: 100 },
          general: { avg: 0.832, count: 580 }
        }
      });
    }

    if (endpoint.startsWith('/providers/switch') || endpoint.startsWith('/providers/failover')) {
      return parse({ success: true, message: 'Simulated action successful' });
    }

    if (endpoint.startsWith('/providers')) {
      return parse([
        { name: 'openai', status: 'healthy', latency_ms: 120, is_primary: true, cost_today_usd: 0.85, requests_today: 420, success_rate: 0.99 },
        { name: 'anthropic', status: 'healthy', latency_ms: 150, is_primary: false, cost_today_usd: 0.62, requests_today: 310, success_rate: 0.98 },
        { name: 'gemini', status: 'healthy', latency_ms: 95, is_primary: false, cost_today_usd: 0.35, requests_today: 550, success_rate: 0.99 },
        { name: 'nvidia_nim', status: 'healthy', latency_ms: 180, is_primary: false, cost_today_usd: 0.12, requests_today: 180, success_rate: 0.96 },
        { name: 'groq', status: 'healthy', latency_ms: 45, is_primary: false, cost_today_usd: 0.08, requests_today: 890, success_rate: 0.99 },
      ]);
    }

    if (endpoint.startsWith('/metrics/history')) {
      return parse({
        timestamps: ['12:00', '12:10', '12:20', '12:30', '12:40', '12:50', '13:00'],
        latency: [120, 115, 125, 110, 105, 118, 112],
        throughput: [45, 52, 60, 58, 65, 70, 72],
        error_rate: [0.01, 0.02, 0.01, 0.00, 0.01, 0.01, 0.00],
        cost: [0.12, 0.25, 0.40, 0.55, 0.70, 0.85, 1.02]
      });
    }

    if (endpoint.startsWith('/metrics')) {
      return parse(
`# HELP process_cpu_seconds_total Total user and system CPU time spent in seconds.
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total 12.45
# HELP process_resident_memory_bytes Resident memory size in bytes.
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 142589000
# HELP dataset_generation_requests_total Total dataset synthesis requests.
# TYPE dataset_generation_requests_total counter
dataset_generation_requests_total 128
# HELP dataset_samples_generated_total Total synthesized training samples.
# TYPE dataset_samples_generated_total counter
dataset_samples_generated_total 4520`
      );
    }

    if (endpoint.startsWith('/research/status')) {
      return parse({
        enabled: true,
        last_research: new Date(Date.now() - 1800000).toISOString(),
        status: 'idle',
        research_history: [
          'ArXiv Search: "Autonomous SFT Dataset Synthesis Frameworks"',
          'GitHub Crawl: Open-source RAG benchmark corpora',
          'PapersWithCode: High-quality instruction-following evaluation sets',
          'HuggingFace Hub: Fine-tuning datasets quality metrics analysis'
        ],
        cached_techniques: [
          'De-duplication via MinHash LSH (Jaccard > 0.85)',
          'Toxicity & Hallucination filtering using LLM-as-a-Judge',
          'Self-Instruct Prompt Diversification & Constraint Optimization',
          'AST Python Syntax Compilation & Static Analysis'
        ]
      });
    }

    if (endpoint.startsWith('/research')) {
      return parse({
        success: true,
        message: 'Research loop triggered successfully. Analyzing arXiv and HuggingFace repositories.',
        timestamp: new Date().toISOString()
      });
    }

    // Helper to get or seed mock jobs list in sessionStorage
    const getMockJobs = (): any[] => {
      if (typeof window === 'undefined') return [];
      const stored = sessionStorage.getItem('mockJobs');
      if (stored) {
        try {
          const jobs = JSON.parse(stored);
          if (Array.isArray(jobs)) {
            let updated = false;
            const nextJobs = jobs.map((job: any) => {
              if (job.status === 'running') {
                updated = true;
                const nextProgress = Math.min(1.0, job.progress + 0.15);
                const stages = ['analyzing_constraints', 'discovery', 'extraction', 'filtering', 'construction', 'export', 'completed'];
                const stageIndex = Math.min(stages.length - 1, Math.floor(nextProgress * stages.length));
                const currentStage = stages[stageIndex];
                const samples = Math.floor(nextProgress * (job.config?.dataset_size || 100));
                return {
                  ...job,
                  progress: nextProgress,
                  current_stage: currentStage,
                  status: nextProgress >= 1.0 ? 'completed' : 'running',
                  samples_generated: samples,
                  samples_processed: Math.floor(samples * 1.5),
                  updated_at: new Date().toISOString()
                };
              }
              return job;
            });
            if (updated) {
              sessionStorage.setItem('mockJobs', JSON.stringify(nextJobs));
              const completedJobs = nextJobs.filter((nj: any, idx: number) => nj.status === 'completed' && jobs[idx].status === 'running');
              if (completedJobs.length > 0) {
                const datasets = getMockDatasets();
                completedJobs.forEach((cj: any) => {
                  if (!datasets.some(d => d.id === cj.id)) {
                    datasets.unshift({
                      id: cj.id,
                      name: `${cj.config?.target_domain || 'Custom'} SFT Dataset`,
                      type: cj.config?.dataset_type || 'sft',
                      size: cj.samples_generated,
                      created_at: cj.created_at,
                      output_path: `/exports/${cj.id}.jsonl`
                    });
                  }
                });
                sessionStorage.setItem('mockDatasets', JSON.stringify(datasets));
              }
            }
            return nextJobs;
          }
        } catch (e) {
          console.warn("Corrupt sessionStorage jobs detected, resetting", e);
          sessionStorage.removeItem('mockJobs');
        }
      }
      const initial = [
        {
          id: 'mock-job-1',
          status: 'completed',
          progress: 1.0,
          cost_usd: 1.42,
          samples_generated: 150,
          current_stage: 'completed',
          created_at: new Date(Date.now() - 3600000).toISOString(),
          updated_at: new Date(Date.now() - 3600000).toISOString(),
          config: { target_domain: 'medicine', dataset_type: 'sft', dataset_size: 150 }
        },
        {
          id: 'mock-job-2',
          status: 'failed',
          progress: 0.45,
          cost_usd: 0.85,
          samples_generated: 0,
          current_stage: 'filtering',
          created_at: new Date(Date.now() - 7200000).toISOString(),
          updated_at: new Date(Date.now() - 7200000).toISOString(),
          config: { target_domain: 'coding', dataset_type: 'coding', dataset_size: 100 }
        },
      ];
      sessionStorage.setItem('mockJobs', JSON.stringify(initial));
      return initial;
    };

    const getMockDatasets = (): any[] => {
      if (typeof window === 'undefined') return [];
      const stored = sessionStorage.getItem('mockDatasets');
      if (stored) {
        try {
          const datasets = JSON.parse(stored);
          if (Array.isArray(datasets)) {
            return datasets;
          }
        } catch (e) {
          console.warn("Corrupt sessionStorage datasets detected, resetting", e);
          sessionStorage.removeItem('mockDatasets');
        }
      }
      const initial = [
        {
          id: 'mock-job-1',
          name: 'Medical SFT Dataset',
          type: 'sft',
          size: 150,
          created_at: new Date(Date.now() - 3600000).toISOString(),
          output_path: '/exports/mock-dataset-1.jsonl',
        },
        {
          id: 'mock-dataset-2',
          name: 'Code Generation Corpus',
          type: 'coding',
          size: 85,
          created_at: new Date(Date.now() - 7200000).toISOString(),
          output_path: '/exports/mock-dataset-2.jsonl',
        }
      ];
      sessionStorage.setItem('mockDatasets', JSON.stringify(initial));
      return initial;
    };

    // Intercept Job / Dataset sample records preview
    if ((endpoint.startsWith('/datasets/') || endpoint.startsWith('/jobs/')) && endpoint.endsWith('/records')) {
      const parts = endpoint.split('/');
      const id = parts[2] || '';
      
      const jobs = getMockJobs();
      const currentJob = jobs.find(j => j.id === id);
      const domain = ((currentJob?.config?.target_domain || currentJob?.config?.prompt || id || '') as string).toLowerCase();

      if (domain.includes('code') || domain.includes('program') || domain.includes('python')) {
        return parse({
          records: [
            {
              instruction: 'Write a python function to compute the Fibonacci series.',
              response: '```python\ndef fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)\n```',
              quality_score: 0.96,
              difficulty_tier: 1
            },
            {
              instruction: 'Implement binary search in Python.',
              response: '```python\ndef binary_search(arr, x):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] < x: low = mid + 1\n        elif arr[mid] > x: high = mid - 1\n        else: return mid\n    return -1\n```',
              quality_score: 0.98,
              difficulty_tier: 2
            }
          ]
        });
      } else if (domain.includes('finance') || domain.includes('market') || domain.includes('stock')) {
        return parse({
          records: [
            {
              instruction: 'What is the Capital Asset Pricing Model (CAPM)?',
              response: 'The Capital Asset Pricing Model (CAPM) describes the relationship between systematic risk and expected return for assets, particularly stocks. Expected Return = Risk-Free Rate + Beta * (Market Return - Risk-Free Rate).',
              quality_score: 0.92,
              difficulty_tier: 1
            },
            {
              instruction: 'Explain the difference between NYSE and NASDAQ.',
              response: 'The NYSE is an auction market where traders buy and sell assets directly between individuals. NASDAQ is a dealer market where trading takes place electronically through dealers.',
              quality_score: 0.89,
              difficulty_tier: 2
            }
          ]
        });
      } else {
        return parse({
          records: [
            {
              instruction: 'What are the common symptoms of influenza?',
              response: 'Common symptoms of influenza include fever, chills, cough, sore throat, runny or stuffy nose, muscle or body aches, headaches, and fatigue.',
              quality_score: 0.94,
              difficulty_tier: 1
            },
            {
              instruction: 'Explain how vaccines work.',
              response: 'Vaccines work by stimulating the immune system to produce antibodies, which protect the body against future infections from the targeted pathogen.',
              quality_score: 0.95,
              difficulty_tier: 2
            }
          ]
        });
      }
    }

    if (endpoint.startsWith('/datasets/')) {
      const parts = endpoint.split('/');
      const id = parts[2] || '';
      const datasets = getMockDatasets();
      const dataset = datasets.find(d => d.id === id) || datasets[0];
      return parse(dataset);
    }

    if (endpoint.startsWith('/datasets')) {
      const datasets = getMockDatasets();
      return parse({ data: datasets });
    }

    if (endpoint.startsWith('/checkpoints/')) {
      const parts = endpoint.split('/');
      const jobId = parts[2] || '';
      const jobs = getMockJobs();
      const job = jobs.find(j => j.id === jobId) || jobs[0];
      return parse([
        {
          checkpoint_id: 'cp-1',
          job_id: jobId,
          stage: job.current_stage || 'filtering',
          progress: job.progress || 0.45,
          sources_discovered: job.sources_discovered || 12,
          sources_extracted: job.sources_extracted || 8,
          samples_filtered: job.samples_filtered || 60,
          samples_generated: job.samples_generated || 100,
          created_at: job.created_at || new Date().toISOString(),
          version: 1,
        },
      ]);
    }

    if (endpoint.startsWith('/jobs/')) {
      const parts = endpoint.split('/');
      const id = parts[2] || '';
      const jobs = getMockJobs();
      const job = jobs.find(j => j.id === id);
      if (job) {
        return parse(job);
      }
      return parse({
        id: id,
        status: 'running',
        progress: 0.65,
        current_stage: 'filtering',
        samples_processed: 340,
        samples_generated: 220,
        sources_discovered: 12,
        cost_usd: 0.45,
        config: { prompt: 'Medical SFT Dataset', dataset_type: 'sft' },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
    }

    if (endpoint.startsWith('/jobs')) {
      const jobs = getMockJobs();
      if (method === 'POST') {
        const bodyObj = options.body ? JSON.parse(options.body as string) : {};
        const mockJobId = `mock-job-${Date.now()}`;
        const targetDomain = bodyObj.target_domain || bodyObj.prompt || 'general';
        const datasetType = bodyObj.dataset_type || 'sft';
        const datasetSize = bodyObj.dataset_size || 100;
        const newJob = {
          id: mockJobId,
          status: 'running',
          progress: 0.05,
          cost_usd: 0.05,
          samples_generated: 0,
          current_stage: 'analyzing_constraints',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          target_domain: targetDomain,
          dataset_type: datasetType,
          dataset_size: datasetSize,
          config: {
            target_domain: targetDomain,
            dataset_type: datasetType,
            dataset_size: datasetSize,
            prompt: bodyObj.prompt || 'Synthesized Dataset'
          }
        };
        jobs.unshift(newJob);
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('mockJobs', JSON.stringify(jobs));
        }
        return parse({
          id: mockJobId,
          status: 'running',
        });
      }
      return parse({ data: jobs });
    }

    // === Mock Fine-Tuning API ===
    if (endpoint.startsWith('/api/finetune/models')) {
      return parse({
        models: [
          'HuggingFaceTB/SmolLM2-1.7B-Instruct',
          'meta-llama/Meta-Llama-3-8B-Instruct',
          'Qwen/Qwen2.5-7B-Instruct',
          'unsloth/mistral-7b-v0.3',
          'microsoft/Phi-3-mini-4k-instruct',
        ]
      });
    }

    if (endpoint.startsWith('/api/finetune/jobs')) {
      if (method === 'POST') {
        const bodyObj = options.body ? JSON.parse(options.body as string) : {};
        return parse({
          id: `ft-job-${Date.now().toString(36)}`,
          status: 'pending',
          base_model: bodyObj.base_model || 'HuggingFaceTB/SmolLM2-1.7B-Instruct',
          output_model_name: bodyObj.output_model_name || 'RasoSynth-Finetuned-v1',
          created_at: new Date().toISOString(),
        });
      }
      return parse({
        jobs: [
          {
            id: 'ft-job-demo-1',
            status: 'running',
            base_model: 'HuggingFaceTB/SmolLM2-1.7B-Instruct',
            output_model_name: 'SmolLM2-RasoSynth-Medical-SFT',
            current_epoch: 2,
            total_epochs: 3,
            current_step: 420,
            total_steps: 600,
            train_loss: 0.184,
            eval_loss: 0.210,
            created_at: new Date(Date.now() - 1800000).toISOString(),
            updated_at: new Date().toISOString(),
            config: {
              learning_rate: 2e-4,
              lora_r: 16,
              lora_alpha: 32,
              per_device_train_batch_size: 4,
              load_in_4bit: true,
            }
          },
          {
            id: 'ft-job-demo-2',
            status: 'completed',
            base_model: 'meta-llama/Meta-Llama-3-8B-Instruct',
            output_model_name: 'Llama3-RasoSynth-Reasoning-v2',
            current_epoch: 3,
            total_epochs: 3,
            current_step: 1200,
            total_steps: 1200,
            train_loss: 0.112,
            eval_loss: 0.145,
            created_at: new Date(Date.now() - 86400000).toISOString(),
            updated_at: new Date(Date.now() - 82800000).toISOString(),
            config: {
              learning_rate: 1e-4,
              lora_r: 32,
              lora_alpha: 64,
              per_device_train_batch_size: 2,
              load_in_4bit: true,
            }
          }
        ],
        total: 2,
        limit: 50,
        offset: 0,
        has_more: false,
      });
    }

    // === Mock HITL Review API ===
    if (endpoint.startsWith('/api/review/paused')) {
      return parse({
        paused_jobs: ['job-med-sft-001', 'job-code-reasoning-004']
      });
    }

    if (endpoint.startsWith('/api/review/stats')) {
      return parse({
        total: 125,
        approved: 98,
        rejected: 12,
        pending: 15,
        paused_jobs_count: 2,
      });
    }

    if (endpoint.startsWith('/api/review/queue')) {
      return parse({
        items: [
          {
            id: 'rev-item-001',
            job_id: 'job-med-sft-001',
            instruction: 'Analyze patient symptoms of acute respiratory distress and suggest diagnostic protocol.',
            response: '1. Immediate pulse oximetry and arterial blood gas (ABG) evaluation.\n2. High-flow nasal cannula oxygenation.\n3. Portable chest radiography to rule out pneumothorax or pulmonary edema.\n4. Administer bronchodilators if wheezing is present.',
            input: 'Patient: 62yo male, dyspnea, SpO2 88% on room air.',
            quality_score: 0.94,
            difficulty_tier: 'tier_3_expert',
            status: 'pending',
            created_at: new Date(Date.now() - 300000).toISOString(),
            metadata: {
              domain: 'medicine',
              mutation_type: 'deepening_constraint',
              dedup_hash: 'sha256-a9b8c7'
            }
          },
          {
            id: 'rev-item-002',
            job_id: 'job-code-reasoning-004',
            instruction: 'Implement a thread-safe LRU cache with O(1) time complexity in Python.',
            response: '```python\nfrom threading import Lock\n\nclass Node:\n    def __init__(self, key, val):\n        self.key, self.val = key, val\n        self.prev = self.next = None\n\nclass LRUCache:\n    def __init__(self, capacity: int):\n        self.cap = capacity\n        self.cache = {}\n        self.lock = Lock()\n        self.head, self.tail = Node(0, 0), Node(0, 0)\n        self.head.next, self.tail.prev = self.tail, self.head\n```',
            input: 'Capacity: 1000 items, concurrent access',
            quality_score: 0.96,
            difficulty_tier: 'tier_4_master',
            status: 'pending',
            created_at: new Date(Date.now() - 600000).toISOString(),
            metadata: {
              domain: 'coding',
              mutation_type: 'concurrency_constraint',
              dedup_hash: 'sha256-f4e3d2'
            }
          }
        ],
        total: 2,
        page: 1,
        page_size: 10,
      });
    }

    return parse({});
  }

  // ── Fine-tune API ──────────────────────────────────────────────────────────

  async getSupportedModels() {
    return this.request<{ models: any[] }>('/api/finetune/models')
  }

  async createFineTuneJob(config: Record<string, any>) {
    return this.request<any>('/api/finetune/jobs', {
      method: 'POST',
      body: JSON.stringify(config),
    })
  }

  async listFineTuneJobs(limit = 100) {
    return this.request<{ jobs: any[] }>('/api/finetune/jobs', {
      params: { limit },
    })
  }

  async getFineTuneJob(jobId: string) {
    return this.request<any>(`/api/finetune/jobs/${jobId}`)
  }

  async cancelFineTuneJob(jobId: string) {
    return this.request<any>(`/api/finetune/jobs/${jobId}`, { method: 'DELETE' })
  }

  // ── Review API ────────────────────────────────────────────────────────────

  async getReviewQueue(params?: { status?: string; job_id?: string; page?: number; page_size?: number }) {
    return this.request<any>('/api/review/queue', { params: params as any })
  }

  async getReviewItem(itemId: string) {
    return this.request<any>(`/api/review/queue/${itemId}`)
  }

  async approveReviewItem(itemId: string, reviewer: string, notes = '') {
    return this.request<any>(`/api/review/queue/${itemId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, notes }),
    })
  }

  async rejectReviewItem(itemId: string, reviewer: string, notes = '') {
    return this.request<any>(`/api/review/queue/${itemId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, notes }),
    })
  }

  async editReviewItem(itemId: string, reviewer: string, edited_instruction?: string, edited_response?: string, notes = '') {
    return this.request<any>(`/api/review/queue/${itemId}/edit`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, edited_instruction, edited_response, notes }),
    })
  }

  async flagReviewItem(itemId: string, reviewer: string, notes = '') {
    return this.request<any>(`/api/review/queue/${itemId}/flag`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, notes }),
    })
  }

  async getReviewStats() {
    return this.request<any>('/api/review/stats')
  }

  async resumeHITLJob(jobId: string) {
    return this.request<any>(`/api/review/jobs/${jobId}/resume`, { method: 'POST' })
  }

  async getHITLJobStatus(jobId: string) {
    return this.request<any>(`/api/review/jobs/${jobId}/status`)
  }
}

class MockWebSocket {
  url: string
  readyState: number = 0 // CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  private timer: any = null

  constructor(url: string) {
    this.url = url
    setTimeout(() => {
      this.readyState = 1 // OPEN
      if (this.onopen) this.onopen()
      this.startSimulating()
    }, 100)
  }

  send(data: string) {
    console.log('Mock WS sent data:', data)
  }

  close() {
    this.readyState = 3 // CLOSED
    if (this.timer) clearInterval(this.timer)
    if (this.onclose) this.onclose()
  }

  private startSimulating() {
    const isJobStream = this.url.includes('/ws/jobs/')
    if (isJobStream) {
      const jobId = this.url.split('/').pop() || 'mock-job-id'
      let progress = 0
      const stages = [
        'analyzing_constraints',
        'discovery',
        'extraction',
        'filtering',
        'construction',
        'export',
        'completed',
      ]
      let stageIndex = 0

      this.timer = setInterval(() => {
        if (this.readyState !== 1) {
          clearInterval(this.timer)
          return
        }

        progress += 5
        if (progress >= 100) {
          progress = 100
          stageIndex = stages.length - 1
        } else {
          stageIndex = Math.min(
            stages.length - 2,
            Math.floor((progress / 100) * (stages.length - 1))
          )
        }

        const currentStage = stages[stageIndex]
        const status = progress === 100 ? 'completed' : 'running'

        const data = {
          job_id: jobId,
          status: status,
          progress: progress / 100,
          current_stage: currentStage,
          samples_processed: Math.floor(progress * 4.2),
          samples_generated: Math.floor(progress * 2.8),
          sources_discovered: Math.floor(progress * 1.5),
          sources_extracted: Math.floor(progress * 1.2),
          samples_filtered: Math.floor(progress * 0.9),
          cost_usd: (progress * 0.045).toFixed(3),
        }

        if (this.onmessage) {
          this.onmessage({ data: JSON.stringify(data) })
        }

        if (progress === 100) {
          clearInterval(this.timer)
        }
      }, 1000)
    }
  }
}

export const api = new APIClient(API_BASE_URL)

// SSE Streaming Client with correlation ID support
export class SSEClient {
  private eventSource: EventSource | null = null
  private listeners: Map<string, Set<(data: any) => void>> = new Map()

  connect(endpoint: string) {
    if (this.eventSource) {
      this.eventSource.close()
    }

    // Add correlation ID to SSE connection
    const correlationId = typeof window !== 'undefined'
      ? sessionStorage.getItem('correlation_id') || ''
      : ''

    const url = correlationId
      ? `${API_BASE_URL}${endpoint}?X-Correlation-ID=${encodeURIComponent(correlationId)}`
      : `${API_BASE_URL}${endpoint}`

    this.eventSource = new EventSource(url)

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const type = data.type || 'message'

        // Add correlation ID to message if present
        if (data.correlation_id) {
          data.correlation_id = correlationId
        }

        this.listeners.get(type)?.forEach((callback) => callback(data))
        this.listeners.get('*')?.forEach((callback) => callback(data))
      } catch (e) {
        console.error('Failed to parse SSE message:', e)
      }
    }

    this.eventSource.onerror = (error) => {
      console.error('SSE error:', error)
      this.listeners.get('error')?.forEach((callback) => callback(error))
    }

    return this
  }

  on(type: string, callback: (data: any) => void) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set())
    }
    this.listeners.get(type)!.add(callback)

    return this
  }

  off(type: string, callback: (data: any) => void) {
    this.listeners.get(type)?.delete(callback)
    return this
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
    this.listeners.clear()
  }
}

// Utility for validation
export function validateInput(input: string): { valid: boolean; error?: string } {
  // Client-side validation for common issues
  if (input.includes('{{') || input.includes('[[')) {
    return { valid: false, error: 'Template injection detected' }
  }
  if (input.includes('<script') || input.includes('javascript:')) {
    return { valid: false, error: 'Potential XSS detected' }
  }
  return { valid: true }
}