"""
Knowledge Base

Continuously evolving internal research knowledge base with
vector search, graph reasoning, and semantic memory.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import hashlib


class KnowledgeType(Enum):
    """Types of knowledge entries."""
    PAPER = "paper"
    TECHNIQUE = "technique"
    BENCHMARK = "benchmark"
    WORKFLOW = "workflow"
    PROVIDER = "provider"
    MODEL = "model"
    HEURISTIC = "heuristic"
    FAILURE_PATTERN = "failure_pattern"


@dataclass
class KnowledgeEntry:
    """A knowledge base entry."""
    entry_id: str
    knowledge_type: KnowledgeType
    title: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0
    usage_count: int = 0
    last_accessed: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KnowledgeGraph:
    """Knowledge graph for relationships."""
    source_id: str
    target_id: str
    relationship: str
    weight: float = 1.0


@dataclass
class Query:
    """Knowledge query."""
    query_id: str
    text: str
    filters: Dict[str, Any] = field(default_factory=dict)
    limit: int = 10
    include_related: bool = True


@dataclass
class QueryResult:
    """Query result."""
    query_id: str
    entries: List[KnowledgeEntry]
    related_entries: List[KnowledgeEntry] = field(default_factory=list)
    reasoning: str = ""


class VectorStore:
    """Simple vector store for embeddings."""

    def __init__(self):
        self._vectors: Dict[str, List[float]] = {}
        self._entries: Dict[str, KnowledgeEntry] = {}

    def add(self, entry: KnowledgeEntry) -> None:
        """Add entry to vector store."""
        self._entries[entry.entry_id] = entry

        if entry.embedding:
            self._vectors[entry.entry_id] = entry.embedding

    def search(
        self,
        query_embedding: List[float],
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """Search by embedding similarity."""
        if not query_embedding:
            return [(eid, 0.0) for eid in list(self._entries.keys())[:limit]]

        results = []
        for entry_id, embedding in self._vectors.items():
            similarity = self._cosine_similarity(query_embedding, embedding)
            results.append((entry_id, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        if len(a) != len(b) or not a:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def delete(self, entry_id: str) -> bool:
        """Delete entry."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            if entry_id in self._vectors:
                del self._vectors[entry_id]
            return True
        return False


