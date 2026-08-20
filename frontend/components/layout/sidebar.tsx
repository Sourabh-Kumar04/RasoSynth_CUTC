'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  Zap,
  Cpu,
  ClipboardCheck,
  Activity,
  CheckCircle2,
  AlertCircle,
  Loader2,
  BarChart2,
  Sparkles,
  LayoutGrid
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { StatusBadge } from '@/components/ui/badge'
import { api } from '@/lib/api/client'
import { navGroups } from './top-nav'

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
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

  // Sync collapsed state with localStorage and page context
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedState = localStorage.getItem('sidebarCollapsed')
      if (storedState !== null) {
        setCollapsed(storedState === 'true')
      } else if (!isHomePage) {
        setCollapsed(true)
      } else {
        setCollapsed(false)
      }
    }
  }, [isHomePage])

  const toggleCollapse = (newVal: boolean) => {
    setCollapsed(newVal)
    if (typeof window !== 'undefined') {
      localStorage.setItem('sidebarCollapsed', String(newVal))
    }
  }

  return (
    <>
      {/* ========================================================================= */}
      {/* MOBILE & TABLET RESPONSIVE QUICK WORKSPACE BAR (< lg BREAKPOINTS)          */}
      {/* ========================================================================= */}
      <div data-tour="sidebar-quick-workspace-mobile" className="lg:hidden w-full bg-[#E8ECE6]/80 border-b border-[#E2E6E0] p-3 px-4 flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LayoutGrid className="h-4 w-4 text-[#1B3B2B]" />
            <span className="text-xs font-bold uppercase tracking-wider font-mono text-[#1B3B2B]">
              Quick Workspace
            </span>
          </div>
          {isHomePage && (
            <div className="flex items-center gap-2 font-mono text-[11px] text-[#55635B]">
              <span className="flex items-center gap-1 text-emerald-700 font-bold">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                {recentJobs.filter(j => j.status === 'running').length || 0} Active
              </span>
              <span>•</span>
              <span>{recentJobs.filter(j => j.status === 'completed').length || 0} Done</span>
            </div>
          )}
        </div>

        {/* Action Buttons horizontal scroll on mobile */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 no-scrollbar text-xs">
          <Link href="/studio" className="shrink-0">
            <Button
              size="sm"
              className="gap-1.5 bg-[#1B3B2B] hover:bg-[#142D21] text-white text-xs rounded-full shadow-xs px-3 h-8"
            >
              <Zap className="h-3.5 w-3.5 text-emerald-400 fill-current" />
              <span>New Preset</span>
            </Button>
          </Link>
          <Link href="/quality" className="shrink-0">
            <Button variant="outline" size="sm" className="gap-1.5 border-[#D1D8CE] bg-white text-[#1B3B2B] hover:bg-[#E8ECE6] text-xs rounded-full h-8">
              <BarChart2 className="h-3.5 w-3.5 text-[#1B3B2B]" />
              <span>Quality</span>
            </Button>
          </Link>
          <Link href="/finetune" className="shrink-0">
            <Button variant="outline" size="sm" className="gap-1.5 border-[#D1D8CE] bg-white text-[#1B3B2B] hover:bg-[#E8ECE6] text-xs rounded-full h-8">
              <Cpu className="h-3.5 w-3.5 text-[#1B3B2B]" />
              <span>Fine-Tune</span>
            </Button>
          </Link>
          <Link href="/review" className="shrink-0">
            <Button variant="outline" size="sm" className="gap-1.5 border-[#D1D8CE] bg-white text-[#1B3B2B] hover:bg-[#E8ECE6] text-xs rounded-full h-8">
              <ClipboardCheck className="h-3.5 w-3.5 text-[#1B3B2B]" />
              <span>HITL Queue</span>
            </Button>
          </Link>
        </div>

        {/* Recent Jobs Pill Strip for Mobile/Tablet */}
        {isHomePage && recentJobs.length > 0 && (
          <div className="flex items-center gap-2 overflow-x-auto pt-1 no-scrollbar">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#55635B] shrink-0">
              Recent:
            </span>
            {recentJobs.slice(0, 3).map((job) => (
              <Link key={job.id} href={`/datasets?job=${job.id}`} className="shrink-0">
                <div className="flex items-center gap-1.5 bg-white border border-[#D1D8CE] px-2.5 py-1 rounded-full text-[11px] font-mono hover:border-[#1B3B2B] transition-all">
                  {job.status === 'running' && <Loader2 className="h-3 w-3 animate-spin text-emerald-600" />}
                  {job.status === 'completed' && <CheckCircle2 className="h-3 w-3 text-emerald-600" />}
                  {job.status === 'failed' && <AlertCircle className="h-3 w-3 text-rose-500" />}
                  <span className="font-medium text-[#1B3B2B] truncate max-w-[120px]">
                    {job.target_domain || job.id}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* DESKTOP SIDEBAR (lg BREAKPOINTS AND UP)                                   */}
      {/* ========================================================================= */}
      {collapsed ? (
        <aside className="hidden lg:flex flex-col w-14 min-w-[56px] shrink-0 border-r border-[#E2E6E0] bg-[#F6F7F4] transition-all min-h-[calc(100vh-4rem)] py-4 items-center justify-between">
          <div className="flex flex-col items-center gap-3 w-full px-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full"
              onClick={() => toggleCollapse(false)}
              title="Expand Quick Workspace Sidebar"
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
                title="Launch Studio Preset Workflow"
                className="h-9 w-9 rounded-xl bg-[#1B3B2B] text-white flex items-center justify-center hover:bg-[#142D21] transition-all shadow-xs"
              >
                <Zap className="h-4 w-4 text-emerald-400 fill-current" />
              </button>
            </Link>
          </div>
        </aside>
      ) : (
        <aside className="hidden lg:flex flex-col w-72 min-w-[288px] shrink-0 border-r border-[#E2E6E0] bg-[#F6F7F4] transition-all sticky top-16 h-[calc(100vh-4rem)] overflow-hidden">
          {/* Sidebar Header */}
          <div className="flex items-center justify-between p-4 border-b border-[#E2E6E0] shrink-0">
            <span className="text-xs font-bold uppercase tracking-wider font-mono text-[#1B3B2B] flex items-center gap-1.5">
              <LayoutGrid className="h-3.5 w-3.5 text-[#1B3B2B] shrink-0" />
              Quick Workspace
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full shrink-0"
              onClick={() => toggleCollapse(true)}
              title="Collapse Sidebar"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
          </div>

          <ScrollArea className="flex-1 h-full">
            <div className="p-3 space-y-3.5">
              {/* Quick Actions */}
              <div data-tour="sidebar-quick-workspace-desktop" className="space-y-1.5 w-full min-w-0 p-2 bg-[#E8ECE6]/60 rounded-2xl border border-[#D1D8CE]/60">
                <Link href="/studio" className="w-full block">
                  <Button
                    size="sm"
                    className="w-full h-7 justify-start gap-2 bg-[#1B3B2B] hover:bg-[#142D21] text-white font-medium text-xs rounded-full shadow-xs min-w-0 px-2.5"
                  >
                    <Zap className="h-3.5 w-3.5 text-emerald-400 fill-current shrink-0" />
                    <span className="truncate min-w-0 flex-1 text-left">New Workflow Preset</span>
                  </Button>
                </Link>
                <Link href="/quality" className="w-full block">
                  <Button variant="ghost" size="sm" className="w-full h-7 justify-start gap-2 text-xs text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full min-w-0 px-2.5">
                    <BarChart2 className="h-3.5 w-3.5 text-[#1B3B2B] shrink-0" />
                    <span className="truncate min-w-0 flex-1 text-left">Quality Benchmarks</span>
                  </Button>
                </Link>
                <Link href="/finetune" className="w-full block">
                  <Button variant="ghost" size="sm" className="w-full h-7 justify-start gap-2 text-xs text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full min-w-0 px-2.5">
                    <Cpu className="h-3.5 w-3.5 text-[#1B3B2B] shrink-0" />
                    <span className="truncate min-w-0 flex-1 text-left">Fine-Tune Studio</span>
                  </Button>
                </Link>
                <Link href="/review" className="w-full block">
                  <Button variant="ghost" size="sm" className="w-full h-7 justify-start gap-2 text-xs text-[#55635B] hover:text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full min-w-0 px-2.5">
                    <ClipboardCheck className="h-3.5 w-3.5 text-[#1B3B2B] shrink-0" />
                    <span className="truncate min-w-0 flex-1 text-left">HITL Inspection Queue</span>
                  </Button>
                </Link>
              </div>

              {/* Recent Active Runs */}
              <div className="space-y-1.5 w-full min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#55635B] truncate">
                    Recent Syntheses
                  </span>
                  <Clock className="h-3 w-3 text-[#55635B] shrink-0" />
                </div>
                {loading ? (
                  <div className="text-xs text-[#55635B] p-1.5 font-mono">Loading active runs...</div>
                ) : recentJobs.length === 0 ? (
                  <div className="text-xs text-[#55635B] p-1.5 font-mono">No active dataset jobs</div>
                ) : (
                  <div className="space-y-1 w-full min-w-0">
                    {recentJobs.slice(0, 4).map((job) => (
                      <Link key={job.id} href={`/datasets?job=${job.id}`} className="w-full block">
                        <div
                          className={clsx(
                            'flex items-center justify-between gap-1.5 p-1.5 px-2 rounded-xl border border-transparent text-xs cursor-pointer transition-colors hover:border-[#D1D8CE] hover:bg-white w-full min-w-0',
                            (pathname as string) === `/datasets` && 'bg-white border-[#E2E6E0] shadow-xs'
                          )}
                        >
                          <div className="flex items-center gap-1.5 min-w-0 flex-1 overflow-hidden">
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
                            <span className="truncate font-mono text-[10px] font-medium text-[#1B3B2B] min-w-0 flex-1">
                              {job.target_domain || job.id}
                            </span>
                          </div>
                          <div className="shrink-0">
                            <StatusBadge status={job.status === 'negotiating' ? 'pending' : job.status} />
                          </div>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {/* Engine Mini Telemetry */}
              <div className="space-y-1.5 w-full min-w-0">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#55635B]">
                    Engine Summary
                  </span>
                  <Activity className="h-3 w-3 text-emerald-600 shrink-0" />
                </div>
                <div className="p-2 px-3 rounded-xl bg-[#1B3B2B] text-white shadow-xs flex items-center justify-between text-xs font-mono w-full">
                  <div className="flex items-center gap-1.5">
                    <span className="text-emerald-100/80">Active:</span>
                    <span className="text-white font-bold">{recentJobs.filter(j => j.status === 'running').length || 0}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="text-emerald-100/80">Completed:</span>
                    <span className="text-emerald-400 font-bold">{recentJobs.filter(j => j.status === 'completed').length || 0}</span>
                  </div>
                </div>
              </div>
            </div>
          </ScrollArea>
        </aside>
      )}
    </>
  )
}
