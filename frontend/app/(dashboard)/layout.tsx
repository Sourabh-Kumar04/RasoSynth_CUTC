'use client'

import { TopNav } from '@/components/layout/top-nav'
import { SubNav } from '@/components/layout/sub-nav'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-[#f8fafc] flex flex-col font-sans antialiased bg-dot-grid">
      <TopNav />
      <SubNav />
      <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
        {children}
      </main>
    </div>
  )
}