class KnowledgeBase:
    """Comprehensive knowledge base."""

    def __init__(self):
        self.vector_store = VectorStore()
        self._graph: List[KnowledgeGraph] = []
        self._entries: Dict[str, KnowledgeEntry] = {}
        self._indexes: Dict[str, List[str]] = {}

    def add_entry(
        self,
        knowledge_type: KnowledgeType,
        title: str,
        content: str,
        metadata: Optional[Dict] = None,
        embedding: Optional[List[float]] = None
    ) -> str:
        """Add entry to knowledge base."""
        entry_id = hashlib.md5(f"{title}_{len(self._entries)}".encode()).hexdigest()[:12]

        entry = KnowledgeEntry(
            entry_id=entry_id,
            knowledge_type=knowledge_type,
            title=title,
            content=content,
            embedding=embedding,
            metadata=metadata or {}
        )

        self._entries[entry_id] = entry
        self.vector_store.add(entry)

        if hasattr(knowledge_type, 'value'):
            key = knowledge_type.value
        else:
            key = str(knowledge_type)

        if key not in self._indexes:
            self._indexes[key] = []
        self._indexes[key].append(entry_id)

        return entry_id

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        weight: float = 1.0
    ) -> None:
        """Add relationship between entries."""
        graph_entry = KnowledgeGraph(
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
            weight=weight
        )
        self._graph.append(graph_entry)

    def query(
        self,
        text: str,
        knowledge_types: Optional[List[KnowledgeType]] = None,
        limit: int = 10,
        embedding_provider: Optional[Any] = None
    ) -> QueryResult:
        """Query the knowledge base."""
        query_embedding = self._generate_embedding(text, embedding_provider)

        vector_results = self.vector_store.search(query_embedding, limit * 2)

        entries = []
        for entry_id, score in vector_results:
            entry = self._entries.get(entry_id)
            if not entry:
                continue

            if knowledge_types and entry.knowledge_type not in knowledge_types:
                continue

            entry.relevance_score = score
            entries.append(entry)

            entry.usage_count += 1
            entry.last_accessed = datetime.utcnow()

        entries = entries[:limit]

        related = self._get_related_entries(entries[:3]) if entries else []

        return QueryResult(
            query_id=f"query_{len(self._entries)}",
            entries=entries,
            related_entries=related,
            reasoning=self._generate_reasoning(entries)
        )

    def _generate_embedding(self, text: str, provider: Optional[Any] = None) -> List[float]:
        """Generate embedding for text using provider or fallback."""
        # Try to use provider if available
        if provider:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(provider.embed(text))
                return result.embedding
            except Exception:
                pass  # Fall through to fallback

        # Fallback: deterministic hash-based embedding
        # This gives consistent results for the same text
        import hashlib
        hash_bytes = hashlib.sha256(text.encode()).digest()

        # Convert to float values and normalize
        embedding = []
        for i in range(0, min(len(hash_bytes), 128), 2):
            value = (hash_bytes[i] << 8 | hash_bytes[i+1]) / 65535.0
            embedding.append(value * 2 - 1)  # Normalize to [-1, 1]

        # Pad if needed
        while len(embedding) < 128:
            embedding.append(0.0)

        return embedding

    def _get_related_entries(self, entries: List[KnowledgeEntry]) -> List[KnowledgeEntry]:
        """Get related entries via graph."""
        related = []
        entry_ids = {e.entry_id for e in entries}

        for edge in self._graph:
            if edge.source_id in entry_ids:
                target = self._entries.get(edge.target_id)
                if target:
                    related.append(target)
            elif edge.target_id in entry_ids:
                source = self._entries.get(edge.source_id)
                if source:
                    related.append(source)

        return related[:5]

    def _generate_reasoning(self, entries: List[KnowledgeEntry]) -> str:
        """Generate reasoning for query results."""
        if not entries:
            return "No relevant entries found in knowledge base."

        top_entry = entries[0]
        return f"Most relevant: {top_entry.title} ({top_entry.relevance_score:.2f} relevance). Found {len(entries)} relevant entries."

    def get_by_type(
        self,
        knowledge_type: KnowledgeType,
        limit: int = 100
    ) -> List[KnowledgeEntry]:
        """Get entries by type."""
        if hasattr(knowledge_type, 'value'):
            key = knowledge_type.value
        else:
            key = str(knowledge_type)
        entry_ids = self._indexes.get(key, [])
        entries = [self._entries[eid] for eid in entry_ids if eid in self._entries]
        return entries[:limit]

    def get_trending(self, limit: int = 10) -> List[KnowledgeEntry]:
        """Get trending entries by usage."""
        entries = sorted(
            self._entries.values(),
            key=lambda e: e.usage_count,
            reverse=True
        )
        return entries[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        type_counts = {}
        for entry in self._entries.values():
            type_counts[entry.knowledge_type.value] = type_counts.get(entry.knowledge_type.value, 0) + 1

        return {
            "total_entries": len(self._entries),
            "by_type": type_counts,
            "relationships": len(self._graph),
            "total_queries": sum(e.usage_count for e in self._entries.values())
        }


class ResearchKnowledgeBase(KnowledgeBase):
    """Specialized knowledge base for research."""

    def __init__(self):
        super().__init__()
        self._papers: Dict[str, Dict] = {}
        self._benchmarks: Dict[str, Dict] = {}
        self._workflows: Dict[str, Dict] = {}

    def add_paper(
        self,
        title: str,
        authors: List[str],
        abstract: str,
        url: str,
        citations: int = 0
    ) -> str:
        """Add research paper."""
        entry_id = self.add_entry(
            KnowledgeType.PAPER,
            title,
            abstract,
            metadata={"authors": authors, "url": url, "citations": citations}
        )

        self._papers[entry_id] = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "url": url,
            "citations": citations
        }

        return entry_id

    def add_benchmark(
        self,
        technique: str,
        metric: str,
        score: float,
        source: str
    ) -> str:
        """Add benchmark result."""
        entry_id = self.add_entry(
            KnowledgeType.BENCHMARK,
            f"{technique}: {metric}",
            f"Score: {score}",
            metadata={"technique": technique, "metric": metric, "source": source}
        )

        self._benchmarks[entry_id] = {
            "technique": technique,
            "metric": metric,
            "score": score,
            "source": source
        }

        return entry_id

    def add_workflow(
        self,
        name: str,
        config: Dict,
        performance: Dict
    ) -> str:
        """Add workflow knowledge."""
        content = json.dumps(config)
        entry_id = self.add_entry(
            KnowledgeType.WORKFLOW,
            name,
            content,
            metadata={"performance": performance}
        )

        self._workflows[entry_id] = {
            "name": name,
            "config": config,
            "performance": performance
        }

        return entry_id

    def get_technique_comparison(self, technique: str) -> List[Dict]:
        """Get comparison data for a technique."""
        results = []

        for bid, bench in self._benchmarks.items():
            if bench["technique"].lower() == technique.lower():
                results.append(bench)

        return sorted(results, key=lambda x: x["score"], reverse=True)

    def get_best_workflow(self, criteria: str = "quality") -> Optional[Dict]:
        """Get best workflow for criteria."""
        if not self._workflows:
            return None

        workflows = list(self._workflows.values())
        if not workflows:
            return None

        return max(workflows, key=lambda w: w["performance"].get(criteria, 0))


