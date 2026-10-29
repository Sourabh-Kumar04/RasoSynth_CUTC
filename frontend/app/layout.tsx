import type { Metadata } from 'next'
import './globals.css'
import { Providers } from '@/components/providers'
import { Toaster } from '@/components/ui/toaster'
import { MockModeBanner } from '@/components/mock-mode-banner'

export const metadata: Metadata = {
  title: 'RasoSynthTune | Autonomous Dataset Synthesis & Fine-Tuning Studio',
  description: 'AI-native dataset generation, multi-tier evaluation, and PEFT/LoRA fine-tuning platform for Indic and specialized LLMs',
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon.ico', sizes: 'any' },
    ],
    shortcut: '/favicon.svg',
    apple: '/favicon.svg',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans antialiased bg-[#0a0a0f] text-[#f5f2ea]">
        <Providers>
          <MockModeBanner />
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  )
}
