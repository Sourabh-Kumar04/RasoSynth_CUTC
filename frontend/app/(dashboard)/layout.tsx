'use client'

import { TopNav } from '@/components/layout/top-nav'
import { Sidebar } from '@/components/layout/sidebar'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-[#F6F7F4] text-[#1B3B2B] flex flex-col font-sans antialiased">
      <TopNav />
      <div className="flex-1 flex w-full relative">
        <Sidebar />
        <main className="flex-1 min-w-0 p-5 sm:p-7 lg:p-10 space-y-6 overflow-x-hidden">
          {children}
        </main>
      </div>
    </div>
  )
}
