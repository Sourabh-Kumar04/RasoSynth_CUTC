import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Model Training Studio (QLoRA) | RasoSynthTune',
  description: 'Parameter-efficient fine-tuning (PEFT/QLoRA) studio with real-time neural convergence telemetry and GGUF export.',
}

export default function FineTuneLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
