import { NextRequest, NextResponse } from 'next/server'

// Server-side backend URL (never exposed to browser)
const BACKEND_URL = (
  process.env.BACKEND_API_URL ||
  process.env.HF_SPACE_URL ||
  'https://sourabh-kumar04-rasosynthtune.hf.space'
).replace(/\/$/, '')

// Server-side private Hugging Face token (never exposed to browser)
const HF_TOKEN = process.env.HF_TOKEN || ''

async function handleProxy(req: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = (params.path || []).join('/')
  const search = req.nextUrl.search
  const targetUrl = `${BACKEND_URL}/${path}${search}`

  const headers: Record<string, string> = {}
  req.headers.forEach((value, key) => {
    const lowerKey = key.toLowerCase()
    if (!['host', 'connection', 'content-length'].includes(lowerKey)) {
      headers[lowerKey] = value
    }
  })

  // Securely inject private HF_TOKEN on server-side without exposing to browser
  if (HF_TOKEN && (BACKEND_URL.includes('hf.space') || BACKEND_URL.includes('huggingface.co'))) {
    headers['authorization'] = `Bearer ${HF_TOKEN}`
  }

  const method = req.method
  const body = ['GET', 'HEAD'].includes(method) ? undefined : await req.arrayBuffer()

  try {
    const response = await fetch(targetUrl, {
      method,
      headers,
      body,
      // @ts-ignore
      duplex: 'half',
    })

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
    return NextResponse.json(
      {
        error: 'Failed to connect to backend service',
        target: targetUrl,
        details: err?.message || String(err),
      },
      { status: 502 }
    )
  }
}

export const GET = handleProxy
export const POST = handleProxy
export const PUT = handleProxy
export const PATCH = handleProxy
export const DELETE = handleProxy
export const OPTIONS = handleProxy
