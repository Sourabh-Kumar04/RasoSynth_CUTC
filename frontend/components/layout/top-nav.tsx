'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import {
  FlaskConical,
  Database,
  Search,
  Workflow,
  Cpu,
  ClipboardCheck,
  BarChart2,
  Activity,
  Beaker,
  TrendingUp,
  Settings as SettingsIcon,
  Menu,
  X,
  Sparkles,
  Zap,
} from 'lucide-react'
import { clsx } from 'clsx'
import { CommandPalette } from '@/components/search/CommandPalette'
import { SpotlightProductTour } from '@/components/onboarding/SpotlightProductTour'
import { BrandLogo } from '@/components/ui/brand-logo'

const MOBILE_NAV_ITEMS = [
  { href: '/studio', label: 'Studio', icon: FlaskConical },
  { href: '/datasets', label: 'Data Library', icon: Database },
  { href: '/finetune', label: 'Model Training', icon: Cpu },
  { href: '/orchestration', label: 'Pipelines', icon: Workflow },
  { href: '/quality', label: 'Quality Jury', icon: BarChart2 },
  { href: '/review', label: 'Data Review', icon: ClipboardCheck },
  { href: '/observability', label: 'Telemetry', icon: Activity },
  { href: '/research', label: 'Benchmarks', icon: TrendingUp },
  { href: '/providers', label: 'AI Providers', icon: Beaker },
  { href: '/settings', label: 'System Status', icon: SettingsIcon },
]

export function TopNav() {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showTour, setShowTour] = useState(false)
  const [showSearch, setShowSearch] = useState(false)

  // Global Cmd+K keyboard shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setShowSearch((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-[#272738] bg-[#0a0a0f]/95 backdrop-blur-md">
        <div className="flex h-14 items-center justify-between px-4 lg:px-6 gap-4">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 shrink-0">
            <Link href="/" className="flex items-center space-x-2.5 group">
              <BrandLogo size={32} />
              <span className="font-bold text-base tracking-tight text-white font-display leading-none">
                RasoSynth<span className="text-[#f26625]">Tune</span>
              </span>
            </Link>
          </div>

          {/* Search Bar (Cmd+K) */}
          <div className="flex-1 max-w-md mx-2 hidden sm:block">
            <button
              onClick={() => setShowSearch(true)}
              className="w-full flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-[#12121a]/80 hover:bg-[#161622] border border-[#272738] hover:border-[#f26625]/40 text-xs text-[#94a3b8] hover:text-zinc-200 transition-all justify-between group shadow-inner"
            >
              <div className="flex items-center space-x-2">
                <Search className="w-3.5 h-3.5 text-[#94a3b8] group-hover:text-[#f26625] transition-colors" />
                <span className="truncate">Search studio, presets, datasets...</span>
              </div>
              <kbd className="px-1.5 py-0.5 rounded bg-[#161622] border border-[#272738] text-[10px] font-mono text-[#94a3b8] group-hover:text-white group-hover:border-[#3b3b52]">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* Right Actions */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowTour(true)}
              className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-[#272738] bg-[#12121a] hover:bg-[#181826] hover:border-amber-500/40 text-xs font-mono text-zinc-300 hover:text-white transition-all"
              title="Launch Guided Product Tour"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Tour</span>
            </button>

            <button
              onClick={() => setShowSearch(true)}
              className="sm:hidden p-2 rounded-lg text-[#94a3b8] hover:text-white hover:bg-[#161622] border border-[#272738]"
              title="Search"
            >
              <Search className="w-4 h-4" />
            </button>

            <Link
              href="/studio"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white text-xs font-mono font-bold transition-all active:scale-95 glow-yc shadow-sm"
            >
              <FlaskConical className="w-3.5 h-3.5 text-white" />
              <span>New Dataset</span>
            </Link>

            {/* Mobile menu toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-1.5 rounded-lg text-[#94a3b8] hover:text-white hover:bg-[#161622] border border-[#272738]"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5 text-white" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <nav className="lg:hidden border-t border-[#272738] bg-[#0e0e13] p-4 space-y-1">
            {MOBILE_NAV_ITEMS.map((item) => {
              const active = pathname === item.href
              const Icon = item.icon
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={clsx(
                    'flex items-center space-x-2.5 px-3 py-2 rounded-md text-xs font-medium transition-colors',
                    active ? 'bg-[#161622] text-[#f26625] border-l-2 border-[#f26625]' : 'text-[#94a3b8] hover:text-white hover:bg-[#161622]'
                  )}
                >
                  <Icon className={clsx('w-4 h-4', active ? 'text-[#f26625]' : 'text-[#94a3b8]')} />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
        )}
      </header>

      {/* Command Palette Modal */}
      <CommandPalette open={showSearch} onOpenChange={setShowSearch} />
      {showTour && <SpotlightProductTour />}
    </>
  )
}
