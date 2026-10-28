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
  ShieldCheck,
  AlertCircle,
  Bot,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useRouter, useSearchParams } from 'next/navigation'
import { ZenSpatialCanvas } from '@/components/zen/zen-spatial-canvas'
import { playClickSound } from '@/lib/audio/sound-effects'
import { api } from '@/lib/api/client'

// 1-Click Enterprise Industry Presets
const INDUSTRY_PRESETS = [
  {
    id: 'aikosh-tax',
    title: 'AI Kosh (GST & Indian Tax)',
    domain: 'Finance & Taxation (Indian GST & Tax Compliance)',
    source: 'AI Kosh & CBIC',
    prompt: 'Indian indirect and direct tax compliance advisory. Focus on Input Tax Credit (ITC) reconciliation under Section 16(4) CGST Act, purchase-register vs GSTR-2B discrepancies, supplier default clawbacks under Section 16(2)(c), and TDS/TCS cross-deductions under Section 194Q / 206C(1H). Apply a 3-tier difficulty curriculum: (1) Definitional statutory citations and filing timelines under CGST/IGST Act 2017; (2) Multi-hop reconciliation calculations with arithmetic proofs and circular citations; (3) Complex multi-party manufacturing disputes grounded in ITAT, High Court, and Supreme Court precedent. Require grounded citations to official CBIC circulars. Exclude foreign tax rules (IRS 45Q, Uzbekistan VAT) and biomedical glutathione collisions.',
    type: 'sft',
    category: 'indic',
    language: 'hinglish',
    scriptMode: 'romanized',
    formalityRegister: 'formal',
    preservedTerms: ['Section 16(4)', 'ITC', 'GSTR-3B', 'GSTR-2B', 'CGST Act', 'Section 194Q', 'Section 206C(1H)', 'ISD', 'Challan', 'ITAT'],
    antiDomains: ['glutathione', 's-transferase', 'nrf2', 'uzbekistan', 'irs section 45q', 'arteriovenous fistula', 'cancer chemotherapy'],
    size: 20000,
    sources: ['AI Kosh', 'CBIC Portals', 'ITAT Bench Rulings'],
  },
  {
    id: 'indic-legal',
    title: 'Bhartiya Nyaya Sanhita (BNS)',
    domain: 'Indian Law & Constitutional Jurisprudence (BNS 2023)',
    source: 'eCourts & SCI',
    prompt: 'Criminal justice statutory transition and legal adjudication under Bharatiya Nyaya Sanhita (BNS 2023), BNSS 2023, and BSA 2023. Focus on: (1) Precision cross-mapping of offences from IPC sections to BNS with legislative intent analysis and altered sentencing maximums; (2) Undertrial bail jurisprudence and statutory bail entitlement under Section 479 BNSS; (3) Electronic evidence hash verification protocols under Section 61 BSA 2023; (4) Precedent reconciliation grounded in Supreme Court of India constitutional bench rulings. Preserve exact statutory terminology without importing US Title 18 or UK common law concepts.',
    type: 'reasoning',
    category: 'indic',
    language: 'indic_multilingual',
    scriptMode: 'native',
    formalityRegister: 'formal',
    parallelBilingual: true,
    preservedTerms: ['BNS 2023', 'Section 479 BNSS', 'BSA Section 61', 'Bhartiya Sakshya Adhiniyam', 'Ratio Decidendi', 'Mandamus', 'Habeas Corpus', 'Mens Rea'],
    antiDomains: ['us code title 18', 'california penal code', 'uk crown prosecution service', 'hallucinated citations'],
    size: 20000,
    sources: ['eCourts India', 'Supreme Court Reports', 'Legislative Dept'],
  },
  {
    id: 'aerospace-airfoil',
    title: 'Aerospace & Aerodynamics',
    domain: 'Aerospace Engineering & Computational Aerodynamics',
    source: 'NASA Glenn & FAA',
    prompt: 'Transonic aircraft aerodynamics and transport category airworthiness certification. Focus on: (1) Governing compressible Navier-Stokes and Reynolds-averaged Navier-Stokes (RANS) turbulence closure models; (2) Supercritical airfoil profile optimization (drag divergence Mach number M_dd, shock-boundary interaction, and lift-to-drag L/D maximization) versus conventional NACA 6-series profiles; (3) FAA FAR Part 25 structural load envelopes and §25.629 flutter margins. Preserve exact standard designations (NACA 0012, Mach 0.82, FAR §25.107). Exclude undergraduate textbook simplifications and retracted NASA technical memos.',
    type: 'reasoning',
    category: 'stem',
    language: 'en',
    scriptMode: 'native',
    formalityRegister: 'formal',
    preservedTerms: ['NACA 0012', 'Mach 0.82', 'FAR §25.107', 'FAR §25.629', 'Supercritical Airfoil', 'Navier-Stokes', 'Lift-to-Drag (L/D)', 'Reynolds Number'],
    antiDomains: ['undergraduate textbook simplifications', 'retracted nasa reports', 'superseded far revisions', 'tin cans'],
    size: 15000,
    sources: ['NASA Technical Reports', 'FAA Regulations', 'AIAA'],
  },
  {
    id: 'bhashini-multilingual',
    title: 'Bhashini Indic Corpus',
    domain: 'Indic Multilingual (Bhashini)',
    source: 'Bhashini Data Vatika',
    prompt: 'Construct a high-fidelity parallel multilingual SFT corpus semantically aligned across Hindi (Devanagari), Tamil (Tamil script), Telugu (Telugu script), and Indian English for critical e-governance and public service delivery. Structure samples across: (1) Tier 1 [35% Single-Intent Queries]: Factual citizen queries on Jan Dhan Yojana, PM-KISAN, Aadhaar biometric locking, and DigiLocker credential retrieval with script-native output. (2) Tier 2 [45% Multi-Step Navigation]: End-to-end procedural guidance for UMANG portal service delivery, caste/income certificate issuance, and plain-language Right to Information (RTI) application drafting. (3) Tier 3 [20% Disambiguation & Cultural Dialects]: Resolving regional vocabulary nuances, formal administrative terminology vs conversational spoken registers, and handling code-mixed queries without degrading Devanagari/Dravidian syntactic structure. Ensure bidirectional semantic fidelity without word-for-word translation artifacts. Never generate medical prescriptions without regulatory disclaimers or substitute Roman transliteration when native Indic script is requested.',
    type: 'sft',
    category: 'indic',
    language: 'indic_multilingual',
    scriptMode: 'native',
    formalityRegister: 'formal',
    parallelBilingual: true,
    preservedTerms: ['Bhashini', 'Jan Dhan', 'PM-KISAN', 'Aadhaar', 'UMANG', 'DigiLocker', 'RTI Act 2005', 'Devanagari', 'Tamil Script', 'Telugu Script'],
    antiDomains: ['unsupervised machine translation', 'synthetic hallucinated schemes', 'romanized garble', 'unverified medical dosages'],
    size: 25000,
    sources: ['Bhashini', 'AI Kosh', 'HuggingFace'],
  },
  {
    id: 'python-codegen',
    title: 'Python Systems Architecture',
    domain: 'Production Python Systems & Async Architecture',
    source: 'GitHub & PyPI',
    prompt: 'Synthesize a production-grade Python systems engineering and high-throughput backend architecture dataset. Structure samples across: (1) Tier 1 [30% Strict Typings & Protocols]: PEP 484/PEP 585 static type annotations, Pydantic v2 strict models with custom validators and Rust core serialization, and abstract base classes / typing.Protocol. (2) Tier 2 [45% Concurrency & Data Pipelines]: Asynchronous I/O pipelines utilizing asyncio.TaskGroup, uvloop event loops, structured concurrency, non-blocking connection pooling, and zero-copy Apache Arrow / Polars dataframe transformations. (3) Tier 3 [25% Distributed Primitives & Test Invariants]: Lock-free shared memory structures with multiprocessing, atomic distributed locks using Redis Redlock / etcd, robust pytest property-based testing with Hypothesis, and memory-leak profile diagnostics. Every code snippet must be fully typed, PEP 8 compliant, include comprehensive docstrings with parameter types and failure modes, and avoid deprecated Python 2 idioms, dummy mocks, or hallucinated third-party package APIs.',
    type: 'coding',
    category: 'code',
    language: 'en',
    preservedTerms: ['asyncio', 'TaskGroup', 'Pydantic v2', 'FastAPI', 'Polars', 'Apache Arrow', 'PEP 484', 'Hypothesis', 'pytest', 'Zero-Copy'],
    antiDomains: ['python 2 syntax', 'hello world boilerplate', 'hallucinated pypi apis', 'giant panda bear', 'ailuropoda melanoleuca'],
    size: 15000,
    sources: ['HuggingFace', 'GitHub', 'ArXiv'],
  },
  {
    id: 'distributed-consensus',
    title: 'Raft & Rust Consensus',
    domain: 'Distributed Systems & Formal Verification (Rust)',
    source: 'USENIX & ACM',
    prompt: 'Construct an advanced systems-engineering dataset for fault-tolerant distributed storage engines and consensus protocols implemented in Rust. Structure samples across: (1) Tier 1 [30% Protocol Transitions]: Formal Raft and Multi-Paxos consensus state machine transitions (Leader Election, Log Replication, Heartbeats) with TLA+ model checking specification invariants. (2) Tier 2 [45% Failure Scenarios]: Network partition split-brain mitigation, joint consensus cluster membership changes, write-ahead logging (WAL) crash recovery, and log compaction with asynchronous snapshotting. (3) Tier 3 [25% Lock-Free Runtime Engineering]: High-performance concurrency with Tokio async runtime, Crossbeam channels, hardware CAS atomics, and LSM-tree tiered compaction strategies under Byzantine network jitter. Code must guarantee compile-time memory safety, zero data races, explicit error handling without unwrap(), and test harnesses simulating split-brain drops.',
    type: 'coding',
    category: 'code',
    language: 'en',
    preservedTerms: ['Raft Term', 'LogCompaction', 'Tokio::select', 'CompareAndSwap', 'Linearizability', 'Byzantine Fault', 'TLA+', 'Crossbeam', 'WAL'],
    antiDomains: ['wheat rust fungus', 'puccinia', 'crop pathology', 'single threaded nodejs', 'deprecated crates', 'trivial mock code'],
    size: 15000,
    sources: ['GitHub', 'ArXiv', 'USENIX ATC'],
  },
  {
    id: 'clinical-reasoning',
    title: 'Medical Clinical Reasoning',
    domain: 'Medical Reasoning & Clinical Differential Diagnosis',
    source: 'PubMed & ACGME',
    prompt: 'Synthesize an evidence-based clinical reasoning and differential diagnosis dataset adhering to ACGME internal medicine residency diagnostic frameworks. Structure samples across: (1) Tier 1 [30% Diagnostic Panel Interpretation]: Comprehensive analysis of standard laboratory profiles (CBC with differential, comprehensive metabolic panel, arterial blood gas, cardiac biomarker troponin kinetics) in clinical context. (2) Tier 2 [45% Bayesian Probability Workup]: Iterative disease probability updating using likelihood ratios, pre-test probability, illness-script matching, and geriatric drug-drug contraindication screening via AGS Beers Criteria. (3) Tier 3 [25% Multi-Morbidity SOAP Formulations]: De-identified acute critical presentations (septic shock, acute coronary syndrome, decompensated heart failure) with ordered differential ranking, exclusion criteria, and diagnostic workup rationale grounded in AHA/ACC/IDSA guidelines. Responses must maintain clinical rigor with diagnostic rationale before treatment conclusions. Strictly exclude any real patient identifiers (HIPAA / DPDP Act 2023 compliance) and unverified dosage recommendations.',
    type: 'reasoning',
    category: 'stem',
    language: 'en',
    preservedTerms: ['Bayesian Pre-Test Probability', 'Beers Criteria', 'CBC', 'CMP', 'LFTs', 'Troponin', 'ABG', 'SOAP Note', 'ACGME'],
    antiDomains: ['real patient identifiers', 'prescriptions without disclaimers', 'unverified dosing', 'tax law', 'software bugs'],
    size: 10000,
    sources: ['PubMed', 'ArXiv', 'Zenodo'],
  },
  {
    id: 'cybersecurity-redteam',
    title: 'Zero-Day Threat Defense',
    domain: 'Offensive Security & Vulnerability Analysis',
    source: 'MITRE ATT&CK & NIST',
    prompt: 'Synthesize a rigorous cybersecurity engineering and defensive threat modeling dataset grounded in NIST CSF 2.0 and MITRE ATT&CK enterprise frameworks. Structure samples across: (1) Tier 1 [30% Vulnerability Root-Cause]: Dissecting memory-safety vulnerabilities (CWE-119 buffer overflows, CWE-416 use-after-free, CWE-362 race conditions) and cryptographic implementation flaws (nonce reuse, ECB mode, side-channel timing). (2) Tier 2 [45% Detection Engineering & Telemetry]: MITRE ATT&CK technique mapping (T1059 Command and Scripting Interpreter, T1055 Process Injection, T1021 Remote Services) with actionable Sigma and YARA detection rules grounded in OS telemetry. (3) Tier 3 [25% Zero-Trust Architectural Defense]: Cloud IAM privilege escalation modeling in AWS/Kubernetes, defense-in-depth perimeter design, and incident response playbooks for ransomware containment. Defensive and analysis focus only — never generate operational weaponized exploit code, polymorphic droppers, or active malicious C2 command payloads.',
    type: 'reasoning',
    category: 'code',
    language: 'en',
    preservedTerms: ['MITRE ATT&CK', 'NIST CSF 2.0', 'CVE', 'CWE-416', 'ASLR', 'DEP', 'Sigma Rule', 'YARA', 'Zero-Trust', 'Least Privilege'],
    antiDomains: ['operational exploit payloads', 'malware droppers', 'c2 infrastructure', 'script kiddie tutorials'],
    size: 12000,
    sources: ['NVD NIST', 'MITRE ATT&CK', 'CISA Advisories'],
  },
]

