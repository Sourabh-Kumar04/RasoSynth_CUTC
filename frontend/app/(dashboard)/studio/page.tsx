'use client'

import { useState, useCallback } from 'react'
import {
  FlaskConical,
  Sparkles,
  Settings2,
  Play,
  Save,
  Copy,
  ChevronRight,
  Plus,
  X,
  Brain,
  Database,
  Zap,
  Shield,
  ArrowRight,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useRouter } from 'next/navigation'

// API client
import { api } from '@/lib/api/client'

// Dataset templates
const templates = [
  {
    id: 'qa',
    name: 'Question & Answer',
    description: 'Generate Q&A pairs from documents',
    icon: '?',
    category: 'NLP',
  },
  {
    id: 'classification',
    name: 'Text Classification',
    description: 'Multi-class text categorization',
    icon: 'T',
    category: 'NLP',
  },
  {
    id: 'ner',
    name: 'Named Entity Recognition',
    description: 'Extract entities from text',
    icon: 'E',
    category: 'NLP',
  },
  {
    id: 'translation',
    name: 'Translation Pairs',
    description: 'Parallel translation datasets',
    icon: 'G',
    category: 'Multilingual',
  },
  {
    id: 'code',
    name: 'Code Generation',
    description: 'Programming code synthesis',
    icon: '</>',
    category: 'Code',
  },
  {
    id: 'summarization',
    name: 'Summarization',
    description: 'Document summarization pairs',
    icon: 'S',
    category: 'NLP',
  },
]

// Provider options - actual provider stats come from API
// This is just the list of available providers for selection
const providers = [
  { id: 'gemini', name: 'Google Gemini' },
  { id: 'nvidia', name: 'NVIDIA NIM' },
  { id: 'claude', name: 'Claude (Anthropic)' },
  { id: 'openai', name: 'OpenAI' },
  { id: 'huggingface', name: 'Hugging Face' },
  { id: 'ollama', name: 'Ollama (Local)' },
]

// Constraint types
const constraintTypes = [
  { id: 'min_length', label: 'Minimum Length', field: 'number' },
  { id: 'max_length', label: 'Maximum Length', field: 'number' },
  { id: 'quality_threshold', label: 'Quality Threshold', field: 'number' },
  { id: 'language', label: 'Language', field: 'select' },
  { id: 'topic', label: 'Topic', field: 'text' },
  { id: 'format', label: 'Format', field: 'select' },
]

// Dataset type mapping
const datasetTypeMap: Record<string, string> = {
  qa: 'sft',
  classification: 'classification',
  ner: 'classification',
  translation: 'sft',
  code: 'coding',
  summarization: 'sft',
}

// Export format mapping
const formatMap: Record<string, string> = {
  jsonl: 'jsonl',
  csv: 'csv',
  parquet: 'parquet',
}

