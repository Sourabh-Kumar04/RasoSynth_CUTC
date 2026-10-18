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
  BarChart2,
  Play,
  Terminal,
  Layers,
  ChevronDown,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { CommandPalette } from '@/components/search/CommandPalette'
import { SpotlightProductTour } from '@/components/onboarding/SpotlightProductTour'
import { api } from '@/lib/api/client'

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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showTour, setShowTour] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [reviewCount, setReviewCount] = useState(0)

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
    if (typeof window !== 'undefined') {
      setMockMode(localStorage.getItem('mockMode') === 'true')
      const handleSync = () => {
        setMockMode(localStorage.getItem('mockMode') === 'true')
      }
      window.addEventListener('mockModeChanged', handleSync)
      window.addEventListener('storage', handleSync)
      return () => {
        window.removeEventListener('mockModeChanged', handleSync)
        window.removeEventListener('storage', handleSync)
      }
    }
  }, [])

  useEffect(() => {
    async function fetchPendingReviews() {
      try {
        const queue = await api.getReviewQueue()
        if (Array.isArray(queue)) {
          setReviewCount(queue.filter((q: any) => q.status === 'pending').length)
        }
      } catch {
        // Fallback or offline
      }
    }
    fetchPendingReviews()
    const timer = setInterval(fetchPendingReviews, 15000)
    return () => clearInterval(timer)
  }, [])

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-[#272738] bg-[#0a0a0f]/95 backdrop-blur-md">
        {/* Upper Telemetry & Brand Bar */}
        <div className="flex h-14 items-center justify-between px-4 lg:px-6 gap-3">
          {/* Logo & Version Badge */}
          <div className="flex items-center space-x-3 shrink-0">
            <Link href="/" className="flex items-center space-x-2.5 group">
              <div className="w-8 h-8 rounded-md bg-[#161622] border border-[#272738] group-hover:border-[#6366f1] flex items-center justify-center transition-all duration-200 shadow-sm relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-[#6366f1]/20 to-[#10b981]/20 opacity-0 group-hover:opacity-100 transition-opacity" />
                <Workflow className="w-4 h-4 text-[#6366f1] group-hover:text-[#818cf8] transition-colors relative z-10" />
              </div>
              <div className="flex flex-col">
                <span className="font-bold text-sm tracking-tight text-white flex items-center gap-1.5 font-display">
                  RasoSynth<span className="text-[#6366f1]">Tune</span>
                </span>
                <span className="text-[10px] font-mono text-[#94a3b8] tracking-widest uppercase">
                  Autonomous Studio
                </span>
              </div>
            </Link>

            <span className="hidden sm:inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-[#161622] border border-[#272738] text-[#10b981]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse mr-1.5" />
              v3.4-PROD
            </span>
          </div>

          {/* Center Telemetry Badges (Desktop) */}
          <div className="hidden xl:flex items-center space-x-2 font-mono text-xs">
            {/* Active Provider Chip */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-[#12121a] border border-[#272738]">
              <Cpu className="w-3.5 h-3.5 text-[#6366f1]" />
              <span className="text-[#94a3b8]">Provider:</span>
              <span className="text-white font-medium">Gemini 2.0 / NIM</span>
            </div>

            {/* Cost Accrual */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-[#12121a] border border-[#272738]">
              <span className="text-[#94a3b8]">Cost:</span>
              <span className="text-[#10b981] font-semibold">$0.041 / 1k</span>
            </div>

            {/* GPU VRAM Progress */}
            <div className="flex items-center space-x-2 px-2.5 py-1 rounded bg-[#12121a] border border-[#272738]">
              <span className="text-[#94a3b8]">VRAM:</span>
              <span className="text-white font-medium">78.4%</span>
              <div className="w-14 h-1.5 bg-[#1a1a24] rounded-full overflow-hidden">
                <div className="bg-[#10b981] h-full rounded-full" style={{ width: '78.4%' }} />
              </div>
            </div>

            {/* Throughput */}
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-[#12121a] border border-[#272738]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
              <span className="text-[#10b981] font-medium">2,420 tok/s</span>
            </div>
          </div>

          {/* Search & Actions */}
          <div className="flex items-center space-x-2.5">
            {/* Cmd+K Search Trigger */}
            <button
              onClick={() => setShowSearch(true)}
              className="flex items-center space-x-2 px-3 py-1.5 rounded-md bg-[#12121a] hover:bg-[#161622] border border-[#272738] hover:border-[#3b3b52] text-xs text-[#94a3b8] transition-all w-48 sm:w-60 justify-between group"
            >
              <div className="flex items-center space-x-2">
                <Search className="w-3.5 h-3.5 text-[#94a3b8] group-hover:text-white transition-colors" />
                <span className="truncate">Search studio...</span>
              </div>
              <kbd className="px-1.5 py-0.5 rounded bg-[#1a1a24] border border-[#272738] text-[10px] font-mono text-[#94a3b8]">
                ⌘K
              </kbd>
            </button>

            {/* Preset Selector */}
            <Link
              href="/studio"
              className="hidden md:inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-md bg-[#12121a] hover:bg-[#161622] border border-[#272738] text-xs text-white transition-colors"
            >
              <span className="text-[#94a3b8]">Preset:</span>
              <span className="text-[#818cf8] font-medium">AI Kosh Indic</span>
              <ChevronDown className="w-3 h-3 text-[#94a3b8]" />
            </Link>

            {/* Execution CTA Button */}
            <Link
              href="/studio"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-md bg-[#6366f1] hover:bg-[#818cf8] text-white font-mono text-xs font-semibold shadow-sm glow-indigo active:scale-95 transition-all"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span className="hidden sm:inline">Trigger Epoch</span>
              <span className="text-[10px] opacity-80">⌘↵</span>
            </Link>

            {/* Mobile menu hamburger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-1.5 rounded-md text-[#94a3b8] hover:text-white hover:bg-[#161622]"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Secondary Navigation Sub-Bar */}
        <nav className="flex items-center justify-between px-4 lg:px-6 h-9 bg-[#0e0e13] border-t border-[#1c1c28] text-xs overflow-x-auto no-scrollbar">
          <div className="flex items-center space-x-1 sm:space-x-4 shrink-0">
            {[
              { href: '/studio', label: 'Studio', icon: FlaskConical },
              { href: '/orchestration', label: 'DAG Orchestrator', icon: Workflow },
              { href: '/datasets', label: 'Datasets', icon: Database },
              { href: '/review', label: 'HITL Queue', icon: ClipboardCheck, badge: reviewCount },
              { href: '/finetune', label: 'LoRA Tuner', icon: Cpu },
              { href: '/quality', label: 'Quality', icon: BarChart2 },
              { href: '/observability', label: 'Telemetry', icon: Activity },
              { href: '/providers', label: 'Providers', icon: Beaker },
            ].map((item) => {
              const active = pathname === item.href
              const Icon = item.icon
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    'relative px-2.5 py-1.5 flex items-center space-x-1.5 font-medium transition-colors rounded-sm',
                    active ? 'text-[#818cf8]' : 'text-[#94a3b8] hover:text-white hover:bg-[#161622]'
                  )}
                >
                  <Icon className={clsx('w-3.5 h-3.5', active ? 'text-[#6366f1]' : 'text-[#94a3b8]')} />
                  <span>{item.label}</span>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span className="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40">
                      {item.badge}
                    </span>
                  )}
                  {active && (
                    <motion.div
                      layoutId="subnav-active"
                      className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#6366f1]"
                    />
                  )}
                </Link>
              )
            })}
          </div>

          <div className="hidden md:flex items-center space-x-4 text-[11px] font-mono text-[#94a3b8] shrink-0">
            <span>RUN: <strong className="text-white">SYNTH-2026-AUTON</strong></span>
            <span className="w-1 h-1 rounded-full bg-[#272738]" />
            <span>MODE: <strong className="text-[#10b981]">Grounded First</strong></span>
          </div>
        </nav>
      </header>

      {/* Command Palette Modal */}
      <CommandPalette open={showSearch} onOpenChange={setShowSearch} />
      {showTour && <SpotlightProductTour />}
    </>
  )
}
