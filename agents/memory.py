"""
Agent Memory - Persistent context and knowledge management

Vector memory, episodic memory, graph memory, and knowledge base for
maintaining persistent state across agent sessions.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import asyncio
import uuid


class MemoryType(Enum):
    """Types of agent memory."""
    EPISODIC = "episodic"  # Specific experiences/events
    SEMANTIC = "semantic"  # General knowledge/concepts
    PROCEDURAL = "procedural"  # How to do things
    WORKING = "working"  # Current context


@dataclass
class MemoryEntry:
    """A single memory entry."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType = MemoryType.EPISODIC
    content: Any = None
    embedding: Optional[List[float]] = None
    importance: float = 1.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    accessed_at: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    source_agent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def access(self) -> None:
        """Record access to this memory."""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "importance": self.importance,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "tags": self.tags,
            "source_agent": self.source_agent,
        }


@dataclass
class Episode:
    """An episodic memory containing related events."""
    episode_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    entries: List[MemoryEntry] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)
    outcome: Optional[str] = None
    agents_involved: List[str] = field(default_factory=list)


@dataclass
class KnowledgeFact:
    """A fact in the knowledge base."""
    fact_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: str = ""
    predicate: str = ""
    object: Any = None
    confidence: float = 1.0
    source: str = ""
    valid_from: datetime = field(default_factory=datetime.utcnow)
    valid_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class VectorMemory:
    """Vector-based semantic memory with embedding search."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._vectors: Dict[str, List[float]] = {}
        self._entries: Dict[str, MemoryEntry] = {}
        self._index: Dict[str, List[str]] = {}  # Tag-based index

    async def store(
        self,
        content: Any,
        embedding: Optional[List[float]] = None,
        memory_type: MemoryType = MemoryType.SEMANTIC,
        tags: Optional[List[str]] = None,
        importance: float = 1.0,
        source_agent: Optional[str] = None
    ) -> MemoryEntry:
        """Store a memory with optional embedding."""
        if embedding is None:
            embedding = await self._generate_embedding(content)

        entry = MemoryEntry(
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            importance=importance,
            tags=tags or [],
            source_agent=source_agent
        )

        self._entries[entry.entry_id] = entry
        self._vectors[entry.entry_id] = embedding

        # Index by tags
        for tag in entry.tags:
            if tag not in self._index:
                self._index[tag] = []
            self._index[tag].append(entry.entry_id)

        return entry

    async def search(
        self,
        query: Any,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
        memory_type: Optional[MemoryType] = None,
        min_importance: float = 0.0
    ) -> List[Tuple[MemoryEntry, float]]:
        """Search for similar memories using embeddings."""
        if query_embedding is None:
            query_embedding = await self._generate_embedding(query)

        scores = []
        for entry_id, embedding in self._vectors.items():
            if entry_id not in self._entries:
                continue

            entry = self._entries[entry_id]

            if memory_type and entry.memory_type != memory_type:
                continue
            if entry.importance < min_importance:
                continue

            similarity = self._cosine_similarity(query_embedding, embedding)
            scores.append((entry, similarity))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    async def search_by_tags(
        self,
        tags: List[str],
        top_k: int = 10
    ) -> List[MemoryEntry]:
        """Search by tags."""
        matching_ids = set()
        for tag in tags:
            if tag in self._index:
                matching_ids.update(self._index[tag])

        entries = [self._entries[eid] for eid in matching_ids if eid in self._entries]
        entries.sort(key=lambda e: (e.access_count, e.importance), reverse=True)
        return entries[:top_k]

    async def _generate_embedding(self, content: Any) -> List[float]:
        """Generate embedding for content (simplified)."""
        # In production, use actual embedding model
        content_str = json.dumps(content) if not isinstance(content, str) else content
        import hashlib
        hash_val = int(hashlib.md5(content_str.encode()).hexdigest(), 16)
        return [
            (hash_val >> (i * 8) & 0xFF) / 255.0
            for i in range(min(self.dimension, 64))
        ] + [0.0] * max(0, self.dimension - 64)

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        if len(a) != len(b):
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5

        if mag_a == 0 or mag_b == 0:
            return 0.0

        return dot / (mag_a * mag_b)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_entries": len(self._entries),
            "total_vectors": len(self._vectors),
            "indexed_tags": len(self._index),
            "memory_types": {
                mt.value: sum(1 for e in self._entries.values() if e.memory_type == mt)
                for mt in MemoryType
            },
        }


class EpisodicMemory:
    """Episodic memory for storing experiences and events."""

    def __init__(self):
        self._episodes: Dict[str, Episode] = {}
        self._current_episode: Optional[Episode] = None
        self._recent_events: List[MemoryEntry] = []
        self._max_recent = 1000

    async def start_episode(
        self,
        name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Episode:
        """Start a new episode."""
        episode = Episode(
            name=name,
            context=context or {},
            start_time=datetime.utcnow()
        )
        self._episodes[episode.episode_id] = episode
        self._current_episode = episode
        return episode

    async def end_episode(self, outcome: Optional[str] = None) -> Optional[Episode]:
        """End the current episode."""
        if self._current_episode:
            self._current_episode.end_time = datetime.utcnow()
            self._current_episode.outcome = outcome
            episode = self._current_episode
            self._current_episode = None
            return episode
        return None

    async def add_memory(
        self,
        content: Any,
        importance: float = 1.0,
        tags: Optional[List[str]] = None
    ) -> MemoryEntry:
        """Add a memory to the current episode."""
        entry = MemoryEntry(
            content=content,
            importance=importance,
            tags=tags or []
        )

        self._recent_events.append(entry)
        if len(self._recent_events) > self._max_recent:
            self._recent_events = self._recent_events[-self._max_recent:]

        if self._current_episode:
            self._current_episode.entries.append(entry)

        return entry

    async def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Get an episode by ID."""
        return self._episodes.get(episode_id)

    async def get_recent_episodes(self, limit: int = 10) -> List[Episode]:
        """Get recent episodes."""
        episodes = sorted(
            self._episodes.values(),
            key=lambda e: e.start_time,
            reverse=True
        )
        return episodes[:limit]

    async def search_episodes(
        self,
        query: str,
        limit: int = 5
    ) -> List[Episode]:
        """Search episodes by content."""
        matching = []
        for episode in self._episodes.values():
            for entry in episode.entries:
                if query.lower() in str(entry.content).lower():
                    matching.append(episode)
                    break

        return matching[:limit]

    def replay_episode(self, episode_id: str) -> List[MemoryEntry]:
        """Get entries for replaying an episode."""
        episode = self._episodes.get(episode_id)
        if episode:
            return episode.entries
        return []


