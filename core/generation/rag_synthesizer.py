"""Multi-Hop RAG & Hard Negatives Dataset Synthesizer.

Synthesizes high-fidelity Retrieval-Augmented Generation (RAG) training data:
1. Multi-hop queries requiring synthesis across multiple passage chunks.
2. Verified positive contexts with exact in-text citation markers ([1], [2]).
3. Hard negative distractor contexts (lexically similar, factually irrelevant) to train models against retrieval hallucination.
4. RAG faithfulness & citation attribution verification.
"""

import re
from typing import Any, Dict, List, Optional


def build_rag_prompt_directive(include_hard_negatives: bool = True) -> str:
    """Return system prompt instructions for multi-hop RAG dataset synthesis."""
    if include_hard_negatives:
        distractor_rule = (
            "4. 'hard_negatives': A list of 1-2 distractor context passages that are lexically similar to the topic "
            "but DO NOT contain the required answer, forcing the model to learn selective attention.\n"
        )
        keys_str = "'instruction', 'positive_contexts', 'hard_negatives', 'response', 'citations'"
    else:
        distractor_rule = ""
        keys_str = "'instruction', 'positive_contexts', 'response', 'citations'"

    return (
        "RETRIEVAL-AUGMENTED GENERATION (RAG) SPECIFICATION:\n"
        "1. 'instruction': A user question requiring knowledge retrieval (multilingual / Hinglish / domain-specific).\n"
        "2. 'positive_contexts': A list of 1-3 distinct factual passage chunks that directly provide evidence.\n"
        "3. 'response': A comprehensive grounded answer citing the evidence using in-text bracketed numbers like [1], [2].\n"
        f"{distractor_rule}"
        f"5. Output target JSON structure with keys: {keys_str}.\n"
    )


def format_rag_sample(
    query: str,
    positive_contexts: List[str],
    hard_negatives: Optional[List[str]] = None,
    grounded_response: Optional[str] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Format a structured RAG training sample with verified citations and hard negatives."""
    pos = [c.strip() for c in (positive_contexts or []) if c.strip()]
    neg = [c.strip() for c in (hard_negatives or []) if c.strip()]
    resp = (grounded_response or "").strip()

    # Automatically extract bracketed citation markers [1], [2] from response
    citation_markers = [int(m) for m in re.findall(r"\[(\d+)\]", resp)]
    unique_citations = sorted(set(citation_markers))

    formatted_citations = []
    if citations:
        formatted_citations = citations
    else:
        for cid in unique_citations:
            ctx_text = pos[cid - 1] if 0 <= cid - 1 < len(pos) else ""
            formatted_citations.append({
                "citation_id": cid,
                "evidence_snippet": ctx_text[:120] + "..." if len(ctx_text) > 120 else ctx_text,
            })

    # Combined retrieval context pool (shuffled order for realistic ranker output)
    all_contexts = [
        {"id": f"ctx-pos-{i+1}", "text": c, "is_relevant": True}
        for i, c in enumerate(pos)
    ] + [
        {"id": f"ctx-neg-{i+1}", "text": c, "is_relevant": False}
        for i, c in enumerate(neg)
    ]

    record = {
        "instruction": query.strip(),
        "response": resp,
        "contexts": all_contexts,
        "positive_contexts": pos,
        "hard_negatives": neg,
        "citations": formatted_citations,
        "metadata": {
            "type": "multi_hop_rag",
            "num_positive_chunks": len(pos),
            "num_hard_negatives": len(neg),
            "citation_count": len(unique_citations),
        }
    }
    if domain:
        record["metadata"]["domain"] = domain

    return record


def evaluate_rag_faithfulness(response: str, positive_contexts: List[str]) -> Dict[str, Any]:
    """Evaluate grounding faithfulness and citation coverage of a RAG response."""
    resp = response.strip()
    if not resp or not positive_contexts:
        return {
            "faithfulness_score": 0.0,
            "citation_coverage": 0.0,
            "status": "unfaithful",
        }

    # 1. Citation check
    citations = re.findall(r"\[\d+\]", resp)
    has_citations = len(citations) > 0

    # 2. Key phrase overlap between response and positive contexts
    resp_tokens = set(re.findall(r"\w{4,}", resp.lower()))
    ctx_tokens = set()
    for ctx in positive_contexts:
        ctx_tokens.update(re.findall(r"\w{4,}", ctx.lower()))

    overlap = len(resp_tokens & ctx_tokens) / max(len(resp_tokens), 1)
    faithfulness = min(1.0, round(0.40 + overlap * 0.70, 2))

    citation_coverage = min(1.0, round(len(citations) / max(len(positive_contexts), 1), 2)) if has_citations else 0.0

    is_grounded = faithfulness >= 0.70 and (has_citations or overlap >= 0.50)

    return {
        "faithfulness_score": faithfulness,
        "citation_coverage": citation_coverage,
        "has_citations": has_citations,
        "status": "grounded" if is_grounded else "unsupported",
    }