export default function StudioPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState('create')
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null)
  const [selectedProviders, setSelectedProviders] = useState<string[]>(['gemini', 'nvidia'])
  const [constraints, setConstraints] = useState<Array<{ type: string; value: string; enabled: boolean }>>([])
  const [naturalLanguageInput, setNaturalLanguageInput] = useState('')

  // Form state
  const [datasetName, setDatasetName] = useState('')
  const [modality, setModality] = useState('text')
  const [targetSize, setTargetSize] = useState(1000)
  const [qualityLevel, setQualityLevel] = useState('high')
  const [outputFormat, setOutputFormat] = useState('jsonl')
  const [generationMode, setGenerationMode] = useState('hybrid')
  const [datasetType, setDatasetType] = useState('sft')

  // API state
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [createdJob, setCreatedJob] = useState<any>(null)

  const addConstraint = (type: string) => {
    setConstraints([...constraints, { type, value: '', enabled: true }])
  }

  const removeConstraint = (index: number) => {
    setConstraints(constraints.filter((_, i) => i !== index))
  }

  const toggleProvider = (id: string) => {
    if (selectedProviders.includes(id)) {
      setSelectedProviders(selectedProviders.filter((p) => p !== id))
    } else {
      setSelectedProviders([...selectedProviders, id])
    }
  }

  // Handle dataset generation
  const handleGenerateDataset = useCallback(async () => {
    if (!naturalLanguageInput.trim()) {
      setSubmitError('Please describe your dataset')
      return
    }

    setIsSubmitting(true)
    setSubmitError(null)
    setCreatedJob(null)

    try {
      // Build job request from form data
      const jobRequest = {
        target_domain: naturalLanguageInput,
        dataset_type: selectedTemplate ? (datasetTypeMap[selectedTemplate] || 'sft') : datasetType,
        dataset_size: targetSize,
        quality_level: qualityLevel,
        language: 'en',
        export_format: formatMap[outputFormat] || 'jsonl',
        preferred_providers: selectedProviders,
        cost_budget_usd: targetSize * 0.05, // Rough estimate
        enable_research_loop: true,
        generation_mode: generationMode,
      }

      const response = await api.createJob(jobRequest)
      setCreatedJob(response)

      // Navigate to datasets page after a short delay
      setTimeout(() => {
        router.push('/datasets')
      }, 2000)
    } catch (err: any) {
      console.error('Failed to create job:', err)
      setSubmitError(err.message || 'Failed to create dataset job')
    } finally {
      setIsSubmitting(false)
    }
  }, [naturalLanguageInput, selectedTemplate, targetSize, qualityLevel, outputFormat, selectedProviders, generationMode, datasetType, router])

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-8">
      {/* Page Header */}
      <div className="flex items-center justify-between border-b border-[#E2E6E0] pb-4">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <span className="text-[10px] font-mono px-2.5 py-0.5 rounded-full bg-[#E8ECE6] border border-[#D1D8CE] text-[#1B3B2B] font-bold uppercase tracking-wider">
              Autonomous Synthesis Engine
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-[#1B3B2B]">Dataset Generation Studio</h1>
          </div>
          <p className="text-xs text-[#55635B]">
            Configure multi-agent dataset synthesis, prompt optimization, and verification rules
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-2 border-[#D1D8CE] bg-white text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full">
            <Save className="h-4 w-4" />
            Save Draft
          </Button>
          <Button
            size="sm"
            className="gap-2 bg-[#1B3B2B] hover:bg-[#142D21] text-white font-medium shadow-xs rounded-full"
            onClick={handleGenerateDataset}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
            ) : (
              <Play className="h-4 w-4 fill-current text-emerald-400" />
            )}
            {isSubmitting ? 'Creating...' : 'Generate Workflow'}
          </Button>
        </div>
      </div>

      {/* Error/Success Messages */}
      {submitError && (
        <Card className="border-rose-300 bg-rose-50/80 rounded-2xl">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-rose-600" />
            <p className="text-sm text-rose-900 font-medium">{submitError}</p>
            <Button variant="ghost" size="sm" onClick={() => setSubmitError(null)} className="rounded-full">
              <X className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      )}

      {createdJob && (
        <Card className="border-emerald-300 bg-emerald-50/80 rounded-2xl">
          <CardContent className="p-4 flex items-center gap-4">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            <div className="flex-1">
              <p className="text-sm font-bold text-emerald-950">Dataset Job Created!</p>
              <p className="text-xs text-emerald-800 font-mono">
                Job ID: {createdJob.id} - Redirecting to datasets...
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-[#E8ECE6] rounded-full border border-[#D1D8CE]">
          <TabsTrigger value="create" className="rounded-full">Natural Language</TabsTrigger>
          <TabsTrigger value="config" className="rounded-full">Configuration</TabsTrigger>
          <TabsTrigger value="templates" className="rounded-full">Templates</TabsTrigger>
          <TabsTrigger value="preview" className="rounded-full">Preview</TabsTrigger>
        </TabsList>

        {/* Natural Language Creation */}
        <TabsContent value="create" className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Input Section */}
            <Card className="col-span-1 border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-[#1B3B2B]">
                  <Brain className="h-5 w-5 text-[#1B3B2B]" />
                  AI-Powered Generation
                </CardTitle>
                <CardDescription className="text-xs text-[#55635B]">
                  Describe your dataset in natural language and let AI configure the workflow
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="relative">
                  <textarea
                    value={naturalLanguageInput}
                    onChange={(e) => setNaturalLanguageInput(e.target.value)}
                    placeholder="e.g., Generate a multilingual legal reasoning dataset with 10,000 examples in English, Spanish, and French. Focus on contract analysis and include explanations for each legal decision..."
                    className="w-full h-64 p-4 rounded-xl border border-[#D1D8CE] bg-[#F6F7F4] text-[#1B3B2B] text-xs resize-none focus:outline-none focus:ring-2 focus:ring-[#1B3B2B] placeholder:text-[#809085]"
                  />
                  <div className="absolute bottom-3 right-3 flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs rounded-full bg-[#E8ECE6] text-[#1B3B2B]">
                      {naturalLanguageInput.length} / 2000
                    </Badge>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button variant="outline" className="flex-1 gap-2 border-[#D1D8CE] text-[#1B3B2B] hover:bg-[#E8ECE6] rounded-full" disabled={isSubmitting}>
                    <Sparkles className="h-4 w-4" />
                    Enhance Prompt
                  </Button>
                  <Button
                    className="flex-1 gap-2 bg-[#1B3B2B] hover:bg-[#142D21] text-white rounded-full font-medium"
                    onClick={handleGenerateDataset}
                    disabled={isSubmitting || !naturalLanguageInput.trim()}
                  >
                    {isSubmitting ? (
                      <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                    ) : (
                      <Zap className="h-4 w-4 text-emerald-400" />
                    )}
                    {isSubmitting ? 'Creating...' : 'Generate Configuration'}
                  </Button>
                </div>

                {/* Preset Prompts for Instant Workflow Creation */}
                <div className="pt-4 border-t border-[#E2E6E0]">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-bold text-[#1B3B2B] font-mono uppercase tracking-wider flex items-center gap-1.5">
                      <Zap className="h-3.5 w-3.5 fill-current text-[#1B3B2B]" />
                      Preset Industry Benchmarks
                    </p>
                    <span className="text-[10px] text-[#55635B] font-mono">1-Click Load & Launch</span>
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    {[
                      {
                        title: '🩺 Medical Clinical Diagnostics & Treatment',
                        prompt: 'Synthesize a clinical instruction-following dataset containing 500 medical diagnostic scenarios. Each example must include patient presentation, differential diagnosis, evidence-based treatment protocols, contraindications, and laboratory workup recommendations.',
                        type: 'sft',
                        size: 500,
                        domain: 'medicine'
                      },
                      {
                        title: '🐍 Python Thread-Safe Concurrent Algorithms',
                        prompt: 'Generate an advanced Python coding instruction dataset focusing on thread-safe data structures, async/await concurrency, lock-free queues, and memory optimization with unit tests for each implementation.',
                        type: 'coding',
                        size: 1000,
                        domain: 'coding'
                      },
                      {
                        title: '⚖️ Legal Contract Risk Analysis & Compliance',
                        prompt: 'Build a legal dataset for contract clause extraction and risk scoring. Scenarios should evaluate indemnification clauses, governing law compliance, liability caps, and intellectual property assignments with step-by-step rationale.',
                        type: 'sft',
                        size: 750,
                        domain: 'legal'
                      },
                      {
                        title: '📊 Financial Market Sentiment & Reasoning',
                        prompt: 'Synthesize a financial analysis dataset focusing on quarterly earnings report interpretation, EBITDA margin trends, macroeconomic sentiment analysis, and multi-step quantitative reasoning.',
                        type: 'sft',
                        size: 1000,
                        domain: 'finance'
                      },
                      {
                        title: '🛡️ Cybersecurity Threat Vector & Code Audit',
                        prompt: 'Generate a security vulnerability auditing dataset with code snippets in C++ and Python containing intentional OWASP Top-10 bugs (buffer overflow, SQL injection, XSS), accompanied by remediation patches.',
                        type: 'coding',
                        size: 500,
                        domain: 'security'
                      }
                    ].map((preset) => (
                      <div
                        key={preset.title}
                        className="group flex flex-col p-3 rounded-xl border border-[#E2E6E0] bg-[#F6F7F4] hover:bg-white hover:border-[#D1D8CE] transition-all text-left"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-bold text-[#1B3B2B]">
                            {preset.title}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <Badge variant="outline" className="text-[10px] py-0 h-4 border-[#D1D8CE] bg-white text-[#1B3B2B] rounded-full">
                              {preset.size} samples
                            </Badge>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-5 px-2 text-[10px] bg-[#E8ECE6] text-[#1B3B2B] hover:bg-[#1B3B2B] hover:text-white font-bold rounded-full transition-colors"
                              onClick={() => {
                                setNaturalLanguageInput(preset.prompt)
                                setTargetSize(preset.size)
                                setDatasetType(preset.type)
                                setDatasetName(preset.title)
                              }}
                            >
                              ⚡ 1-Click Load
                            </Button>
                          </div>
                        </div>
                        <p className="text-[11px] text-[#55635B] line-clamp-2 leading-relaxed">
                          {preset.prompt}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Selected Template Preview */}
            <Card className="col-span-1 border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base text-[#1B3B2B]">
                  <Settings2 className="h-5 w-5 text-[#1B3B2B]" />
                  Configuration Preview
                </CardTitle>
                <CardDescription className="text-xs text-[#55635B]">
                  Your current settings
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0] space-y-3">
                    <div className="flex justify-between">
                      <span className="text-xs text-[#55635B]">Target Size</span>
                      <span className="text-xs font-mono font-bold text-[#1B3B2B]">{targetSize.toLocaleString()} records</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-[#55635B]">Quality Level</span>
                      <Badge variant="outline" className="rounded-full border-[#D1D8CE] bg-white text-[#1B3B2B]">{qualityLevel}</Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-[#55635B]">Output Format</span>
                      <span className="text-xs font-mono uppercase font-bold text-[#1B3B2B]">{outputFormat}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-[#55635B]">Modality</span>
                      <span className="text-xs font-mono capitalize text-[#1B3B2B]">{modality}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-[#55635B]">Estimated Cost</span>
                      <span className="text-xs font-mono text-amber-700 font-bold">
                        ~${(targetSize * 0.05).toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-bold text-[#55635B] uppercase font-mono">
                      Selected Providers
                    </p>
                    <div className="flex gap-2 flex-wrap">
                      {selectedProviders.length > 0 ? (
                        selectedProviders.map((p) => (
                          <Badge key={p} variant="outline" className="capitalize rounded-full border-[#D1D8CE] bg-white text-[#1B3B2B]">
                            {p}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-xs text-[#55635B]">None selected</span>
                      )}
                    </div>
                  </div>

                  {selectedTemplate && (
                    <div className="space-y-2">
                      <p className="text-xs font-bold text-[#55635B] uppercase font-mono">
                        Template
                      </p>
                      <div className="p-2.5 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0] text-xs font-medium text-[#1B3B2B]">
                        {templates.find((t) => t.id === selectedTemplate)?.name || 'Unknown'}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Configuration Tab */}
        <TabsContent value="config" className="mt-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Dataset Configuration */}
            <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader>
                <CardTitle className="text-base font-bold flex items-center gap-2 text-[#1B3B2B]">
                  <Database className="h-4 w-4 text-[#1B3B2B]" />
                  Dataset Settings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1B3B2B]">Dataset Name</label>
                  <Input placeholder="my-dataset-v1" className="rounded-full border-[#D1D8CE] text-xs" />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1B3B2B]">Modality</label>
                  <Select defaultValue="text">
                    <SelectTrigger className="rounded-full border-[#D1D8CE] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="text">Text</SelectItem>
                      <SelectItem value="image">Image</SelectItem>
                      <SelectItem value="code">Code</SelectItem>
                      <SelectItem value="multimodal">Multimodal</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1B3B2B]">Dataset Type</label>
                  <Select value={datasetType} onValueChange={setDatasetType}>
                    <SelectTrigger className="rounded-full border-[#D1D8CE] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="sft">Standard SFT (Alpaca)</SelectItem>
                      <SelectItem value="conversational">Conversational (Multi-Turn Chat)</SelectItem>
                      <SelectItem value="rag">RAG Context-Q&A</SelectItem>
                      <SelectItem value="reasoning">Chain of Thought Reasoning</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1B3B2B]">Target Size</label>
                  <Input type="number" placeholder="1000" defaultValue="1000" className="rounded-full border-[#D1D8CE] text-xs" />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1B3B2B]">Quality Level</label>
                  <Select defaultValue="high">
                    <SelectTrigger className="rounded-full border-[#D1D8CE] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1B3B2B]">Output Format</label>
                  <Select defaultValue="jsonl">
                    <SelectTrigger className="rounded-full border-[#D1D8CE] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="jsonl">JSONL</SelectItem>
                      <SelectItem value="parquet">Parquet</SelectItem>
                      <SelectItem value="csv">CSV</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1B3B2B]">Generation Mode</label>
                  <Select value={generationMode} onValueChange={setGenerationMode}>
                    <SelectTrigger className="rounded-full border-[#D1D8CE] text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hybrid">Hybrid (Crawl + Fallback)</SelectItem>
                      <SelectItem value="synthetic">Pure Synthetic (Seedless)</SelectItem>
                      <SelectItem value="source">Source-Based (Strict)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            {/* Provider Selection */}
            <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader>
                <CardTitle className="text-base font-bold flex items-center gap-2 text-[#1B3B2B]">
                  <Zap className="h-4 w-4 text-[#1B3B2B]" />
                  Provider Selection
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2.5">
                  {providers.map((provider) => (
                    <div
                      key={provider.id}
                      onClick={() => toggleProvider(provider.id)}
                      className={clsx(
                        'p-3 rounded-xl border cursor-pointer transition-all',
                        selectedProviders.includes(provider.id)
                          ? 'border-[#1B3B2B] bg-[#E8ECE6]/80'
                          : 'border-[#E2E6E0] bg-[#F6F7F4] hover:bg-white'
                      )}
                    >
                      <div className="flex items-center justify-between mb-0.5">
                        <span className="font-bold text-xs text-[#1B3B2B]">{provider.name}</span>
                        <div
                          className={clsx(
                            'h-4 w-4 rounded-full border flex items-center justify-center',
                            selectedProviders.includes(provider.id)
                              ? 'bg-[#1B3B2B] border-[#1B3B2B]'
                              : 'border-[#D1D8CE]'
                          )}
                        >
                          {selectedProviders.includes(provider.id) && (
                            <span className="text-white text-[10px]">✓</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 p-3 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0]">
                  <div className="flex justify-between text-xs">
                    <span className="text-[#55635B]">Priority Order</span>
                    <span className="font-mono font-bold text-[#1B3B2B]">{selectedProviders.length > 0 ? selectedProviders.join(' → ') : 'None selected'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Constraints */}
            <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
              <CardHeader>
                <CardTitle className="text-base font-bold flex items-center gap-2 text-[#1B3B2B]">
                  <Shield className="h-4 w-4 text-[#1B3B2B]" />
                  Constraints
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {constraints.map((constraint, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-2 p-2 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0]"
                      >
                        <span className="text-xs font-medium text-[#1B3B2B] flex-1">
                          {constraintTypes.find((c) => c.id === constraint.type)?.label}
                        </span>
                        <Input
                          className="w-24 h-7 text-xs rounded-full border-[#D1D8CE]"
                          placeholder="Value"
                          value={constraint.value}
                          onChange={(e) => {
                            const updated = [...constraints]
                            updated[index].value = e.target.value
                            setConstraints(updated)
                          }}
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0 rounded-full text-[#1B3B2B]"
                          onClick={() => removeConstraint(index)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}

                    <div className="pt-2">
                      <p className="text-xs text-[#55635B] font-mono uppercase mb-2">Add Constraint</p>
                      <div className="flex flex-wrap gap-1.5">
                        {constraintTypes
                          .filter((c) => !constraints.find((con) => con.type === c.id))
                          .map((constraint) => (
                            <Button
                              key={constraint.id}
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs rounded-full border-[#D1D8CE] text-[#1B3B2B]"
                              onClick={() => addConstraint(constraint.id)}
                            >
                              <Plus className="h-3 w-3 mr-1" />
                              {constraint.label}
                            </Button>
                          ))}
                      </div>
                    </div>
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="mt-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {templates.map((template) => (
              <Card
                key={template.id}
                className={clsx(
                  'cursor-pointer transition-all border-[#E2E6E0] bg-white rounded-2xl card-shadow hover:border-[#1B3B2B]',
                  selectedTemplate === template.id && 'border-[#1B3B2B] bg-[#E8ECE6]/40'
                )}
                onClick={() => setSelectedTemplate(template.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="h-10 w-10 rounded-xl bg-[#1B3B2B] text-white flex items-center justify-center font-bold">
                      {template.icon}
                    </div>
                    <Badge variant="secondary" className="text-xs rounded-full bg-[#E8ECE6] text-[#1B3B2B]">
                      {template.category}
                    </Badge>
                  </div>
                  <h3 className="font-bold text-sm text-[#1B3B2B] mb-1">{template.name}</h3>
                  <p className="text-xs text-[#55635B]">{template.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {selectedTemplate && (
            <div className="mt-6 flex justify-end">
              <Button className="gap-2 bg-[#1B3B2B] hover:bg-[#142D21] text-white rounded-full px-6 font-medium" onClick={() => setActiveTab('config')}>
                Use Template
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </TabsContent>

        {/* Preview Tab */}
        <TabsContent value="preview" className="mt-6">
          <Card className="border-[#E2E6E0] bg-white rounded-2xl card-shadow">
            <CardHeader>
              <CardTitle className="text-base font-bold text-[#1B3B2B]">Configuration Preview</CardTitle>
              <CardDescription className="text-xs text-[#55635B]">
                Review your dataset generation configuration before starting
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="p-4 rounded-xl bg-[#F6F7F4] border border-[#E2E6E0] overflow-auto text-xs font-mono text-[#1B3B2B]">
                {JSON.stringify(
                  {
                    name: 'my-dataset-v1',
                    modality: 'text',
                    targetSize: 1000,
                    qualityLevel: 'high',
                    format: 'jsonl',
                    providers: selectedProviders,
                    constraints: constraints.filter((c) => c.enabled),
                  },
                  null,
                  2
                )}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
