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
  ShieldCheck,
  TrendingUp,
  Settings as SettingsIcon,
  Menu,
  X,
} from 'lucide-react'
import { clsx } from 'clsx'
import { CommandPalette } from '@/components/search/CommandPalette'
import { SpotlightProductTour } from '@/components/onboarding/SpotlightProductTour'
import { api } from '@/lib/api/client'

const MOBILE_NAV_ITEMS = [
  { href: '/studio', label: 'Studio', icon: FlaskConical },
  { href: '/orchestration', label: 'DAG Orchestrator', icon: Workflow },
  { href: '/datasets', label: 'Datasets & DBOM', icon: Database },
  { href: '/finetune', label: 'Fine-Tune Studio', icon: Cpu },
  { href: '/research', label: 'Research & Benchmarks', icon: TrendingUp },
  { href: '/review', label: 'HITL Review', icon: ClipboardCheck },
  { href: '/quality', label: 'Quality Canvas', icon: BarChart2 },
  { href: '/observability', label: 'Telemetry & Traces', icon: Activity },
  { href: '/providers', label: 'Providers', icon: Beaker },
  { href: '/settings', label: 'Settings', icon: SettingsIcon },
]

export function TopNav() {
  const pathname = usePathname()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showTour, setShowTour] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [isHealthy, setIsHealthy] = useState(true)

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

  useEffect(() => {
    async function checkHealth() {
      try {
        const health = await api.getHealth()
        setIsHealthy(Boolean(health && (health.status === 'ok' || health.status === 'healthy')))
      } catch {
        setIsHealthy(false)
      }
    }
    checkHealth()
    const timer = setInterval(checkHealth, 30000)
    return () => clearInterval(timer)
  }, [])

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-[#272738] bg-[#0a0a0f]/95 backdrop-blur-md">
        <div className="flex h-14 items-center justify-between px-4 lg:px-6 gap-4">
          {/* Logo & Brand - YC Style */}
          <div className="flex items-center space-x-3 shrink-0">
            <Link href="/" className="flex items-center space-x-2.5 group">
              <div className="w-8 h-8 rounded-md bg-[#f26625] flex items-center justify-center transition-all duration-200 shadow-sm relative overflow-hidden group-hover:bg-[#de581a]">
                <span className="font-mono font-black text-white text-base tracking-tighter">Y</span>
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-base tracking-tight text-white font-display leading-none">
                  RasoSynth<span className="text-[#f26625]">Tune</span>
                </span>
                <span className="text-[10px] font-mono text-[#f26625] tracking-wider uppercase mt-0.5 font-semibold">
                  Autonomous Refinery
                </span>
              </div>
            </Link>

            <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[#161622] border border-[#272738] text-[#10b981]">
              <span className={clsx('w-1.5 h-1.5 rounded-full mr-1.5', isHealthy ? 'bg-[#10b981] animate-pulse' : 'bg-amber-400')} />
              {isHealthy ? 'Online' : 'Degraded'}
            </span>

            <Link
              href="/datasets"
              className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-medium bg-emerald-950/30 border border-emerald-500/30 text-[#10b981] hover:bg-emerald-950/50 transition-colors"
              title="Cryptographic DBOM Attestation Engine Active"
            >
              <ShieldCheck className="w-3 h-3 text-[#10b981]" />
              <span>DBOM Verified</span>
            </Link>

            <span className="hidden xl:inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono text-[#f26625] bg-orange-950/30 border border-orange-500/30">
              <span className="w-1.5 h-1.5 rounded-full bg-[#f26625]" />
              <span>YC Proof-Carrier</span>
            </span>
          </div>

          {/* Search Bar (Cmd+K) */}
          <div className="flex-1 max-w-md mx-2 hidden sm:block">
            <button
              onClick={() => setShowSearch(true)}
              className="w-full flex items-center space-x-2 px-3 py-1.5 rounded-full bg-[#12121a] hover:bg-[#161622] border border-[#272738] hover:border-[#3b3b52] text-xs text-[#94a3b8] transition-all justify-between group"
            >
              <div className="flex items-center space-x-2">
                <Search className="w-3.5 h-3.5 text-[#94a3b8] group-hover:text-white transition-colors" />
                <span className="truncate">Search studio, presets, datasets...</span>
              </div>
              <kbd className="px-1.5 py-0.5 rounded bg-[#161622] border border-[#272738] text-[10px] font-mono text-[#94a3b8]">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* Right Actions */}
          <div className="flex items-center space-x-2.5">
            <button
              onClick={() => setShowSearch(true)}
              className="sm:hidden p-2 rounded-lg text-[#94a3b8] hover:text-white hover:bg-[#161622] border border-[#272738]"
              title="Search"
            >
              <Search className="w-4 h-4" />
            </button>

            <Link
              href="/studio"
              className="inline-flex items-center space-x-1.5 px-3.5 py-1.5 rounded-md bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white text-xs font-mono font-bold shadow-sm transition-all active:scale-95 glow-yc"
            >
              <FlaskConical className="w-3.5 h-3.5" />
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
                    'flex items-center space-x-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors',
                    active ? 'bg-[#161622] text-[#818cf8]' : 'text-[#94a3b8] hover:text-white hover:bg-[#161622]'
                  )}
                >
                  <Icon className={clsx('w-4 h-4', active ? 'text-[#6366f1]' : 'text-[#94a3b8]')} />
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
