import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Quality Inspector & LLM Jury | RasoSynthTune',
  description: 'Multi-provider LLM jury evaluation, 2D semantic clustering, decontamination audits, and curriculum balancing.',
}

export default function QualityLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
