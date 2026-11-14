'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect, useRef } from 'react'
import {
  FlaskConical,
  Database,
  Workflow,
  Cpu,
  Search,
  Settings as SettingsIcon,
  Menu,
  X,
  Sparkles,
  Plus,
  ShieldCheck,
  Activity,
  Key,
  ClipboardCheck,
  BarChart2,
  Briefcase,
  TrendingUp,
  LogOut,
} from 'lucide-react'
import { clsx } from 'clsx'
import { CommandPalette } from '@/components/search/CommandPalette'
import { SpotlightProductTour } from '@/components/onboarding/SpotlightProductTour'
import { BrandLogo } from '@/components/ui/brand-logo'
import { api } from '@/lib/api/client'

const CORE_PILLARS = [
  { href: '/studio', label: 'Studio', icon: FlaskConical },
  { href: '/datasets', label: 'Datasets', icon: Database },
  { href: '/orchestration', label: 'Pipelines', icon: Workflow },
  { href: '/finetune', label: 'Models', icon: Cpu },
]

const SETTINGS_DROPDOWN_ITEMS = [
  { href: '/settings', label: 'Settings', desc: 'System status & configuration', icon: SettingsIcon },
  { href: '/observability', label: 'Telemetry', desc: 'Cluster metrics & observability', icon: Activity },
  { href: '/providers', label: 'API Keys', desc: 'Model providers & API credentials', icon: Key },
  { href: '/dbom', label: 'Attestation', desc: 'DBOM cryptographic provenance', icon: ShieldCheck },
]

const SECONDARY_MANAGEMENT_ITEMS = [
  { href: '/review', label: 'Review', icon: ClipboardCheck },
  { href: '/quality', label: 'Quality', icon: BarChart2 },
  { href: '/jobs', label: 'Jobs', icon: Briefcase },
  { href: '/research', label: 'Benchmarks', icon: TrendingUp },
]

