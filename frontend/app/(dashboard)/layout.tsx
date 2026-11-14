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
    <div className="relative min-h-screen bg-[#0a0a0f] text-[#f5f2ea] flex flex-col font-sans antialiased bg-dot-grid selection:bg-[#f26625]/30 selection:text-white">
      <div className="relative z-10 flex flex-col min-h-screen">
        <TopNav />
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
          {children}
        </main>

        {/* Global App Shell Footer */}
        <footer className="w-full border-t border-[#1f1f2e] bg-[#08080d]/90 backdrop-blur-md mt-auto py-5 px-4 sm:px-8 text-xs font-mono text-[#a8a29e]">
          <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Left: Brand Identity & Status */}
            <div className="flex flex-wrap items-center gap-3 text-center sm:text-left">
              <Link href="/" className="flex items-center gap-2 text-white hover:text-[#f26625] transition-colors">
                <BrandLogo size={20} />
                <span className="font-bold tracking-tight">RasoSynthTune</span>
              </Link>
              <span className="text-[#4a463f] hidden sm:inline">|</span>
              <FooterStatus />
            </div>

            {/* Right: Copyright */}
            <div className="text-xs text-[#71717a]">
              © 2026 RasoSynthTune
            </div>
          </div>
        </footer>
      </div>
    </div>
  )
}
