'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import {
  FlaskConical,
  Database,
  Workflow,
  Briefcase,
  ShieldCheck,
} from 'lucide-react'
import { clsx } from 'clsx'
import { api } from '@/lib/api/client'

const NAV_LINKS = [
  { href: '/studio', label: 'Studio', icon: FlaskConical },
  { href: '/jobs', label: 'Jobs', icon: Briefcase },
  { href: '/datasets', label: 'Datasets', icon: Database },
  { href: '/orchestration', label: 'Orchestration', icon: Workflow },
  { href: '/dbom', label: 'DBOM', icon: ShieldCheck },
]

export function DashboardNavigation() {
  const pathname = usePathname()
  const [commitHash, setCommitHash] = useState<string | null>(null)

  useEffect(() => {
    api.getHealth()
      .then((res) => {
        if (res && res.commit_hash) {
          setCommitHash(res.commit_hash)
        }
      })
      .catch(() => {})
  }, [])

  return (
    <div className="sticky top-14 z-30 w-full border-b border-[#22222e] bg-[#0c0e14]/90 backdrop-blur-md select-none">
      <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-11 justify-between">
        {/* Horizontal Navigation Tabs */}
        <nav className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1 scroll-smooth">
          {NAV_LINKS.map((item) => {
            const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={clsx(
                  'flex items-center space-x-1 sm:space-x-1.5 px-2.5 sm:px-3 py-1.5 rounded-md text-xs font-mono transition-all whitespace-nowrap shrink-0 group focus-visible:ring-2 focus-visible:ring-[#f26625] focus-visible:outline-none',
                  active
                    ? 'bg-[#181824] text-white border border-[#f26625]/50 shadow-[0_0_12px_rgba(242,102,37,0.2)] font-semibold'
                    : 'text-[#a8a29e] hover:bg-[#14141e] hover:text-white hover:border-[#272738] border border-transparent'
                )}
              >
                <Icon
                  className={clsx(
                    'w-3.5 h-3.5 shrink-0 transition-transform duration-200 group-hover:scale-110',
                    active ? 'text-[#f26625]' : 'text-[#a8a29e] group-hover:text-zinc-200'
                  )}
                />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* Active Deployment Commit Marker */}
        <div className="hidden sm:flex items-center space-x-2 shrink-0 pl-3 border-l border-[#22222e] text-xs font-mono text-zinc-500">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-zinc-400">v2.0.0</span>
          <span className="text-zinc-600">/</span>
          <span className="text-zinc-300 font-mono bg-[#161622] px-1.5 py-0.5 rounded border border-[#272738]">
            git:{commitHash ? commitHash.slice(0, 7) : (process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ? process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA.slice(0, 7) : 'latest')}
          </span>
        </div>
      </div>
    </div>
  )
}
