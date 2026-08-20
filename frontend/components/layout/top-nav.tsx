'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import {
  FlaskConical,
  Database,
  Search,
  Command,
  Activity,
  Workflow,
  Beaker,
  Settings as SettingsIcon,
  Cpu,
  ClipboardCheck,
  Zap,
  Sparkles,
  Menu,
  X,
  BarChart2
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { OnboardingModal } from '@/components/onboarding/OnboardingModal'
import { CommandPalette } from '@/components/search/CommandPalette'
import { InteractiveProductTour } from '@/components/onboarding/InteractiveProductTour'

export interface NavGroup {
  name: string
  items: {
    href: string
    label: string
    icon: any
    tooltip?: string
  }[]
}

export const navGroups: NavGroup[] = [
  {
    name: 'Build',
    items: [
      { href: '/studio', label: 'Studio', icon: FlaskConical, tooltip: 'AI-Powered Dataset Synthesis Workspace' },
      { href: '/datasets', label: 'Datasets', icon: Database, tooltip: 'Dataset Explorer & Format Exporter' },
      { href: '/orchestration', label: 'Orchestration', icon: Workflow, tooltip: 'Real-time DAG Execution Engine' },
    ],
  },
  {
    name: 'Train & Quality',
    items: [
      { href: '/finetune', label: 'Fine-Tune', icon: Cpu, tooltip: 'PEFT / LoRA Training Studio' },
      { href: '/review', label: 'Review', icon: ClipboardCheck, tooltip: 'Human-in-the-Loop (HITL) Queue' },
      { href: '/quality', label: 'Quality', icon: BarChart2, tooltip: 'Dataset Benchmarks & Grounding' },
    ],
  },
  {
    name: 'Operate',
    items: [
      { href: '/observability', label: 'Observability', icon: Activity, tooltip: 'OpenTelemetry Metrics & Tracing' },
      { href: '/providers', label: 'Providers', icon: Beaker, tooltip: 'Multi-Provider Health & Latency' },
    ],
  },
  {
    name: 'Research & System',
    items: [
      { href: '/research', label: 'Research', icon: Beaker, tooltip: 'Provider Benchmarking & DSPy Evaluation' },
      { href: '/settings', label: 'Settings', icon: SettingsIcon, tooltip: 'Platform Environment & API Keys' },
    ],
  },
]

