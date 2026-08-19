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
  Zap,
  Layers,
  Sparkles
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge, StatusBadge } from '@/components/ui/badge'
import { api } from '@/lib/api/client'

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
        console.debug('No recent jobs available')
      } finally {
        setLoading(false)
      }
    }
    fetchRecentJobs()
  }, [])

  if (collapsed) {
    return (
      <aside className="hidden lg:flex flex-col w-14 min-w-[56px] shrink-0 border-r border-[#E2E6E0] bg-[#F6F7F4] transition-all min-h-full">
        <Button
          variant="ghost"
          size="icon"
          className="m-2 text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6]"
          onClick={() => setCollapsed(false)}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </aside>
    )
  }

  return (
    <aside className="hidden lg:flex flex-col w-64 min-w-[256px] shrink-0 border-r border-[#E2E6E0] bg-[#F6F7F4] transition-all min-h-full">
      {/* Sidebar Header */}
      <div className="flex items-center justify-between p-5 border-b border-[#E2E6E0]">
        <span className="text-xs font-bold uppercase tracking-wider font-mono text-[#55635B]">
          Quick Navigation
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full"
          onClick={() => setCollapsed(true)}
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Quick Actions */}
          <div className="space-y-2">
            <Link href="/studio">
              <Button
                size="sm"
                className="w-full justify-start gap-2 bg-[#1B3B2B] hover:bg-[#142D21] text-white font-medium text-xs rounded-full shadow-xs"
              >
                <Zap className="h-3.5 w-3.5 text-emerald-400 fill-current" />
                New Workflow Presets
              </Button>
            </Link>
            <Link href="/quality">
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full">
                <BarChart3 className="h-3.5 w-3.5 text-[#1B3B2B]" />
                Quality Benchmarks
              </Button>
            </Link>
            <Link href="/finetune">
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full">
                <Cpu className="h-3.5 w-3.5 text-[#1B3B2B]" />
                Fine-Tune Studio
              </Button>
            </Link>
            <Link href="/review">
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full">
                <ClipboardCheck className="h-3.5 w-3.5 text-[#1B3B2B]" />
                HITL Inspection Queue
              </Button>
            </Link>
          </div>

          {/* Recent Active Runs */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#55635B]">
                Recent Syntheses
              </span>
              <Clock className="h-3 w-3 text-[#55635B]" />
            </div>
            {loading ? (
              <div className="text-xs text-[#55635B] p-2 font-mono">Loading active runs...</div>
            ) : recentJobs.length === 0 ? (
              <div className="text-xs text-[#55635B] p-2 font-mono">No active dataset jobs</div>
            ) : (
              <div className="space-y-1.5">
                {recentJobs.map((job) => (
                  <Link key={job.id} href={`/datasets?job=${job.id}`}>
                    <div
                      className={clsx(
                        'flex items-center justify-between p-2.5 rounded-xl border border-transparent text-xs cursor-pointer transition-colors hover:border-[#D1D8CE] hover:bg-white',
                        pathname === `/datasets` && 'bg-white border-[#E2E6E0] shadow-xs'
                      )}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {job.status === 'running' && (
                          <Loader2 className="h-3 w-3 animate-spin text-emerald-600 shrink-0" />
                        )}
                        {job.status === 'completed' && (
                          <CheckCircle2 className="h-3 w-3 text-emerald-600 shrink-0" />
                        )}
                        {job.status === 'failed' && (
                          <AlertCircle className="h-3 w-3 text-rose-500 shrink-0" />
                        )}
                        {(job.status === 'pending' || job.status === 'negotiating') && (
                          <Clock className="h-3 w-3 text-[#55635B] shrink-0" />
                        )}
                        <span className="truncate font-mono text-[11px] font-medium text-[#1B3B2B]">{job.target_domain || job.id}</span>
                      </div>
                      <StatusBadge status={job.status === 'negotiating' ? 'pending' : job.status} />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* System Telemetry Overview - Dark Forest Pine Green Mini Card */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#55635B]">
                Engine Telemetry
              </span>
              <Activity className="h-3 w-3 text-emerald-600" />
            </div>
            <div className="p-3.5 rounded-2xl bg-[#1B3B2B] text-white shadow-xs space-y-2">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-emerald-100/80">Active Workflows</span>
                <span className="text-white font-bold">{recentJobs.filter(j => j.status === 'running').length || 0}</span>
              </div>
              <div className="flex justify-between text-xs font-mono">
                <span className="text-emerald-100/80">Completed</span>
                <span className="text-emerald-400 font-bold">{recentJobs.filter(j => j.status === 'completed').length || 0}</span>
              </div>
            </div>
          </div>
        </div>
      </ScrollArea>
    </aside>
  )
}
