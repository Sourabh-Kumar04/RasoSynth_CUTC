import Link from 'next/link'
import { TopNav } from '@/components/layout/top-nav'
import { BrandLogo } from '@/components/ui/brand-logo'
import { FooterStatus } from '@/components/layout/footer-status'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="relative min-h-screen bg-[#07060a] text-[#f5f2ea] flex flex-col font-sans antialiased bg-dot-grid selection:bg-[#f26625]/30 selection:text-white">
      <div className="relative z-10 flex flex-col min-h-screen">
        <TopNav />
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
          {children}
        </main>

        {/* Global App Shell Footer - Seamless, borderless */}
        <footer className="w-full border-t border-white/[0.06] bg-[#07060a]/90 backdrop-blur-xl mt-auto py-5 px-4 sm:px-8 text-xs font-mono text-zinc-400">
          <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Left: Brand Identity & Status */}
            <div className="flex flex-wrap items-center gap-3 text-center sm:text-left">
              <Link href="/" className="flex items-center gap-2 text-white hover:text-[#f26625] transition-colors">
                <BrandLogo size={22} />
                <span className="font-bold tracking-tight text-white">RasoSynthTune</span>
              </Link>
              <span className="text-zinc-700 hidden sm:inline">|</span>
              <FooterStatus />
            </div>

            {/* Right: Copyright */}
            <div className="text-xs text-zinc-500">
              © 2026 RasoSynthTune
            </div>
          </div>
        </footer>
      </div>
    </div>
  )
}
