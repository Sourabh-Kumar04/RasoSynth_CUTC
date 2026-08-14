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
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'

// All pages connected to real APIs
const navItems = [
  { href: '/datasets', label: 'Datasets', icon: Database },
  { href: '/studio', label: 'Studio', icon: FlaskConical },
  { href: '/orchestration', label: 'Orchestration', icon: Workflow },
  { href: '/observability', label: 'Observability', icon: Activity },
  { href: '/providers', label: 'Providers', icon: Beaker },
  { href: '/research', label: 'Research', icon: Beaker },
  { href: '/settings', label: 'Settings', icon: SettingsIcon },
]

export function TopNav() {
  const pathname = usePathname()
  const [mockMode, setMockMode] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setMockMode(localStorage.getItem('mockMode') === 'true' || localStorage.getItem('mockMode') === null)
      
      const handleSync = () => {
        setMockMode(localStorage.getItem('mockMode') === 'true' || localStorage.getItem('mockMode') === null)
      }
      window.addEventListener('storage', handleSync)
      window.addEventListener('mockModeChanged', handleSync)
      return () => {
        window.removeEventListener('storage', handleSync)
        window.removeEventListener('mockModeChanged', handleSync)
      }
    }
  }, [])

  const handleToggleMock = () => {
    const newVal = !mockMode
    setMockMode(newVal)
    localStorage.setItem('mockMode', newVal ? 'true' : 'false')
    window.location.reload()
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex h-14 items-center px-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 mr-8 group">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-orange-500 to-amber-500 flex items-center justify-center shadow-[0_0_10px_rgba(249,115,22,0.3)] transition-all group-hover:scale-105 group-hover:shadow-[0_0_15px_rgba(249,115,22,0.5)]">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              className="h-5 w-5 text-white"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="font-bold text-lg hidden md:inline-block tracking-wide select-none">
            <span className="text-white">Raso</span>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-amber-500">SynthTune</span>
          </span>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = pathname.startsWith(item.href)

            return (
              <Link key={item.href} href={item.href}>
                <Button
                  variant="ghost"
                  size="sm"
                  className={clsx(
                    'gap-2 text-muted-foreground hover:text-foreground',
                    isActive && 'bg-surface text-foreground'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="hidden lg:inline">{item.label}</span>
                </Button>
              </Link>
            )
          })}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Search */}
        <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground">
          <Search className="h-4 w-4" />
          <span className="hidden md:inline">Search...</span>
          <kbd className="hidden md:inline-flex h-5 items-center gap-1 rounded border border-border bg-surface px-1.5 text-xs font-mono text-muted-foreground">
            <Command className="h-3 w-3" />K
          </kbd>
        </Button>

        {/* Mock/Demo Mode Toggle */}
        <Button
          variant={mockMode ? 'default' : 'outline'}
          size="sm"
          onClick={handleToggleMock}
          className={clsx(
            'ml-2 gap-1.5 transition-all text-xs',
            mockMode
              ? 'bg-amber-600 hover:bg-amber-700 text-white border-transparent shadow-[0_0_10px_rgba(217,119,6,0.3)] animate-pulse'
              : 'border-border text-muted-foreground hover:text-foreground'
          )}
        >
          <FlaskConical className="h-3.5 w-3.5" />
          <span>{mockMode ? 'Demo Active' : 'Go Demo'}</span>
        </Button>

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="ml-2 relative">
          <Bell className="h-4 w-4" />
          <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-accent" />
        </Button>
      </div>
    </header>
  )
}
