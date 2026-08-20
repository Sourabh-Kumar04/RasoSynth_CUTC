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
      <div className="w-full max-w-lg bg-white border border-[#E2E6E0] rounded-3xl shadow-2xl overflow-hidden flex flex-col">
        {/* Search Header Input */}
        <div className="flex items-center gap-3 p-4 border-b border-[#E2E6E0] bg-[#F6F7F4]">
          <Search className="h-4 w-4 text-[#1B3B2B] shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            placeholder="Search pages, presets, workflows, settings... (Cmd+K)"
            className="w-full bg-transparent text-xs text-[#1B3B2B] font-medium outline-none placeholder:text-[#809085]"
          />
          <button
            onClick={() => onOpenChange(false)}
            className="text-[#55635B] hover:text-[#1B3B2B] p-1 rounded-full hover:bg-[#E8ECE6]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-xs text-[#55635B] font-mono">
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
                  className={`flex items-center justify-between p-3 rounded-2xl cursor-pointer transition-all ${
                    isSelected ? 'bg-[#1B3B2B] text-white shadow-xs' : 'hover:bg-[#F6F7F4] text-[#1B3B2B]'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`h-8 w-8 rounded-xl flex items-center justify-center shrink-0 ${
                        isSelected ? 'bg-white/10 text-emerald-400' : 'bg-[#E8ECE6] text-[#1B3B2B]'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold truncate">{item.title}</span>
                        <span
                          className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full ${
                            isSelected ? 'bg-emerald-950 text-emerald-300' : 'bg-[#E8ECE6] text-[#55635B]'
                          }`}
                        >
                          {item.category}
                        </span>
                      </div>
                      <p className={`text-[11px] truncate mt-0.5 ${isSelected ? 'text-emerald-100/80' : 'text-[#55635B]'}`}>
                        {item.subtitle}
                      </p>
                    </div>
                  </div>
                  <ArrowRight className={`h-4 w-4 shrink-0 ml-2 ${isSelected ? 'text-emerald-400' : 'opacity-0'}`} />
                </div>
              )
            })
          )}
        </div>

        {/* Footer shortcuts hint */}
        <div className="p-3 bg-[#F6F7F4] border-t border-[#E2E6E0] flex items-center justify-between text-[10px] font-mono text-[#55635B]">
          <div className="flex items-center gap-3">
            <span><kbd className="px-1 py-0.5 bg-white rounded border border-[#D1D8CE]">↑↓</kbd> Navigate</span>
            <span><kbd className="px-1 py-0.5 bg-white rounded border border-[#D1D8CE]">↵</kbd> Select</span>
            <span><kbd className="px-1 py-0.5 bg-white rounded border border-[#D1D8CE]">ESC</kbd> Close</span>
          </div>
          <span>RasoSynthTune Search</span>
        </div>
      </div>
    </div>
  )
}
