'use client'

import { useState, useEffect, useRef } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Clock,
  Zap,
  Cpu,
  ClipboardCheck,
  Activity,
  BarChart2,
  Sparkles,
  Database,
  Workflow,
  FlaskConical,
  Beaker,
  Settings as SettingsIcon,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  CheckCircle2,
  Loader2,
  ExternalLink,
} from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api/client'

const SUB_NAV_LINKS = [
  { href: '/studio', label: 'Studio Pipeline', icon: FlaskConical },
  { href: '/orchestration', label: 'DAG Visualizer', icon: Workflow },
  { href: '/datasets', label: 'Dataset Store', icon: Database },
  { href: '/finetune', label: 'Fine-Tune', icon: Cpu },
  { href: '/research', label: 'Research', icon: BarChart2 },
  { href: '/observability', label: 'Telemetry', icon: Activity },
  { href: '/review', label: 'Review', icon: ClipboardCheck },
  { href: '/quality', label: 'Quality', icon: Sparkles },
]

export function SubNav() {
  const pathname = usePathname()
  const [recentJobs, setRecentJobs] = useState<any[]>([])
  const [recentJobsOpen, setRecentJobsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    async function fetchRecentJobs() {
      try {
        const response = await api.getJobs({ limit: 6 })
        if (response.data && response.data.length > 0) {
          setRecentJobs(response.data.slice(0, 6))
        }
      } catch {
        console.debug('No recent jobs available')
      }
    }
    fetchRecentJobs()
    const timer = setInterval(fetchRecentJobs, 12000)
    return () => clearInterval(timer)
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setRecentJobsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const runningCount = recentJobs.filter((j) => j.status === 'running').length

  return (
    <div className="sticky top-14 z-30 w-full border-b border-[#22222e] bg-[#0c0e14]/95 backdrop-blur-md select-none">
      <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4 h-11">
        
        {/* Horizontal Navigation Tabs */}
        <nav className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1 scroll-smooth shrink min-w-0">
          {SUB_NAV_LINKS.map((item) => {
            const active = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  'flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-mono transition-all whitespace-nowrap shrink-0',
                  active
                    ? 'bg-[#1a1a24] text-white border border-[#f26625]/40 shadow-sm font-semibold'
                    : 'text-[#94a3b8] hover:bg-[#14141e] hover:text-white'
                )}
              >
                <Icon
                  className={clsx(
                    'w-3.5 h-3.5 shrink-0',
                    active ? 'text-[#f26625]' : 'text-[#94a3b8]'
                  )}
                />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Right Section: Recent Jobs Dropdown & Telemetry */}
        <div ref={dropdownRef} className="relative shrink-0 flex items-center gap-2.5">
          <button
            onClick={() => setRecentJobsOpen((prev) => !prev)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#12121a] hover:bg-[#161622] border border-[#272738] text-[11px] font-mono text-[#94a3b8] hover:text-white transition-colors"
          >
            <Clock className="w-3.5 h-3.5 text-[#f26625]" />
            <span className="hidden sm:inline">Recent Jobs</span>
            {runningCount > 0 ? (
              <span className="px-1.5 py-0.2 rounded bg-[#f26625]/20 text-[#f26625] font-bold text-[10px]">
                {runningCount}
              </span>
            ) : (
              <span className="text-[#94a3b8] font-bold text-[10px]">({recentJobs.length})</span>
            )}
            <ChevronDown className={clsx('w-3 h-3 text-[#94a3b8] transition-transform', recentJobsOpen && 'rotate-180')} />
          </button>

          {/* Popover Menu for Recent Jobs */}
          {recentJobsOpen && (
            <div className="absolute right-0 top-10 w-80 bg-[#12121a] border border-[#272738] rounded-md shadow-2xl p-3 z-50 space-y-2 animate-fade-in font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-[#1c1c28] text-[10px] uppercase text-[#94a3b8]">
                <span className="font-bold text-white flex items-center gap-1">
                  <Clock className="w-3 h-3 text-[#f26625]" />
                  Recent Pipeline Runs
                </span>
                <span className="text-emerald-400 font-semibold">Live Feed</span>
              </div>

              <div className="space-y-1.5 max-h-60 overflow-y-auto">
                {recentJobs.length === 0 ? (
                  <p className="text-[11px] text-[#94a3b8] text-center py-4">No recent jobs recorded</p>
                ) : (
                  recentJobs.map((job) => {
                    const isRunning = job.status === 'running'
                    const isCompleted = job.status === 'completed'
                    return (
                      <Link
                        key={job.id}
                        href={`/orchestration?job=${job.id}`}
                        onClick={() => setRecentJobsOpen(false)}
                        className="block p-2 rounded-sm bg-[#0a0a0f] hover:bg-[#161622] border border-[#1c1c28] hover:border-[#272738] transition-colors"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-white font-bold truncate max-w-[140px]">
                            {job.config?.target_domain || job.id.slice(0, 10)}
                          </span>
                          <span
                            className={clsx(
                              'text-[9px] uppercase px-1.5 py-0.2 rounded font-semibold',
                              isRunning && 'bg-[#f26625]/20 text-[#f26625] border border-[#f26625]/40',
                              isCompleted && 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40',
                              !isRunning && !isCompleted && 'bg-amber-950/40 text-amber-400 border border-amber-500/30'
                            )}
                          >
                            {job.status}
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-[10px] text-[#94a3b8]">
                          <span>{job.samples_generated || 0} samples</span>
                          <span className="text-white font-mono">{job.id.slice(0, 8)}...</span>
                        </div>
                      </Link>
                    )
                  })
                )}
              </div>

              <div className="pt-2 border-t border-[#1c1c28] flex items-center justify-between text-[10px] text-[#94a3b8]">
                <span>RAM: 42%</span>
                <span className="text-[#10b981] font-semibold">LATENCY: 38ms</span>
                <Link
                  href="/orchestration"
                  onClick={() => setRecentJobsOpen(false)}
                  className="text-[#f26625] hover:underline font-bold"
                >
                  View All &rarr;
                </Link>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}

// Backward-compatible alias for Sidebar
export function Sidebar() {
  return <SubNav />
}
