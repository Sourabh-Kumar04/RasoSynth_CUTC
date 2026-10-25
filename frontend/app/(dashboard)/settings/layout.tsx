import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'System Status & Configuration | RasoSynthTune',
  description: 'Infrastructure architecture inspection, active database engine telemetry, and API key configuration status.',
}

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
