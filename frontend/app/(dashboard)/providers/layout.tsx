import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Providers & Failover Engine | RasoSynthTune',
  description: 'Multi-provider routing, priority failover chains, circuit-breaker states, and token budget controls.',
}

export default function ProvidersLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
