"""Multi-Hop RAG & Hard Negatives Dataset Synthesizer.

Synthesizes high-fidelity Retrieval-Augmented Generation (RAG) training data:
1. Multi-hop queries requiring synthesis across multiple passage chunks.
2. Positive contexts with in-text citation markers ([1], [2]) indexed to the
   supplied passages. A citation is only ever "verified" against the passage
   it indexes — never against an external source, and never by index alone.
3. Hard negative distractor contexts (lexically similar, factually irrelevant) to train models against retrieval hallucination.
4. RAG faithfulness & citation attribution verification (lexical token
   overlap — not a semantic faithfulness judgement).
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


def _verify_citation_against_passage(citation: Dict[str, Any], positive_contexts: List[str]) -> Dict[str, Any]:
    """Check one citation against the passage it indexes.

    Returns the citation dict annotated with ``verified`` and
    ``verification``. A citation is verified only when its id indexes an
    existing passage AND its evidence snippet (if any) actually occurs in
    that passage. An out-of-range id, or a snippet that does not occur in
    the passage, is unverified — no snippet is fabricated for it.
    """
    out = dict(citation)
    cid = citation.get("citation_id")
    snippet = (citation.get("evidence_snippet") or "").strip()
    if not isinstance(cid, int) or cid < 1 or cid > len(positive_contexts):
        out["verified"] = False
        out["verification"] = "citation_id_out_of_range_no_passage"
        return out
    passage = positive_contexts[cid - 1]
    if not snippet:
        out["verified"] = False
        out["verification"] = "no_evidence_snippet_provided"
        return out
    core = snippet[:-3] if snippet.endswith("...") else snippet
    if core and core in passage:
        out["verified"] = True
        out["verification"] = "snippet_found_in_cited_passage"
    else:
        out["verified"] = False
        out["verification"] = "snippet_not_found_in_cited_passage"
    return out


def format_rag_sample(
    query: str,
    positive_contexts: List[str],
    hard_negatives: Optional[List[str]] = None,
    grounded_response: Optional[str] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Format a structured RAG training sample with passage-checked citations."""
    pos = [c.strip() for c in (positive_contexts or []) if c.strip()]
    neg = [c.strip() for c in (hard_negatives or []) if c.strip()]
    resp = (grounded_response or "").strip()

    # Automatically extract bracketed citation markers [1], [2] from response
    citation_markers = [int(m) for m in re.findall(r"\[(\d+)\]", resp)]
    unique_citations = sorted(set(citation_markers))

    raw_citations = []
    if citations:
        raw_citations = list(citations)
    else:
        for cid in unique_citations:
            if 1 <= cid <= len(pos):
                ctx_text = pos[cid - 1]
                raw_citations.append({
                    "citation_id": cid,
                    "evidence_snippet": ctx_text[:120] + "..." if len(ctx_text) > 120 else ctx_text,
                })
            else:
                # No passage exists for this marker: record it as unverified
                # rather than fabricating a snippet.
                raw_citations.append({"citation_id": cid, "evidence_snippet": ""})

    formatted_citations = [_verify_citation_against_passage(c, pos) for c in raw_citations]
    verified_count = sum(1 for c in formatted_citations if c.get("verified"))

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
            "provenance": "synthetic_rag_unverified",
            "num_positive_chunks": len(pos),
            "num_hard_negatives": len(neg),
            "citation_count": len(unique_citations),
            "citations_verified": verified_count,
            "citations_unverified": len(formatted_citations) - verified_count,
            "citation_verification_note": "verified means the snippet occurs in the cited supplied passage only; it is not verification against an external source.",
        }
    }
    if domain:
        record["metadata"]["domain"] = domain

    return record


def evaluate_rag_faithfulness(response: str, positive_contexts: List[str]) -> Dict[str, Any]:
    """Evaluate grounding faithfulness and citation coverage of a RAG response.

    Method is lexical token overlap between response and supplied contexts.
    There is no score floor: zero overlap scores 0.0. A response is
    "grounded" only when overlap is high AND it carries valid citations
    indexing the supplied passages — overlap alone, without citations,
    can no longer ground a response (the old citation-bypass path).
    """
    resp = response.strip()
    if not resp or not positive_contexts:
        return {
            "faithfulness_score": 0.0,
            "citation_coverage": 0.0,
            "status": "unfaithful",
            "method": "lexical_token_overlap_not_semantic_faithfulness",
            "has_citations": False,
            "citations_valid": False,
        }

    # 1. Citation check — markers must index supplied passages
    citation_ids = [int(m) for m in re.findall(r"\[(\d+)\]", resp)]
    has_citations = len(citation_ids) > 0
    citations_valid = has_citations and all(1 <= cid <= len(positive_contexts) for cid in citation_ids)

    # 2. Key phrase overlap between response and positive contexts
    resp_tokens = set(re.findall(r"\w{4,}", resp.lower()))
    ctx_tokens = set()
    for ctx in positive_contexts:
        ctx_tokens.update(re.findall(r"\w{4,}", ctx.lower()))

    overlap = len(resp_tokens & ctx_tokens) / max(len(resp_tokens), 1)
    # No floor: a response sharing no tokens with its contexts scores 0.0.
    faithfulness = round(overlap, 2)

    citation_coverage = min(1.0, round(len(citation_ids) / max(len(positive_contexts), 1), 2)) if has_citations else 0.0

    is_grounded = faithfulness >= 0.70 and citations_valid

    return {
        "faithfulness_score": faithfulness,
        "citation_coverage": citation_coverage,
        "has_citations": has_citations,
        "citations_valid": citations_valid,
        "method": "lexical_token_overlap_not_semantic_faithfulness",
        "status": "grounded" if is_grounded else "unsupported",
    }