function SystemHealthIndicator() {
  const [status, setStatus] = useState<'healthy' | 'degraded' | 'offline' | 'checking'>('checking')

  useEffect(() => {
    let cancelled = false
    api
      .getHealth()
      .then((res: unknown) => {
        if (cancelled) return
        const r = res as { status?: string; system_metrics?: { memory_used_percent?: number; cpu_load_1m?: number } } | null
        const rawStatus = (r?.status || 'unknown').toLowerCase()
        const memPct = r?.system_metrics?.memory_used_percent
        const cpuLoad = r?.system_metrics?.cpu_load_1m
        const critical = (memPct != null && memPct > 85) || (cpuLoad != null && cpuLoad > 3.0)
        if (critical || rawStatus === 'degraded' || rawStatus === 'standby') {
          setStatus('degraded')
        } else if (rawStatus === 'healthy') {
          setStatus('healthy')
        } else {
          setStatus('healthy')
        }
      })
      .catch(() => {
        if (!cancelled) setStatus('offline')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const dotColor =
    status === 'healthy'
      ? 'bg-emerald-400'
      : status === 'degraded'
      ? 'bg-amber-400'
      : status === 'offline'
      ? 'bg-rose-400'
      : 'bg-zinc-500'

  const label =
    status === 'healthy'
      ? 'Healthy'
      : status === 'degraded'
      ? 'Degraded'
      : status === 'offline'
      ? 'Offline'
      : 'Checking'

  return (
    <Link
      href="/observability"
      className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#12121a] hover:bg-[#161622] border border-[#272738] hover:border-[#3b3b52] text-xs font-mono text-zinc-300 transition-colors shrink-0"
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full', dotColor, status === 'healthy' && 'animate-pulse')} />
      <span className="text-[11px] font-medium text-zinc-300">{label}</span>
    </Link>
  )
}

export function TopNav() {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [showTour, setShowTour] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [authenticated, setAuthenticated] = useState<boolean | null>(null)
  const mobileToggleRef = useRef<HTMLButtonElement>(null)
  const mobileDrawerRef = useRef<HTMLElement>(null)
  const settingsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setAuthenticated(api.isAuthenticated())
    const handleAuthChange = () => setAuthenticated(api.isAuthenticated())
    window.addEventListener('storage', handleAuthChange)
    return () => window.removeEventListener('storage', handleAuthChange)
  }, [])

  const handleLogout = async () => {
    await api.logout()
    setAuthenticated(false)
    window.location.href = '/dashboard'
  }

  // Close settings dropdown on click outside or Escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
        setSettingsOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setSettingsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  // Mobile drawer keyboard & scroll lock
  useEffect(() => {
    if (!mobileMenuOpen) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    mobileDrawerRef.current?.querySelector('a')?.focus()
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false)
        mobileToggleRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = prevOverflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [mobileMenuOpen])

  // Global Cmd+K listener
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
      <header className="sticky top-0 z-40 w-full border-b border-[#272738] bg-[#0a0a0f]/95 backdrop-blur-md select-none">
        <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14 gap-2 sm:gap-4">
          {/* Left: Brand Logo & 4 Pillars */}
          <div className="flex items-center space-x-3 lg:space-x-6 shrink-0">
            <Link href="/" className="flex items-center space-x-2.5 group">
              <BrandLogo size={36} showWordmark wordmarkClassName="text-[16px]" />
            </Link>

            {/* 4 Core Pillars */}
            <nav className="hidden md:flex items-center space-x-1">
              {CORE_PILLARS.map((item) => {
                const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={clsx(
                      'flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-colors shrink-0',
                      active
                        ? 'bg-[#181824] text-white border border-[#f26625]/50 shadow-[0_0_12px_rgba(242,102,37,0.15)] font-semibold'
                        : 'text-[#a8a29e] hover:bg-[#14141e] hover:text-white border border-transparent'
                    )}
                  >
                    <Icon className={clsx('w-3.5 h-3.5', active ? 'text-[#f26625]' : 'text-[#a8a29e]')} />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>

          {/* Center: Global Search Bar (Cmd+K) */}
          <div className="flex-1 max-w-xs xl:max-w-md hidden sm:block mx-2">
            <button
              type="button"
              onClick={() => setShowSearch(true)}
              className="w-full flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#12121a]/80 hover:bg-[#161622] border border-[#272738] hover:border-[#f26625]/40 text-xs text-[#a8a29e] hover:text-zinc-200 transition-all justify-between group shadow-inner"
            >
              <div className="flex items-center space-x-2 truncate">
                <Search className="w-3.5 h-3.5 text-[#a8a29e] group-hover:text-[#f26625] transition-colors shrink-0" />
                <span className="truncate">Search studio, datasets, pipelines...</span>
              </div>
              <kbd className="px-1.5 py-0.5 rounded bg-[#161622] border border-[#272738] text-[10px] font-mono text-[#a8a29e] group-hover:text-white group-hover:border-[#3b3b52] shrink-0">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* Right: Health Indicator, Settings Cog Dropdown, Tour, + New Dataset, Mobile Toggle */}
          <div className="flex items-center space-x-2 shrink-0">
            {/* Mobile Search Button */}
            <button
              type="button"
              onClick={() => setShowSearch(true)}
              className="sm:hidden p-2 rounded-lg text-[#a8a29e] hover:text-white hover:bg-[#161622] border border-[#272738]"
              aria-label="Search"
            >
              <Search className="w-4 h-4" />
            </button>

            {/* System Health Dot Indicator */}
            <SystemHealthIndicator />

            {/* Settings Cog Dropdown */}
            <div className="relative" ref={settingsRef}>
              <button
                type="button"
                aria-expanded={settingsOpen}
                aria-haspopup="menu"
                onClick={() => setSettingsOpen(!settingsOpen)}
                className={clsx(
                  'p-1.5 rounded-md border text-zinc-400 hover:text-white transition-all',
                  settingsOpen
                    ? 'bg-[#181824] text-[#f26625] border-[#f26625]/50'
                    : 'bg-[#12121a] border-[#272738] hover:bg-[#161622]'
                )}
                aria-label="Settings and management options"
              >
                <SettingsIcon className={clsx('w-4 h-4 transition-transform', settingsOpen && 'rotate-45 text-[#f26625]')} />
              </button>

              {settingsOpen && (
                <div className="absolute right-0 mt-2 w-64 rounded-xl bg-[#0f0f17] border border-[#272738] shadow-2xl py-2 z-50 animate-fade-in text-xs font-mono">
                  <div className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-zinc-500 font-bold border-b border-[#1c1c28]">
                    Settings &amp; Governance
                  </div>
                  <div className="py-1">
                    {SETTINGS_DROPDOWN_ITEMS.map((item) => {
                      const active = pathname === item.href
                      const Icon = item.icon
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={() => setSettingsOpen(false)}
                          className={clsx(
                            'flex items-start space-x-2.5 px-3 py-2 transition-colors hover:bg-[#1a1a26]',
                            active ? 'text-[#f26625] bg-[#161622]' : 'text-zinc-300'
                          )}
                        >
                          <Icon className={clsx('w-4 h-4 mt-0.5 shrink-0', active ? 'text-[#f26625]' : 'text-[#a8a29e]')} />
                          <div>
                            <div className={clsx('font-semibold text-xs', active ? 'text-[#f26625]' : 'text-zinc-200')}>
                              {item.label}
                            </div>
                            <div className="text-[10px] text-zinc-500 font-sans">{item.desc}</div>
                          </div>
                        </Link>
                      )
                    })}
                  </div>

                  <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-500 font-bold border-t border-[#1c1c28] mt-1 pt-2">
                    Workspace Tools
                  </div>
                  <div className="grid grid-cols-2 gap-1 px-2 py-1">
                    {SECONDARY_MANAGEMENT_ITEMS.map((item) => {
                      const active = pathname === item.href
                      const Icon = item.icon
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          onClick={() => setSettingsOpen(false)}
                          className={clsx(
                            'flex items-center space-x-1.5 px-2 py-1.5 rounded text-[11px] transition-colors hover:bg-[#1a1a26]',
                            active ? 'text-[#f26625] bg-[#161622]' : 'text-zinc-400 hover:text-white'
                          )}
                        >
                          <Icon className="w-3 h-3 shrink-0" />
                          <span className="truncate">{item.label}</span>
                        </Link>
                      )
                    })}
                  </div>

                  <div className="border-t border-[#1c1c28] mt-1 pt-1.5 px-2">
                    <button
                      type="button"
                      onClick={() => {
                        setSettingsOpen(false)
                        setShowTour(true)
                      }}
                      className="w-full flex items-center space-x-2 px-2.5 py-1.5 rounded text-xs text-zinc-400 hover:text-white hover:bg-[#1a1a26] transition-colors"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      <span>Product Tour</span>
                    </button>

                    {authenticated && (
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="w-full flex items-center space-x-2 px-2.5 py-1.5 rounded text-xs text-rose-400 hover:bg-rose-500/10 transition-colors"
                      >
                        <LogOut className="w-3.5 h-3.5" />
                        <span>Log Out</span>
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Primary CTA: + New Dataset */}
            <Link
              href="/studio"
              className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-md bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white text-xs font-mono font-bold transition-all active:scale-95 shadow-sm shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden xs:inline">New Dataset</span>
            </Link>

            {/* Mobile menu toggle */}
            <button
              ref={mobileToggleRef}
              type="button"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-nav-drawer"
              aria-label="Toggle site navigation"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 rounded-lg text-[#a8a29e] hover:text-white hover:bg-[#161622] border border-[#272738]"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5 text-white" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <nav
            ref={mobileDrawerRef}
            id="mobile-nav-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Site navigation"
            className="md:hidden border-t border-[#272738] bg-[#0e0e13] p-4 space-y-3"
          >
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono font-bold">
              Core Pillars
            </div>
            <div className="grid grid-cols-2 gap-2">
              {CORE_PILLARS.map((item) => {
                const active = pathname === item.href
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={() => setMobileMenuOpen(false)}
                    className={clsx(
                      'flex items-center space-x-2 px-3 py-2 rounded-md text-xs font-medium font-mono transition-colors border',
                      active
                        ? 'bg-[#181824] text-[#f26625] border-[#f26625]/50'
                        : 'bg-[#12121a] text-zinc-300 border-[#222232] hover:text-white'
                    )}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>

            <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono font-bold pt-2 border-t border-[#1c1c28]">
              Settings &amp; Management
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {[...SETTINGS_DROPDOWN_ITEMS, ...SECONDARY_MANAGEMENT_ITEMS].map((item) => {
                const active = pathname === item.href
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={() => setMobileMenuOpen(false)}
                    className={clsx(
                      'flex items-center space-x-2 px-2.5 py-1.5 rounded text-xs font-mono transition-colors',
                      active ? 'text-[#f26625] bg-[#161622]' : 'text-zinc-400 hover:text-white hover:bg-[#14141e]'
                    )}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>
          </nav>
        )}
      </header>

      {/* Command Palette Modal */}
      <CommandPalette open={showSearch} onOpenChange={setShowSearch} />
      {showTour && <SpotlightProductTour />}
    </>
  )
}
