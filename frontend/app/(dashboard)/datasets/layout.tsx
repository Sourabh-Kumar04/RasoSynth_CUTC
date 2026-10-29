import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Data Library & Exports | RasoSynthTune',
  description: 'Browse synthetic datasets, DBOM provenance seals, and download production archives.',
}

export default function DatasetsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
