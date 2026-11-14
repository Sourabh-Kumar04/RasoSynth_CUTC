'use client'

import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Sparkles, ShieldCheck, Database, Cpu, CheckCircle2 } from 'lucide-react'

interface FlowStage {
  id: string
  title: string
  subtitle: string
  metric: string
  icon: React.ReactNode
  color: string
}

const STAGES: FlowStage[] = [
  {
    id: 'extract',
    title: 'Corpus Extraction',
    subtitle: 'Trafilatura · PDF Plumber · LangDetect',
    metric: '99.4% Text Yield',
    icon: <Database className="w-4 h-4 text-[#f26625]" />,
    color: '#f26625',
  },
  {
    id: 'synthesize',
    title: '7-Engine Synthesis',
    subtitle: 'CoT · Socratic · DPO · Tool Schemas',
    metric: '7 Invariant Generators',
    icon: <Sparkles className="w-4 h-4 text-[#fb923c]" />,
    color: '#fb923c',
  },
  {
    id: 'judge',
    title: 'LLM Quality Judge',
    subtitle: 'Consensus L2 · Decontamination Probe',
    metric: '> 0.88 Quality Threshold',
    icon: <Cpu className="w-4 h-4 text-emerald-400" />,
    color: '#10b981',
  },
  {
    id: 'attest',
    title: 'DBOM Attestation',
    subtitle: 'SHA-256 Merkle Root · HF & GGUF',
    metric: '100% Cryptographic Proof',
    icon: <ShieldCheck className="w-4 h-4 text-[#f26625]" />,
    color: '#f26625',
  },
]

export function SynthesisFlowDiagram() {
  const [activeStage, setActiveStage] = useState<string>('synthesize')

  return (
    <div className="w-full my-8 p-6 rounded-2xl bg-[#0a0a0f]/90 border border-[#272738] shadow-2xl relative overflow-hidden backdrop-blur-md">
      {/* Background Accent */}
      <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-96 h-48 bg-[#f26625]/5 rounded-full pointer-events-none" />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 mb-6 border-b border-[#1c1c28] gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-widest text-[#f26625]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#f26625] animate-ping" />
            <span>Interactive Architecture Vector</span>
          </div>
          <h3 className="text-base font-bold text-white font-display mt-0.5">
            End-to-End Autonomous Refinery Stream
          </h3>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
          <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Zero-Drop Fault Tolerant Bus</span>
        </div>
      </div>

      {/* Responsive SVG Architecture Vector Map */}
      <div className="relative w-full overflow-x-auto pb-4">
        <svg
          viewBox="0 0 920 120"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="min-w-[800px] w-full h-auto select-none"
        >
          <defs>

          </defs>

          {/* Main Transit Pipeline Highway */}
          <line
            x1="80"
            y1="60"
            x2="840"
            y2="60"
            stroke="#1c1c28"
            strokeWidth="4"
            strokeLinecap="round"
          />

          {/* Flowing Laser Signal Vector */}
          <line
            x1="80"
            y1="60"
            x2="840"
            y2="60"
            stroke="#f26625"
            strokeWidth="2.5"
            strokeDasharray="8 6"
            strokeLinecap="round"
            className="animate-pulse"
          />

          {/* Node 1: Extract (cx: 110) */}
          <g className="cursor-pointer" onClick={() => setActiveStage('extract')}>
            <circle cx="110" cy="60" r="26" fill="#12121a" stroke="#f26625" strokeWidth="2" />
            <circle cx="110" cy="60" r="6" fill="#f26625" />
            <text x="110" y="104" textAnchor="middle" fill="#ffffff" fontSize="11" fontFamily="monospace" fontWeight="bold">01. INGEST</text>
          </g>

          {/* Flow Indicator 1 -> 2 */}
          <polygon points="280,56 290,60 280,64" fill="#fb923c" />

          {/* Node 2: Synthesize (cx: 350) */}
          <g className="cursor-pointer" onClick={() => setActiveStage('synthesize')}>
            <circle cx="350" cy="60" r="28" fill="#12121a" stroke="#fb923c" strokeWidth="2.5" />
            <circle cx="350" cy="60" r="7" fill="#fb923c" />
            <text x="350" y="104" textAnchor="middle" fill="#ffffff" fontSize="11" fontFamily="monospace" fontWeight="bold">02. SYNTHESIZE</text>
          </g>

          {/* Flow Indicator 2 -> 3 */}
          <polygon points="520,56 530,60 520,64" fill="#10b981" />

          {/* Node 3: Quality Judge (cx: 590) */}
          <g className="cursor-pointer" onClick={() => setActiveStage('judge')}>
            <circle cx="590" cy="60" r="26" fill="#12121a" stroke="#10b981" strokeWidth="2" />
            <circle cx="590" cy="60" r="6" fill="#10b981" />
            <text x="590" y="104" textAnchor="middle" fill="#ffffff" fontSize="11" fontFamily="monospace" fontWeight="bold">03. EVALUATE</text>
          </g>

          {/* Flow Indicator 3 -> 4 */}
          <polygon points="750,56 760,60 750,64" fill="#f26625" />

          {/* Node 4: DBOM Attestation (cx: 810) */}
          <g className="cursor-pointer" onClick={() => setActiveStage('attest')}>
            <circle cx="810" cy="60" r="26" fill="#12121a" stroke="#f26625" strokeWidth="2" />
            <circle cx="810" cy="60" r="6" fill="#f26625" />
            <text x="810" y="104" textAnchor="middle" fill="#ffffff" fontSize="11" fontFamily="monospace" fontWeight="bold">04. ATTEST</text>
          </g>
        </svg>
      </div>

      {/* Interactive Detail Stage Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
        {STAGES.map((stg) => {
          const isSelected = activeStage === stg.id
          return (
            <div
              key={stg.id}
              onClick={() => setActiveStage(stg.id)}
              className={`p-3.5 rounded-xl border transition-all cursor-pointer relative ${
                isSelected
                  ? 'bg-[#141420] border-[#f26625] shadow-lg shadow-[#f26625]/10'
                  : 'bg-[#0f0f17] border-[#222230] hover:border-[#333348]'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded bg-[#181824] flex items-center justify-center">
                    {stg.icon}
                  </div>
                  <span className="text-xs font-bold text-white font-mono">{stg.title}</span>
                </div>
                {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-[#f26625]" />}
              </div>
              <p className="text-xs text-zinc-400 mb-2 leading-relaxed font-sans">{stg.subtitle}</p>
              <div className="pt-2 border-t border-[#1c1c28] flex items-center justify-between text-xs font-mono text-zinc-500">
                <span className="text-[#f26625] font-semibold">{stg.metric}</span>
                <span className="text-xs uppercase tracking-wider text-zinc-400">Validated</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
