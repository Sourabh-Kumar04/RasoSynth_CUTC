import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Dashboard | RasoSynthTune',
  description: 'Dataset generation and fine-tuning workspace: job status, pipeline stages, and live quality metrics.',
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

