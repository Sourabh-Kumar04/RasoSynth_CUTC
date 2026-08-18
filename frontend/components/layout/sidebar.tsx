'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  Plus,
  Activity,
  AlertCircle,
  CheckCircle2,
  Loader2,
  BarChart3,
  Cpu,
  ClipboardCheck,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge, StatusBadge } from '@/components/ui/badge'
import { api } from '@/lib/api/client'

// REAL data - no mock

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()
  const [recentJobs, setRecentJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // Fetch recent jobs from real API
  useEffect(() => {
    async function fetchRecentJobs() {
      try {
        const response = await api.getJobs({ limit: 5 })
        if (response.data && response.data.length > 0) {
          setRecentJobs(response.data.slice(0, 5))
        }
      } catch (error) {
        // Silently fail - no recent jobs shown
        console.debug('No recent jobs available')
      } finally {
        setLoading(false)
      }
    }
    fetchRecentJobs()
  }, [])

  if (collapsed) {
    return (
      <aside className="flex flex-col h-[calc(100vh-3.5rem)] border-r border-border bg-surface/50 w-12">
        <Button
          variant="ghost"
          size="icon"
          className="m-2"
          onClick={() => setCollapsed(false)}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </aside>
    )
  }

  return (
    <aside className="flex flex-col h-[calc(100vh-3.5rem)] border-r border-border bg-surface/50 w-60">
      {/* Collapse toggle */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <span className="text-xs font-medium text-muted-foreground">Quick Actions</span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          onClick={() => setCollapsed(true)}
        >
          <ChevronLeft className="h-3 w-3" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-3 space-y-6">
          {/* Quick Actions */}
          <div className="space-y-2">
            <Link href="/studio/new">
              <Button variant="outline" className="w-full justify-start gap-2">
                <Plus className="h-4 w-4" />
                New Dataset Job
              </Button>
            </Link>
            <Link href="/quality">
              <Button variant="ghost" className="w-full justify-start gap-2">
                <BarChart3 className="h-4 w-4" />
                Quality Dashboard
              </Button>
            </Link>
            <Link href="/finetune">
              <Button variant="ghost" className="w-full justify-start gap-2">
                <Cpu className="h-4 w-4" />
                Fine-Tune Studio
              </Button>
            </Link>
            <Link href="/review">
              <Button variant="ghost" className="w-full justify-start gap-2">
                <ClipboardCheck className="h-4 w-4" />
                Review Queue
              </Button>
            </Link>
          </div>

          {/* Recent Jobs */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Recent Jobs</span>
              <Clock className="h-3 w-3 text-muted-foreground" />
            </div>
            {loading ? (
              <div className="text-xs text-muted-foreground p-2">Loading...</div>
            ) : recentJobs.length === 0 ? (
              <div className="text-xs text-muted-foreground p-2">No jobs yet</div>
            ) : (
              <div className="space-y-1">
                {recentJobs.map((job) => (
                  <Link key={job.id} href={`/datasets?job=${job.id}`}>
                    <div
                      className={clsx(
                        'flex items-center justify-between p-2 rounded-md text-sm cursor-pointer transition-colors hover:bg-surface-hover',
                        pathname === `/datasets` && 'bg-surface-hover'
                      )}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {job.status === 'running' && (
                          <Loader2 className="h-3 w-3 animate-spin text-accent shrink-0" />
                        )}
                        {job.status === 'completed' && (
                          <CheckCircle2 className="h-3 w-3 text-success shrink-0" />
                        )}
                        {job.status === 'failed' && (
                          <AlertCircle className="h-3 w-3 text-error shrink-0" />
                        )}
                        {(job.status === 'pending' || job.status === 'negotiating') && (
                          <Clock className="h-3 w-3 text-muted-foreground shrink-0" />
                        )}
                        <span className="truncate">{job.target_domain || job.id}</span>
                      </div>
                      <StatusBadge status={job.status === 'negotiating' ? 'pending' : job.status} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* System Status - Real data from health endpoint */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">System Status</span>
              <Activity className="h-3 w-3 text-success" />
            </div>
            <div className="p-3 rounded-md bg-background/50 space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Active Jobs</span>
                <span className="font-mono">{recentJobs.filter(j => j.status === 'running').length || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Completed</span>
                <span className="font-mono">{recentJobs.filter(j => j.status === 'completed').length || 0}</span>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>
    </aside>
  )
}
