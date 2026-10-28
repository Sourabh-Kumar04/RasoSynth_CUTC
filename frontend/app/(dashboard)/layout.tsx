import Link from 'next/link'
import { TopNav } from '@/components/layout/top-nav'
import { DashboardNavigation } from '@/components/layout/sub-nav'
import { BrandLogo } from '@/components/ui/brand-logo'
import { FooterStatus } from '@/components/layout/footer-status'
import { ShieldCheck, Terminal, Github, ExternalLink, Activity, Info } from 'lucide-react'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="relative min-h-screen bg-[#0a0a0f] text-[#f8fafc] flex flex-col font-sans antialiased bg-dot-grid selection:bg-[#f26625]/30 selection:text-white">
      {/* Ambient Lighting Gradient Beam */}
      <div 
        aria-hidden="true" 
        className="pointer-events-none fixed inset-x-0 top-0 h-[480px] bg-[radial-gradient(ellipse_80%_60%_at_50%_-15%,rgba(242,102,37,0.12),rgba(99,102,241,0.04)_45%,transparent_75%)] z-0"
      />
      
      <div className="relative z-10 flex flex-col min-h-screen">
        <TopNav />
        <DashboardNavigation />
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
          {children}
        </main>

        {/* Global App Shell Footer */}
        <footer className="w-full border-t border-[#1f1f2e] bg-[#08080d]/90 backdrop-blur-md mt-auto py-5 px-4 sm:px-8 text-xs font-mono text-[#94a3b8]">
          <div className="max-w-[1600px] mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
            {/* Left: Brand Identity & Honesty Note */}
            <div className="flex flex-wrap items-center gap-3 text-center md:text-left">
              <Link href="/" className="flex items-center gap-2 text-white hover:text-[#f26625] transition-colors">
                <BrandLogo size={20} />
                <span className="font-bold tracking-tight">RasoSynthTune</span>
              </Link>
              <span className="text-[#334155] hidden sm:inline">|</span>
              <FooterStatus />
              <span className="text-[11px] text-amber-400/90 hidden lg:inline">
                (Demo Guard: $50 Cap · In-Memory Ring Logging)
              </span>
            </div>

            {/* Right: Quick Links, Docs, GitHub, Open Source */}
            <div className="flex flex-wrap items-center justify-center gap-4 text-[11px]">
              <Link href="/observability" className="hover:text-white transition-colors flex items-center gap-1">
                <Activity className="w-3 h-3 text-[#f26625]" />
                <span>Telemetry</span>
              </Link>
              <a
                href="https://github.com/Sourabh-Kumar04/RasoSynth_CUTC"
                target="_blank"
                rel="noreferrer"
                className="hover:text-white transition-colors flex items-center gap-1"
              >
                <Github className="w-3 h-3" />
                <span>GitHub</span>
              </a>
              <Link href="/settings" className="hover:text-white transition-colors">
                System Status
              </Link>
              <span className="text-[#334155]">|</span>
              <span className="text-[#64748b]">
                Apache-2.0 License · Self-Hostable
              </span>
            </div>
          </div>
        </footer>
      </div>
    </div>
  )
}
