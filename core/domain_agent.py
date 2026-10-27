"""Semantic Discovery Agent for Domain, Syntactic Invariants, and Polysemy Anti-Domains.

Provides autonomous ontology extraction for synthetic dataset design:
- Target Domain refinement and disambiguation
- Syntactic Invariants (Preserved Terms: legal sections, formulas, symbols, acronyms)
- Polysemy Anti-Domains (homonym collision mitigation, cross-discipline traps)
- Curriculum topics & difficulty hierarchy (easy/medium/hard split)
"""
import hashlib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set

from core.discipline_matrix import (
    Discipline,
    detect_discipline,
    get_polysemy_anti_domains,
)
from core.intent_extractor import extract_intent
from core.provider_router import ProviderRouter, TaskType

logger = logging.getLogger(__name__)

DOMAIN_AGENT_SYSTEM_PROMPT = """You are an elite AI Dataset Architect & Ontologist Agent.
Your job is to analyze a dataset prompt/goal and discover:
1. "domain": Precise canonical domain title (e.g. "Indian Taxation & GST Compliance", "Aerospace Engineering & Fluid Dynamics", "Distributed Systems & Raft Consensus").
2. "primary_task": One of: "supervised_fine_tuning" | "chain_of_thought_reasoning" | "dpo_preference_alignment" | "socratic_dialogue" | "tool_calling" | "multilingual_sft".
3. "preserved_terms": Array of domain-critical invariant strings that must NEVER be altered, transliterated, or translated.
   - Include statutory sections (e.g. "Section 16(4)", "Sec. 194Q", "FAR Part 25", "BNS 2023").
   - Include mathematical/engineering notations (e.g. "Mach 0.82", "Navier-Stokes", "L/D", "O(n log n)").
   - Include library primitives & protocols (e.g. "Tokio::select", "Pydantic v2", "Raft Term", "LogCompaction").
   - Include clinical criteria & panels (e.g. "Beers Criteria", "CBC", "Troponin", "ABG").
   - 4 to 12 high-precision invariants.
4. "anti_domains": Array of polysemy collisions, false homonyms, and incompatible jurisdictions/disciplines to strictly exclude.
   - For GST: ["glutathione", "s-transferase", "nrf2", "uzbekistan", "irs section 45q", "arteriovenous fistula"]
   - For Rust: ["wheat rust fungus", "puccinia", "crop pathology", "iron oxidation", "corrosion metallurgy"]
   - For Pandas: ["giant panda bear", "ailuropoda melanoleuca", "wildlife sanctuary", "bamboo forest"]
   - 5 to 15 items in lowercase.
5. "curriculum_topics": 3 to 6 structured topics representing the curriculum progression.
6. "difficulty_split": {"easy": 35, "medium": 45, "hard": 20} (percentages summing to 100).
7. "refined_prompt": Enhanced domain specification formatted strictly using the Universal Enterprise Prompt Framework (4-Pillar Spec):
    [DOMAIN & OPERATIONAL SCENARIO]
    <Substantive subject matter, regulatory context, or technical scope>

    [CURRICULUM HIERARCHY & DIFFICULTY DISTRIBUTION]
    - Tier 1 (30-35% Factual Grounding): Exact definitions, statutory/protocol citations, and baseline formulas. Zero speculative extrapolation.
    - Tier 2 (45-50% Multi-Hop Reconciliation): Multi-variable problem solving, conflicting inputs, cross-referencing disparate statutes/APIs, and step-by-step arithmetic or logical proofs.
    - Tier 3 (20-25% Adversarial & Boundary Stress-Testing): Incomplete records, contradictory facts, high-risk edge cases requiring explicit refusal, calibrated caveats, or appeal strategy.

    [STRUCTURAL INVARIANTS]
    Require exact citations to authoritative primary sources. Preserve technical tokens verbatim.

    [ANTI-DOMAIN BOUNDARIES]
    Strictly exclude homonym collisions, foreign/irrelevant jurisdictions, deprecated versions, toy boilerplate, and unsubstantiated claims.
    (Do NOT force SFT, CoT, or specific format labels into the prompt text, ensuring the user can freely choose any synthesis engine).
8. "confidence": Float between 0.0 and 1.0.

Return ONLY a valid JSON object. No preamble, no markdown code fence, no postscript.
"""

