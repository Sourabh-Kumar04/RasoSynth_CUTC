'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api/client'

type HealthSnapshot = {
  status?: string
  system_metrics?: {
    cpu_load_1m?: number
    memory_used_percent?: number
  }
}

/**
 * FooterStatus — the dashboard footer's status dot, wired to the same rule
 * the observability page uses for its headline displayStatus: host pressure
 * (memory > 85% or 1m CPU load > 3.0) forces "degraded", otherwise the
 * health endpoint's status. While loading or on fetch failure the dot is
 * neutral stone — it never claims emerald "Active" without data.
 */
export function FooterStatus() {
  const [snapshot, setSnapshot] = useState<HealthSnapshot | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    api
      .getHealth()
      .then((res) => {
        if (!cancelled) setSnapshot(res as unknown as HealthSnapshot)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (failed || snapshot === null) {
    return (
      <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#12121a] border border-[#272738] text-xs text-zinc-300">
        <span className="w-1.5 h-1.5 rounded-full bg-[#a8a29e]" />
        <span>{failed ? 'System status unknown' : 'Checking system status…'}</span>
      </span>
    )
  }

  const hostPressureCritical =
    (snapshot.system_metrics?.memory_used_percent ?? 45) > 85 ||
    (snapshot.system_metrics?.cpu_load_1m ?? 0.1) > 3.0
  const displayStatus = hostPressureCritical ? 'degraded' : snapshot.status || 'healthy'
  const degraded = displayStatus.toLowerCase() === 'degraded'
  const label = displayStatus.charAt(0).toUpperCase() + displayStatus.slice(1)

  return (
    <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#12121a] border border-[#272738] text-xs text-zinc-300">
      <span
        className={`w-1.5 h-1.5 rounded-full animate-pulse ${degraded ? 'bg-amber-400' : 'bg-emerald-400'}`}
      />
      <span>
        {label}: Hybrid Standalone · Real Supabase PostgreSQL
      </span>
    </span>
  )
}
