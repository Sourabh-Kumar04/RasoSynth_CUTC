'use client'

import { useState, useEffect } from 'react'
import { api, TraceInfo } from '@/lib/api/client'
import {
  GitBranch,
  Clock,
  Activity,
  Copy,
  CheckCircle2,
  AlertCircle,
  Search,
  Zap,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

interface TracePanelProps {
  className?: string
}

export function TracePanel({ className }: TracePanelProps) {
  const [traces, setTraces] = useState<TraceInfo[]>([])
  const [correlationId, setCorrelationId] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [searchCorrelationId, setSearchCorrelationId] = useState('')
  const [copied, setCopied] = useState(false)

  // Get current correlation ID from session
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const cid = sessionStorage.getItem('correlation_id')
      if (cid) {
        setCorrelationId(cid)
      } else {
        const array = new Uint8Array(8)
        crypto.getRandomValues(array)
        const randomHex = Array.from(array).map(b => b.toString(16).padStart(2, '0')).join('')
        const newCid = `corr-${Date.now()}-${randomHex}`
        sessionStorage.setItem('correlation_id', newCid)
        setCorrelationId(newCid)
      }
    }
  }, [])

  // Fetch traces
  const fetchTraces = async () => {
    setLoading(true)
    try {
      const data = await api.getTraces({ limit: 20 })
      setTraces(data.traces || [])
    } catch (err) {
      console.error('Failed to fetch traces:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTraces()
    const interval = setInterval(fetchTraces, 10000) // Poll every 10s
    return () => clearInterval(interval)
  }, [])

  const copyCorrelationId = () => {
    navigator.clipboard.writeText(correlationId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const searchByCorrelationId = async () => {
    if (!searchCorrelationId.trim()) return

    setLoading(true)
    try {
      const data = await api.getTraceByCorrelation(searchCorrelationId)
      setTraces(data.traces || [])
    } catch (err) {
      console.error('Failed to search traces:', err)
    } finally {
      setLoading(false)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ok':
        return <CheckCircle2 className="h-3 w-3 text-green-500" />
      case 'error':
        return <AlertCircle className="h-3 w-3 text-red-500" />
      default:
        return <Clock className="h-3 w-3 text-yellow-500" />
    }
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <GitBranch className="h-5 w-5" />
          Tracing
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Current Correlation ID */}
          <div className="p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Current Session</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={copyCorrelationId}
                className="h-6 px-2"
              >
                {copied ? (
                  <CheckCircle2 className="h-3 w-3" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
            <code className="text-xs font-mono bg-background px-2 py-1 rounded block overflow-x-auto">
              {correlationId || 'Generating...'}
            </code>
          </div>

          {/* Search by Correlation ID */}
          <div className="flex gap-2">
            <Input
              placeholder="Search by correlation ID..."
              value={searchCorrelationId}
              onChange={(e) => setSearchCorrelationId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && searchByCorrelationId()}
              className="text-sm"
            />
            <Button size="sm" onClick={searchByCorrelationId}>
              <Search className="h-4 w-4" />
            </Button>
          </div>

          {/* Recent Traces */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Recent Traces</span>
              <Button variant="ghost" size="sm" onClick={fetchTraces} disabled={loading}>
                <Zap className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {traces.map((trace) => (
                <div
                  key={trace.id}
                  className="p-2 border rounded text-sm flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    {getStatusIcon(trace.status)}
                    <span className="font-mono text-xs">{trace.operation}</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{trace.duration}</span>
                    <span>{trace.timestamp}</span>
                  </div>
                </div>
              ))}

              {traces.length === 0 && !loading && (
                <p className="text-center text-muted-foreground py-4 text-sm">
                  No traces available
                </p>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

export function CorrelationIdBadge() {
  const [correlationId, setCorrelationId] = useState('')

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const cid = sessionStorage.getItem('correlation_id')
      if (cid) setCorrelationId(cid)
    }
  }, [])

  if (!correlationId) return null

  return (
    <Badge variant="outline" className="font-mono text-xs">
      {correlationId.substring(0, 12)}...
    </Badge>
  )
}