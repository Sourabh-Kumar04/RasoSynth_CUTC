'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
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
} from 'lucide-react'
import { clsx } from 'clsx'

const SUB_NAV_LINKS = [
  { href: '/studio', label: 'Dataset Studio', icon: FlaskConical },
  { href: '/datasets', label: 'Data Library', icon: Database },
  { href: '/finetune', label: 'Model Training', icon: Cpu },
  { href: '/quality', label: 'Quality Inspector', icon: Sparkles },
  { href: '/review', label: 'Data Review', icon: ClipboardCheck },
  { href: '/observability', label: 'System Insights', icon: Activity },
  { href: '/orchestration', label: 'Pipelines', icon: Workflow },
  { href: '/research', label: 'Benchmarks', icon: BarChart2 },
  { href: '/providers', label: 'AI Providers', icon: Beaker },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export function SubNav() {
  const pathname = usePathname()

  return (
    <div className="sticky top-14 z-30 w-full border-b border-[#22222e] bg-[#0c0e14]/90 backdrop-blur-md select-none">
      <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-11">
        {/* Horizontal Navigation Tabs */}
        <nav className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-1 scroll-smooth w-full">
          {SUB_NAV_LINKS.map((item) => {
            const active = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  'flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-mono transition-all whitespace-nowrap shrink-0 group',
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
        </nav>
      </div>
    </div>
  )
}

// Backward-compatible alias for Sidebar
export function Sidebar() {
  return <SubNav />
}