# Compiled patterns with case sensitivity where appropriate
_STATUTE_PATTERN = re.compile(r'\b(?:Section|Sec\.|FAR\s*Part|FAR|Article|Rule|Order|Clause|NACA|ISO|IEEE|RFC|PEP)\s*(?:§\s*)?[A-Za-z0-9\(\)\.\-]+', re.IGNORECASE)
_FORMULA_PATTERN = re.compile(r'\b(?:O\([A-Za-z0-9\s\+\*\^\(\)nlog]+\)|Mach\s*\d+(?:\.\d+)?|L\/D|PK\/PD|Navier-Stokes|Reynolds|Brayton\s*cycle)\b', re.IGNORECASE)
_SYSTEM_PATTERN = re.compile(r'\b(?:[A-Za-z0-9_]+::[A-Za-z0-9_]+|Pydantic(?:\s*v\d+)?|FastAPI|Polars|Apache\s*Arrow|PyTorch|Tokio|asyncio|Crossbeam|LSM-tree|WAL|TLA\+)\b', re.IGNORECASE)
_MEDICAL_PATTERN = re.compile(r'\b(?:Beers\s*Criteria|CBC|CMP|LFTs?|Troponin|ABG|SOAP\s*note|Bayesian\s*Pre-Test)\b', re.IGNORECASE)
_ACRONYM_PATTERN = re.compile(r'\b[A-Z]{2,6}(?:-[A-Z0-9]+)?\b')  # STRICT uppercase only
_QUOTED_PATTERN = re.compile(r'["\']([^"\']{2,40})["\']')

_COMMON_STOP_WORDS: Set[str] = {
    'AND', 'THE', 'FOR', 'ARE', 'NOT', 'BUT', 'ALL', 'NEW', 'SET', 'OUT',
    'CAN', 'GET', 'USE', 'HOW', 'WHY', 'WHO', 'YES', 'NO', 'ANY', 'OUR',
    'HAS', 'HAD', 'HAVE', 'WITH', 'FROM', 'THIS', 'THAT', 'THEY', 'THEM',
    'WHAT', 'WHEN', 'WHERE', 'WHICH', 'WILL', 'WOULD', 'COULD', 'SHOULD',
    'INTO', 'OVER', 'THEN', 'SOME', 'SUCH', 'THAN', 'EACH', 'VERY', 'MORE',
    'MOST', 'BEEN', 'BEING', 'DOES', 'DID', 'DONE', 'ONLY', 'EVEN', 'ALSO',
}


def extract_syntactic_invariants_regex(text: str) -> List[str]:
    """Extract syntactic domain invariants, technical symbols, and statutory citations via regex."""
    if not text:
        return []

    found: Set[str] = set()

    for pattern in [_STATUTE_PATTERN, _FORMULA_PATTERN, _SYSTEM_PATTERN, _MEDICAL_PATTERN]:
        for m in pattern.findall(text):
            clean = m.strip()
            if len(clean) >= 2 and clean.upper() not in _COMMON_STOP_WORDS:
                found.add(clean)

    # Acronyms (case-sensitive)
    for m in _ACRONYM_PATTERN.findall(text):
        clean = m.strip()
        if clean not in _COMMON_STOP_WORDS and len(clean) >= 2:
            found.add(clean)

    # Quoted terms
    for q in _QUOTED_PATTERN.findall(text):
        clean = q.strip()
        if clean and clean.upper() not in _COMMON_STOP_WORDS and len(clean) >= 2:
            found.add(clean)

    return sorted(list(found), key=lambda x: (len(x), x))


