'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useState, useEffect } from 'react'
import {
  FlaskConical,
  Database,
  Bell,
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
  Layers,
  Menu,
  X
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'

const navItems = [
  { href: '/datasets', label: 'Datasets', icon: Database },
  { href: '/studio', label: 'Studio', icon: FlaskConical },
  { href: '/orchestration', label: 'Orchestration', icon: Workflow },
  { href: '/finetune', label: 'Fine-Tune', icon: Cpu },
  { href: '/review', label: 'Review', icon: ClipboardCheck },
  { href: '/observability', label: 'Observability', icon: Activity },
  { href: '/providers', label: 'Providers', icon: Beaker },
  { href: '/research', label: 'Research', icon: Beaker },
  { href: '/settings', label: 'Settings', icon: SettingsIcon },
]

export function TopNav() {
  const pathname = usePathname()
  const [mockMode, setMockMode] = useState(false)
  const [showFallbackNotice, setShowFallbackNotice] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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
    <header className="sticky top-0 z-50 w-full border-b border-[#E2E6E0] bg-[#F6F7F4]/90 backdrop-blur-md">
      {/* Demo Mode Notice Banner */}
      {showFallbackNotice && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-4 py-1.5 text-xs flex items-center justify-between text-amber-800">
          <div className="flex items-center gap-2">
            <span className="font-bold text-[#1B3B2B]">⚡ Offline Preview Mode:</span>
            <span>Live backend unreachable. Running instant offline workflow preview for fast testing.</span>
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

      <div className="flex h-16 items-center justify-between px-6 sm:px-8 lg:px-12 max-w-[1600px] mx-auto">
        {/* Brand Logo */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="h-9 w-9 rounded-xl bg-[#1B3B2B] text-white flex items-center justify-center shadow-xs transition-transform group-hover:scale-105">
              <Sparkles className="h-4 w-4 text-emerald-400 font-bold" />
            </div>
            <div className="flex items-center">
              <span className="font-bold text-lg tracking-tight select-none leading-none text-[#1B3B2B]">
                Raso<span className="text-[#2D5E48]">SynthTune</span>
              </span>
            </div>
          </Link>

          {/* Live Telemetry Indicator */}
          <div className="hidden xl:flex items-center gap-2 px-3 py-1 rounded-full border border-[#D1D8CE] bg-[#E8ECE6] text-[11px] font-mono text-[#1B3B2B]">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-semibold uppercase tracking-wider text-[10px] text-[#55635B]">Telemetry:</span>
            <span className="font-bold">Online (99.8%)</span>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center gap-1.5 bg-[#E8ECE6]/80 p-1 rounded-full border border-[#D1D8CE]">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = pathname.startsWith(item.href)

              return (
                <Link key={item.href} href={item.href}>
                  <button
                    className={clsx(
                      'flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full transition-all duration-150',
                      isActive
                        ? 'bg-[#1B3B2B] text-white font-semibold shadow-xs'
                        : 'text-[#55635B] hover:text-[#1B3B2B] hover:bg-white/60'
                    )}
                  >
                    <Icon className={clsx("h-3.5 w-3.5", isActive ? "text-emerald-300" : "text-[#55635B]")} />
                    <span>{item.label}</span>
                  </button>
                </Link>
              )
            })}
          </nav>
        </div>

        {/* Right Controls & Mobile Menu Toggle */}
        <div className="flex items-center gap-2">
          {/* Quick Search */}
          <Button variant="outline" size="sm" className="hidden md:flex gap-2 text-[#55635B] border-[#D1D8CE] hover:bg-[#E8ECE6] rounded-full">
            <Search className="h-3.5 w-3.5 text-[#1B3B2B]" />
            <span className="text-xs">Search...</span>
            <kbd className="h-4 items-center gap-1 rounded bg-[#E8ECE6] px-1.5 text-[10px] font-mono text-[#55635B]">
              <Command className="h-2.5 w-2.5" />K
            </kbd>
          </Button>

          {/* Demo Mode Toggle */}
          <Button
            variant={mockMode ? 'default' : 'outline'}
            size="sm"
            onClick={handleToggleMock}
            title={mockMode ? 'Click to switch to Live Backend' : 'Click to enable Offline Preview Mode'}
            className={clsx(
              'gap-1.5 transition-all text-xs font-mono font-medium rounded-full',
              mockMode
                ? 'bg-[#1B3B2B] hover:bg-[#142D21] text-white'
                : 'border-[#D1D8CE] text-[#1B3B2B] hover:bg-[#E8ECE6]'
            )}
          >
            <Zap className={clsx("h-3.5 w-3.5", mockMode ? "text-emerald-400" : "text-[#1B3B2B]")} />
            <span>{mockMode ? 'Offline Demo' : 'Live Mode'}</span>
          </Button>

          {/* Notifications */}
          <Button variant="ghost" size="icon" className="relative text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full">
            <Bell className="h-4 w-4" />
            <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-emerald-500" />
          </Button>

          {/* Mobile Navigation Toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile Drawer Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden border-b border-[#E2E6E0] bg-[#F6F7F4] px-4 py-3 space-y-1 animate-in slide-in-from-top-2 duration-200">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname.startsWith(item.href)

            return (
              <Link key={item.href} href={item.href} onClick={() => setMobileMenuOpen(false)}>
                <Button
                  variant="ghost"
                  size="sm"
                  className={clsx(
                    'w-full justify-start gap-3 text-xs font-medium py-2.5 rounded-xl',
                    isActive ? 'bg-[#1B3B2B] text-white font-semibold' : 'text-[#55635B] hover:bg-[#E8ECE6]'
                  )}
                >
                  <Icon className={clsx("h-4 w-4", isActive ? "text-emerald-300" : "text-[#55635B]")} />
                  <span>{item.label}</span>
                </Button>
              </Link>
            )
          })}
        </div>
      )}
    </header>
  )
}
