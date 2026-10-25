import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Human-in-the-Loop Review Studio | RasoSynthTune',
  description: 'Stratified human verification queue with keyboard shortcuts, audit logging, and DBOM attestation export.',
}

export default function ReviewLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
