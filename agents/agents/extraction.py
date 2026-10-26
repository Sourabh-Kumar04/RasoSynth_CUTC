"""
Extraction Agents - Data extraction from various sources

Agents for web crawling, OCR processing, and multimodal document extraction.
"""

from typing import Dict, List, Optional, Any, Iterator
from datetime import datetime, timezone

from agents.base import Agent, AgentConfig, AgentType, AgentState, TaskResult, AgentContext


class WebCrawlerAgent(Agent):
    """Agent for large-scale web crawling and scraping."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._crawl_stats: Dict[str, int] = {}
        self._visited_urls: set = set()

    async def initialize(self) -> bool:
        """Initialize the web crawler agent."""
        self.update_state(AgentState.IDLE)
        self._crawl_stats = {
            "pages_crawled": 0,
            "pages_failed": 0,
            "bytes_downloaded": 0,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute web crawling task."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"urls": [task]}
            # Fetching belongs to pipeline.extraction, which has timeout,
            # robots, and provenance policy enforcement.  This agent adapts its
            # real page artifacts; it never represents placeholder text as a
            # crawl result.
            pages = task_input.get("pages") or task_input.get("extracted_pages") or context.extracted_data
            results = await self._crawl_urls(pages)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "crawled_pages": results["crawled"],
                    "extracted_content": results["content"],
                    "failed_pages": results["failed"],
                },
                confidence=0.85,
                execution_time_ms=execution_time,
                metrics={
                    "total_crawled": len(results["crawled"]),
                    "total_content_mb": results["bytes"] / (1024 * 1024),
                    "depth_reached": results["max_depth"],
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _crawl_urls(self, pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize page artifacts emitted by the canonical crawler."""
        crawled = []
        failed = []
        content = []
        bytes_total = 0
        max_depth_found = 0

        for page in (pages or [])[:100]:  # Limit for safety
            if not isinstance(page, dict):
                failed.append(str(page))
                continue
            url = str(page.get("url") or page.get("source_url") or "").strip()
            text = str(page.get("text") or page.get("content") or "").strip()
            if not url or not text:
                failed.append(url or "missing_url_or_content")
                continue
            if url in self._visited_urls:
                continue

            self._visited_urls.add(url)
            page_content = {
                "url": url,
                "title": str(page.get("title") or ""),
                "text": text,
                "links": list(page.get("links") or []),
                "metadata": {
                    **(page.get("metadata") or {}),
                    "adapted_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            content.append(page_content)
            crawled.append(url)
            bytes_total += len(text.encode("utf-8"))

        self._crawl_stats["pages_crawled"] += len(crawled)
        self._crawl_stats["pages_failed"] += len(failed)
        self._crawl_stats["bytes_downloaded"] += bytes_total

        return {
            "crawled": crawled,
            "failed": failed,
            "content": content,
            "bytes": bytes_total,
            "max_depth": max_depth_found,
        }

    async def cleanup(self) -> None:
        """Cleanup web crawler resources."""
        self._visited_urls.clear()
        self.update_state(AgentState.TERMINATED)

    def get_crawl_stats(self) -> Dict[str, int]:
        """Get crawling statistics."""
        return self._crawl_stats.copy()


class OCRAgent(Agent):
    """Agent for processing scanned documents and images with OCR."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._ocr_stats: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize the OCR agent."""
        self.update_state(AgentState.IDLE)
        self._ocr_stats = {
            "pages_processed": 0,
            "chars_extracted": 0,
            "avg_confidence": 0.0,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute OCR processing on images."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"images": [task]}
            images = task_input.get("ocr_results") or task_input.get("images", [])
            language = task_input.get("language", "en")
            enhance = task_input.get("enhance", True)

            results = await self._process_images(images, language, enhance)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "processed_images": results["processed"],
                    "extracted_text": results["texts"],
                    "confidence_scores": results["confidences"],
                },
                confidence=0.88,
                execution_time_ms=execution_time,
                metrics={
                    "pages_processed": len(results["processed"]),
                    "chars_extracted": sum(len(t) for t in results["texts"]),
                    "avg_confidence": sum(results["confidences"]) / max(len(results["confidences"]), 1),
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _process_images(
        self,
        images: List[Any],
        language: str,
        enhance: bool
    ) -> Dict[str, Any]:
        """Process images with OCR."""
        processed = []
        texts = []
        confidences = []

        for image in images[:50]:  # Limit for safety
            # OCR engines belong to the extraction provider.  Preserve only
            # their actual results rather than fabricating transcriptions.
            if not isinstance(image, dict):
                continue
            text = str(image.get("text") or "").strip()
            if not text:
                continue
            processed.append(image.get("image") or image.get("path") or image.get("url") or "unknown")
            texts.append(text)
            confidences.append(float(image.get("confidence", 0.0) or 0.0))

        self._ocr_stats["pages_processed"] += len(processed)
        self._ocr_stats["chars_extracted"] += sum(len(t) for t in texts)

        return {
            "processed": processed,
            "texts": texts,
            "confidences": confidences,
        }

    async def cleanup(self) -> None:
        """Cleanup OCR agent resources."""
        self.update_state(AgentState.TERMINATED)


class MultimodalAgent(Agent):
    """Agent for extracting text, tables, and images from complex documents."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._extraction_stats: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize the multimodal extraction agent."""
        self.update_state(AgentState.IDLE)
        self._extraction_stats = {
            "documents_processed": 0,
            "tables_extracted": 0,
            "images_extracted": 0,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute multimodal extraction on documents."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"documents": [task]}
            documents = task_input.get("documents", [])
            extract_tables = task_input.get("extract_tables", True)
            extract_images = task_input.get("extract_images", True)

            results = await self._extract_multimodal(
                documents,
                extract_tables,
                extract_images
            )

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "documents_processed": results["documents"],
                    "text_content": results["texts"],
                    "tables": results["tables"],
                    "images": results["images"],
                    "structured_data": results["structured"],
                },
                confidence=0.87,
                execution_time_ms=execution_time,
                metrics={
                    "docs_processed": len(results["documents"]),
                    "tables_found": len(results["tables"]),
                    "images_found": len(results["images"]),
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.now(timezone.utc).timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _extract_multimodal(
        self,
        documents: List[Any],
        extract_tables: bool,
        extract_images: bool
    ) -> Dict[str, Any]:
        """Extract text, tables, and images from documents."""
        docs_processed = []
        texts = []
        tables = []
        images = []
        structured = []

        for document in documents[:50]:
            # This is an adapter for a real multimodal extractor's artifacts.
            # Absence of such artifacts is represented as zero extraction.
            if not isinstance(document, dict):
                continue
            document_id = document.get("id") or document.get("url") or document.get("path")
            if not document_id:
                continue
            docs_processed.append(document_id)
            text = str(document.get("text") or "").strip()
            if text:
                texts.append(text)
            if extract_tables:
                tables.extend(table for table in (document.get("tables") or []) if isinstance(table, dict))
            if extract_images:
                images.extend(image for image in (document.get("images") or []) if isinstance(image, dict))
            structured.append({
                "document_id": document_id,
                "type": document.get("type") or "unknown",
                "page_count": document.get("page_count"),
            })

        self._extraction_stats["documents_processed"] += len(docs_processed)
        self._extraction_stats["tables_extracted"] += len(tables)
        self._extraction_stats["images_extracted"] += len(images)

        return {
            "documents": docs_processed,
            "texts": texts,
            "tables": tables,
            "images": images,
            "structured": structured,
        }

    async def cleanup(self) -> None:
        """Cleanup multimodal agent resources."""
        self.update_state(AgentState.TERMINATED)

    def get_extraction_stats(self) -> Dict[str, Any]:
        """Get extraction statistics."""
        return self._extraction_stats.copy()
