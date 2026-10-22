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
} from 'lucide-react'
import { clsx } from 'clsx'

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

  return (
    <div className="sticky top-14 z-30 w-full border-b border-[#1e2235] bg-[#07080d]/95 backdrop-blur-md select-none">
      <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-11">
        {/* Horizontal Navigation Tabs */}
        <nav className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1 scroll-smooth w-full">
          {SUB_NAV_LINKS.map((item) => {
            const active = pathname === item.href
            const Icon = item.icon
            const isOrchestration = item.href === '/orchestration'
            return (
              <Link
                key={item.href}
                href={item.href}
                className={clsx(
                  'flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-mono transition-all whitespace-nowrap shrink-0 relative',
                  active
                    ? 'bg-[#0f111a] text-white border border-[#008ecc]/50 shadow-[0_0_12px_rgba(0,142,204,0.3)] font-semibold'
                    : 'text-[#8b949e] hover:bg-[#0c0d14] hover:text-white'
                )}
              >
                <Icon
                  className={clsx(
                    'w-3.5 h-3.5 shrink-0',
                    active ? 'text-[#008ecc]' : 'text-[#8b949e]'
                  )}
                />
                <span>{item.label}</span>
                {isOrchestration && (
                  <span className="h-1.5 w-1.5 rounded-full bg-[#ff0038] shadow-[0_0_8px_rgba(255,0,56,0.8)] animate-pulse" />
                )}
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
