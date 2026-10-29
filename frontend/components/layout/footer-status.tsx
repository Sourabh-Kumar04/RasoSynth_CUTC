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
 * health endpoint's status.
 *
 * Health/standby rendering rule:
 * - healthy = emerald dot only when the backend actually reported healthy
 * - standby / unknown = amber / grey dot with "Standby" or "Unknown" (never green)
 * - degraded / error / unhealthy = amber / red accordingly
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

  const memPct = snapshot.system_metrics?.memory_used_percent
  const cpuLoad = snapshot.system_metrics?.cpu_load_1m
  const hostPressureCritical =
    (memPct != null && memPct > 85) || (cpuLoad != null && cpuLoad > 3.0)
  const rawStatus = (snapshot.status || 'unknown').toLowerCase()
  const displayStatus = hostPressureCritical ? 'degraded' : rawStatus

  let dotColor = 'bg-[#a8a29e]'
  let label = 'Unknown'

  if (displayStatus === 'healthy') {
    dotColor = 'bg-emerald-400'
    label = 'Healthy'
  } else if (displayStatus === 'standby') {
    dotColor = 'bg-amber-400'
    label = 'Standby'
  } else if (displayStatus === 'degraded') {
    dotColor = 'bg-amber-400'
    label = 'Degraded'
  } else if (displayStatus === 'unhealthy' || displayStatus === 'error') {
    dotColor = 'bg-rose-400'
    label = displayStatus.charAt(0).toUpperCase() + displayStatus.slice(1)
  } else {
    dotColor = 'bg-[#a8a29e]'
    label = displayStatus.charAt(0).toUpperCase() + displayStatus.slice(1)
  }

  return (
    <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#12121a] border border-[#272738] text-xs text-zinc-300">
      <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${dotColor}`} />
      <span>{label}</span>
    </span>
  )
}