class GraphMemory:
    """Graph-based knowledge memory with relationships."""

    def __init__(self):
        self._nodes: Dict[str, Dict] = {}
        self._edges: List[Dict] = []
        self._node_index: Dict[str, List[str]] = {}

    async def add_node(
        self,
        node_type: str,
        properties: Dict[str, Any],
        node_id: Optional[str] = None
    ) -> str:
        """Add a node to the graph."""
        if node_id is None:
            node_id = str(uuid.uuid4())

        node = {
            "node_id": node_id,
            "node_type": node_type,
            "properties": properties,
            "created_at": datetime.utcnow().isoformat(),
        }

        self._nodes[node_id] = node

        # Index by type
        if node_type not in self._node_index:
            self._node_index[node_type] = []
        self._node_index[node_type].append(node_id)

        return node_id

    async def add_edge(
        self,
        source_id: str,
        target_id: str,
        relationship: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Add an edge between nodes."""
        if source_id not in self._nodes or target_id not in self._nodes:
            return False

        edge = {
            "edge_id": str(uuid.uuid4()),
            "source_id": source_id,
            "target_id": target_id,
            "relationship": relationship,
            "properties": properties or {},
            "created_at": datetime.utcnow().isoformat(),
        }

        self._edges.append(edge)
        return True

    async def query(
        self,
        node_type: Optional[str] = None,
        relationships: Optional[List[str]] = None,
        property_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Query the graph."""
        results = []

        # Filter by type
        if node_type:
            node_ids = self._node_index.get(node_type, [])
            candidates = [self._nodes[nid] for nid in node_ids if nid in self._nodes]
        else:
            candidates = list(self._nodes.values())

        # Filter by properties
        if property_filters:
            candidates = [
                n for n in candidates
                if all(n["properties"].get(k) == v for k, v in property_filters.items())
            ]

        # Filter by relationships
        if relationships:
            node_ids_with_rel = set()
            for edge in self._edges:
                if edge["relationship"] in relationships:
                    node_ids_with_rel.add(edge["source_id"])
                    node_ids_with_rel.add(edge["target_id"])
            candidates = [n for n in candidates if n["node_id"] in node_ids_with_rel]

        return candidates

    async def get_connected(
        self,
        node_id: str,
        relationship: Optional[str] = None,
        direction: str = "both"
    ) -> List[Dict]:
        """Get nodes connected to a given node."""
        connected = []

        for edge in self._edges:
            if relationship and edge["relationship"] != relationship:
                continue

            if edge["source_id"] == node_id and direction in ("out", "both"):
                if edge["target_id"] in self._nodes:
                    connected.append({
                        **self._nodes[edge["target_id"]],
                        "via_relationship": edge["relationship"]
                    })
            elif edge["target_id"] == node_id and direction in ("in", "both"):
                if edge["source_id"] in self._nodes:
                    connected.append({
                        **self._nodes[edge["source_id"]],
                        "via_relationship": edge["relationship"]
                    })

        return connected

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "node_types": {
                ntype: len(ids) for ntype, ids in self._node_index.items()
            },
            "relationship_types": list(set(e["relationship"] for e in self._edges)),
        }


