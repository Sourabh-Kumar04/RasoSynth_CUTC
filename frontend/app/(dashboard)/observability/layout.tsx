import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'System Insights & Telemetry | RasoSynthTune',
  description: 'Real-time telemetry, container worker pool monitoring, resource pressure thresholds, and self-correction logs.',
}

export default function ObservabilityLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
