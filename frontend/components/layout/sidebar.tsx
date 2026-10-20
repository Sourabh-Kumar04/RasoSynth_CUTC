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
  LayoutGrid,
  Server,
  Layers,
  Database,
  Workflow,
  FlaskConical,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { api } from '@/lib/api/client'

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()
  const [recentJobs, setRecentJobs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchRecentJobs() {
      try {
        const response = await api.getJobs({ limit: 6 })
        if (response.data && response.data.length > 0) {
          setRecentJobs(response.data.slice(0, 6))
        }
      } catch {
        console.debug('No recent jobs available')
      } finally {
        setLoading(false)
      }
    }
    fetchRecentJobs()
    const timer = setInterval(fetchRecentJobs, 12000)
    return () => clearInterval(timer)
  }, [])

  return (
    <>
      {/* ========================================================================= */}
      {/* DESKTOP HIGH-DENSITY COCKPIT SIDE RAIL (>= lg BREAKPOINTS)                */}
      {/* ========================================================================= */}
      <motion.aside
        animate={{ width: collapsed ? 68 : 256 }}
        transition={{ type: 'spring', stiffness: 350, damping: 30 }}
        className="hidden lg:flex flex-col justify-between bg-[#0e0e13] border-r border-[#272738] shrink-0 sticky top-24 h-[calc(100vh-6rem)] z-30 select-none overflow-hidden"
      >
        <div className="p-3 space-y-4">
          {/* Cluster Status Header */}
          <div className="p-2.5 rounded-md bg-[#12121a] border border-[#272738] relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
                {!collapsed && (
                  <span className="text-[11px] font-mono font-bold tracking-wider text-white uppercase">
                    CLUSTER-ALPHA
                  </span>
                )}
              </div>
              <button
                onClick={() => setCollapsed(!collapsed)}
                className="p-1 rounded text-[#94a3b8] hover:text-white hover:bg-[#1a1a24] transition-colors"
                title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
              >
                {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronLeft className="w-3.5 h-3.5" />}
              </button>
            </div>

            {!collapsed && (
              <div className="mt-2 pt-2 border-t border-[#1c1c28] space-y-1 text-[10px] font-mono text-[#94a3b8]">
                <div className="flex justify-between items-center">
                  <span>SOVEREIGN: Sarvam-2B</span>
                  <span className="text-[#10b981] font-semibold">AIR-GAPPED</span>
                </div>
                <div className="flex justify-between items-center text-[9px] text-[#64748b]">
                  <span>DBOM MERKLE ENGINE</span>
                  <span className="text-emerald-400 font-bold">SHA-256 LIVE</span>
                </div>
              </div>
            )}
          </div>

          {/* Quick Workspace Navigation */}
          <div className="space-y-1">
            <div className="px-2 pb-1 text-[10px] font-mono font-bold text-[#94a3b8] uppercase tracking-wider">
              {!collapsed && 'Navigation'}
            </div>
            {[
              { href: '/studio', label: 'Studio Pipeline', icon: FlaskConical },
              { href: '/orchestration', label: 'DAG Visualizer', icon: Workflow },
              { href: '/datasets', label: 'Dataset Store & DBOM', icon: Database },
              { href: '/finetune', label: 'Fine-Tune Studio', icon: Cpu },
              { href: '/research', label: 'Research & Benchmarks', icon: BarChart2 },
              { href: '/observability', label: 'Telemetry & Traces', icon: Activity },
              { href: '/review', label: 'HITL Review Queue', icon: ClipboardCheck },
              { href: '/quality', label: 'Quality & Grounding', icon: Sparkles },
            ].map((item) => {
              const active = pathname === item.href
              const Icon = item.icon
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    'flex items-center space-x-2.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all group',
                    active
                      ? 'bg-[#1a1a24] text-white border-l-2 border-[#f26625] shadow-sm'
                      : 'text-[#94a3b8] hover:bg-[#161622] hover:text-white'
                  )}
                  title={collapsed ? item.label : undefined}
                >
                  <Icon className={clsx('w-4 h-4 shrink-0', active ? 'text-[#f26625]' : 'text-[#94a3b8] group-hover:text-white')} />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </Link>
              )
            })}
          </div>

          {/* Recent Synthesis Runs */}
          {!collapsed && (
            <div className="space-y-2 pt-2 border-t border-[#1c1c28]">
              <div className="px-2 flex items-center justify-between text-[10px] font-mono text-[#94a3b8] uppercase tracking-wider">
                <span>Recent Jobs</span>
                <Clock className="w-3 h-3 text-[#94a3b8]" />
              </div>

              <div className="space-y-1">
                {recentJobs.length === 0 ? (
                  <div className="px-2 py-3 text-[11px] font-mono text-[#94a3b8]/60 text-center">
                    No recent jobs
                  </div>
                ) : (
                  recentJobs.map((job) => {
                    const isRunning = job.status === 'running'
                    const isCompleted = job.status === 'completed'
                    return (
                      <Link
                        key={job.id}
                        href={`/orchestration?job=${job.id}`}
                        className="block p-2 rounded-md bg-[#12121a]/60 hover:bg-[#161622] border border-[#1c1c28] hover:border-[#272738] transition-all group text-xs"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-mono text-[10px] text-[#94a3b8] group-hover:text-white truncate max-w-[120px]">
                            {job.id.slice(0, 8)}...
                          </span>
                          <span className={clsx(
                            'text-[9px] font-mono uppercase px-1 py-0.2 rounded',
                            isRunning && 'bg-[#f26625]/20 text-[#f26625]',
                            isCompleted && 'bg-[#10b981]/20 text-[#10b981]',
                            !isRunning && !isCompleted && 'bg-[#f59e0b]/20 text-[#f59e0b]'
                          )}>
                            {job.status}
                          </span>
                        </div>
                        <div className="flex justify-between items-center text-[10px] text-[#94a3b8]">
                          <span className="truncate max-w-[110px]">
                            {job.config?.target_domain || 'Grounded extraction'}
                          </span>
                          <span className="font-mono text-[#10b981]">
                            {job.samples_generated || 0} spls
                          </span>
                        </div>
                      </Link>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar Footer telemetry */}
        {!collapsed && (
          <div className="p-3 border-t border-[#1c1c28] bg-[#0a0a0f] text-[10px] font-mono text-[#94a3b8] flex justify-between items-center">
            <span>RAM: 42%</span>
            <span className="text-[#10b981]">LATENCY: 38ms</span>
          </div>
        )}
      </motion.aside>
    </>
  )
}