function usePromptLint(text: string) {
  const warnings: string[] = []
  const tips: Array<{ text: string; actionLabel: string; appendSnippet: string }> = []

  const len = text.trim().length
  if (len === 0) return { score: 0, warnings: [], tips: [] }

  if (len < 45) {
    warnings.push('Sparse instruction prompt: add explicit curriculum criteria or difficulty split.')
  }

  const lower = text.toLowerCase()
  const isLegal = lower.includes('tax') || lower.includes('law') || lower.includes('gst') || lower.includes('bns') || lower.includes('court')
  const hasStatute = lower.includes('section') || lower.includes('sec') || lower.includes('act') || lower.includes('circular') || lower.includes('rule')
  if (isLegal && !hasStatute) {
    tips.push({
      text: 'Ground legal reasoning in statutory provisions (e.g. Section 16(4) CGST Act or BNS 2023).',
      actionLabel: '+ Add Statutory Grounding',
      appendSnippet: ' Ground all reasoning steps in relevant statutory provisions (e.g. Section 16(4) CGST Act or BNS 2023) with zero hallucinated citations.',
    })
  }

  const isCode = lower.includes('code') || lower.includes('python') || lower.includes('rust') || lower.includes('api')
  const hasVersion = lower.includes('python 3') || lower.includes('async') || lower.includes('pydantic') || lower.includes('fastapi') || lower.includes('tokio')
  if (isCode && !hasVersion) {
    tips.push({
      text: 'Specify target language versions and frameworks (e.g. Python 3.12, Pydantic v2).',
      actionLabel: '+ Add Framework Spec',
      appendSnippet: ' Enforce Python 3.12 modern type hints, Pydantic v2 schemas, and robust pytest test cases.',
    })
  }

  const hasDifficultySplit = lower.includes('difficulty') || lower.includes('easy') || lower.includes('tiers') || lower.includes('curriculum') || lower.includes('split')
  if (!hasDifficultySplit) {
    tips.push({
      text: 'Apply a 3-tier difficulty curriculum (35% easy / 45% medium / 20% hard) for balanced training.',
      actionLabel: '+ Add Curriculum Split',
      appendSnippet: ' Apply a 3-tier difficulty curriculum: (easy) definitional lookups; (medium) multi-variable reconciliation; (hard) adversarial edge cases.',
    })
  }

  let score = 50
  if (len >= 60) score += 20
  if (hasStatute || hasVersion) score += 15
  if (hasDifficultySplit) score += 15
  score = Math.min(100, score)

  return { score, warnings, tips }
}

function StudioContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [prompt, setPrompt] = useState(
    searchParams.get('prompt') ||
    'Synthesize 10,000 multi-turn instruction dialogues from AI Kosh tax rulings & GST statutes with self-correction'
  )
  const promptLint = usePromptLint(prompt)
  const [targetDomain, setTargetDomain] = useState(
    searchParams.get('domain') || 'Finance & Taxation (AI Kosh)'
  )
  const [datasetType, setDatasetType] = useState('sft')
  const [synthesisMode, setSynthesisMode] = useState(
    searchParams.get('engine') || 'standard'
  )
  const [instructionFormat, setInstructionFormat] = useState('alpaca')
  const [language, setLanguage] = useState(searchParams.get('language') || 'en')
  const [customLanguage, setCustomLanguage] = useState('')
  const [isCustomLang, setIsCustomLang] = useState(false)
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
  const [antiDomainsInput, setAntiDomainsInput] = useState<string>('glutathione, s-transferase, nrf2, uzbekistan, irs 45q, arteriovenous fistula')
  const [parallelBilingual, setParallelBilingual] = useState<boolean>(false)
  const [datasetSize, setDatasetSize] = useState(10000)
  const [generationMode, setGenerationMode] = useState<'grounded' | 'synthetic'>('grounded')
  const [humanReview, setHumanReview] = useState<boolean>(true)
  const [llmReview, setLlmReview] = useState<boolean>(true)
  const [requireCitations, setRequireCitations] = useState<boolean>(true)
  const [humanReviewPercentage, setHumanReviewPercentage] = useState<number>(10)
  const [prioritizeAiKosh, setPrioritizeAiKosh] = useState<boolean>(true)
  const [isZenMode, setIsZenMode] = useState<boolean>(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isAutoDetecting, setIsAutoDetecting] = useState(false)
  const [discoveredSources, setDiscoveredSources] = useState<Array<{ name: string; url?: string; source_type?: string }>>([])
  const [autoDetectNotice, setAutoDetectNotice] = useState<string | null>(null)
  const [coverageMatrix, setCoverageMatrix] = useState<{ dimensions?: Record<string, any>; cells?: Array<Record<string, any>>; total_cells?: number } | null>(null)
  const [activePreset, setActivePreset] = useState<string>('aikosh-tax')
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'indic' | 'code' | 'stem'>('all')
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
    let mergedTerms = Array.from(new Set([...currentList, ...localTerms]))

    try {
      let agentDomain = targetDomain
      try {
        const agentRes = await api.analyzeDomain({
          prompt: queryText,
          target_domain: targetDomain,
          language,
        })
        if (agentRes) {
          if (agentRes.domain && agentRes.domain !== 'unknown') {
            agentDomain = agentRes.domain
            setTargetDomain(agentRes.domain)
          }
          if (Array.isArray(agentRes.preserved_terms) && agentRes.preserved_terms.length > 0) {
            mergedTerms = Array.from(new Set([...mergedTerms, ...agentRes.preserved_terms]))
            setPreservedTermsInput(mergedTerms.join(', '))
          }
          if (Array.isArray(agentRes.anti_domains) && agentRes.anti_domains.length > 0) {
            setAntiDomainsInput(agentRes.anti_domains.join(', '))
          }
        }
      } catch (agentErr) {
        console.warn('Agent domain analysis fallback:', agentErr)
      }

      const previewRes = await api.previewJobSources({
        query: queryText,
        max_sources: 12,
      })

      if (previewRes) {
        const intentEntities: string[] = previewRes.query_plan?.intent?.key_entities || []
        const dynamicDomain = previewRes.query_plan?.intent?.domain
        if (dynamicDomain && (!targetDomain || targetDomain === 'Finance & Taxation (AI Kosh)')) {
          setTargetDomain(dynamicDomain)
        }

        const allTerms = Array.from(new Set([...mergedTerms, ...intentEntities]))
        setPreservedTermsInput(allTerms.join(', '))

        const intentAnti: string[] = previewRes.query_plan?.anti_domains || previewRes.query_plan?.intent?.anti_domains || []
        if (intentAnti.length > 0) {
          setAntiDomainsInput(intentAnti.join(', '))
        }

        if (Array.isArray(previewRes.sources) && previewRes.sources.length > 0) {
          setDiscoveredSources(previewRes.sources.map((s: any) => ({
            name: s.title || s.name || s.domain || 'Verified Domain Repository',
            url: s.url,
            source_type: s.source_type || 'discovery',
          })))
        }

        // Fetch execution plan and coverage matrix
        try {
          const planRes = await api.planJob({
            target_domain: agentDomain || dynamicDomain || targetDomain,
            domain: agentDomain || dynamicDomain || targetDomain,
            dataset_size: 20,
            target_size: 20,
            synthesis_mode: synthesisMode,
            language: language,
          })
          if (planRes?.coverage_matrix && planRes.coverage_matrix.cells?.length > 0) {
            setCoverageMatrix(planRes.coverage_matrix)
          }
        } catch {
          // Non-blocking for auto-detect preview
        }

        setAutoDetectNotice(
          `Agent Discovered: ${allTerms.length} invariants · ${previewRes.sources?.length || 0} authority sources`
        )
      } else {
        setPreservedTermsInput(mergedTerms.join(', '))
        setAutoDetectNotice(`Agent extracted ${mergedTerms.length} invariant terms`)
      }
    } catch {
      setPreservedTermsInput(mergedTerms.join(', '))
      setAutoDetectNotice(`Agent extracted ${mergedTerms.length} invariant terms`)
    } finally {
      setIsAutoDetecting(false)
    }
  }, [prompt, targetDomain, preservedTermsInput, language, synthesisMode, extractSyntacticInvariants])

  // Launch job
  const handleGenerate = async () => {
    playClickSound()
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

      const antiDomains = antiDomainsInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)

      const payload: Record<string, any> = {
        target_domain: prompt.trim() || targetDomain,
        dataset_name: targetDomain,
        dataset_type: datasetType,
        synthesis_mode: synthesisMode,
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
        ...(antiDomains.length > 0 ? { anti_domains: antiDomains } : {}),
        parallel_bilingual: parallelBilingual,
        dataset_size: datasetSize,
        quality_level: 'standard',
        generation_mode: generationMode === 'grounded' ? 'hybrid' : 'synthetic',
        allow_seedless_generation: true,
        require_reference_sources: requireCitations,
        enable_research_loop: true,
        human_review: humanReview,
        human_review_percentage: humanReview ? humanReviewPercentage : 0,
        human_review_mode: 'blocking',
        llm_review_enabled: llmReview,
        llm_review_sample_limit: 50,
        ...(prioritizeAiKosh ? { preferred_providers: ['ai_kosh'] } : {}),
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
            Synthetic Dataset Studio
          </h1>
          <p className="text-xs text-[#94a3b8]">
            Curate and synthesize fine-tuning datasets with automated provenance and quality validation
          </p>
        </div>

        <Button
          onClick={handleGenerate}
          disabled={isSubmitting}
          className="bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white font-mono text-xs font-bold h-9 px-5 shadow-sm glow-yc flex items-center gap-2 rounded-md self-start sm:self-auto"
        >
          {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-3.5 h-3.5 fill-current" />}
          <span>Synthesize Dataset</span>
        </Button>
      </div>

      {/* Industry Presets */}
      {!isZenMode && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-mono font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-[#f26625]" />
              Domain Curricula & Linguistic Presets
            </span>
            <span className="text-[11px] font-mono text-[#10b981]">Grounded Schemas</span>
          </div>

          {/* Facet Filter Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: 'all', label: 'All Curricula' },
              { id: 'indic', label: 'Indic Vernacular & Legal' },
              { id: 'code', label: 'Code & Distributed Systems' },
              { id: 'stem', label: 'Aerospace & Healthcare' },
            ].map((cat) => (
              <button
                key={cat.id}
                type="button"
                onClick={() => {
                  playClickSound()
                  setSelectedCategory(cat.id as any)
                }}
                className={clsx(
                  "px-3 py-1 text-xs font-mono rounded-md border transition-all cursor-pointer",
                  selectedCategory === cat.id
                    ? "bg-[#f26625]/20 text-[#f26625] border-[#f26625] font-bold shadow-sm"
                    : "bg-[#0e0e17] text-[#94a3b8] border-[#272738] hover:text-white hover:border-[#3b3b52]"
                )}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
            {INDUSTRY_PRESETS.filter(p => selectedCategory === 'all' || (p as any).category === selectedCategory).map((preset) => {
              const isSelected = activePreset === preset.id
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => {
                    playClickSound()
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
                    if ((preset as any).antiDomains) {
                      setAntiDomainsInput(((preset as any).antiDomains || []).join(', '))
                    } else {
                      setAntiDomainsInput('')
                    }
                    if ((preset as any).parallelBilingual !== undefined) {
                      setParallelBilingual(Boolean((preset as any).parallelBilingual))
                    }
                    const hasAiKosh = ((preset as any).sources || []).some((s: string) => s.toLowerCase().includes('kosh')) ||
                      (preset.source || '').toLowerCase().includes('kosh')
                    setPrioritizeAiKosh(hasAiKosh)
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
                  <h4
                    className="text-xs font-semibold text-white line-clamp-2 leading-tight min-h-[2rem]"
                    title={preset.title}
                  >
                    {preset.title}
                  </h4>
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
      )}

      {/* Main Studio Controls */}
      <ZenSpatialCanvas
        activeMode="Zen Kinetic Spatial"
        isZenMode={isZenMode}
        onZenModeChange={setIsZenMode}
      >
        {isZenMode ? (
          <div className="space-y-6 max-w-3xl mx-auto py-4">
            <div className="flex items-center justify-between border-b border-[#1c1c28] pb-4">
              <div>
                <h2 className="text-sm font-bold text-white font-mono flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#f26625]" />
                  <span>Zen Intent Synthesis Nexus</span>
                </h2>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Distraction-free spatial canvas. Secondary parameters suppressed into verified defaults.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                  {datasetSize.toLocaleString()} samples
                </span>
                <span className="text-[10px] font-mono text-[#f26625] px-2 py-0.5 rounded bg-[#f26625]/10 border border-[#f26625]/20 uppercase">
                  {synthesisMode}
                </span>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-[10px] font-mono uppercase text-zinc-400 block mb-1.5">
                  Target Domain or Corpus
                </label>
                <Input
                  value={targetDomain}
                  onChange={(e) => setTargetDomain(e.target.value)}
                  placeholder="e.g. Finance & Taxation (AI Kosh), Aerospace, Medical..."
                  className="bg-[#12121a] border-[#272738] text-white text-xs font-mono h-10"
                />
              </div>

              <div>
                <label className="text-[10px] font-mono uppercase text-zinc-400 block mb-1.5">
                  Synthesis Instruction Scope &amp; Constraints
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={6}
                  placeholder="Describe dataset instructions, schemas, statutory citations, and edge-cases..."
                  className="w-full bg-[#12121a] border border-[#272738] rounded-md p-3 text-xs font-mono text-white placeholder-zinc-500 focus:outline-none focus:border-[#f26625] transition-colors resize-none leading-relaxed"
                />
                {/* Live Prompt Heuristic Linter Strip (Zen) */}
                {prompt.trim().length > 0 && (
                  <div className="mt-2 p-2.5 rounded-md bg-[#0a0a0f] border border-[#1f1f2e] space-y-1.5 text-xs font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-[#94a3b8] uppercase font-bold flex items-center gap-1.5">
                        <ShieldCheck className="h-3.5 w-3.5 text-[#10b981]" />
                        Prompt Quality:
                        <strong className={clsx(
                          promptLint.score >= 80 ? "text-emerald-400" :
                          promptLint.score >= 60 ? "text-amber-400" : "text-rose-400"
                        )}>
                          {promptLint.score}/100
                        </strong>
                      </span>
                    </div>
                    {promptLint.warnings.map((w, idx) => (
                      <div key={idx} className="flex items-center gap-1.5 text-amber-400/90 text-[11px]">
                        <AlertCircle className="h-3 w-3 shrink-0" />
                        <span>{w}</span>
                      </div>
                    ))}
                    {promptLint.tips.map((tip, idx) => (
                      <div key={idx} className="text-[#94a3b8] text-[11px] flex items-center justify-between gap-2 bg-[#12121c] p-1.5 rounded border border-[#222232]">
                        <div className="flex items-center gap-1.5 truncate">
                          <span className="text-cyan-400 shrink-0">💡</span>
                          <span className="truncate">{tip.text}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            playClickSound()
                            setPrompt((p) => (p.trim() ? `${p.trim()} ${tip.appendSnippet.trim()}` : tip.appendSnippet.trim()))
                          }}
                          className="shrink-0 text-[10px] font-mono text-[#f26625] hover:text-white px-2 py-0.5 rounded bg-[#f26625]/10 hover:bg-[#f26625]/20 border border-[#f26625]/30 transition-all cursor-pointer"
                        >
                          {tip.actionLabel}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Synthesis Mode Switcher */}
              <div className="space-y-1.5">
                <label className="text-[10px] font-mono uppercase text-zinc-400 block">
                  Synthesis Cognitive Engine
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { id: 'standard', name: 'Standard' },
                    { id: 'cot', name: 'CoT Reasoning' },
                    { id: 'socratic', name: 'Socratic' },
                    { id: 'preference', name: 'DPO Pairs' },
                    { id: 'multi_turn', name: 'Multi-Turn' },
                    { id: 'tool_calling', name: 'Tool Calling' },
                    { id: 'contrastive', name: 'Contrastive' },
                    { id: 'rag', name: 'RAG Grounded' },
                  ].map((mode) => {
                    const isSelected = synthesisMode === mode.id
                    return (
                      <button
                        key={mode.id}
                        type="button"
                        onClick={() => {
                          playClickSound()
                          setSynthesisMode(mode.id)
                        }}
                        className={clsx(
                          'px-3 py-1.5 rounded-md text-xs font-mono transition-all',
                          isSelected
                            ? 'bg-[#f26625] text-white font-bold shadow-sm'
                            : 'bg-[#12121a] text-zinc-400 hover:text-white border border-[#272738]'
                        )}
                      >
                        {mode.name}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Execution Action */}
              <div className="pt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setIsZenMode(false)}
                  className="text-xs font-mono text-zinc-400 hover:text-white underline decoration-[#272738] text-left"
                >
                  Configure fine-grained invariants (PII, Dialect, Anchors) in Lab View →
                </button>

                <Button
                  onClick={handleGenerate}
                  disabled={isSubmitting}
                  className="bg-[#f26625] hover:bg-[#de581a] border border-[#ea580c] text-white font-mono font-bold text-xs h-10 px-6 rounded-md shadow-sm glow-yc flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-current" />
                  )}
                  <span>Launch Pipeline</span>
                </Button>
              </div>
            </div>
          </div>
        ) : (
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
              {/* Live Prompt Heuristic Linter Strip (Standard) */}
              {prompt.trim().length > 0 && (
                <div className="mt-2 p-2.5 rounded-md bg-[#0a0a0f] border border-[#1f1f2e] space-y-1.5 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-[#94a3b8] uppercase font-bold flex items-center gap-1.5">
                      <ShieldCheck className="h-3.5 w-3.5 text-[#10b981]" />
                      Prompt Specification Quality:
                      <strong className={clsx(
                        promptLint.score >= 80 ? "text-emerald-400" :
                        promptLint.score >= 60 ? "text-amber-400" : "text-rose-400"
                      )}>
                        {promptLint.score}/100
                      </strong>
                    </span>
                  </div>
                  {promptLint.warnings.map((w, idx) => (
                    <div key={idx} className="flex items-center gap-1.5 text-amber-400/90 text-[11px]">
                      <AlertCircle className="h-3 w-3 shrink-0" />
                      <span>{w}</span>
                    </div>
                  ))}
                  {promptLint.tips.map((tip, idx) => (
                    <div key={idx} className="text-[#94a3b8] text-[11px] flex items-center justify-between gap-2 bg-[#12121c] p-1.5 rounded border border-[#222232]">
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="text-cyan-400 shrink-0">💡</span>
                        <span className="truncate">{tip.text}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          playClickSound()
                          setPrompt((p) => (p.trim() ? `${p.trim()} ${tip.appendSnippet.trim()}` : tip.appendSnippet.trim()))
                        }}
                        className="shrink-0 text-[10px] font-mono text-[#f26625] hover:text-white px-2 py-0.5 rounded bg-[#f26625]/10 hover:bg-[#f26625]/20 border border-[#f26625]/30 transition-all cursor-pointer"
                      >
                        {tip.actionLabel}
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={handleAutoDetect}
                    disabled={isAutoDetecting}
                    className="h-8 px-3.5 text-xs font-mono font-bold border-[#f26625]/40 text-[#f26625] bg-[#f26625]/10 hover:bg-[#f26625]/20 rounded-md flex items-center gap-1.5 glow-yc transition-all"
                  >
                    {isAutoDetecting ? <Loader2 className="w-3.5 h-3.5 animate-spin text-[#f26625]" /> : <Bot className="w-3.5 h-3.5 text-[#f26625]" />}
                    <span>{isAutoDetecting ? 'Agent Analyzing Domain…' : 'Agent Auto-Detect'}</span>
                  </Button>
                </div>
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
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase text-[#94a3b8]">
                    Authoritative Grounding Sources ({discoveredSources.length}):
                  </span>
                  <span className="px-1.5 py-0.5 rounded-sm bg-emerald-950/60 border border-emerald-800/60 text-[9px] font-mono text-emerald-400 flex items-center gap-1">
                    <ShieldCheck className="w-3 h-3 text-emerald-400" />
                    Polysemy Filtered
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {discoveredSources.map((s, idx) => {
                    const st = (s.source_type || '').toLowerCase()
                    const typeLabel = st === 'wikipedia' ? 'Wikipedia' :
                                      st === 'books' ? 'Book' :
                                      st === 'blog' ? 'Blog' :
                                      st.includes('dataset') ? 'Dataset' :
                                      st === 'arxiv_paper' ? 'Paper' :
                                      st.includes('github') ? 'Repo' : null
                    const typeColor = st === 'wikipedia' ? 'bg-sky-950/60 border-sky-800/60 text-sky-400' :
                                      st === 'books' ? 'bg-amber-950/60 border-amber-800/60 text-amber-400' :
                                      st === 'blog' ? 'bg-indigo-950/60 border-indigo-800/60 text-indigo-400' :
                                      st.includes('dataset') ? 'bg-emerald-950/60 border-emerald-800/60 text-emerald-400' :
                                      'bg-[#161622] border-[#272738] text-zinc-400'

                    return (
                      <span
                        key={idx}
                        className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-[#0a0a0f] border border-[#272738] text-[10px] font-mono text-zinc-200 truncate max-w-[280px]"
                        title={s.name}
                      >
                        {typeLabel && (
                          <span className={`px-1 py-0.2 rounded-[2px] text-[8px] uppercase tracking-wider border font-bold ${typeColor}`}>
                            {typeLabel}
                          </span>
                        )}
                        <span className="truncate">{s.name}</span>
                      </span>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Synthetic Diversity & Topic Coverage Matrix */}
            {coverageMatrix && coverageMatrix.cells && coverageMatrix.cells.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-[#1c1c28]">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase text-[#94a3b8] flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-[#f26625]" />
                    Topic &amp; Diversity Coverage Matrix ({coverageMatrix.cells.length} cells planned)
                  </span>
                  <span className="px-1.5 py-0.5 rounded-sm bg-purple-950/60 border border-purple-800/60 text-[9px] font-mono text-purple-300">
                    Balanced Sampling Guarantee
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 max-h-48 overflow-y-auto p-2 bg-[#0a0a0f] border border-[#272738] rounded-md">
                  {coverageMatrix.cells.map((cell, idx) => (
                    <div
                      key={idx}
                      className="p-1.5 rounded bg-[#161622] border border-[#272738]/60 text-[10px] font-mono space-y-0.5 hover:border-[#f26625]/40 transition-colors"
                    >
                      {Object.entries(cell).map(([k, v]) => (
                        <div key={k} className="flex items-center justify-between text-[9px]">
                          <span className="text-[#64748b] truncate max-w-[70px]">{k}:</span>
                          <span className="text-purple-300 font-semibold truncate max-w-[90px]" title={String(v)}>
                            {String(v)}
                          </span>
                        </div>
                      ))}
                    </div>
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
                  Synthesis Engine Mode
                </label>
                <select
                  value={synthesisMode}
                  onChange={(e) => setSynthesisMode(e.target.value)}
                  className="w-full bg-[#0a0a0f] border border-[#272738] focus:border-[#f26625] rounded-md p-2 text-xs font-mono text-white focus:outline-none"
                >
                  <option value="standard">Standard SFT (Grounded &amp; Adaptive)</option>
                  <option value="cot">Chain-of-Thought (DeepSeek-R1 / &lt;thought&gt; Tags)</option>
                  <option value="socratic">Socratic Dialectic Debate (Multi-Persona Verdict)</option>
                  <option value="multi_turn">Multi-Turn Dialogue Trajectories</option>
                  <option value="simpo">SimPO Preference Optimization (Length-Normalized)</option>
                  <option value="kto">KTO Binary Utility (Prospect Theory)</option>
                  <option value="tool_calling">Tool &amp; Function Calling (OpenAI / Hermes Schema)</option>
                  <option value="contrastive">Contrastive Critique (Hallucination Perturbation)</option>
                  <option value="rag">Multi-Hop RAG (Hard Negatives &amp; Citations)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] font-mono uppercase text-[#94a3b8] block mb-1">
                  Language
                </label>
                <select
                  value={isCustomLang ? 'custom' : language}
                  onChange={(e) => {
                    if (e.target.value === 'custom') {
                      setIsCustomLang(true)
                    } else {
                      setIsCustomLang(false)
                      setLanguage(e.target.value)
                    }
                  }}
                  className="w-full bg-[#0a0a0f] border border-[#272738] focus:border-[#f26625] rounded-md p-2 text-xs font-mono text-white focus:outline-none"
                >
                  <optgroup label="Common & Multilingual">
                    <option value="en">English</option>
                    <option value="hi">Hindi (हिन्दी)</option>
                    <option value="hinglish">Hindi + English (Hinglish)</option>
                    <option value="indic_multilingual">Indic Multilingual (22 Indic Languages)</option>
                  </optgroup>
                  <optgroup label="22 Official Indian Languages (8th Schedule)">
                    <option value="as">Assamese (অসমীয়া)</option>
                    <option value="bn">Bengali (বাংলা)</option>
                    <option value="brx">Bodo (बड़ो)</option>
                    <option value="doi">Dogri (डोगरी)</option>
                    <option value="gu">Gujarati (ગુજરાતી)</option>
                    <option value="kn">Kannada (ಕನ್ನಡ)</option>
                    <option value="ks">Kashmiri (कॉशुर / کٲشُر)</option>
                    <option value="kok">Konkani (कोंकणी)</option>
                    <option value="mai">Maithili (मैथिली)</option>
                    <option value="ml">Malayalam (മലയാളം)</option>
                    <option value="mni">Manipuri / Meitei (মৈতৈলোন্)</option>
                    <option value="mr">Marathi (मराठी)</option>
                    <option value="ne">Nepali (नेपाली)</option>
                    <option value="or">Odia (ଓଡ଼ିଆ)</option>
                    <option value="pa">Punjabi (ਪੰਜਾਬੀ)</option>
                    <option value="sa">Sanskrit (संस्कृतम्)</option>
                    <option value="sat">Santali (संताली)</option>
                    <option value="sd">Sindhi (سنڌي / सिन्धी)</option>
                    <option value="ta">Tamil (தமிழ்)</option>
                    <option value="te">Telugu (తెలుగు)</option>
                    <option value="ur">Urdu (اردو)</option>
                  </optgroup>
                  <optgroup label="Major Global Languages">
                    <option value="ar">Arabic (العربية)</option>
                    <option value="zh">Chinese (中文)</option>
                    <option value="fr">French (Français)</option>
                    <option value="de">German (Deutsch)</option>
                    <option value="ja">Japanese (日本語)</option>
                    <option value="ko">Korean (한국어)</option>
                    <option value="pt">Portuguese (Português)</option>
                    <option value="ru">Russian (Русский)</option>
                    <option value="es">Spanish (Español)</option>
                  </optgroup>
                  <optgroup label="Custom Specification">
                    <option value="custom">Other / Custom Language (Type below)...</option>
                  </optgroup>
                </select>
                {isCustomLang && (
                  <input
                    type="text"
                    placeholder="Enter language code or name (e.g. sw, it, nl, Latin)..."
                    value={customLanguage}
                    onChange={(e) => {
                      setCustomLanguage(e.target.value)
                      setLanguage(e.target.value.trim().toLowerCase())
                    }}
                    className="mt-2 w-full bg-[#0a0a0f] border border-[#f26625] rounded-md p-2 text-xs font-mono text-white focus:outline-none placeholder-[#64748b]"
                  />
                )}
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
                <div className="flex items-center justify-between text-[10px] font-mono text-[#94a3b8] mt-2 p-2 rounded bg-[#0a0a0f] border border-[#1f1f2e]">
                  <span>Est. Cloud API: <strong className="text-zinc-200 font-bold">${((datasetSize / 1000) * 0.06).toFixed(2)}</strong> <span className="text-emerald-400">($0.00 Local)</span></span>
                  <span>Est. Time: <strong className="text-zinc-200 font-bold">{datasetSize <= 100 ? '~15s' : datasetSize <= 1000 ? '~1.8m' : datasetSize <= 5000 ? '~8.5m' : `~${Math.round(datasetSize / 650)}m`}</strong></span>
                </div>
              </div>

              {/* Quality & Human Review Gates */}
              <div className="pt-3 border-t border-[#1c1c28] space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono uppercase text-[#94a3b8] font-bold">
                    Pipeline Gates &amp; Sources
                  </span>
                  <span className="text-[10px] font-mono text-[#f26625]">Quality Control</span>
                </div>

                {/* HITL Review Toggle */}
                <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738] space-y-2">
                  <label className="flex items-center justify-between text-xs font-mono text-white cursor-pointer">
                    <div className="flex flex-col">
                      <span className="font-semibold text-white">Stratified HITL Review</span>
                      <span className="text-[10px] text-[#94a3b8]">
                        Pause at awaiting_review gate to inspect, edit, or reject samples
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={humanReview}
                      onChange={(e) => setHumanReview(e.target.checked)}
                      className="w-4 h-4 accent-[#f26625] cursor-pointer"
                    />
                  </label>

                  {humanReview && (
                    <div className="pt-2 border-t border-[#1c1c28] space-y-1.5">
                      <div className="flex justify-between items-center text-[10px] font-mono">
                        <span className="text-[#94a3b8]">Sampling Ratio</span>
                        <span className="text-[#f26625] font-bold">{humanReviewPercentage}% of dataset</span>
                      </div>
                      <input
                        type="range"
                        min={1}
                        max={50}
                        step={1}
                        value={humanReviewPercentage}
                        onChange={(e) => setHumanReviewPercentage(Number(e.target.value))}
                        className="w-full accent-[#f26625] bg-[#12121a] cursor-pointer"
                      />
                    </div>
                  )}
                </div>

                <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                  <label className="flex items-center justify-between text-xs font-mono text-white cursor-pointer">
                    <div className="flex flex-col">
                      <span className="font-semibold text-white">Independent LLM Jury</span>
                      <span className="text-[10px] text-[#94a3b8]">
                        Compare provider-specific reviews; disagreements are escalated to HITL
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={llmReview}
                      onChange={(e) => setLlmReview(e.target.checked)}
                      className="w-4 h-4 accent-[#f26625] cursor-pointer"
                    />
                  </label>
                </div>

                <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                  <label className="flex items-center justify-between text-xs font-mono text-white cursor-pointer">
                    <div className="flex flex-col">
                      <span className="font-semibold text-white">Require Source Evidence</span>
                      <span className="text-[10px] text-[#94a3b8]">
                        Keep only examples with a source URL, content hash, and citation span
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={requireCitations}
                      onChange={(e) => setRequireCitations(e.target.checked)}
                      className="w-4 h-4 accent-[#f26625] cursor-pointer"
                    />
                  </label>
                </div>

                {/* AI Kosh Prioritization Toggle */}
                <div className="p-2.5 rounded-md bg-[#0a0a0f] border border-[#272738]">
                  <label className="flex items-center justify-between text-xs font-mono text-white cursor-pointer">
                    <div className="flex flex-col">
                      <span className="font-semibold text-white">Prioritize AI Kosh &amp; IndiaAI</span>
                      <span className="text-[10px] text-[#94a3b8]">
                        Query Indian statutory, GST, and legal open corpora first
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={prioritizeAiKosh}
                      onChange={(e) => setPrioritizeAiKosh(e.target.checked)}
                      className="w-4 h-4 accent-[#f26625] cursor-pointer"
                    />
                  </label>
                </div>
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

                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-[10px] font-mono uppercase text-[#94a3b8] flex items-center gap-1.5">
                          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                          Anti-Domains &amp; Homonym Exclusions
                        </label>
                        <span className="text-[9px] font-mono text-emerald-400">Polysemy Guard Active</span>
                      </div>
                      <Input
                        value={antiDomainsInput}
                        onChange={(e) => setAntiDomainsInput(e.target.value)}
                        placeholder="e.g. glutathione, puccinia, uzbekistan (comma-separated)"
                        className="bg-[#0a0a0f] border-[#272738] text-xs font-mono text-white h-8"
                      />
                      <p className="text-[10px] font-mono text-[#64748b] mt-1">
                        Excludes cross-discipline collisions, foreign statutory codes, and unrelated scientific homonyms.
                      </p>
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
      )}
    </ZenSpatialCanvas>
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
