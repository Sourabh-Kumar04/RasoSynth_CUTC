'use client'

import { TopNav } from '@/components/layout/top-nav'
import { SubNav } from '@/components/layout/sub-nav'

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
        <SubNav />
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
          {children}
        </main>
      </div>
    </div>
  )
}
