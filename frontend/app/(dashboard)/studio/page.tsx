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
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dataset Generation Studio</h1>
          <p className="text-sm text-muted-foreground">
            Create and configure autonomous dataset generation workflows
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-2">
            <Save className="h-4 w-4" />
            Save Draft
          </Button>
          <Button
            size="sm"
            className="gap-2"
            onClick={handleGenerateDataset}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {isSubmitting ? 'Creating...' : 'Generate Dataset'}
          </Button>
        </div>
      </div>

      {/* Error/Success Messages */}
      {submitError && (
        <Card className="border-destructive">
          <CardContent className="p-4 flex items-center gap-4">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <p className="text-sm">{submitError}</p>
            <Button variant="ghost" size="sm" onClick={() => setSubmitError(null)}>
              <X className="h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      )}

      {createdJob && (
        <Card className="border-green-500">
          <CardContent className="p-4 flex items-center gap-4">
            <CheckCircle2 className="h-5 w-5 text-green-500" />
            <div className="flex-1">
              <p className="text-sm font-medium">Dataset Job Created!</p>
              <p className="text-xs text-muted-foreground">
                Job ID: {createdJob.id} - Redirecting to datasets...
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="create">Natural Language</TabsTrigger>
          <TabsTrigger value="config">Configuration</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
        </TabsList>

        {/* Natural Language Creation */}
        <TabsContent value="create" className="mt-6">
          <div className="grid grid-cols-2 gap-6">
            {/* Input Section */}
            <Card className="col-span-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5 text-accent" />
                  AI-Powered Generation
                </CardTitle>
                <CardDescription>
                  Describe your dataset in natural language and let AI configure the workflow
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="relative">
                  <textarea
                    value={naturalLanguageInput}
                    onChange={(e) => setNaturalLanguageInput(e.target.value)}
                    placeholder="e.g., Generate a multilingual legal reasoning dataset with 10,000 examples in English, Spanish, and French. Focus on contract analysis and include explanations for each legal decision..."
                    className="w-full h-64 p-4 rounded-lg border border-border bg-surface text-sm resize-none focus:outline-none focus:ring-2 focus:ring-accent placeholder:text-muted-foreground"
                  />
                  <div className="absolute bottom-3 right-3 flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">
                      {naturalLanguageInput.length} / 2000
                    </Badge>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Button variant="outline" className="flex-1 gap-2" disabled={isSubmitting}>
                    <Sparkles className="h-4 w-4" />
                    Enhance Prompt
                  </Button>
                  <Button
                    className="flex-1 gap-2"
                    onClick={handleGenerateDataset}
                    disabled={isSubmitting || !naturalLanguageInput.trim()}
                  >
                    {isSubmitting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Zap className="h-4 w-4" />
                    )}
                    {isSubmitting ? 'Creating...' : 'Generate Configuration'}
                  </Button>
                </div>

                {/* Quick Suggestions */}
                <div className="pt-4 border-t border-border">
                  <p className="text-xs text-muted-foreground mb-2">Quick Prompts</p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      'Legal QA',
                      'Medical Records',
                      'Code Translation',
                      'Customer Support',
                    ].map((prompt) => (
                      <button
                        key={prompt}
                        onClick={() => setNaturalLanguageInput(prompt)}
                        className="px-3 py-1 rounded-full border border-border text-xs hover:border-accent hover:text-accent transition-colors"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Selected Template Preview */}
            <Card className="col-span-1">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings2 className="h-5 w-5 text-accent" />
                  Configuration Preview
                </CardTitle>
                <CardDescription>
                  Your current settings
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="p-4 rounded-lg bg-surface/50 space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Target Size</span>
                      <span className="text-sm font-mono">{targetSize.toLocaleString()} records</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Quality Level</span>
                      <Badge variant="outline">{qualityLevel}</Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Output Format</span>
                      <span className="text-sm font-mono uppercase">{outputFormat}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Modality</span>
                      <span className="text-sm font-mono capitalize">{modality}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Estimated Cost</span>
                      <span className="text-sm font-mono text-warning">
                        ~${(targetSize * 0.05).toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">
                      Selected Providers
                    </p>
                    <div className="flex gap-2 flex-wrap">
                      {selectedProviders.length > 0 ? (
                        selectedProviders.map((p) => (
                          <Badge key={p} variant="outline" className="capitalize">
                            {p}
                          </Badge>
                        ))
                      ) : (
                        <span className="text-xs text-muted-foreground">None selected</span>
                      )}
                    </div>
                  </div>

                  {selectedTemplate && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-muted-foreground">
                        Template
                      </p>
                      <div className="p-2 rounded bg-surface/50 text-sm">
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
          <div className="grid grid-cols-3 gap-6">
            {/* Dataset Configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Database className="h-4 w-4 text-accent" />
                  Dataset Settings
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Dataset Name</label>
                  <Input placeholder="my-dataset-v1" />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Modality</label>
                  <Select defaultValue="text">
                    <SelectTrigger>
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

                <div className="space-y-2">
                  <label className="text-sm font-medium">Dataset Type</label>
                  <Select value={datasetType} onValueChange={setDatasetType}>
                    <SelectTrigger>
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

                <div className="space-y-2">
                  <label className="text-sm font-medium">Target Size</label>
                  <Input type="number" placeholder="1000" defaultValue="1000" />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Quality Level</label>
                  <Select defaultValue="high">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Output Format</label>
                  <Select defaultValue="jsonl">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="jsonl">JSONL</SelectItem>
                      <SelectItem value="parquet">Parquet</SelectItem>
                      <SelectItem value="csv">CSV</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Generation Mode</label>
                  <Select value={generationMode} onValueChange={setGenerationMode}>
                    <SelectTrigger>
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
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Zap className="h-4 w-4 text-accent" />
                  Provider Selection
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {providers.map((provider) => (
                    <div
                      key={provider.id}
                      onClick={() => toggleProvider(provider.id)}
                      className={clsx(
                        'p-3 rounded-lg border cursor-pointer transition-all',
                        selectedProviders.includes(provider.id)
                          ? 'border-accent bg-accent/5'
                          : 'border-border hover:border-accent/50'
                      )}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium text-sm">{provider.name}</span>
                        <div
                          className={clsx(
                            'h-4 w-4 rounded border flex items-center justify-center',
                            selectedProviders.includes(provider.id)
                              ? 'bg-accent border-accent'
                              : 'border-border'
                          )}
                        >
                          {selectedProviders.includes(provider.id) && (
                            <span className="text-white text-xs">✓</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="mt-4 p-3 rounded-lg bg-surface/50">
                  <div className="flex justify-between text-sm">
                    <span>Priority Order</span>
                    <span className="font-mono">{selectedProviders.length > 0 ? selectedProviders.join(' → ') : 'None selected'}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Constraints */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Shield className="h-4 w-4 text-accent" />
                  Constraints
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {constraints.map((constraint, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-2 p-2 rounded bg-surface/50"
                      >
                        <span className="text-sm flex-1">
                          {constraintTypes.find((c) => c.id === constraint.type)?.label}
                        </span>
                        <Input
                          className="w-24 h-7 text-xs"
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
                          className="h-7 w-7 p-0"
                          onClick={() => removeConstraint(index)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}

                    <div className="pt-2">
                      <p className="text-xs text-muted-foreground mb-2">Add Constraint</p>
                      <div className="flex flex-wrap gap-1">
                        {constraintTypes
                          .filter((c) => !constraints.find((con) => con.type === c.id))
                          .map((constraint) => (
                            <Button
                              key={constraint.id}
                              variant="outline"
                              size="sm"
                              className="h-7 text-xs"
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
          <div className="grid grid-cols-3 gap-4">
            {templates.map((template) => (
              <Card
                key={template.id}
                className={clsx(
                  'cursor-pointer transition-all hover:border-accent',
                  selectedTemplate === template.id && 'border-accent bg-accent/5'
                )}
                onClick={() => setSelectedTemplate(template.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-accent to-purple-600 flex items-center justify-center text-white font-bold">
                      {template.icon}
                    </div>
                    <Badge variant="secondary" className="text-xs">
                      {template.category}
                    </Badge>
                  </div>
                  <h3 className="font-medium mb-1">{template.name}</h3>
                  <p className="text-xs text-muted-foreground">{template.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {selectedTemplate && (
            <div className="mt-6 flex justify-end">
              <Button className="gap-2" onClick={() => setActiveTab('config')}>
                Use Template
                <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </TabsContent>

        {/* Preview Tab */}
        <TabsContent value="preview" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Configuration Preview</CardTitle>
              <CardDescription>
                Review your dataset generation configuration before starting
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="p-4 rounded-lg bg-surface overflow-auto text-sm font-mono">
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