class SemanticMemory:
    """Semantic memory for learning from experiences."""

    def __init__(self):
        self._experiences: Dict[str, List[Dict]] = {}

    def record_experience(
        self,
        category: str,
        context: Dict,
        action: Dict,
        outcome: Dict
    ) -> str:
        """Record an experience."""
        experience_id = f"exp_{category}_{len(self._experiences)}"

        experience = {
            "experience_id": experience_id,
            "context": context,
            "action": action,
            "outcome": outcome,
            "success": outcome.get("success", False),
            "timestamp": datetime.utcnow().isoformat()
        }

        if category not in self._experiences:
            self._experiences[category] = []
        self._experiences[category].append(experience)

        return experience_id

    def get_similar_experience(
        self,
        category: str,
        context: Dict
    ) -> Optional[Dict]:
        """Find similar experience."""
        experiences = self._experiences.get(category, [])
        if not experiences:
            return None

        similar = None
        best_score = 0.0

        for exp in experiences:
            score = self._calculate_similarity(context, exp["context"])
            if score > best_score:
                best_score = score
                similar = exp

        return similar if best_score > 0.5 else None

    def _calculate_similarity(self, a: Dict, b: Dict) -> float:
        """Calculate context similarity."""
        if not a or not b:
            return 0.0

        matching_keys = sum(1 for k in a if k in b and a[k] == b[k])
        total_keys = len(set(a.keys()) | set(b.keys()))

        return matching_keys / max(total_keys, 1)

    def get_success_patterns(self, category: str) -> List[Dict]:
        """Extract success patterns from experiences."""
        experiences = self._experiences.get(category, [])
        successes = [e for e in experiences if e["success"]]

        patterns = []
        for success in successes:
            patterns.append({
                "action": success["action"],
                "outcome_quality": success["outcome"].get("quality", 0),
                "timestamp": success["timestamp"]
            })

        return sorted(patterns, key=lambda p: p["outcome_quality"], reverse=True)
