'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import {
  Search,
  FlaskConical,
  Database,
  Workflow,
  Cpu,
  ClipboardCheck,
  BarChart2,
  Activity,
  Beaker,
  Settings,
  Sparkles,
  Zap,
  ArrowRight,
  X
} from 'lucide-react'

interface SearchItem {
  id: string
  title: string
  subtitle: string
  category: 'Pages' | 'Preset Workflows' | 'Actions'
  href: string
  icon: any
}

const SEARCH_ITEMS: SearchItem[] = [
  {
    id: 'studio',
    title: 'Dataset Generation Studio',
    subtitle: 'AI-powered synthetic dataset synthesis and prompt design',
    category: 'Pages',
    href: '/studio',
    icon: FlaskConical
  },
  {
    id: 'medical-preset',
    title: '🩺 Medical Diagnostics & Treatment Preset',
    subtitle: '500 clinical instruction scenarios with differential diagnosis',
    category: 'Preset Workflows',
    href: '/studio',
    icon: Zap
  },
  {
    id: 'python-preset',
    title: '🐍 Python Concurrent Algorithms Preset',
    subtitle: '1,000 thread-safe Python coding examples with unit tests',
    category: 'Preset Workflows',
    href: '/studio',
    icon: Zap
  },
  {
    id: 'legal-preset',
    title: '⚖️ Legal Risk & Contract Analysis Preset',
    subtitle: '750 contract clause extraction & risk scoring pairs',
    category: 'Preset Workflows',
    href: '/studio',
    icon: Zap
  },
  {
    id: 'datasets',
    title: 'Datasets Explorer & Exporter',
    subtitle: 'Browse synthesized datasets, filter records, export JSONL / Parquet',
    category: 'Pages',
    href: '/datasets',
    icon: Database
  },
  {
    id: 'quality',
    title: 'Quality & Consensus Benchmarks',
    subtitle: 'Automated 4-tier deduplication, hallucination risk, grounding',
    category: 'Pages',
    href: '/quality',
    icon: BarChart2
  },
  {
    id: 'review',
    title: 'HITL Review & Curation Queue',
    subtitle: 'Human-in-the-loop sample inspection with hotkeys (A/R/E)',
    category: 'Pages',
    href: '/review',
    icon: ClipboardCheck
  },
  {
    id: 'finetune',
    title: 'Fine-Tune Studio (PEFT / LoRA)',
    subtitle: 'Train parameter-efficient adapter models directly on synthesized data',
    category: 'Pages',
    href: '/finetune',
    icon: Cpu
  },
  {
    id: 'observability',
    title: 'OpenTelemetry Observability',
    subtitle: 'Real-time distributed tracing, latency budgets, API health',
    category: 'Pages',
    href: '/observability',
    icon: Activity
  },
  {
    id: 'providers',
    title: 'Multi-Provider Health & Latency',
    subtitle: 'Gemini, Claude, NVIDIA NIM, OpenAI, Groq status & budgets',
    category: 'Pages',
    href: '/providers',
    icon: Beaker
  },
  {
    id: 'research',
    title: 'DSPy Research & Benchmarking',
    subtitle: 'LLM prompt optimizer and model comparison evaluations',
    category: 'Pages',
    href: '/research',
    icon: Beaker
  },
  {
    id: 'settings',
    title: 'Settings & Environment Keys',
    subtitle: 'API keys, system configuration, environment variables',
    category: 'Pages',
    href: '/settings',
    icon: Settings
  }
]

export function CommandPalette({
  open,
  onOpenChange
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const router = useRouter()
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-focus input when opened
  useEffect(() => {
    if (open) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Filter items
  const filtered = SEARCH_ITEMS.filter((item) => {
    const q = query.toLowerCase()
    return (
      item.title.toLowerCase().includes(q) ||
      item.subtitle.toLowerCase().includes(q) ||
      item.category.toLowerCase().includes(q)
    )
  })

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!open) return

      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev < filtered.length - 1 ? prev + 1 : 0))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) => (prev > 0 ? prev - 1 : filtered.length - 1))
      } else if (e.key === 'Enter' && filtered[selectedIndex]) {
        e.preventDefault()
        router.push(filtered[selectedIndex].href)
        onOpenChange(false)
      } else if (e.key === 'Escape') {
        onOpenChange(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, filtered, selectedIndex, router, onOpenChange])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-20 p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div className="w-full max-w-lg bg-[#12121a] border border-[#272738] rounded-xl shadow-2xl overflow-hidden flex flex-col">
        {/* Search Header Input */}
        <div className="flex items-center gap-3 p-4 border-b border-[#272738] bg-[#0a0a0f]">
          <Search className="h-4 w-4 text-[#f26625] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            placeholder="Search pages, presets, workflows, settings... (Cmd+K)"
            className="w-full bg-transparent text-xs text-[#f8fafc] font-medium outline-none placeholder:text-[#64748b]"
          />
          <button
            onClick={() => onOpenChange(false)}
            className="text-[#94a3b8] hover:text-[#f8fafc] p-1 rounded-md hover:bg-[#161622]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#94a3b8] font-mono">
              No matching pages or features found for &quot;{query}&quot;
            </div>
          ) : (
            filtered.map((item, idx) => {
              const Icon = item.icon
              const isSelected = idx === selectedIndex

              return (
                <div
                  key={item.id}
                  onClick={() => {
                    router.push(item.href)
                    onOpenChange(false)
                  }}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all ${
                    isSelected ? 'bg-[#f26625] text-white shadow-xs glow-yc' : 'hover:bg-[#161622] text-[#f8fafc]'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`h-8 w-8 rounded-md flex items-center justify-center shrink-0 ${
                        isSelected ? 'bg-white/20 text-white' : 'bg-[#161622] text-[#f26625]'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold truncate">{item.title}</span>
                        <span
                          className={`text-xs font-mono px-1.5 py-0.5 rounded-full ${
                            isSelected ? 'bg-[#f26625]/15 text-white' : 'bg-[#161622] text-[#94a3b8]'
                          }`}
                        >
                          {item.category}
                        </span>
                      </div>
                      <p className={`text-xs truncate mt-0.5 ${isSelected ? 'text-white' : 'text-[#94a3b8]'}`}>
                        {item.subtitle}
                      </p>
                    </div>
                  </div>
                  <ArrowRight className={`h-4 w-4 shrink-0 ml-2 ${isSelected ? 'text-white' : 'opacity-0'}`} />
                </div>
              )
            })
          )}
        </div>

        {/* Footer shortcuts hint */}
        <div className="p-3 bg-[#0a0a0f] border-t border-[#272738] flex items-center justify-between text-xs font-mono text-[#94a3b8]">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1 py-0.5 bg-[#161622] text-[#94a3b8] rounded border border-[#3b3b52]">↑↓</kbd> Navigate</span>
            <span><kbd className="px-1 py-0.5 bg-[#161622] text-[#94a3b8] rounded border border-[#3b3b52]">↵</kbd> Select</span>
            <span><kbd className="px-1 py-0.5 bg-[#161622] text-[#94a3b8] rounded border border-[#3b3b52]">ESC</kbd> Close</span>
          </div>
          <span>RasoSynthTune Search</span>
        </div>
      </div>
    </div>
  )
}
