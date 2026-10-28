'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useRef, useEffect } from 'react'
import {
  Cpu,
  ClipboardCheck,
  Activity,
  BarChart2,
  Sparkles,
  Database,
  Workflow,
  FlaskConical,
  Beaker,
  Settings,
  ChevronDown,
} from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api/client'

const PRIMARY_NAV_LINKS = [
  { href: '/studio', label: 'Studio', fullLabel: 'Dataset Studio', icon: FlaskConical },
  { href: '/datasets', label: 'Data Library', fullLabel: 'Data Library & Exports', icon: Database },
  { href: '/finetune', label: 'Model Training', fullLabel: 'QLoRA Training Studio', icon: Cpu },
  { href: '/orchestration', label: 'Pipelines', fullLabel: 'DAG Execution Engine', icon: Workflow },
  { href: '/quality', label: 'Quality', fullLabel: 'Quality Inspector', icon: Sparkles },
  { href: '/review', label: 'Review', fullLabel: 'Human-in-the-Loop Review', icon: ClipboardCheck },
  { href: '/observability', label: 'Telemetry', fullLabel: 'System Insights', icon: Activity },
]

const SECONDARY_NAV_LINKS = [
  { href: '/research', label: 'Benchmarks', fullLabel: 'Benchmarks & ROI', icon: BarChart2 },
  { href: '/providers', label: 'Providers', fullLabel: 'AI Providers & Failover', icon: Beaker },
  { href: '/settings', label: 'System Status', fullLabel: 'System Status & Configuration', icon: Settings },
]

export function DashboardNavigation() {
  const pathname = usePathname()
  const [moreOpen, setMoreOpen] = useState(false)
  const [commitHash, setCommitHash] = useState<string | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.getHealth()
      .then((res) => {
        if (res && res.commit_hash) {
          setCommitHash(res.commit_hash)
        }
      })
      .catch(() => {})
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setMoreOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isSecondaryActive = SECONDARY_NAV_LINKS.some((item) => pathname === item.href)

  return (
    <div className="sticky top-14 z-30 w-full border-b border-[#22222e] bg-[#0c0e14]/90 backdrop-blur-md select-none">
      <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-11 justify-between">
        {/* Horizontal Navigation Tabs */}
        <nav className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1 scroll-smooth w-full">
          {PRIMARY_NAV_LINKS.map((item) => {
            const active = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.fullLabel}
                  aria-current={active ? 'page' : undefined}
                className={clsx(
                  'flex items-center space-x-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs font-mono transition-all whitespace-nowrap shrink-0 group focus-visible:ring-2 focus-visible:ring-[#f26625] focus-visible:outline-none',
                  active
                    ? 'bg-[#181824] text-white border border-[#f26625]/50 shadow-[0_0_12px_rgba(242,102,37,0.2)] font-semibold'
                    : 'text-[#94a3b8] hover:bg-[#14141e] hover:text-white hover:border-[#272738] border border-transparent'
                )}
              >
                <Icon
                  className={clsx(
                    'w-3.5 h-3.5 shrink-0 transition-transform duration-200 group-hover:scale-110',
                    active ? 'text-[#f26625]' : 'text-[#94a3b8] group-hover:text-zinc-200'
                  )}
                />
                <span>{item.label}</span>
              </Link>
            )
          })}

          {/* Secondary links visible on wider desktop (>= 1280px / 1440px) */}
          <div className="hidden xl:flex items-center gap-1.5 shrink-0">
            {SECONDARY_NAV_LINKS.map((item) => {
              const active = pathname === item.href
              const Icon = item.icon
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={item.fullLabel}
                  aria-current={active ? 'page' : undefined}
                  className={clsx(
                    'flex items-center space-x-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs font-mono transition-all whitespace-nowrap shrink-0 group focus-visible:ring-2 focus-visible:ring-[#f26625] focus-visible:outline-none',
                    active
                      ? 'bg-[#181824] text-white border border-[#f26625]/50 shadow-[0_0_12px_rgba(242,102,37,0.2)] font-semibold'
                      : 'text-[#94a3b8] hover:bg-[#14141e] hover:text-white hover:border-[#272738] border border-transparent'
                  )}
                >
                  <Icon
                    className={clsx(
                      'w-3.5 h-3.5 shrink-0 transition-transform duration-200 group-hover:scale-110',
                      active ? 'text-[#f26625]' : 'text-[#94a3b8] group-hover:text-zinc-200'
                    )}
                  />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>

          {/* More Dropdown for intermediate viewports (< 1280px) */}
          <div className="relative xl:hidden shrink-0" ref={dropdownRef}>
            <button
              type="button"
              aria-expanded={moreOpen}
              onClick={() => setMoreOpen(!moreOpen)}
              className={clsx(
                'flex items-center space-x-1.5 px-2.5 py-1.5 rounded-md text-xs font-mono transition-all whitespace-nowrap shrink-0 border focus-visible:ring-2 focus-visible:ring-[#f26625] focus-visible:outline-none',
                isSecondaryActive
                  ? 'bg-[#181824] text-[#f26625] border-[#f26625]/50 font-semibold'
                  : 'text-[#94a3b8] hover:bg-[#14141e] hover:text-white border-[#272738] bg-[#0a0a0f]'
              )}
            >
              <span>More</span>
              <ChevronDown className={clsx('w-3 h-3 transition-transform', moreOpen && 'rotate-180')} />
            </button>

            {moreOpen && (
              <div className="absolute right-0 mt-1 w-44 rounded-md bg-[#12121a] border border-[#272738] shadow-xl py-1 z-50 animate-fade-in text-xs font-mono">
                {SECONDARY_NAV_LINKS.map((item) => {
                  const active = pathname === item.href
                  const Icon = item.icon
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? 'page' : undefined}
                      onClick={() => setMoreOpen(false)}
                      className={clsx(
                        'flex items-center space-x-2 px-3 py-2 text-xs transition-colors hover:bg-[#1c1c28]',
                        active ? 'text-[#f26625] bg-[#161622] font-semibold' : 'text-[#94a3b8] hover:text-white'
                      )}
                    >
                      <Icon className={clsx('w-3.5 h-3.5', active ? 'text-[#f26625]' : 'text-[#94a3b8]')} />
                      <span>{item.label}</span>
                    </Link>
                  )
                })}
              </div>
            )}
          </div>
        </nav>

        {/* Active Deployment Commit Marker */}
        <div className="hidden lg:flex items-center space-x-2 shrink-0 pl-3 border-l border-[#22222e] text-[10px] font-mono text-zinc-500">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-zinc-400">v2.0.0</span>
          <span className="text-zinc-600">/</span>
          <span className="text-zinc-300 font-mono bg-[#161622] px-1.5 py-0.5 rounded border border-[#272738]" title="Deployed Git Commit">
            git:{commitHash ? commitHash.slice(0, 7) : '8e41824'}
          </span>
        </div>
      </div>
    </div>
  )
}
