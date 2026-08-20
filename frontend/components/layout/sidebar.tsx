'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  Zap,
  BarChart3,
  Cpu,
  ClipboardCheck,
  Activity,
  CheckCircle2,
  AlertCircle,
  Loader2,
  BarChart2
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { StatusBadge } from '@/components/ui/badge'
import { api } from '@/lib/api/client'
import { navGroups } from './top-nav'

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(true)
  const pathname = usePathname()
  const isHomePage = pathname === '/'
  const [recentJobs, setRecentJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  // Fetch recent jobs
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

  // On non-home subpages, default to collapsed unless toggled by user
  useEffect(() => {
    if (!isHomePage) {
      setCollapsed(true)
    } else {
      setCollapsed(false)
    }
  }, [isHomePage])

  if (collapsed) {
    return (
      <aside className="hidden lg:flex flex-col w-14 min-w-[56px] shrink-0 border-r border-[#E2E6E0] bg-[#F6F7F4] transition-all min-h-[calc(100vh-4rem)] py-4 items-center justify-between">
        <div className="flex flex-col items-center gap-3 w-full px-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full"
            onClick={() => setCollapsed(false)}
            title="Expand Sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>

          <div className="w-8 h-px bg-[#E2E6E0] my-1" />

          {/* Icon Quick Nav */}
          {navGroups.map((group) => (
            <div key={group.name} className="flex flex-col gap-2 py-1 items-center">
              {group.items.map((item) => {
                const Icon = item.icon
                const isActive = pathname.startsWith(item.href)
                return (
                  <Link key={item.href} href={item.href}>
                    <button
                      title={`${item.label} (${group.name})`}
                      className={clsx(
                        'h-9 w-9 rounded-xl flex items-center justify-center transition-all',
                        isActive
                          ? 'bg-[#1B3B2B] text-white shadow-xs'
                          : 'text-[#55635B] hover:bg-[#E8ECE6] hover:text-[#1B3B2B]'
                      )}
                    >
                      <Icon className={clsx('h-4 w-4', isActive ? 'text-emerald-300' : 'text-[#55635B]')} />
                    </button>
                  </Link>
                )
              })}
            </div>
          ))}
        </div>

        <div className="flex flex-col items-center gap-2">
          <Link href="/studio">
            <button
              title="Launch Studio Preset"
              className="h-9 w-9 rounded-xl bg-[#1B3B2B] text-white flex items-center justify-center hover:bg-[#142D21] transition-all shadow-xs"
            >
              <Zap className="h-4 w-4 text-emerald-400 fill-current" />
            </button>
          </Link>
        </div>
      </aside>
    )
  }

  return (
    <aside className="hidden lg:flex flex-col w-64 min-w-[256px] shrink-0 border-r border-[#E2E6E0] bg-[#F6F7F4] transition-all min-h-[calc(100vh-4rem)]">
      {/* Sidebar Header */}
      <div className="flex items-center justify-between p-4 border-b border-[#E2E6E0]">
        <span className="text-xs font-bold uppercase tracking-wider font-mono text-[#55635B]">
          Quick Workspace
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full"
          onClick={() => setCollapsed(true)}
          title="Collapse Sidebar"
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
                New Workflow Preset
              </Button>
            </Link>
            <Link href="/quality">
              <Button variant="ghost" size="sm" className="w-full justify-start gap-2 text-xs text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full">
                <BarChart2 className="h-3.5 w-3.5 text-[#1B3B2B]" />
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

          {/* Recent Active Runs (Only on Home Page or when explicit) */}
          {isHomePage && (
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
                          'flex items-center justify-between p-2 rounded-xl border border-transparent text-xs cursor-pointer transition-colors hover:border-[#D1D8CE] hover:bg-white',
                          (pathname as string) === `/datasets` && 'bg-white border-[#E2E6E0] shadow-xs'
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
                          <span className="truncate font-mono text-[11px] font-medium text-[#1B3B2B]">
                            {job.target_domain || job.id}
                          </span>
                        </div>
                        <StatusBadge status={job.status === 'negotiating' ? 'pending' : job.status} />
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Engine Mini Telemetry */}
          {isHomePage && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-[#55635B]">
                  Engine Summary
                </span>
                <Activity className="h-3 w-3 text-emerald-600" />
              </div>
              <div className="p-3 rounded-xl bg-[#1B3B2B] text-white shadow-xs space-y-1.5">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-emerald-100/80">Active</span>
                  <span className="text-white font-bold">{recentJobs.filter(j => j.status === 'running').length || 0}</span>
                </div>
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-emerald-100/80">Completed</span>
                  <span className="text-emerald-400 font-bold">{recentJobs.filter(j => j.status === 'completed').length || 0}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </aside>
  )
}
