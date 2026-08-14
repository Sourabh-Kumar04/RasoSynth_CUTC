"""
Discovery Agents - Source discovery and search optimization

Agents for finding relevant data sources and optimizing search queries
for better retrieval across web and structured data sources.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

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
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"domain": task}
            domain = task_input.get("domain", "")
            query = task_input.get("query", "")
            keywords = task_input.get("keywords", [])

            sources = await self._discover_sources(domain, query, keywords)
            rankings = await self._rank_sources(sources)

            self._discovered_sources.extend(sources)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "sources": sources,
                    "rankings": rankings,
                    "total_discovered": len(sources),
                },
                confidence=0.85,
                execution_time_ms=execution_time,
                metrics={
                    "sources_found": len(sources),
                    "high_quality": sum(1 for s in sources if s.get("quality_score", 0) > 0.8),
                }
            )

        except Exception as e:
            return TaskResult(
                task_id=str(datetime.utcnow().timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
            )
        finally:
            self.update_state(AgentState.IDLE)

    async def _discover_sources(
        self,
        domain: str,
        query: str,
        keywords: List[str]
    ) -> List[Dict[str, Any]]:
        """Discover data sources matching the domain."""
        sources = []

        # Web sources
        web_sources = [
            {"url": f"https://example.com/{domain}", "type": "web", "format": "html"},
            {"url": f"https://api.example.com/data", "type": "api", "format": "json"},
        ]

        # Structured data sources
        structured_sources = [
            {"url": "https://commoncrawl.org/", "type": "web_archive", "format": "warc"},
            {"url": "https://huggingface.co/datasets", "type": "dataset_repo", "format": "various"},
        ]

        # Domain-specific sources
        domain_sources = []
        if "code" in domain.lower():
            domain_sources.append({"url": "https://github.com", "type": "code", "format": "git"})
            domain_sources.append({"url": "https://stackoverflow.com", "type": "q&a", "format": "html"})
        if "medical" in domain.lower() or "health" in domain.lower():
            domain_sources.append({"url": "https://pubmed.ncbi.nlm.nih.gov/", "type": "academic", "format": "xml"})
            domain_sources.append({"url": "https://clinicaltrials.gov/", "type": "clinical", "format": "xml"})

        all_sources = web_sources + structured_sources + domain_sources

        for source in all_sources:
            source["domain"] = domain
            source["quality_score"] = 0.7 + (hash(source["url"]) % 30) / 100
            source["estimated_size_gb"] = (hash(source["url"]) % 1000) / 10
            sources.append(source)

        return sources

    async def _rank_sources(self, sources: List[Dict]) -> Dict[str, float]:
        """Rank sources by relevance and quality."""
        rankings = {}
        for source in sources:
            url = source["url"]
            quality = source.get("quality_score", 0.5)
            relevance = source.get("relevance_score", 0.5)
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
        start_time = datetime.utcnow()
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
                "timestamp": datetime.utcnow().isoformat(),
            })

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
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
                task_id=str(datetime.utcnow().timestamp()),
                agent_id=self.agent_id,
                success=False,
                error=str(e),
                execution_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000
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

        # Synonym expansion
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

        # Boolean variations
        if " " in query:
            queries.append({
                "query": f'"{query}"',
                "type": "phrase",
                "weight": 0.9,
            })

        return queries

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