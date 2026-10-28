import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Pipeline Execution Engine | RasoSynthTune',
  description: 'Asynchronous DAG orchestrator, early-preview acceptance gates, and multi-agent consensus telemetry.',
}

export default function OrchestrationLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
