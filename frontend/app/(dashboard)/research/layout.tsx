import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Benchmarks & Techniques | RasoSynthTune',
  description: 'Empirical ROI benchmark evaluations, algorithmic deduplication rates, and mutation technique controls.',
}

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
