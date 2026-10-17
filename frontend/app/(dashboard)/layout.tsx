'use client'

import { TopNav } from '@/components/layout/top-nav'
import { Sidebar } from '@/components/layout/sidebar'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-[#0a0a0f] text-[#f8fafc] flex flex-col font-sans antialiased bg-dot-grid">
      <TopNav />
      <div className="flex-1 flex w-full relative">
        <Sidebar />
        <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 space-y-6 overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