export function TopNav() {
  const pathname = usePathname()
  const [mockMode, setMockMode] = useState(false)
  const [showFallbackNotice, setShowFallbackNotice] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showTour, setShowTour] = useState(false)
  const [showSearch, setShowSearch] = useState(false)

  // Global Cmd+K / Ctrl+K keyboard shortcut listener
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
    if (typeof window !== 'undefined') {
      setMockMode(localStorage.getItem('mockMode') === 'true')

      const handleSync = () => {
        setMockMode(localStorage.getItem('mockMode') === 'true')
      }

      const handleFallback = () => {
        setMockMode(true)
        setShowFallbackNotice(true)
      }

      window.addEventListener('storage', handleSync)
      window.addEventListener('mockModeChanged', handleSync)
      window.addEventListener('backend-unreachable-fallback', handleFallback)

      return () => {
        window.removeEventListener('storage', handleSync)
        window.removeEventListener('mockModeChanged', handleSync)
        window.removeEventListener('backend-unreachable-fallback', handleFallback)
      }
    }
  }, [])

  const handleToggleMock = () => {
    const newVal = !mockMode
    setMockMode(newVal)
    localStorage.setItem('mockMode', newVal ? 'true' : 'false')
    window.location.reload()
  }

  const handleRetryLiveBackend = () => {
    setMockMode(false)
    localStorage.setItem('mockMode', 'false')
    setShowFallbackNotice(false)
    window.location.reload()
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#E2E6E0] bg-[#F6F7F4]/95 backdrop-blur-md">
      {/* Auto-popup or requested Onboarding Guided Tour */}
      <OnboardingModal open={showTour} onOpenChange={setShowTour} />

      {/* Global Interactive Command Palette Search */}
      <CommandPalette open={showSearch} onOpenChange={setShowSearch} />

      {/* Floating Interactive Product Tour Widget */}
      <InteractiveProductTour />

      {/* Demo Mode Notice Banner */}
      {showFallbackNotice && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 text-xs flex items-center justify-between text-amber-800">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[#1B3B2B]">⚡ Offline Preview Mode:</span>
            <span>Live backend unreachable. Running instant offline workflow preview for testing.</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-6 text-[11px] border-amber-600/30 text-amber-900 hover:bg-amber-500/10 rounded-full"
              onClick={handleRetryLiveBackend}
            >
              Retry Live Connection
            </Button>
            <button
              onClick={() => setShowFallbackNotice(false)}
              className="text-[#1B3B2B] hover:opacity-70 ml-2 font-bold"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      <div className="flex h-16 items-center justify-between px-4 sm:px-6 lg:px-8 w-full gap-4">
        {/* Brand Logo */}
        <div className="flex items-center gap-4 lg:gap-6 min-w-0">
          <Link href="/" className="flex items-center gap-2.5 group shrink-0">
            <div className="h-9 w-9 rounded-xl bg-[#1B3B2B] text-white flex items-center justify-center shadow-xs transition-transform group-hover:scale-105">
              <Sparkles className="h-4 w-4 text-emerald-400 font-bold" />
            </div>
            <div className="flex items-center">
              <span className="font-bold text-lg tracking-tight select-none leading-none text-[#1B3B2B]">
                Raso<span className="bg-gradient-to-r from-emerald-600 to-cyan-600 bg-clip-text text-transparent">SynthTune</span>
              </span>
            </div>
          </Link>

          {/* Desktop Categorized Navigation */}
          <nav className="hidden lg:flex items-center gap-2 bg-[#E8ECE6]/80 p-1 rounded-full border border-[#D1D8CE]">
            {navGroups.map((group) => (
              <div key={group.name} className="flex items-center gap-1 border-r last:border-r-0 border-[#D1D8CE] pr-1.5 last:pr-0">
                {group.items.map((item) => {
                  const Icon = item.icon
                  const isActive = pathname.startsWith(item.href)

                  return (
                    <Link key={item.href} href={item.href} className="shrink-0">
                      <button
                        title={item.tooltip || item.label}
                        className={clsx(
                          'flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full transition-all duration-150 shrink-0',
                          isActive
                            ? 'bg-[#1B3B2B] text-white font-semibold shadow-xs'
                            : 'text-[#55635B] hover:text-[#1B3B2B] hover:bg-white/60'
                        )}
                      >
                        <Icon className={clsx("h-3.5 w-3.5 shrink-0", isActive ? "text-emerald-300" : "text-[#55635B]")} />
                        <span>{item.label}</span>
                      </button>
                    </Link>
                  )
                })}
              </div>
            ))}
          </nav>
        </div>

        {/* Right Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Functional Quick Search with Cmd+K */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSearch(true)}
            className="flex gap-2 text-[#55635B] border-[#D1D8CE] hover:bg-[#E8ECE6] rounded-full text-xs font-medium"
            title="Open Search (Cmd+K)"
          >
            <Search className="h-3.5 w-3.5 text-[#1B3B2B]" />
            <span className="hidden sm:inline text-xs">Search...</span>
            <kbd className="hidden sm:inline-flex h-4 items-center gap-1 rounded bg-[#E8ECE6] px-1.5 text-[10px] font-mono text-[#55635B]">
              <Command className="h-2.5 w-2.5" />K
            </kbd>
          </Button>

          {/* Mode Indicator & Toggle */}
          <div className="flex items-center gap-1.5 bg-[#E8ECE6] p-1 rounded-full border border-[#D1D8CE]">
            <Button
              variant={mockMode ? 'default' : 'outline'}
              size="sm"
              onClick={handleToggleMock}
              title={mockMode ? 'Click to switch to Live API Backend' : 'Click to enable Offline Preview Mode'}
              className={clsx(
                'gap-1.5 transition-all text-xs font-mono font-medium rounded-full h-7 px-3',
                mockMode
                  ? 'bg-amber-600 hover:bg-amber-700 text-white'
                  : 'bg-[#1B3B2B] hover:bg-[#142D21] text-white border-transparent'
              )}
            >
              <span className={clsx("h-2 w-2 rounded-full", mockMode ? "bg-amber-300" : "bg-emerald-400 animate-pulse")} />
              <span>{mockMode ? 'Offline Demo' : 'Live API'}</span>
            </Button>
          </div>

          {/* Mobile Menu Toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden h-9 w-9 rounded-full text-[#1B3B2B] hover:bg-[#E8ECE6]"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Categorized Drawer Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-t border-[#E2E6E0] bg-white p-4 space-y-4 animate-fade-in shadow-xl max-h-[85vh] overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.name} className="space-y-1.5">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#55635B] px-1">
                {group.name}
              </span>
              <div className="grid grid-cols-2 gap-2">
                {group.items.map((item) => {
                  const Icon = item.icon
                  const isActive = pathname.startsWith(item.href)

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <div
                        className={clsx(
                          'flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium transition-all',
                          isActive
                            ? 'bg-[#1B3B2B] text-white border-[#1B3B2B] font-semibold'
                            : 'bg-[#F6F7F4] text-[#1B3B2B] border-[#E2E6E0] hover:bg-[#E8ECE6]'
                        )}
                      >
                        <Icon className={clsx('h-4 w-4 shrink-0', isActive ? 'text-emerald-300' : 'text-[#1B3B2B]')} />
                        <span className="truncate">{item.label}</span>
                      </div>
                    </Link>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </header>
  )
}
