import { TopNav } from '@/components/layout/top-nav'
import { DashboardNavigation } from '@/components/layout/sub-nav'
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
        <DashboardNavigation />
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
          {children}
        </main>

        {/* Global App Shell Presentation Footer */}
        <footer className="w-full border-t border-[#1f1f2e] bg-[#08080d]/90 backdrop-blur-md mt-auto py-3 px-4 sm:px-8 text-xs font-mono text-zinc-500">
          <div className="max-w-[1600px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>© 2026 RasoSynthTune · Autonomous Synthetic Data Engine</span>
            <FooterStatus />
          </div>
        </footer>
      </div>
    </div>
  )
}