class KnowledgeBase:
    """Knowledge base with facts and relationships."""

    def __init__(self):
        self._facts: Dict[str, KnowledgeFact] = {}
        self._subject_index: Dict[str, List[str]] = {}
        self._predicate_index: Dict[str, List[str]] = {}
        self.vector_memory = VectorMemory()
        self.episodic_memory = EpisodicMemory()

    async def add_fact(
        self,
        subject: str,
        predicate: str,
        object_val: Any,
        confidence: float = 1.0,
        source: str = ""
    ) -> KnowledgeFact:
        """Add a fact to the knowledge base."""
        fact = KnowledgeFact(
            subject=subject,
            predicate=predicate,
            object=object_val,
            confidence=confidence,
            source=source
        )

        self._facts[fact.fact_id] = fact

        # Index by subject
        if subject not in self._subject_index:
            self._subject_index[subject] = []
        self._subject_index[subject].append(fact.fact_id)

        # Index by predicate
        if predicate not in self._predicate_index:
            self._predicate_index[predicate] = []
        self._predicate_index[predicate].append(fact.fact_id)

        return fact

    async def query(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[KnowledgeFact]:
        """Query facts."""
        fact_ids = set()

        if subject and subject in self._subject_index:
            fact_ids.update(self._subject_index[subject])

        if predicate and predicate in self._predicate_index:
            if not fact_ids:
                fact_ids.update(self._predicate_index[predicate])
            else:
                fact_ids.intersection_update(self._predicate_index[predicate])

        results = []
        for fact_id in fact_ids:
            fact = self._facts[fact_id]
            if fact.confidence >= min_confidence:
                results.append(fact)

        return results

    async def get_about(self, subject: str) -> List[KnowledgeFact]:
        """Get all facts about a subject."""
        fact_ids = self._subject_index.get(subject, [])
        return [self._facts[fid] for fid in fact_ids if fid in self._facts]

    async def update_fact(
        self,
        fact_id: str,
        object_val: Any,
        confidence: float = 1.0
    ) -> bool:
        """Update an existing fact."""
        if fact_id not in self._facts:
            return False

        fact = self._facts[fact_id]
        fact.object = object_val
        fact.confidence = confidence
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        return {
            "total_facts": len(self._facts),
            "unique_subjects": len(self._subject_index),
            "unique_predicates": len(self._predicate_index),
            "avg_confidence": sum(f.confidence for f in self._facts.values()) / max(len(self._facts), 1),
        }


class AgentMemoryManager:
    """Manages all memory types for agents."""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.vector_memory = VectorMemory()
        self.episodic_memory = EpisodicMemory()
        self.graph_memory = GraphMemory()
        self.knowledge_base = KnowledgeBase()
        self.working_memory: Dict[str, Any] = {}

    async def store(
        self,
        content: Any,
        memory_type: MemoryType = MemoryType.EPISODIC,
        tags: Optional[List[str]] = None,
        importance: float = 1.0
    ) -> MemoryEntry:
        """Store a memory entry."""
        entry = await self.vector_memory.store(
            content=content,
            memory_type=memory_type,
            tags=tags,
            importance=importance,
            source_agent=self.agent_id
        )
        return entry

    async def recall(
        self,
        query: Any,
        memory_types: Optional[List[MemoryType]] = None,
        top_k: int = 5
    ) -> List[MemoryEntry]:
        """Recall memories matching a query."""
        results = await self.vector_memory.search(query, top_k=top_k * 2)

        if memory_types:
            results = [
                (entry, score) for entry, score in results
                if entry.memory_type in memory_types
            ]

        return [entry for entry, _ in results[:top_k]]

    async def remember_episode(self, episode_id: str) -> List[MemoryEntry]:
        """Remember all entries from an episode."""
        return self.episodic_memory.replay_episode(episode_id)

    def clear_working_memory(self) -> None:
        """Clear working memory."""
        self.working_memory.clear()

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all memory types."""
        return {
            "agent_id": self.agent_id,
            "vector_memory": self.vector_memory.get_stats(),
            "episodic_memory": {
                "total_episodes": len(self.episodic_memory._episodes),
                "recent_events": len(self.episodic_memory._recent_events),
            },
            "graph_memory": self.graph_memory.get_stats(),
            "knowledge_base": self.knowledge_base.get_stats(),
        }