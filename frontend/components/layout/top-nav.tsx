'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect, useRef } from 'react'
import {
  FlaskConical,
  Database,
  Workflow,
  Cpu,
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
import { SpotlightProductTour } from '@/components/onboarding/SpotlightProductTour'
import { BrandLogo } from '@/components/ui/brand-logo'
import { api } from '@/lib/api/client'

// Core primary navigation items - evenly spaced across the center
const NAV_ITEMS = [
  { href: '/studio', label: 'Studio', icon: FlaskConical },
  { href: '/datasets', label: 'Datasets', icon: Database },
  { href: '/quality', label: 'Quality', icon: BarChart2 },
  { href: '/review', label: 'Review', icon: ClipboardCheck },
  { href: '/orchestration', label: 'Pipelines', icon: Workflow },
  { href: '/finetune', label: 'Models', icon: Cpu },
  { href: '/jobs', label: 'Jobs', icon: Briefcase },
  { href: '/research', label: 'Benchmarks', icon: TrendingUp },
]

// Settings & Governance dropdown items
const SETTINGS_DROPDOWN_ITEMS = [
  { href: '/settings', label: 'Settings', desc: 'System status & compute config', icon: SettingsIcon },
  { href: '/providers', label: 'API Keys', desc: 'Model providers & credentials', icon: Key },
  { href: '/dbom', label: 'Provenance', desc: 'Cryptographic DBOM attestations', icon: ShieldCheck },
  { href: '/observability', label: 'Telemetry', desc: 'Cluster resources & health', icon: Activity },
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
      ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]'
      : status === 'degraded'
      ? 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]'
      : status === 'offline'
      ? 'bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.6)]'
      : 'bg-zinc-500'

  const label =
    status === 'healthy'
      ? 'Live'
      : status === 'degraded'
      ? 'Degraded'
      : status === 'offline'
      ? 'Offline'
      : 'Checking'

  return (
    <Link
      href="/observability"
      className="hidden lg:inline-flex items-center gap-1.5 px-2 py-1 text-xs text-zinc-400 hover:text-white transition-colors shrink-0 group"
      title="System Health & Observability"
    >
      <span className={clsx('w-2 h-2 rounded-full transition-transform group-hover:scale-125', dotColor, status === 'healthy' && 'animate-pulse')} />
      <span className="text-[12px] font-medium tracking-tight text-zinc-400 group-hover:text-zinc-200">{label}</span>
    </Link>
  )
}

