'use client'

import React, { useMemo, useState } from 'react'
import {
  Activity,
  Cpu,
  Zap,
  TrendingDown,
  Gauge,
  Sparkles,
  Layers,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react'
import { clsx } from 'clsx'

interface TelemetryChartProps {
  lossHistory: number[]
  currentEpoch: number
  totalEpochs: number
  trainLoss: number | null
  evalLoss: number | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  targetPlatform?: 'local' | 'modal' | 'runpod'
  gpuDeviceName?: string
  isSimulated?: boolean
}

export function TelemetryChart({
  lossHistory,
  currentEpoch,
  totalEpochs,
  trainLoss,
  evalLoss,
  status,
  targetPlatform = 'local',
  gpuDeviceName = 'Simulated Container Pool / Emulated NVIDIA A10G (24GB VRAM)',
  isSimulated = true,
}: TelemetryChartProps) {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)

  // Only use real loss history; require at least 2 points for a curve
  const hasLossHistory = lossHistory && lossHistory.length >= 2
  const losses = useMemo(() => {
    if (hasLossHistory) return lossHistory
    return []
  }, [hasLossHistory, lossHistory])

  const initialLoss = losses.length > 0 ? losses[0] : null
  const latestLoss = losses.length > 0 ? losses[losses.length - 1] : null
  const minLoss = losses.length > 0 ? Math.min(...losses) : 0
  const maxLoss = losses.length > 0 ? Math.max(...losses) : 1
  const lossDeltaPct = (initialLoss !== null && latestLoss !== null && initialLoss > 0)
    ? (((initialLoss - latestLoss) / initialLoss) * 100).toFixed(1)
    : null

  // Dynamic cost calculation based on epochs/steps
  const estGpuHours = ((totalEpochs || 1) * 0.04).toFixed(2)
  const estCost = ((totalEpochs || 1) * 0.14).toFixed(2)

  // SVG Chart Dimensions
  const SVG_W = 500
  const SVG_H = 140
  const PAD_X = 35
  const PAD_Y = 20

  const points = useMemo(() => {
    if (losses.length < 2) return []
    const range = maxLoss - minLoss || 0.1
    return losses.map((val, idx) => {
      const x = PAD_X + (idx / (losses.length - 1)) * (SVG_W - PAD_X * 2)
      const y = SVG_H - PAD_Y - ((val - minLoss) / range) * (SVG_H - PAD_Y * 2)
      return { x, y, val, step: idx + 1 }
    })
  }, [losses, minLoss, maxLoss])

  const polylineStr = points.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')
  const areaPolygonStr = points.length > 0
    ? `${points[0].x.toFixed(1)},${SVG_H - PAD_Y} ${polylineStr} ${points[points.length - 1].x.toFixed(1)},${SVG_H - PAD_Y}`
    : ''

  // VRAM & Compute metrics calculation — real hardware telemetry is not reported by standard container stubs
  const vramTotalGb = 24.0

  return (
    <div className="rounded-xl border border-[#272738] bg-[#0d0d14] p-4 shadow-xl space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#272738] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-md bg-[#10b981]/15 border border-[#10b981]/30 flex items-center justify-center text-[#10b981]">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white flex items-center gap-2">
              Neural Convergence & GPU Telemetry
              {isSimulated && (
                <span className="px-1.5 py-0.5 rounded text-xs font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30 uppercase tracking-wider">
                  Simulated
                </span>
              )}
              {status === 'running' && (
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#10b981] opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-[#10b981]"></span>
                </span>
              )}
            </h3>
            <p className="text-xs font-mono text-[#a8a29e]">
              Target: <span className="text-white font-bold">{targetPlatform.toUpperCase()}</span> · {gpuDeviceName}
            </p>
          </div>
        </div>

        {/* Quick loss reduction badge */}
        <div className="flex items-center gap-2">
          {lossDeltaPct !== null ? (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 font-mono text-xs">
              <TrendingDown className="h-3.5 w-3.5 text-emerald-400" />
              <span className="font-bold">Δ {lossDeltaPct}%</span>
              <span className="text-xs text-emerald-400/80">loss reduction</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-900 border border-[#272738] text-[#a8a29e] font-mono text-xs">
              <span className="text-xs">No convergence history</span>
            </div>
          )}
        </div>
      </div>

      {/* Metrics & Cost Breakdown Strip */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 rounded-lg bg-[#07070b] border border-[#1f1f2e] text-xs font-mono text-[#a8a29e]">
        <div className="flex items-center gap-3">
          <span>Train Loss: <strong className="text-white">{trainLoss !== null && trainLoss !== undefined ? trainLoss.toFixed(4) : latestLoss !== null ? latestLoss.toFixed(4) : 'Unknown'}</strong></span>
          <span className="text-zinc-700">·</span>
          <span>Eval Loss: <strong className="text-white">{evalLoss !== null && evalLoss !== undefined ? evalLoss.toFixed(4) : 'Unknown'}</strong></span>
        </div>
        <div className="flex items-center gap-2">
          <span>Est. Cost (Simulated, assumed rate): <strong className="text-zinc-200 font-bold">${estCost}</strong> <span className="text-xs text-zinc-500">({estGpuHours} GPU-hrs @ assumed $0.35/hr)</span></span>
          <span className="text-zinc-700">·</span>
          <span className="text-zinc-400">Convergence: {lossDeltaPct !== null && Number(lossDeltaPct) > 0 ? 'Improving' : 'Monitoring'}</span>
        </div>
      </div>

      {/* SVG Loss Curve Canvas */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs font-mono text-[#a8a29e] px-1">
          <span>Objective Loss: Cross-Entropy (Teacher Forcing)</span>
          <span>
            {hoveredIdx !== null ? (
              <span className="text-white font-bold">
                Step {points[hoveredIdx]?.step}: Loss {points[hoveredIdx]?.val.toFixed(4)}
              </span>
            ) : (
              <span>Current: <strong className={latestLoss !== null ? "text-emerald-400 font-bold" : "text-[#a8a29e]"}>{latestLoss !== null ? latestLoss.toFixed(4) : 'Unknown'}</strong></span>
            )}
          </span>
        </div>

        <div className="relative rounded-lg bg-[#07070b] border border-[#1f1f2e] p-2 overflow-hidden">
          {losses.length < 2 ? (
            <div className="h-36 flex flex-col items-center justify-center text-[#a8a29e] text-xs font-mono gap-1">
              <span>No loss history recorded yet</span>
              <span className="text-zinc-600">Telemetry will render as training steps stream loss checkpoints</span>
            </div>
          ) : (
            <svg
              viewBox={`0 0 ${SVG_W} ${SVG_H}`}
              className="w-full h-36 overflow-visible cursor-crosshair"
              onMouseLeave={() => setHoveredIdx(null)}
            >
              <defs>
                
              </defs>

              {/* Gridlines */}
              <line x1={PAD_X} y1={PAD_Y} x2={SVG_W - PAD_X} y2={PAD_Y} stroke="#1b1b26" strokeDasharray="3 3" />
              <line x1={PAD_X} y1={SVG_H / 2} x2={SVG_W - PAD_X} y2={SVG_H / 2} stroke="#1b1b26" strokeDasharray="3 3" />
              <line x1={PAD_X} y1={SVG_H - PAD_Y} x2={SVG_W - PAD_X} y2={SVG_H - PAD_Y} stroke="#272738" />

              {/* Min / Max Labels */}
              <text x={PAD_X - 6} y={PAD_Y + 4} fill="#a8a29e" fontSize="9" fontFamily="monospace" textAnchor="end">
                {maxLoss.toFixed(2)}
              </text>
              <text x={PAD_X - 6} y={SVG_H - PAD_Y + 3} fill="#a8a29e" fontSize="9" fontFamily="monospace" textAnchor="end">
                {minLoss.toFixed(2)}
              </text>

              {/* Shaded Area */}
              {areaPolygonStr && (
                <polygon points={areaPolygonStr} fill="#10b981" fillOpacity="0.15" />
              )}

              {/* Polyline */}
              {polylineStr && (
                <polyline
                  points={polylineStr}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              )}

              {/* Interactive Data Points */}
              {points.map((pt, i) => (
                <g key={i}>
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={hoveredIdx === i ? 5 : 2.5}
                    fill={hoveredIdx === i ? '#f26625' : '#10b981'}
                    stroke="#07070b"
                    strokeWidth="1.5"
                    className="transition-all duration-150"
                    onMouseEnter={() => setHoveredIdx(i)}
                  />
                </g>
              ))}
            </svg>
          )}
        </div>
      </div>

      {/* GPU Hardware Telemetry Sub-panel */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
        {/* VRAM Gauge */}
        <div className="rounded-lg bg-[#07070b] border border-[#1f1f2e] p-3 space-y-1.5">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[#a8a29e] flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-[#f26625]" />
              GPU VRAM Allocation
            </span>
            <span className="font-bold text-[#a8a29e]">Unknown</span>
          </div>
          <div className="h-2 w-full rounded-full bg-[#161622] overflow-hidden">
            <div className="h-full bg-zinc-700" style={{ width: '0%' }} />
          </div>
          <div className="flex justify-between text-xs font-mono text-[#a8a29e]">
            <span>Hardware Probe Required</span>
            <span>Unknown Peak</span>
          </div>
        </div>

        {/* Compute Load */}
        <div className="rounded-lg bg-[#07070b] border border-[#1f1f2e] p-3 space-y-1.5">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[#a8a29e] flex items-center gap-1.5">
              <Gauge className="h-3.5 w-3.5 text-[#f26625]" />
              SM Streaming Cores
            </span>
            <span className="font-bold text-[#a8a29e]">Unknown</span>
          </div>
          <div className="h-2 w-full rounded-full bg-[#161622] overflow-hidden">
            <div className="h-full bg-zinc-700" style={{ width: '0%' }} />
          </div>
          <div className="flex justify-between text-xs font-mono text-[#a8a29e]">
            <span>Compute Metrics</span>
            <span>Unknown Temp</span>
          </div>
        </div>

        {/* Throughput & Schedule */}
        <div className="rounded-lg bg-[#07070b] border border-[#1f1f2e] p-3 space-y-1">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-[#a8a29e] flex items-center gap-1.5">
              <Zap className="h-3.5 w-3.5 text-[#f26625]" />
              Throughput
            </span>
            <span className="font-bold text-[#a8a29e]">Unknown</span>
          </div>
          <div className="text-xs font-mono text-[#a8a29e] pt-1">
            <span>Execution Status: </span>
            <span className="text-white font-bold">{status ? status.toUpperCase() : 'UNKNOWN'}</span>
          </div>
          <div className="text-xs font-mono text-[#a8a29e] flex items-center gap-1">
            <span>Target: {targetPlatform.toUpperCase()}</span>
          </div>
        </div>
      </div>
    </div>
  )
}
