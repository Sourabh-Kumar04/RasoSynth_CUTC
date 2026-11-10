"""
Indian Regulatory & Legal Gazette Document Extractor.

Specialized structured parser for:
- GST Council & CBIC circulars and notifications
- Income Tax Department statutory orders
- Press Information Bureau (PIB) press releases
- High Court / Supreme Court judgment orders
Preserves:
- Official notification / circular numbers and dates
- Statutory section references (e.g., Section 16(4) of CGST Act)
- Tabular rate / exemption schedules
- Bilingual English/Hindi parallel text sections
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RegulatoryDocument:
    circular_id: Optional[str] = None
    issuing_authority: str = "Government of India"
    date_issued: Optional[str] = None
    subject: str = ""
    summary: str = ""
    statutory_references: List[str] = field(default_factory=list)
    structured_tables: List[str] = field(default_factory=list)
    raw_markdown: str = ""
    qa_pairs: List[Dict[str, str]] = field(default_factory=list)


class IndianRegulatoryExtractor:
    """Extracts structured legal and regulatory datasets from official notifications."""

    # Regex patterns for notification references
    CIRCULAR_PATTERNS = [
        r"(?:Circular\s+No\.?|Notification\s+No\.?)\s*([0-9]+/[0-9]+(?:/[0-9]+)?(?:-[A-Za-z]+)?)",
        r"(?:F\.\s*No\.?)\s*([A-Za-z0-9/\-_]+)",
    ]

    DATE_PATTERNS = [
        r"(?:Dated|Date)\s*:?\s*(?:the\s+)?([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})",
        r"(?:Dated|Date)\s*:?\s*(?:the\s+)?([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{4})",
        r"\b([0-9]{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+[0-9]{4})\b",
    ]

    SECTION_PATTERNS = [
        r"(?:Section|sub-section)\s+([0-9]+(?:\([0-9a-zA-Z]+\))*)\s+of\s+(?:the\s+)?([A-Za-z\s]+Act(?:,\s*[0-9]{4})?)",
        r"(?:Rule)\s+([0-9]+(?:\([0-9a-zA-Z]+\))*)\s+of\s+(?:the\s+)?([A-Za-z\s]+Rules(?:,\s*[0-9]{4})?)",
    ]

    def extract(self, text: str, title: str = "") -> RegulatoryDocument:
        """Parse raw crawled legal/statutory text into structured metadata and QA pairs."""
        doc = RegulatoryDocument()

        # 1. Circular / Notification number
        for pattern in self.CIRCULAR_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                doc.circular_id = m.group(1).strip()
                break

        # 2. Date
        for pattern in self.DATE_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                doc.date_issued = m.group(1).strip()
                break

        # 3. Issuing Authority identification
        if "Central Board of Indirect Taxes" in text or "CBIC" in text:
            doc.issuing_authority = "Central Board of Indirect Taxes and Customs (CBIC)"
        elif "Central Board of Direct Taxes" in text or "CBDT" in text:
            doc.issuing_authority = "Central Board of Direct Taxes (CBDT)"
        elif "Reserve Bank of India" in text or "RBI" in text:
            doc.issuing_authority = "Reserve Bank of India (RBI)"
        elif "Ministry of Corporate Affairs" in text or "MCA" in text:
            doc.issuing_authority = "Ministry of Corporate Affairs (MCA)"

        # 4. Extract subject line
        subject_match = re.search(r"(?:Subject|Sub):\s*(.+?)(?:\n\n|\n[A-Z0-9]|\.)", text, re.DOTALL | re.IGNORECASE)
        if subject_match:
            doc.subject = subject_match.group(1).strip().replace("\n", " ")
        elif title:
            doc.subject = title

        # 5. Extract statutory section references
        seen_refs = set()
        for pattern in self.SECTION_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                ref_str = f"Section {m.group(1)} of {m.group(2).strip()}"
                if ref_str not in seen_refs:
                    seen_refs.add(ref_str)
                    doc.statutory_references.append(ref_str)

        # 6. Synthesize domain instruction-response pairs
        if doc.subject:
            prompt = f"What is the statutory objective and administrative scope of {doc.circular_id or 'the notification'} on '{doc.subject}' issued by {doc.issuing_authority}?"
            response = (
                f"{doc.issuing_authority} issued {doc.circular_id or 'statutory guidance'} regarding {doc.subject}. "
                + (f"Governing provisions include: {', '.join(doc.statutory_references[:3])}. " if doc.statutory_references else "")
                + "The directive clarifies compliance criteria, filing obligations, and statutory procedures under Indian law."
            )
            doc.qa_pairs.append({
                "instruction": prompt,
                "response": response,
                "metadata": {
                    "circular_id": doc.circular_id,
                    "authority": doc.issuing_authority,
                    "date": doc.date_issued,
                    "sections": doc.statutory_references,
                }
            })

        doc.raw_markdown = text
        return doc
