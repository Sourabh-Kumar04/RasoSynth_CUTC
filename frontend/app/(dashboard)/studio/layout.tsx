import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Dataset Studio | RasoSynthTune',
  description: 'Design and synthesize high-precision instruction datasets with domain presets and prompt curriculum engineering.',
}

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