def heuristic_domain_refinement(prompt: str, target_domain: Optional[str] = None) -> Dict[str, Any]:
    """Deterministic fallback analysis when LLM is unavailable or offline."""
    combined = f"{target_domain or ''} {prompt}".strip()
    lower = combined.lower()

    invariants = extract_syntactic_invariants_regex(combined)
    poly_anti = get_polysemy_anti_domains(target_domain or prompt, raw_input=prompt)

    # Detect domain classification
    if any(k in lower for k in ["tax", "gst", "cgst", "sgst", "itat", "16(4)", "itc", "gstr"]):
        domain = "Finance & Taxation (Indian GST & Tax Compliance)"
        primary_task = "supervised_fine_tuning"
        topics = [
            "GST Input Tax Credit reconciliation under Section 16(4)",
            "GSTR-2B vs purchase-register discrepancy audits",
            "TDS/TCS deduction compliance under Section 194Q",
            "ITAT appellate reasoning & statutory interpretation",
        ]
        invariants.extend(["Section 16(4)", "ITC", "GSTR-3B", "GSTR-2B", "CGST Act", "Section 194Q"])
    elif any(k in lower for k in ["bns", "bhartiya nyaya", "ipc", "crpc", "bail", "high court", "supreme court", "legal"]):
        domain = "Indian Law & Constitutional Jurisprudence (BNS 2023)"
        primary_task = "chain_of_thought_reasoning"
        topics = [
            "IPC to BNS statutory transition cross-mapping",
            "Bail jurisprudence and custody timelines under BNSS Section 479",
            "Electronic evidence certification under Section 61 BSA",
            "Appellate legal drafting grounded in Supreme Court precedents",
        ]
        invariants.extend(["BNS 2023", "Section 479 BNSS", "BSA Section 61", "Ratio Decidendi"])
    elif any(k in lower for k in ["airfoil", "aerospace", "mach", "navier-stokes", "aerodynamic", "far part 25"]):
        domain = "Aerospace Engineering & Computational Aerodynamics"
        primary_task = "chain_of_thought_reasoning"
        topics = [
            "Transonic supercritical airfoil profile optimization",
            "Navier-Stokes turbulent boundary layer analysis",
            "FAA FAR Part 25 transport category airworthiness certification",
            "Compressible flow shock-wave boundary-layer interactions",
        ]
        invariants.extend(["NACA 0012", "Mach 0.82", "FAR §25.107", "Supercritical Airfoil", "L/D"])
    elif any(k in lower for k in ["raft", "paxos", "tokio", "consensus", "distributed", "concurrency", "rust"]):
        domain = "Distributed Systems & Formal Verification (Rust)"
        primary_task = "coding"
        topics = [
            "Raft consensus term election & split-brain prevention",
            "Asynchronous write-ahead logging (WAL) & log compaction",
            "Lock-free concurrency with Tokio and atomics",
            "TLA+ model checking specification & validation",
        ]
        invariants.extend(["Raft Term", "LogCompaction", "Tokio::select", "CompareAndSwap", "Linearizability"])
    elif any(k in lower for k in ["clinical", "medical", "patient", "diagnosis", "differential", "beers", "troponin"]):
        domain = "Medical Reasoning & Clinical Differential Diagnosis"
        primary_task = "chain_of_thought_reasoning"
        topics = [
            "Bayesian pre-test probability differential ranking",
            "Multi-panel diagnostic interpretation (CBC, CMP, LFTs, troponin)",
            "Geriatric pharmacotherapy & Beers Criteria contraindications",
            "Complex SOAP clinical note synthesis",
        ]
        invariants.extend(["Bayesian Pre-Test Probability", "Beers Criteria", "CBC", "CMP", "Troponin", "ABG"])
    elif any(k in lower for k in ["python", "asyncio", "pydantic", "fastapi", "polars"]):
        domain = "Production Python Software Engineering & Architecture"
        primary_task = "coding"
        topics = [
            "Asyncio concurrency patterns & structured task groups",
            "Pydantic v2 schema validation & high-throughput serialization",
            "Polars & Apache Arrow zero-copy data transformations",
            "Robust pytest test suite with property-based invariants",
        ]
        invariants.extend(["asyncio", "Pydantic v2", "FastAPI", "Polars", "Apache Arrow", "PEP 484", "pytest"])
    elif any(k in lower for k in ["bhashini", "indic", "hindi", "tamil", "telugu", "multilingual"]):
        domain = "Indic Multilingual Natural Language Processing"
        primary_task = "multilingual_sft"
        topics = [
            "Parallel semantic equivalence across Devanagari, Tamil, and Telugu",
            "Citizen-centric e-governance service navigation dialogues",
            "Primary healthcare symptom triage with cultural nuances",
            "Formal and colloquial register preservation",
        ]
        invariants.extend(["Bhashini", "Devanagari", "Tamil", "Telugu", "Script Preservation"])
    else:
        domain = target_domain or (prompt[:50] if len(prompt) <= 50 else prompt[:47] + "...")
        primary_task = "supervised_fine_tuning"
        topics = [
            f"{domain} fundamental principles and definitions",
            f"{domain} applied multi-step problem solving",
            f"{domain} advanced boundary conditions and edge cases",
        ]

    # Deduplicate and sort
    invariants = list(dict.fromkeys([inv.strip() for inv in invariants if inv.strip()]))
    poly_anti = list(dict.fromkeys([a.strip().lower() for a in poly_anti if a.strip()]))

    inv_summary = ", ".join(invariants[:6]) if invariants else "exact technical tokens"
    anti_summary = ", ".join(poly_anti[:6]) if poly_anti else "homonym collisions"

    four_pillar_prompt = f"""[DOMAIN & OPERATIONAL SCENARIO]
{prompt or domain}

[CURRICULUM HIERARCHY & DIFFICULTY DISTRIBUTION]
- Tier 1 (30-35% Factual Grounding): Exact definitions, statutory/protocol citations, and baseline formulas. Zero speculative extrapolation.
- Tier 2 (45-50% Multi-Hop Reconciliation): Multi-variable problem solving, conflicting inputs, cross-referencing disparate statutes/APIs, and step-by-step arithmetic or logical proofs.
- Tier 3 (20-25% Adversarial & Boundary Stress-Testing): Incomplete records, contradictory facts, high-risk edge cases requiring explicit refusal, calibrated caveats, or appeal strategy.

[STRUCTURAL INVARIANTS]
Require exact citations to authoritative primary sources. Preserve technical tokens verbatim: {inv_summary}.

[ANTI-DOMAIN BOUNDARIES]
Strictly exclude homonym collisions, foreign/irrelevant jurisdictions, deprecated versions, toy boilerplate, and unsubstantiated claims: {anti_summary}."""

    return {
        "domain": domain,
        "primary_task": primary_task,
        "modality": "text",
        "preserved_terms": invariants[:15],
        "anti_domains": poly_anti[:20],
        "curriculum_topics": topics,
        "difficulty_split": {"easy": 35, "medium": 45, "hard": 20},
        "refined_prompt": four_pillar_prompt,
        "confidence": 0.85,
    }


