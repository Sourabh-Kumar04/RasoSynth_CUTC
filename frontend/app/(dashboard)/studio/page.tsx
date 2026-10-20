'use client'

import { useState, useCallback, useEffect, Suspense } from 'react'
import {
  FlaskConical,
  Sparkles,
  Settings2,
  Play,
  Plus,
  X,
  ChevronDown,
  ChevronUp,
  Loader2,
  Check,
  CheckCircle2,
  ExternalLink,
  Layers,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useRouter, useSearchParams } from 'next/navigation'
import { api } from '@/lib/api/client'

// 1-Click Industry Benchmark Presets
const INDUSTRY_PRESETS = [
  {
    id: 'aikosh-tax',
    title: 'AI Kosh (GST & Indian Tax)',
    domain: 'Finance & Taxation (AI Kosh)',
    source: 'AI Kosh',
    prompt: 'Synthesize 20,000 multi-turn legal and financial audit dialogues from Indian GST statutes, Income Tax Appellate Tribunal decisions, and Section 16(4) input-tax-credit reconciliation case studies with grounded citations.',
    type: 'sft',
    language: 'hinglish',
    scriptMode: 'romanized',
    formalityRegister: 'formal',
    preservedTerms: ['ITC', 'GSTR-3B', 'Section 16(4)', 'Challan'],
    size: 20000,
    sources: ['AI Kosh', 'OpenML', 'India.gov.in'],
  },
  {
    id: 'aerospace-airfoil',
    title: 'Aerospace & Aerodynamics',
    domain: 'Aerospace Engineering & Aerodynamics',
    source: 'NASA Glenn & FAA',
    prompt: 'Synthesize 15,000 multi-stage aeronautical engineering and transonic airfoil design QA dialogues based on NASA supercritical airfoil wind-tunnel data, compressible Navier-Stokes flow regimes, and FAA FAR Part 25 airworthiness certification specifications.',
    type: 'reasoning',
    language: 'en',
    scriptMode: 'native',
    formalityRegister: 'formal',
    preservedTerms: ['NACA 0012', 'Mach 0.82', 'FAR §25.107', 'Supercritical Airfoil', 'Lift-to-Drag (L/D)'],
    size: 15000,
    sources: ['NASA Technical Reports', 'FAA Regulations', 'AIAA'],
  },
  {
    id: 'bhashini-multilingual',
    title: 'Bhashini Indic Corpus',
    domain: 'Indic Multilingual (Bhashini)',
    source: 'Bhashini Data Vatika',
    prompt: 'Construct high-quality parallel instruction-tuning dialogues across Hindi, Tamil, Telugu, and English covering healthcare and public governance with script validation.',
    type: 'sft',
    language: 'indic_multilingual',
    scriptMode: 'native',
    formalityRegister: 'formal',
    parallelBilingual: true,
    size: 25000,
    sources: ['Bhashini', 'AI Kosh', 'HuggingFace'],
  },
  {
    id: 'python-codegen',
    title: 'Python Code Synthesis',
    domain: 'Python Math & Code',
    source: 'GitHub & HF',
    prompt: 'Generate 15,000 competitive programming and algorithmic Python solutions with comprehensive test suites, edge case validations, and asymptotic time-space analysis.',
    type: 'coding',
    language: 'en',
    size: 15000,
    sources: ['HuggingFace', 'GitHub', 'ArXiv'],
  },
  {
    id: 'clinical-reasoning',
    title: 'Medical Clinical Reasoning',
    domain: 'Medical Reasoning',
    source: 'PubMed & Open Data',
    prompt: 'Extract step-by-step diagnostic reasoning trajectories from PubMed open clinical case studies with contraindication warnings and differential diagnosis verification.',
    type: 'reasoning',
    language: 'en',
    size: 10000,
    sources: ['PubMed', 'ArXiv', 'Zenodo'],
  },
]

function StudioContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [prompt, setPrompt] = useState(
    searchParams.get('prompt') ||
    'Synthesize 10,000 multi-turn instruction dialogues from AI Kosh tax rulings & GST statutes with self-correction'
  )
  const [targetDomain, setTargetDomain] = useState(
    searchParams.get('domain') || 'Finance & Taxation (AI Kosh)'
  )
  const [datasetType, setDatasetType] = useState('sft')
  const [instructionFormat, setInstructionFormat] = useState('alpaca')
  const [language, setLanguage] = useState(searchParams.get('language') || 'en')
  const [scriptMode, setScriptMode] = useState<'native' | 'romanized' | 'dual'>('native')
  const [formalityRegister, setFormalityRegister] = useState<'formal' | 'neutral' | 'casual'>('formal')
  const [codeSwitchIntensity, setCodeSwitchIntensity] = useState<'light' | 'balanced' | 'heavy'>('balanced')
  const [regionalDialect, setRegionalDialect] = useState<string>('standard')
  const [numberFormatting, setNumberFormatting] = useState<'indian_lakhs' | 'western_millions'>('indian_lakhs')
  const [chatNoiseLevel, setChatNoiseLevel] = useState<number>(0.0)
  const [maskIndianPii, setMaskIndianPii] = useState<boolean>(true)
  const [speechNormalization, setSpeechNormalization] = useState<boolean>(false)
  const [generateDpoRefusalPairs, setGenerateDpoRefusalPairs] = useState<boolean>(false)
  const [turnLanguageDrift, setTurnLanguageDrift] = useState<boolean>(false)
  const [enableCotReasoning, setEnableCotReasoning] = useState<boolean>(false)
  const [curriculumSort, setCurriculumSort] = useState<'none' | 'ascending' | 'staged_curriculum' | 'replay_interleaved'>('none')
  const [preservedTermsInput, setPreservedTermsInput] = useState<string>('')
  const [parallelBilingual, setParallelBilingual] = useState<boolean>(false)
  const [datasetSize, setDatasetSize] = useState(10000)
  const [generationMode, setGenerationMode] = useState<'grounded' | 'synthetic'>('grounded')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isAutoDetecting, setIsAutoDetecting] = useState(false)
  const [discoveredSources, setDiscoveredSources] = useState<Array<{ name: string; url?: string; source_type?: string }>>([])
  const [autoDetectNotice, setAutoDetectNotice] = useState<string | null>(null)
  const [activePreset, setActivePreset] = useState<string>('aikosh-tax')
  const [idealSamples, setIdealSamples] = useState<Array<{ instruction: string; response: string }>>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [showAnchors, setShowAnchors] = useState(false)

  // Live Tokenizer Fertility Estimation
  const isIndicOrHinglish = ['hi', 'hinglish', 'indic_multilingual', 'ta', 'te', 'bn', 'mr', 'gu', 'kn', 'ml', 'pa'].includes(language)
  const estLlama3Fertility = isIndicOrHinglish ? (scriptMode === 'romanized' || language === 'hinglish' ? 1.55 : 3.65) : 1.25
  const estSarvamFertility = isIndicOrHinglish ? (scriptMode === 'romanized' || language === 'hinglish' ? 1.32 : 1.28) : 1.24
  const estSavings = Math.round((1 - estSarvamFertility / estLlama3Fertility) * 100)

  // Dynamic entity & technical token extractor
  const extractSyntacticInvariants = useCallback((text: string): string[] => {
    const terms = new Set<string>()
    const sectionMatches = text.match(/\b(?:Section|Sec\.|FAR\s*Part|FAR|Article|Rule|Order|NACA|ISO|IEEE)\s*(?:§\s*)?[A-Za-z0-9\(\)\.\-]+/gi) || []
    sectionMatches.forEach(m => terms.add(m.trim()))

    const formulaMatches = text.match(/\b(?:O\([A-Za-z0-9\s\+\*\^\log]+\)|Mach\s*\d+(?:\.\d+)?|L\/D|PK\/PD|Navier-Stokes|Reynolds)/gi) || []
    formulaMatches.forEach(m => terms.add(m.trim()))

    const quoteMatches = text.match(/["']([^"']{2,40})["']/g) || []
    quoteMatches.forEach(m => terms.add(m.replace(/["']/g, '').trim()))

    const stopWords = new Set(['AND', 'THE', 'FOR', 'ARE', 'NOT', 'BUT', 'ALL', 'NEW', 'SET', 'OUT', 'CAN', 'GET', 'USE', 'HOW', 'WHY', 'WHO', 'YES', 'NO'])
    const acronymMatches = text.match(/\b[A-Z]{2,6}(?:-[A-Z0-9]+)?\b/g) || []
    acronymMatches.forEach(m => {
      const clean = m.trim()
      if (!stopWords.has(clean)) terms.add(clean)
    })

    return Array.from(terms)
  }, [])

  const handleAutoDetect = useCallback(async () => {
    const queryText = (prompt || targetDomain).trim()
    if (!queryText) return
    setIsAutoDetecting(true)
    setAutoDetectNotice(null)

    const localTerms = extractSyntacticInvariants(`${targetDomain} ${prompt}`)
    const currentList = preservedTermsInput
      .split(',')
      .map(t => t.trim())
      .filter(Boolean)
    const mergedTerms = Array.from(new Set([...currentList, ...localTerms]))

    try {
      const previewRes = await api.previewJobSources({
        query: queryText,
        max_sources: 6,
      })

      if (previewRes) {
        const intentEntities: string[] = previewRes.query_plan?.intent?.key_entities || []
        const dynamicDomain = previewRes.query_plan?.intent?.domain
        if (dynamicDomain && (!targetDomain || targetDomain === 'Finance & Taxation (AI Kosh)')) {
          setTargetDomain(dynamicDomain)
        }

        const allTerms = Array.from(new Set([...mergedTerms, ...intentEntities]))
        setPreservedTermsInput(allTerms.join(', '))

        if (Array.isArray(previewRes.sources) && previewRes.sources.length > 0) {
          setDiscoveredSources(previewRes.sources.map((s: any) => ({
            name: s.name || s.domain || 'Verified Domain Repository',
            url: s.url,
            source_type: s.source_type || 'discovery',
          })))
        }

        setAutoDetectNotice(
          `Discovered ${allTerms.length} invariant terms · ${previewRes.sources?.length || 0} authority sources`
        )
      } else {
        setPreservedTermsInput(mergedTerms.join(', '))
        setAutoDetectNotice(`Extracted ${mergedTerms.length} invariant terms`)
      }
    } catch {
      setPreservedTermsInput(mergedTerms.join(', '))
      setAutoDetectNotice(`Extracted ${mergedTerms.length} invariant terms`)
    } finally {
      setIsAutoDetecting(false)
    }
  }, [prompt, targetDomain, preservedTermsInput, extractSyntacticInvariants])

  // Launch job
  const handleGenerate = async () => {
    setIsSubmitting(true)
    try {
      const validAnchors = idealSamples
        .filter((s) => s.instruction.trim() && s.response.trim())
        .map((s) => ({
          instruction: s.instruction.trim(),
          response: s.response.trim(),
        }))

      const preservedTerms = preservedTermsInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)

      const payload: Record<string, any> = {
        target_domain: prompt.trim() || targetDomain,
        dataset_name: targetDomain,
        dataset_type: datasetType,
        instruction_format: instructionFormat,
        language: language,
        script_mode: scriptMode,
        formality_register: formalityRegister,
        code_switch_intensity: codeSwitchIntensity,
        regional_dialect: regionalDialect,
        number_formatting: numberFormatting,
        chat_noise_level: chatNoiseLevel,
        mask_indian_pii: maskIndianPii,
        speech_normalization: speechNormalization,
        generate_dpo_refusal_pairs: generateDpoRefusalPairs,
        turn_language_drift: turnLanguageDrift,
        enable_cot_reasoning: enableCotReasoning,
        curriculum_sort: curriculumSort,
        preserved_terms: preservedTerms,
        parallel_bilingual: parallelBilingual,
        dataset_size: datasetSize,
        quality_level: 'standard',
        generation_mode: generationMode === 'grounded' ? 'strict_source' : 'synthetic',
        allow_seedless_generation: generationMode === 'synthetic',
      }

      if (validAnchors.length > 0) {
        payload.ideal_samples = validAnchors
      }

      const response = await api.createJob(payload)
      if (response && response.id) {
        router.push(`/orchestration?job=${response.id}`)
      }
    } catch (err: any) {
      console.error('Job creation failed:', err)
      router.push('/orchestration')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="w-full max-w-[1600px] mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#272738] pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display mb-1">
            Autonomous Dataset Studio
          </h1>
          <p className="text-xs text-[#94a3b8]">
            Synthesize verified fine-tuning and reasoning datasets grounded in authoritative corpora
          </p>
        </div>

        <Button
          onClick={handleGenerate}
          disabled={isSubmitting}
          className="bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white font-mono text-xs font-bold h-9 px-5 shadow-sm glow-yc flex items-center gap-2 rounded-md self-start sm:self-auto"
        >
          {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
          <span>Launch Pipeline</span>
        </Button>
      </div>

      {/* Industry Presets */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[#f26625]" />
            Industry Presets
          </span>
          <span className="text-[11px] font-mono text-[#10b981]">Grounded Schemas</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {INDUSTRY_PRESETS.map((preset) => {
            const isSelected = activePreset === preset.id
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => {
                  setActivePreset(preset.id)
                  setTargetDomain(preset.domain)
                  setPrompt(preset.prompt)
                  setDatasetSize(preset.size)
                  setDatasetType(preset.type)
                  if ((preset as any).language) setLanguage((preset as any).language)
                  if ((preset as any).scriptMode) setScriptMode((preset as any).scriptMode)
                  if ((preset as any).formalityRegister) setFormalityRegister((preset as any).formalityRegister)
                  if ((preset as any).preservedTerms) {
                    setPreservedTermsInput(((preset as any).preservedTerms || []).join(', '))
                  }
                  if ((preset as any).parallelBilingual !== undefined) {
                    setParallelBilingual(Boolean((preset as any).parallelBilingual))
                  }
                }}
                className={clsx(
                  'p-3.5 rounded-md border text-left transition-all space-y-2 relative overflow-hidden',
                  isSelected
                    ? 'bg-[#161622] border-[#f26625] shadow-sm glow-yc'
                    : 'bg-[#12121a] border-[#272738] hover:border-[#f26625]/40 hover:bg-[#161622]/60'
                )}
              >
                <div className="flex justify-between items-start">
                  <span className="text-[10px] font-mono font-bold uppercase text-[#f26625] truncate">
                    {preset.source}
                  </span>
                  <span className="text-[10px] font-mono text-[#10b981] font-semibold">
                    {preset.size.toLocaleString()}
                  </span>
                </div>
                <h4 className="text-xs font-semibold text-white truncate">{preset.title}</h4>
                <div className="flex items-center gap-1 text-[10px] font-mono text-[#94a3b8]">
                  <span className="px-1.5 py-0.5 rounded-sm bg-[#0a0a0f] border border-[#272738] uppercase">
                    {preset.type}
                  </span>
                  <span className="px-1.5 py-0.5 rounded-sm bg-[#0a0a0f] border border-[#272738]">
                    {preset.language}
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Main Studio Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Intent, Prompt & Grounding Invariants */}
        <div className="lg:col-span-7 p-5 rounded-md bg-[#12121a] border border-[#272738] space-y-5">
          <div className="flex items-center justify-between pb-3 border-b border-[#1c1c28]">
            <div className="flex items-center space-x-2">
              <FlaskConical className="w-4 h-4 text-[#f26625]" />
              <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                Dataset Intent &amp; Scope
              </h3>
            </div>
            <div className="inline-flex p-0.5 rounded bg-[#0a0a0f] border border-[#272738]">
              <button
                type="button"
                onClick={() => setGenerationMode('grounded')}
                className={clsx(
                  'px-3 py-1 rounded text-xs font-mono transition-all',
                  generationMode === 'grounded'
                    ? 'bg-[#1a1a24] text-white font-semibold border border-[#272738] shadow-sm'
                    : 'text-[#94a3b8] hover:text-white'
                )}
              >
                Grounded Source
              </button>
              <button
                type="button"
                onClick={() => setGenerationMode('synthetic')}
                className={clsx(
                  'px-3 py-1 rounded text-xs font-mono transition-all',
                  generationMode === 'synthetic'
                    ? 'bg-[#1a1a24] text-white font-semibold border border-[#272738] shadow-sm'
                    : 'text-[#94a3b8] hover:text-white'
                )}
              >
                Pure Synthetic
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1.5">
                Target Domain or Repository Topic
              </label>
              <Input
                value={targetDomain}
                onChange={(e) => setTargetDomain(e.target.value)}
                className="bg-[#0a0a0f] border-[#272738] focus:border-[#f26625] text-xs font-mono text-white rounded-md"
                placeholder="e.g. Aerospace Engineering or Finance & Taxation"
              />
            </div>

            <div>
              <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1.5">
                Specification Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                className="w-full bg-[#0a0a0f] border border-[#272738] focus:border-[#f26625] rounded-md p-3 text-xs font-mono text-white placeholder:text-[#94a3b8] focus:outline-none transition-colors resize-none"
                placeholder="Describe instruction schema, target personas, and validation constraints..."
              />
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={handleAutoDetect}
                  disabled={isAutoDetecting}
                  className="h-8 px-3.5 text-xs font-mono font-bold border-[#f26625]/40 text-[#f26625] bg-[#f26625]/10 hover:bg-[#f26625]/20 rounded-md flex items-center gap-1.5 glow-yc transition-all"
                >
                  {isAutoDetecting ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#f26625]" /> : <Sparkles className="w-3.5 h-3.5 text-[#f26625]" />}
                  <span>{isAutoDetecting ? 'Discovering Invariants…' : 'Auto-Detect Terms & Sources'}</span>
                </Button>
                {autoDetectNotice && (
                  <span className="text-[11px] font-mono text-emerald-400 flex items-center gap-1">
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    {autoDetectNotice}
                  </span>
                )}
              </div>
            </div>

            {/* Preserved Domain Terms / Glossary */}
            <div className="space-y-2 pt-2 border-t border-[#1c1c28]">
              <label className="text-[10px] font-mono uppercase text-[#94a3b8] block">
                Preserved Domain Terms (Invariants)
              </label>
              <Input
                type="text"
                value={preservedTermsInput}
                onChange={(e) => setPreservedTermsInput(e.target.value)}
                placeholder="e.g. NACA 0012, Mach 0.82, Section 16(4), ITC, GSTR-3B"
                className="bg-[#0a0a0f] border-[#272738] focus:border-[#f26625] text-xs font-mono text-white rounded-md"
              />
              {preservedTermsInput && (
                <div className="flex flex-wrap gap-1.5 pt-1 max-h-24 overflow-y-auto">
                  {preservedTermsInput
                    .split(',')
                    .map((t) => t.trim())
                    .filter(Boolean)
                    .map((term, i) => (
                      <span
                        key={i}
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-[#161622] border border-[#f26625]/30 text-[#f26625] text-[10px] font-mono"
                      >
                        {term}
                        <button
                          type="button"
                          onClick={() => {
                            const remaining = preservedTermsInput
                              .split(',')
                              .map((t) => t.trim())
                              .filter((t) => t !== term)
                            setPreservedTermsInput(remaining.join(', '))
                          }}
                          className="hover:text-rose-400 font-bold ml-1"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                </div>
              )}
            </div>

            {/* Discovered Authoritative Sources */}
            {discoveredSources.length > 0 && (
              <div className="space-y-1.5 pt-2 border-t border-[#1c1c28]">
                <span className="text-[10px] font-mono uppercase text-[#94a3b8] block">
                  Authoritative Grounding Sources ({discoveredSources.length}):
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {discoveredSources.map((s, idx) => (
                    <span
                      key={idx}
                      className="px-2 py-0.5 rounded-sm bg-[#0a0a0f] border border-[#272738] text-[10px] font-mono text-emerald-400 truncate max-w-[220px]"
                      title={s.name}
                    >
                      {s.name}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Collapsible Few-Shot Anchor Examples */}
            <div className="pt-2 border-t border-[#1c1c28]">
              <button
                type="button"
                onClick={() => setShowAnchors(!showAnchors)}
                className="flex items-center justify-between w-full text-xs font-mono text-[#94a3b8] hover:text-white py-1"
              >
                <span className="flex items-center gap-1.5">
                  Few-Shot Output Anchors ({idealSamples.length})
                </span>
                {showAnchors ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {showAnchors && (
                <div className="space-y-3 pt-3">
                  {idealSamples.map((sample, idx) => (
                    <div key={idx} className="p-3 rounded-md bg-[#0a0a0f] border border-[#272738] space-y-2">
                      <div className="flex items-center justify-between text-[10px] font-mono text-[#f26625]">
                        <span>Anchor #{idx + 1}</span>
                        <button
                          type="button"
                          onClick={() => setIdealSamples(idealSamples.filter((_, i) => i !== idx))}
                          className="text-rose-400 hover:underline"
                        >
                          Remove
                        </button>
                      </div>
                      <Input
                        value={sample.instruction}
                        onChange={(e) => {
                          const updated = [...idealSamples]
                          updated[idx].instruction = e.target.value
                          setIdealSamples(updated)
                        }}
                        placeholder="User instruction..."
                        className="bg-[#12121a] border-[#272738] text-xs font-mono text-white h-7"
                      />
                      <textarea
                        value={sample.response}
                        onChange={(e) => {
                          const updated = [...idealSamples]
                          updated[idx].response = e.target.value
                          setIdealSamples(updated)
                        }}
                        rows={2}
                        placeholder="Target model response..."
                        className="w-full bg-[#12121a] border border-[#272738] rounded-md p-2 text-xs font-mono text-white placeholder:text-[#64748b] focus:outline-none resize-none"
                      />
                    </div>
                  ))}

                  {idealSamples.length < 3 && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setIdealSamples([...idealSamples, { instruction: '', response: '' }])}
                      className="h-7 text-xs font-mono border-[#272738] bg-[#0a0a0f] hover:bg-[#161622] text-[#94a3b8] hover:text-white"
                    >
                      <Plus className="w-3 h-3 mr-1" />
                      Add Anchor Sample
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Parameters & Launch */}
        <div className="lg:col-span-5 p-5 rounded-md bg-[#12121a] border border-[#272738] flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-[#1c1c28]">
              <div className="flex items-center space-x-2">
                <Settings2 className="w-4 h-4 text-[#f26625]" />
                <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-white">
                  Dataset Parameters
                </h3>
              </div>
              <span className="text-[10px] font-mono text-[#94a3b8]">Format: JSONL</span>
            </div>

            {/* Core Settings */}
            <div className="space-y-3.5">
              <div>
                <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1">
                  Dataset Type
                </label>
                <select
                  value={datasetType}
                  onChange={(e) => setDatasetType(e.target.value)}
                  className="w-full bg-[#0a0a0f] border border-[#272738] focus:border-[#f26625] rounded-md p-2 text-xs font-mono text-white focus:outline-none"
                >
                  <option value="sft">Supervised Fine-Tuning (SFT / Dialogue)</option>
                  <option value="reasoning">Chain-of-Thought Reasoning (CoT)</option>
                  <option value="coding">Code Generation &amp; Translation</option>
                  <option value="tool_calling">Function &amp; Tool Calling</option>
                  <option value="rlhf">Preference Pairs (RLHF / DPO)</option>
                  <option value="simpo">Simple Preference (SimPO)</option>
                  <option value="rag">Retrieval-Augmented Generation (RAG)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1">
                  Language
                </label>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                  className="w-full bg-[#0a0a0f] border border-[#272738] focus:border-[#f26625] rounded-md p-2 text-xs font-mono text-white focus:outline-none"
                >
                  <option value="en">English</option>
                  <option value="hi">Hindi (हिन्दी)</option>
                  <option value="hinglish">Hindi + English (Hinglish)</option>
                  <option value="indic_multilingual">Indic Multilingual (Hindi, Tamil, Telugu)</option>
                  <option value="ta">Tamil (தமிழ்)</option>
                  <option value="te">Telugu (తెలుగు)</option>
                  <option value="bn">Bengali (বাংলা)</option>
                  <option value="mr">Marathi (मराठी)</option>
                </select>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1.5">
                  <label className="text-[10px] font-mono uppercase text-[#94a3b8]">Target Size</label>
                  <span className="text-xs font-mono text-[#f26625] font-bold">
                    {datasetSize.toLocaleString()} rows
                  </span>
                </div>
                <input
                  type="range"
                  min={100}
                  max={50000}
                  step={500}
                  value={datasetSize}
                  onChange={(e) => setDatasetSize(Number(e.target.value))}
                  className="w-full accent-[#f26625] bg-[#0a0a0f] cursor-pointer"
                />
              </div>

              {/* Collapsible Advanced Configuration */}
              <div className="pt-2 border-t border-[#1c1c28]">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="flex items-center justify-between w-full py-1.5 text-xs font-mono text-[#94a3b8] hover:text-white"
                >
                  <span className="flex items-center gap-1.5">
                    Advanced Linguistic &amp; Alignment Controls
                  </span>
                  {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>

                {showAdvanced && (
                  <div className="space-y-3 pt-3">
                    <div>
                      <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1">
                        Script &amp; Orthography
                      </label>
                      <select
                        value={scriptMode}
                        onChange={(e) => setScriptMode(e.target.value as any)}
                        className="w-full bg-[#0a0a0f] border border-[#272738] rounded-md p-2 text-xs font-mono text-white focus:outline-none"
                      >
                        <option value="native">Native Script</option>
                        <option value="romanized">Romanized / Phonetic</option>
                        <option value="dual">Dual-Script</option>
                      </select>
                    </div>

                    <div>
                      <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1">
                        Register &amp; Honorifics
                      </label>
                      <select
                        value={formalityRegister}
                        onChange={(e) => setFormalityRegister(e.target.value as any)}
                        className="w-full bg-[#0a0a0f] border border-[#272738] rounded-md p-2 text-xs font-mono text-white focus:outline-none"
                      >
                        <option value="formal">Formal / Honorific (आप)</option>
                        <option value="neutral">Professional Neutral</option>
                        <option value="casual">Casual (तुम)</option>
                      </select>
                    </div>

                    {/* Checkbox Options */}
                    <div className="space-y-2 pt-1">
                      <label className="flex items-center justify-between p-2 rounded-md bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-white cursor-pointer">
                        <span>Indian DPDP PII Masking</span>
                        <input
                          type="checkbox"
                          checked={maskIndianPii}
                          onChange={(e) => setMaskIndianPii(e.target.checked)}
                          className="w-4 h-4 accent-[#f26625]"
                        />
                      </label>

                      <label className="flex items-center justify-between p-2 rounded-md bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-white cursor-pointer">
                        <span>DPO Refusal Pairs</span>
                        <input
                          type="checkbox"
                          checked={generateDpoRefusalPairs}
                          onChange={(e) => setGenerateDpoRefusalPairs(e.target.checked)}
                          className="w-4 h-4 accent-[#f26625]"
                        />
                      </label>

                      <label className="flex items-center justify-between p-2 rounded-md bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-white cursor-pointer">
                        <span>CoT Reasoning &lt;thought&gt;</span>
                        <input
                          type="checkbox"
                          checked={enableCotReasoning}
                          onChange={(e) => setEnableCotReasoning(e.target.checked)}
                          className="w-4 h-4 accent-[#f26625]"
                        />
                      </label>

                      <label className="flex items-center justify-between p-2 rounded-md bg-[#0a0a0f] border border-[#272738] text-xs font-mono text-white cursor-pointer">
                        <span>Parallel Bilingual Bitext</span>
                        <input
                          type="checkbox"
                          checked={parallelBilingual}
                          onChange={(e) => setParallelBilingual(e.target.checked)}
                          className="w-4 h-4 accent-[#f26625]"
                        />
                      </label>
                    </div>

                    {/* Tokenizer Fertility */}
                    <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738] font-mono text-[11px] space-y-1">
                      <div className="flex justify-between items-center text-[10px]">
                        <span className="text-[#94a3b8] uppercase font-bold">Tokenizer Efficiency</span>
                        <span className="text-[#10b981] font-bold">
                          {isIndicOrHinglish ? `~${estSavings}% Token Savings` : 'Standard Latin'}
                        </span>
                      </div>
                      <div className="flex justify-between text-[10px] text-[#94a3b8]">
                        <span>Llama-3: {estLlama3Fertility} t/w</span>
                        <span className="text-[#10b981]">Sarvam: {estSarvamFertility} t/w</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <Button
            onClick={handleGenerate}
            disabled={isSubmitting}
            className="w-full bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white font-mono font-bold text-xs h-10 rounded-md shadow-sm glow-yc flex items-center justify-center gap-2"
          >
            {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
            <span>Execute Generation Run</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

export default function StudioPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="h-8 w-8 animate-spin text-[#f26625]" />
        </div>
      }
    >
      <StudioContent />
    </Suspense>
  )
}
