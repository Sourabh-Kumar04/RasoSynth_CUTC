import type { Metadata } from 'next'
import './globals.css'
import { Providers } from '@/components/providers'
import { Toaster } from '@/components/ui/toaster'

export const metadata: Metadata = {
  title: 'RasoSynthTune | Autonomous Dataset Synthesis',
  description: 'AI-native dataset generation and evaluation orchestration platform',
  icons: {
    icon: '/favicon.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased bg-[#F6F7F4] text-[#1B3B2B]">
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}