export function TopNav() {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [showTour, setShowTour] = useState(false)
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

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-white/[0.06] bg-[#07060a]/90 backdrop-blur-xl select-none transition-colors">
        <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between h-14 gap-2">
          {/* Left: Brand Logo */}
          <div className="flex items-center shrink-0">
            <Link href="/" className="flex items-center space-x-2.5 group transition-transform active:scale-98">
              <BrandLogo size={34} showWordmark wordmarkClassName="text-[16px]" />
            </Link>
          </div>

          {/* Center: Evenly Spaced Primary Navigation */}
          <nav className="hidden md:flex items-center justify-center flex-1 mx-2 lg:mx-4">
            <div className="flex items-center justify-evenly w-full max-w-4xl gap-0.5 sm:gap-1">
              {NAV_ITEMS.map((item) => {
                const active = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    className={clsx(
                      'relative flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium tracking-wide transition-all shrink-0',
                      active
                        ? 'text-white font-semibold'
                        : 'text-zinc-400 hover:text-white hover:bg-white/[0.04]'
                    )}
                  >
                    <Icon className={clsx('w-3.5 h-3.5 transition-colors', active ? 'text-[#f26625]' : 'text-zinc-400')} />
                    <span>{item.label}</span>
                    {active && (
                      <span className="absolute bottom-0 left-2 right-2 h-[2px] bg-[#f26625] rounded-full shadow-[0_0_8px_rgba(242,102,37,0.7)]" />
                    )}
                  </Link>
                )
              })}
            </div>
          </nav>

          {/* Right Controls: Health Indicator, Settings Cog, + New Dataset */}
          <div className="flex items-center space-x-2 sm:space-x-3 shrink-0">
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
                  'p-2 rounded-lg text-zinc-400 hover:text-white transition-all',
                  settingsOpen
                    ? 'text-[#f26625] bg-white/[0.08]'
                    : 'hover:bg-white/[0.05]'
                )}
                aria-label="Settings and options"
              >
                <SettingsIcon className={clsx('w-4 h-4 transition-transform duration-200', settingsOpen && 'rotate-45 text-[#f26625]')} />
              </button>

              {settingsOpen && (
                <div className="absolute right-0 mt-2 w-64 rounded-2xl bg-[#0c0b14]/95 backdrop-blur-2xl border border-white/[0.08] shadow-[0_10px_35px_rgba(0,0,0,0.6)] py-2 z-50 animate-fade-in text-xs font-mono">
                  <div className="px-3.5 py-1.5 text-[10px] uppercase tracking-wider text-zinc-500 font-bold border-b border-white/[0.06]">
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
                            'flex items-start space-x-2.5 px-3.5 py-2 transition-colors hover:bg-white/[0.05]',
                            active ? 'text-[#f26625] bg-white/[0.04]' : 'text-zinc-300'
                          )}
                        >
                          <Icon className={clsx('w-4 h-4 mt-0.5 shrink-0', active ? 'text-[#f26625]' : 'text-zinc-400')} />
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

                  <div className="border-t border-white/[0.06] mt-1 pt-1.5 px-2.5">
                    <button
                      type="button"
                      onClick={() => {
                        setSettingsOpen(false)
                        setShowTour(true)
                      }}
                      className="w-full flex items-center space-x-2 px-2.5 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                      <span>Product Tour</span>
                    </button>

                    {authenticated && (
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="w-full flex items-center space-x-2 px-2.5 py-1.5 rounded-lg text-xs text-rose-400 hover:bg-rose-500/10 transition-colors"
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
              className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-md bg-[#f26625] hover:bg-[#de581a] text-white text-xs font-semibold tracking-wide transition-all active:scale-95 shadow-sm shrink-0"
            >
              <Plus className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">New Dataset</span>
            </Link>

            {/* Mobile menu toggle */}
            <button
              ref={mobileToggleRef}
              type="button"
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-nav-drawer"
              aria-label="Toggle site navigation"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors"
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
            className="md:hidden border-t border-white/[0.06] bg-[#07060a]/95 backdrop-blur-2xl p-4 space-y-3 animate-fade-in"
          >
            <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold px-1">
              Platform Navigation
            </div>
            <div className="space-y-1">
              {NAV_ITEMS.map((item) => {
                const active = pathname === item.href
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={() => setMobileMenuOpen(false)}
                    className={clsx(
                      'flex items-center space-x-3 px-3 py-2.5 rounded-xl text-xs font-medium transition-colors',
                      active
                        ? 'bg-white/[0.08] text-[#f26625] font-semibold'
                        : 'text-zinc-300 hover:bg-white/[0.04] hover:text-white'
                    )}
                  >
                    <Icon className={clsx('w-4 h-4', active ? 'text-[#f26625]' : 'text-zinc-400')} />
                    <span>{item.label}</span>
                  </Link>
                )
              })}
            </div>

            <div className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold pt-3 border-t border-white/[0.06] px-1">
              Settings &amp; Tools
            </div>
            <div className="space-y-1">
              {SETTINGS_DROPDOWN_ITEMS.map((item) => {
                const active = pathname === item.href
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? 'page' : undefined}
                    onClick={() => setMobileMenuOpen(false)}
                    className={clsx(
                      'flex items-center space-x-3 px-3 py-2 rounded-xl text-xs transition-colors',
                      active ? 'text-[#f26625] bg-white/[0.06]' : 'text-zinc-400 hover:text-white hover:bg-white/[0.03]'
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

      {showTour && <SpotlightProductTour />}
    </>
  )
}
