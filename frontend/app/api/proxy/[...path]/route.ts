import { NextRequest, NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'
export const maxDuration = 60

// Server-side backend URL (never exposed to browser)
const BACKEND_URL = (
  process.env.BACKEND_API_URL ||
  process.env.HF_SPACE_URL ||
  'https://sourabh-kumar04-rasosynthtune.hf.space'
).replace(/\/$/, '')

// Server-side private Hugging Face token (never exposed to browser)
const HF_TOKEN = process.env.HF_TOKEN || process.env.HUGGINGFACE_TOKEN || process.env.HF_API_KEY || ''

type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'DELETE'

interface AllowlistRule {
  pattern: RegExp
  methods: HttpMethod[]
}

// Strict allowlist derived directly from frontend/lib/api/client.ts call sites
const ALLOWLIST: AllowlistRule[] = [
  // Health & System
  { pattern: /^health$/, methods: ['GET'] },
  { pattern: /^health\/ready$/, methods: ['GET'] },
  { pattern: /^health\/providers\/metrics$/, methods: ['GET'] },
  { pattern: /^health\/circuit-breakers$/, methods: ['GET'] },

  // Auth & CSRF
  { pattern: /^auth\/csrf-token$/, methods: ['GET'] },
  { pattern: /^auth\/login$/, methods: ['POST'] },
  { pattern: /^auth\/me$/, methods: ['GET'] },
  { pattern: /^auth\/logout$/, methods: ['POST'] },

  // Jobs
  { pattern: /^jobs$/, methods: ['GET', 'POST'] },
  { pattern: /^jobs\/estimate$/, methods: ['POST'] },
  { pattern: /^jobs\/preview$/, methods: ['POST'] },
  { pattern: /^jobs\/preview\/batch$/, methods: ['POST'] },
  { pattern: /^jobs\/plan$/, methods: ['POST'] },
  { pattern: /^jobs\/[^/]+$/, methods: ['GET', 'DELETE'] },
  { pattern: /^jobs\/[^/]+\/cancel$/, methods: ['POST'] },
  { pattern: /^jobs\/[^/]+\/preview_samples$/, methods: ['GET'] },
  { pattern: /^jobs\/[^/]+\/accept_preview$/, methods: ['POST'] },
  { pattern: /^jobs\/[^/]+\/reject_preview$/, methods: ['POST'] },
  { pattern: /^jobs\/[^/]+\/report$/, methods: ['GET'] },
  { pattern: /^jobs\/[^/]+\/records$/, methods: ['GET'] },
  { pattern: /^jobs\/[^/]+\/summary$/, methods: ['GET'] },
  { pattern: /^jobs\/[^/]+\/signed-url$/, methods: ['POST'] },

  // Datasets & Deliveries
  { pattern: /^datasets$/, methods: ['GET'] },
  { pattern: /^datasets\/[^/]+$/, methods: ['GET', 'DELETE'] },
  { pattern: /^datasets\/[^/]+\/export$/, methods: ['POST'] },
  { pattern: /^datasets\/[^/]+\/deliver$/, methods: ['POST'] },
  { pattern: /^datasets\/[^/]+\/huggingface-card$/, methods: ['GET'] },
  { pattern: /^datasets\/[^/]+\/publish-huggingface$/, methods: ['POST'] },
  { pattern: /^datasets\/[^/]+\/training-recipe$/, methods: ['GET'] },
  { pattern: /^datasets\/[^/]+\/dbom$/, methods: ['GET'] },
  { pattern: /^deliveries\/[^/]+$/, methods: ['GET'] },

  // Providers & Failover
  { pattern: /^providers$/, methods: ['GET'] },
  { pattern: /^providers\/[^/]+$/, methods: ['GET', 'PATCH'] },
  { pattern: /^providers\/[^/]+\/metrics$/, methods: ['GET'] },
  { pattern: /^providers\/switch$/, methods: ['POST'] },
  { pattern: /^providers\/failover$/, methods: ['POST'] },
  { pattern: /^providers\/techniques$/, methods: ['GET'] },
  { pattern: /^providers\/test$/, methods: ['POST'] },
  { pattern: /^failover\/history$/, methods: ['GET'] },
  { pattern: /^failover\/stats$/, methods: ['GET'] },

  // Metrics & Observability
  { pattern: /^metrics$/, methods: ['GET'] },
  { pattern: /^metrics\/history$/, methods: ['GET'] },
  { pattern: /^traces$/, methods: ['GET'] },
  { pattern: /^traces\/correlation$/, methods: ['GET'] },
  { pattern: /^traces\/[^/]+$/, methods: ['GET'] },
  { pattern: /^cluster\/ray$/, methods: ['GET'] },
  { pattern: /^orchestration\/dag$/, methods: ['GET'] },

  // Settings & Validation
  { pattern: /^settings\/compute$/, methods: ['GET', 'POST'] },
  { pattern: /^validate$/, methods: ['POST'] },
  { pattern: /^validate\/dataset$/, methods: ['POST'] },

  // Checkpoints
  { pattern: /^checkpoints$/, methods: ['POST'] },
  { pattern: /^checkpoints\/[^/]+$/, methods: ['GET'] },
  { pattern: /^checkpoints\/[^/]+\/history$/, methods: ['GET'] },
  { pattern: /^checkpoints\/[^/]+\/restore$/, methods: ['POST'] },

  // Research & Benchmarks & Adaptability & Agent
  { pattern: /^research$/, methods: ['POST'] },
  { pattern: /^research\/status$/, methods: ['GET'] },
  { pattern: /^benchmarks\/quality$/, methods: ['GET'] },
  { pattern: /^benchmarks\/evaluation$/, methods: ['GET'] },
  { pattern: /^adaptability$/, methods: ['POST'] },
  { pattern: /^agent\/analyze-domain$/, methods: ['POST'] },

  // Tools & Analysis
  { pattern: /^tools\/generate-adversarial-probes$/, methods: ['POST'] },
  { pattern: /^tools\/audit-contamination$/, methods: ['POST'] },
  { pattern: /^tools\/evaluate-rubric$/, methods: ['POST'] },
  { pattern: /^tools\/evaluate-rag$/, methods: ['POST'] },
  { pattern: /^tools\/semantic-density$/, methods: ['POST'] },
  { pattern: /^tools\/evaluate-dialogue$/, methods: ['POST'] },
  { pattern: /^tools\/best-of-n$/, methods: ['POST'] },
  { pattern: /^tools\/audit-representation$/, methods: ['POST'] },
  { pattern: /^tools\/verify-dbom$/, methods: ['POST'] },
  { pattern: /^tools\/generate-contrastive-pair$/, methods: ['POST'] },
  { pattern: /^tools\/rebalance-dataset$/, methods: ['POST'] },
  { pattern: /^tools\/generate-dialectic$/, methods: ['POST'] },
  { pattern: /^tools\/calibrate-judge$/, methods: ['POST'] },
  { pattern: /^tools\/evaluate-benchmark$/, methods: ['POST'] },
  { pattern: /^tools\/shard-dataset$/, methods: ['POST'] },

  // Fine-tuning API
  { pattern: /^api\/finetune\/models$/, methods: ['GET'] },
  { pattern: /^api\/finetune\/jobs$/, methods: ['GET', 'POST'] },
  { pattern: /^api\/finetune\/jobs\/[^/]+$/, methods: ['GET', 'DELETE'] },
  { pattern: /^api\/finetune\/jobs\/[^/]+\/logs$/, methods: ['GET'] },
  { pattern: /^api\/finetune\/jobs\/[^/]+\/model_card$/, methods: ['GET'] },
  { pattern: /^api\/finetune\/jobs\/[^/]+\/export_gguf$/, methods: ['POST'] },
  { pattern: /^api\/finetune\/jobs\/[^/]+\/modelfile$/, methods: ['GET'] },

  // Review (HITL) API
  { pattern: /^api\/review\/queue$/, methods: ['GET'] },
  { pattern: /^api\/review\/queue\/[^/]+$/, methods: ['GET'] },
  { pattern: /^api\/review\/queue\/[^/]+\/approve$/, methods: ['POST'] },
  { pattern: /^api\/review\/queue\/[^/]+\/reject$/, methods: ['POST'] },
  { pattern: /^api\/review\/queue\/[^/]+\/edit$/, methods: ['POST'] },
  { pattern: /^api\/review\/queue\/[^/]+\/flag$/, methods: ['POST'] },
  { pattern: /^api\/review\/stats$/, methods: ['GET'] },
  { pattern: /^api\/review\/jobs\/[^/]+\/resume$/, methods: ['POST'] },
  { pattern: /^api\/review\/jobs\/[^/]+\/status$/, methods: ['GET'] },
  { pattern: /^api\/review\/paused$/, methods: ['GET'] },

  // Agents API
  { pattern: /^agents$/, methods: ['GET'] },
  { pattern: /^agents\/stats$/, methods: ['GET'] },

  // Quality Analytics API
  { pattern: /^api\/quality\/overview$/, methods: ['GET'] },
  { pattern: /^api\/quality\/trends$/, methods: ['GET'] },
  { pattern: /^api\/quality\/distributions$/, methods: ['GET'] },
  { pattern: /^api\/quality\/sources$/, methods: ['GET'] },
  { pattern: /^api\/quality\/segmented$/, methods: ['GET'] },
]

function isPathAndMethodAllowed(path: string, method: string): boolean {
  for (const rule of ALLOWLIST) {
    if (rule.pattern.test(path) && rule.methods.includes(method as HttpMethod)) {
      return true
    }
  }
  return false
}

async function handleProxy(req: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = (params.path || []).join('/')
  const method = req.method as HttpMethod

  // Strict allowlist validation
  if (!isPathAndMethodAllowed(path, method)) {
    return NextResponse.json(
      { error: 'Endpoint or method not permitted by proxy allowlist' },
      { status: 403 }
    )
  }

  const search = req.nextUrl.search
  const targetUrl = `${BACKEND_URL}/${path}${search}`
  const isHealthCheck = path === 'health' || path === 'health/ready'

  // Header hygiene: forward only explicitly permitted headers, never cookies or ambient auth
  const headers: Record<string, string> = {}
  
  // Explicitly forward content-type, accept, and correlation headers if present
  const contentType = req.headers.get('content-type')
  if (contentType) headers['content-type'] = contentType

  const accept = req.headers.get('accept')
  if (accept) headers['accept'] = accept

  const correlationId = req.headers.get('x-correlation-id')
  if (correlationId) headers['x-correlation-id'] = correlationId

  const csrfToken = req.headers.get('x-csrf-token')
  if (csrfToken) headers['x-csrf-token'] = csrfToken

  // Explicitly forward backend token attached by client (e.g. from localStorage/sessionStorage)
  const clientAuth = req.headers.get('authorization')
  if (clientAuth && clientAuth.startsWith('Bearer ')) {
    headers['authorization'] = clientAuth
  }

  // If targeting Hugging Face Space and no client auth was provided, securely inject HF_TOKEN
  if (!headers['authorization'] && HF_TOKEN && (BACKEND_URL.includes('hf.space') || BACKEND_URL.includes('huggingface.co'))) {
    headers['authorization'] = `Bearer ${HF_TOKEN}`
  }

  const body = ['GET', 'HEAD'].includes(method) ? undefined : await req.arrayBuffer()

  const timeoutMs = isHealthCheck ? 8000 : 45000
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(targetUrl, {
      method,
      headers,
      body,
      signal: controller.signal,
      // @ts-ignore
      duplex: 'half',
    })
    clearTimeout(timeoutId)

    // Detect Hugging Face Space sleeping or paused state (503 / 504 / 404 / 429)
    const isSleeping = response.status === 503 || response.status === 504 ||
      response.headers.get('x-space-status') === 'sleeping' ||
      response.headers.get('x-space-status') === 'paused'

    if (isSleeping) {
      return NextResponse.json({
        error: 'Backend service unavailable',
        status: 'standby',
        warming_up: true,
      }, {
        status: 503,
        headers: { 'Retry-After': '15' }
      })
    }

    const responseHeaders = new Headers()
    response.headers.forEach((value, key) => {
      const lowerKey = key.toLowerCase()
      if (!['transfer-encoding', 'content-encoding', 'content-length', 'set-cookie'].includes(lowerKey)) {
        responseHeaders.set(key, value)
      }
    })

    return new NextResponse(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    })
  } catch (err: any) {
    clearTimeout(timeoutId)

    return NextResponse.json(
      {
        error: 'Backend service unavailable',
        status: 'unavailable',
      },
      { status: 503, headers: { 'Retry-After': '15' } }
    )
  }
}

export const GET = handleProxy
export const POST = handleProxy
export const PATCH = handleProxy
export const DELETE = handleProxy