async def analyze_dataset_domain(
    prompt: str,
    target_domain: Optional[str] = None,
    provider_router: Optional[ProviderRouter] = None,
    redis_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Autonomous Semantic Discovery Agent:
    Discovers targetDomain, preservedTerms, antiDomains, and curriculum structure
    from raw user prompt / target domain using LLM routing or deterministic fallback.
    """
    clean_prompt = prompt.strip() if prompt else ""
    clean_domain = target_domain.strip() if target_domain else ""
    input_text = f"Target Domain: {clean_domain}\nPrompt: {clean_prompt}" if clean_domain else clean_prompt

    if not input_text:
        return heuristic_domain_refinement("", "")

    cache_key = f"domain_agent:{hashlib.sha256(input_text.encode('utf-8')).hexdigest()}"

    # Cache lookup
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.info("Semantic Domain Agent cache hit for: %s", input_text[:60])
                return json.loads(cached)
        except Exception as e:
            logger.warning("Redis cache read failed (non-fatal): %s", e)

    # Fast heuristic baseline
    baseline = heuristic_domain_refinement(clean_prompt, clean_domain)

    # If provider router is available, prompt the LLM agent
    if provider_router:
        try:
            llm_res = await provider_router.route(
                task=TaskType.TEXT_GENERATION,
                prompt=f"Analyze this dataset generation requirement:\n{input_text}",
                system_prompt=DOMAIN_AGENT_SYSTEM_PROMPT,
                temperature=0.0,
                max_tokens=1500,
                response_format={"type": "json_object"},
                reasoning_effort="low",
            )
            if llm_res and llm_res.content:
                text = llm_res.content.strip()
                # Clean JSON fences if present
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\n?", "", text)
                    text = re.sub(r"\n?```$", "", text)
                parsed = json.loads(text)

                # Merge LLM discoveries with deterministic invariants and polysemy matrix
                domain = parsed.get("domain") or baseline["domain"]
                primary_task = parsed.get("primary_task") or baseline["primary_task"]

                llm_terms = parsed.get("preserved_terms") or []
                all_invariants = list(dict.fromkeys(
                    [t.strip() for t in (llm_terms + baseline["preserved_terms"]) if t.strip()]
                ))

                llm_anti = [a.lower().strip() for a in parsed.get("anti_domains") or []]
                matrix_anti = get_polysemy_anti_domains(domain, raw_input=clean_prompt)
                all_anti = list(dict.fromkeys(
                    [a for a in (llm_anti + matrix_anti + baseline["anti_domains"]) if a]
                ))

                curriculum = parsed.get("curriculum_topics") or baseline["curriculum_topics"]
                diff = parsed.get("difficulty_split") or baseline["difficulty_split"]
                refined_prompt = parsed.get("refined_prompt") or baseline["refined_prompt"]
                confidence = float(parsed.get("confidence", 0.95))

                result = {
                    "domain": domain,
                    "primary_task": primary_task,
                    "modality": parsed.get("modality", "text"),
                    "preserved_terms": all_invariants[:15],
                    "anti_domains": all_anti[:25],
                    "curriculum_topics": curriculum,
                    "difficulty_split": diff,
                    "refined_prompt": refined_prompt,
                    "confidence": confidence,
                }

                # Cache write
                if redis_client:
                    try:
                        await redis_client.set(cache_key, json.dumps(result), ex=7200)
                    except Exception:
                        pass

                return result
        except Exception as exc:
            logger.warning("Domain Agent LLM routing failed: %s; falling back to heuristic matrix.", exc)

    # Return baseline heuristic
    return baseline
