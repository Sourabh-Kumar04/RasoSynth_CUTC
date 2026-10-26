"""
Discovery Agents - Source discovery and search optimization

Agents for finding relevant data sources and optimizing search queries
for better retrieval across web and structured data sources.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from urllib.parse import urlparse

from agents.base import Agent, AgentConfig, AgentType, AgentState, TaskResult, AgentContext


class SourceDiscoveryAgent(Agent):
    """Agent for discovering relevant data sources across the web."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._discovered_sources: List[Dict] = []
        self._source_rankings: Dict[str, float] = {}

    async def initialize(self) -> bool:
        """Initialize the source discovery agent."""
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute source discovery for a domain."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"domain": task}
            domain = task_input.get("domain", "")
            query = task_input.get("query", "")
            keywords = task_input.get("keywords", [])

            # Discovery is deliberately an evidence-aware role.  Network search is
            # performed by the canonical discovery pipeline; this agent ranks the
            # concrete candidates it produced instead of manufacturing URLs.
            candidates = task_input.get("sources") or context.sources
            sources = await self._discover_sources(domain, query, keywords, candidates)
            rankings = await self._rank_sources(sources)

            self._discovered_sources.extend(sources)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "sources": sources,
                    "rankings": rankings,
                    "total_discovered": len(sources),
                },
                confidence=0.9 if sources else 0.4,
                execution_time_ms=execution_time,
                metrics={
                    "sources_found": len(sources),
                    "high_quality": sum(1 for s in sources if s.get("quality_score", 0) > 0.8),
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

    async def _discover_sources(
        self,
        domain: str,
        query: str,
        keywords: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Validate and rank candidates supplied by an actual search provider.

        This agent must not fabricate sources.  Returning an empty list signals
        that discovery needs a search/crawl provider, rather than making fake
        provenance look real in the rest of the workflow.
        """
        sources: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        query_terms = {term.lower() for term in (query.split() + keywords) if term}

        for candidate in candidates or []:
            if not isinstance(candidate, dict):
                continue
            url = str(candidate.get("url") or candidate.get("source_url") or "").strip()
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or url in seen_urls:
                continue
            seen_urls.add(url)
            title = str(candidate.get("title") or "")
            text = str(candidate.get("text") or candidate.get("content") or "")
            haystack = f"{title} {text}".lower()
            term_coverage = (
                sum(term in haystack for term in query_terms) / len(query_terms)
                if query_terms else 0.0
            )
            has_license = bool(candidate.get("license") or (candidate.get("metadata") or {}).get("license"))
            has_content = bool(text)
            quality = round(min(1.0, 0.35 + 0.35 * term_coverage + 0.2 * has_content + 0.1 * has_license), 3)
            sources.append({
                **candidate,
                "url": url,
                "domain": domain or parsed.netloc,
                "quality_score": quality,
                "relevance_score": round(term_coverage, 3),
            })

        return sources

    async def _rank_sources(self, sources: List[Dict]) -> Dict[str, float]:
        """Rank sources by relevance and quality."""
        rankings = {}
        for source in sources:
            url = source["url"]
            quality = source.get("quality_score", 0.5)
            relevance = source.get("relevance_score", 0.0)
            rankings[url] = (quality + relevance) / 2

        self._source_rankings.update(rankings)
        return rankings

    async def cleanup(self) -> None:
        """Cleanup discovery agent resources."""
        self._discovered_sources.clear()
        self.update_state(AgentState.TERMINATED)


class SearchOptimizationAgent(Agent):
    """Agent for optimizing search queries for better retrieval."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._query_history: List[Dict] = []
        self._optimization_rules: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize the search optimization agent."""
        self.update_state(AgentState.IDLE)
        self._optimization_rules = {
            "min_relevance": 0.6,
            "max_results": 1000,
            "expand_factor": 3,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute search query optimization."""
        start_time = datetime.now(timezone.utc)
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"query": task}
            original_query = task_input.get("query", "")
            domain = task_input.get("domain", "")
            optimization_level = task_input.get("optimization_level", "standard")

            optimized_queries = await self._optimize_query(
                original_query,
                domain,
                optimization_level
            )

            self._query_history.append({
                "original": original_query,
                "optimized": optimized_queries,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.now(timezone.utc).timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "original_query": original_query,
                    "optimized_queries": optimized_queries,
                    "search_strategy": "multi_query_expansion",
                },
                confidence=0.88,
                execution_time_ms=execution_time,
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

    async def _optimize_query(
        self,
        query: str,
        domain: str,
        level: str
    ) -> List[Dict[str, Any]]:
        """Optimize a search query."""
        queries = []

        # Base query
        queries.append({
            "query": query,
            "type": "exact",
            "weight": 1.0,
        })

        # Synonym expansion is transparent, bounded query reformulation; it is
        # not presented as retrieved evidence.
        synonyms = await self._expand_synonyms(query, domain)
        for syn in synonyms[:5]:
            queries.append({
                "query": syn,
                "type": "synonym",
                "weight": 0.8,
            })

        # Related concepts
        concepts = await self._find_related_concepts(query, domain)
        for concept in concepts[:3]:
            queries.append({
                "query": concept,
                "type": "related",
                "weight": 0.6,
            })

        # Phrase and domain variations are useful to real search backends.
        if " " in query:
            queries.append({
                "query": f'"{query}"',
                "type": "phrase",
                "weight": 0.9,
            })

        if domain and "." in domain and " " not in domain:
            queries.append({
                "query": f"site:{domain} {query}".strip(),
                "type": "site_restricted",
                "weight": 0.85,
            })

        unique_queries: List[Dict[str, Any]] = []
        seen = set()
        for item in queries:
            normalized = item["query"].strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique_queries.append(item)
        return unique_queries

    async def _expand_synonyms(self, query: str, domain: str) -> List[str]:
        """Expand query with synonyms."""
        synonyms_map = {
            "data": ["dataset", "information", "records"],
            "analysis": ["examination", "study", "research"],
            "learning": ["training", "education", "development"],
        }

        words = query.lower().split()
        expansions = []

        for word in words:
            if word in synonyms_map:
                expansions.extend(synonyms_map[word])

        return expansions[:5]

    async def _find_related_concepts(self, query: str, domain: str) -> List[str]:
        """Find related concepts for a query."""
        concepts = [
            f"{query} applications",
            f"{query} methods",
            f"{query} techniques",
        ]
        return concepts

    async def cleanup(self) -> None:
        """Cleanup search optimization agent resources."""
        self._query_history.clear()
        self.update_state(AgentState.TERMINATED)

    def get_query_history(self) -> List[Dict]:
        """Get query optimization history."""
        return self._query_history.copy()
