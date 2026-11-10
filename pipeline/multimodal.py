"""Multimodal Document & Table Extraction Pipeline.

Extracts structured tables, financial schedules, and statutory gazettes from PDF
documents, converting visual grid layouts into standardized Markdown and
Vision-Language instruction pairs (for Qwen2-VL, Llama-3.2-Vision, etc.).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTable:
    title: str
    headers: List[str]
    rows: List[List[str]]
    page_number: int = 1
    confidence: float = 0.95
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render table to Github-flavored Markdown table format."""
        if not self.headers and not self.rows:
            return ""
        cols = max(len(self.headers), max((len(r) for r in self.rows), default=0))
        h = self.headers + [""] * (cols - len(self.headers))
        header_line = "| " + " | ".join(h) + " |"
        sep_line = "| " + " | ".join(["---"] * cols) + " |"

        row_lines = []
        for row in self.rows:
            r = row + [""] * (cols - len(row))
            clean_cells = [c.replace("\n", " ").strip() for c in r]
            row_lines.append("| " + " | ".join(clean_cells) + " |")

        title_block = f"### {self.title}\n" if self.title else ""
        return f"{title_block}{header_line}\n{sep_line}\n" + "\n".join(row_lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "headers": self.headers,
            "rows": self.rows,
            "page_number": self.page_number,
            "confidence": self.confidence,
            "markdown": self.to_markdown(),
            "metadata": self.metadata,
        }


class MultimodalDocumentExtractor:
    """Extracts tables, layouts, and generates visual instruction-tuning pairs."""

    @classmethod
    def parse_text_table_grid(cls, text: str, title: str = "Document Table") -> List[ExtractedTable]:
        """Heuristic tabular grid parser for structured text/markdown extracts."""
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if len(lines) < 2:
            return []

        # Check if text already contains pipe delimited table
        pipe_lines = [l for l in lines if "|" in l]
        if len(pipe_lines) >= 2:
            # Parse pipe table
            raw_header = [c.strip() for c in pipe_lines[0].split("|") if c.strip()]
            data_rows = []
            for l in pipe_lines[1:]:
                if "---" in l:
                    continue
                cells = [c.strip() for c in l.split("|") if c.strip()]
                if cells:
                    data_rows.append(cells)
            if raw_header and data_rows:
                return [ExtractedTable(title=title, headers=raw_header, rows=data_rows)]

        # Tab or multi-space column parser
        split_pattern = re.compile(r"\t+|\s{2,}")
        parsed_rows = [split_pattern.split(l) for l in lines]
        valid_rows = [r for r in parsed_rows if len(r) >= 2]
        if len(valid_rows) >= 2:
            headers = valid_rows[0]
            rows = valid_rows[1:]
            return [ExtractedTable(title=title, headers=headers, rows=rows)]

        return []

    @classmethod
    def extract_from_pdf_path(cls, pdf_path: str | Path) -> List[ExtractedTable]:
        """Extract tables from PDF file using pdfplumber/pypdfium2 if available, with robust fallback."""
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF document not found: {pdf_path}")

        extracted: List[ExtractedTable] = []
        try:
            import pdfplumber  # type: ignore

            with pdfplumber.open(path) as pdf:
                for page_idx, page in enumerate(pdf.pages, 1):
                    tables = page.extract_tables()
                    for t_idx, raw_t in enumerate(tables):
                        if raw_t and len(raw_t) >= 2:
                            headers = [str(c or "").strip() for c in raw_t[0]]
                            rows = [[str(c or "").strip() for c in r] for r in raw_t[1:]]
                            extracted.append(
                                ExtractedTable(
                                    title=f"Page {page_idx} Table {t_idx + 1}",
                                    headers=headers,
                                    rows=rows,
                                    page_number=page_idx,
                                )
                            )
        except ImportError:
            # Fallback to reading text content
            text_content = ""
            try:
                import pypdfium2  # type: ignore

                pdf = pypdfium2.PdfDocument(path)
                text_content = "\n".join(page.get_textpage().get_text_range() for page in pdf)
            except Exception:
                text_content = path.read_text(encoding="utf-8", errors="ignore")

            tables = cls.parse_text_table_grid(text_content, title=path.stem)
            extracted.extend(tables)

        return extracted

    @classmethod
    def synthesize_vision_qa_pairs(
        cls,
        table: ExtractedTable,
        domain: str = "taxation",
    ) -> List[Dict[str, Any]]:
        """Transform structured table extract into QA instruction tuning pairs."""
        md = table.to_markdown()
        pairs = []

        if table.headers and table.rows:
            # Pair 1: Column lookup & aggregation
            target_col = table.headers[0] if table.headers else "Entity"
            target_val = table.rows[0][0] if table.rows[0] else "Default"
            prompt_1 = f"Based on the following {domain} data table, what details correspond to '{target_val}'?"
            row_summary = ", ".join(f"{h}: {v}" for h, v in zip(table.headers, table.rows[0]))
            response_1 = f"According to the table, the record for '{target_val}' indicates: {row_summary}."

            pairs.append({
                "instruction": prompt_1,
                "table_markdown": md,
                "response": response_1,
                "modality": "multimodal_table",
                "metadata": {"title": table.title, "page": table.page_number, "domain": domain},
            })

            # Pair 2: Summary and structural interpretation
            prompt_2 = f"Summarize the primary statutory or quantitative metrics presented in table '{table.title}'."
            response_2 = (
                f"The table presents structured {domain} records with {len(table.rows)} rows across "
                f"{len(table.headers)} dimensions: {', '.join(table.headers)}."
            )
            pairs.append({
                "instruction": prompt_2,
                "table_markdown": md,
                "response": response_2,
                "modality": "multimodal_table",
                "metadata": {"title": table.title, "page": table.page_number, "domain": domain},
            })

        return pairs
