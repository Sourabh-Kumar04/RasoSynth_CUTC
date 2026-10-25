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

async function handleProxy(req: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = (params.path || []).join('/')
  const search = req.nextUrl.search
  const targetUrl = `${BACKEND_URL}/${path}${search}`
  const isHealthCheck = path === 'health' || path === 'health/ready'

  const headers: Record<string, string> = {}
  req.headers.forEach((value, key) => {
    const lowerKey = key.toLowerCase()
    if (!['host', 'connection', 'content-length'].includes(lowerKey)) {
      headers[lowerKey] = value
    }
  })

  // Securely inject private HF_TOKEN on server-side without exposing to browser
  if (HF_TOKEN && (BACKEND_URL.includes('hf.space') || BACKEND_URL.includes('huggingface.co'))) {
    if (!headers['authorization']) {
      headers['authorization'] = `Bearer ${HF_TOKEN}`
    }
  }

  const method = req.method
  const body = ['GET', 'HEAD'].includes(method) ? undefined : await req.arrayBuffer()

  // Use a shorter timeout for health checks so UI stays responsive during cold starts
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
      if (isHealthCheck) {
        return NextResponse.json({
          status: 'standby',
          service: 'rasosynthtune-backend',
          warming_up: true,
          message: 'Hugging Face Space backend is warming up...',
        }, { status: 200 })
      }
      return NextResponse.json({
        error: 'Backend container is warming up',
        status: 'standby',
        warming_up: true,
        target: targetUrl,
        message: 'Hugging Face Space backend is currently waking from standby. Please retry in a few seconds.',
      }, {
        status: 503,
        headers: { 'Retry-After': '15' }
      })
    }

    const responseHeaders = new Headers()
    response.headers.forEach((value, key) => {
      const lowerKey = key.toLowerCase()
      if (!['transfer-encoding', 'content-encoding', 'content-length'].includes(lowerKey)) {
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

    // Graceful standby response on network timeout or connection failure
    if (isHealthCheck) {
      return NextResponse.json({
        status: 'standby',
        service: 'rasosynthtune-backend',
        warming_up: true,
        message: 'Backend is warming up or temporarily unreachable.',
      }, { status: 200 })
    }

    return NextResponse.json(
      {
        error: 'Failed to connect to backend service',
        status: 'standby',
        warming_up: true,
        target: targetUrl,
        details: err?.message || String(err),
      },
      { status: 503, headers: { 'Retry-After': '15' } }
    )
  }
}

export const GET = handleProxy
export const POST = handleProxy
export const PUT = handleProxy
export const PATCH = handleProxy
export const DELETE = handleProxy
export const OPTIONS = handleProxy
