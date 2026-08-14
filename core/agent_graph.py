"""Multi-agent graph for specialized dataset processing agents."""
import asyncio
from dataclasses import dataclass
from typing import Any, TypedDict
from datetime import datetime
from langgraph.graph import StateGraph, END
from enum import Enum


class AgentType(Enum):
    WEB_CRAWLER = "web_crawler"
    EXTRACTION = "extraction"
    QUALITY = "quality"
    AUGMENTATION = "augmentation"
    EXPORT = "export"


@dataclass
class AgentMessage:
    sender: str
    receiver: str
    content: Any
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "timestamp": self.timestamp,
        }


class MultiAgentState(TypedDict):
    """State for multi-agent graph."""
    messages: list[dict]
    current_agent: str
    task: dict
    result: Any
    errors: list[str]
    completed_agents: list[str]


class BaseAgent:
    """Base class for all agents."""

    def __init__(self, name: str, router):
        self.name = name
        self.router = router

    async def run(self, task: dict) -> dict:
        """Run the agent on a task."""
        raise NotImplementedError

    async def health_check(self) -> bool:
        """Check if agent is healthy."""
        return True


class WebCrawlerAgent(BaseAgent):
    """Agent specialized in web crawling and discovery."""

    async def run(self, task: dict) -> dict:
        """Execute web crawling task."""
        from pipeline.discovery import DiscoveryPipeline, SourceType

        query = task.get("query", "")
        domain = task.get("domain", "")
        config = task.get("config", {})

        discovery = DiscoveryPipeline(config)
        sources = []

        async for source in discovery.discover(query, domain):
            sources.append({
                "url": source.url,
                "source_type": source.source_type.value,
                "title": source.title,
                "metadata": source.metadata_,
            })

        return {
            "status": "success",
            "agent": self.name,
            "sources": sources,
            "count": len(sources),
        }


class ExtractionAgent(BaseAgent):
    """Agent specialized in content extraction."""

    async def run(self, task: dict) -> dict:
        """Execute extraction task."""
        from pipeline.extraction import ExtractionPipeline

        sources = task.get("sources", [])
        config = task.get("config", {})

        extraction = ExtractionPipeline(config)
        extracted = []

        for source in sources:
            url = source.get("url", "")
            async for content in extraction.extract_from_url(url):
                extracted.append({
                    "content": content.content,
                    "content_type": content.content_type,
                    "url": content.url,
                    "metadata": content.metadata,
                })

        return {
            "status": "success",
            "agent": self.name,
            "extracted": extracted,
            "count": len(extracted),
        }


class QualityAgent(BaseAgent):
    """Agent specialized in quality checking and validation."""

    async def run(self, task: dict) -> dict:
        """Execute quality checking task."""
        from pipeline.filtering import FilteringPipeline

        content = task.get("content", [])
        config = task.get("config", {})
        target_domain = config.get("target_domain", "")

        filtering = FilteringPipeline(self.router, config)
        results = []

        for item in content:
            sample = type('Content', (), item)()
            result = await filtering.filter(sample, target_domain)
            if result:
                results.append({
                    "content": result.content,
                    "quality_score": result.quality_score,
                    "relevance_score": result.relevance_score,
                    "toxicity_score": result.toxicity_score,
                    "issues": result.issues,
                })

        avg_quality = sum(r.get("quality_score", 0) for r in results) / max(len(results), 1)

        return {
            "status": "success",
            "agent": self.name,
            "results": results,
            "count": len(results),
            "avg_quality": avg_quality,
        }


class AugmentationAgent(BaseAgent):
    """Agent specialized in synthetic data augmentation."""

    async def run(self, task: dict) -> dict:
        """Execute augmentation task."""
        from pipeline.construction import ConstructionPipeline

        samples = task.get("samples", [])
        config = task.get("config", {})

        augmentation = ConstructionPipeline(self.router, config)
        augmented = []

        for sample_data in samples:
            sample = type('Sample', (), sample_data)()
            async for augmented_sample in augmentation.construct(sample, config.get("target_domain", "")):
                augmented.append({
                    "instruction": augmented_sample.instruction,
                    "response": augmented_sample.response,
                    "metadata": augmented_sample.metadata_,
                    "difficulty_tier": augmented_sample.difficulty_tier,
                })

        return {
            "status": "success",
            "agent": self.name,
            "augmented": augmented,
            "count": len(augmented),
        }


class ExportAgent(BaseAgent):
    """Agent specialized in dataset export."""

    async def run(self, task: dict) -> dict:
        """Execute export task."""
        from pipeline.export import ExportPipeline, ExportConfig

        samples = task.get("samples", [])
        job_id = task.get("job_id", "unknown")
        config = task.get("config", {})

        export_config = ExportConfig(
            format=config.get("export_format", "jsonl"),
            output_dir=config.get("output_dir", "outputs"),
            dataset_name=f"dataset_{job_id}",
        )

        exporter = ExportPipeline(export_config)
        output_paths = await exporter.export(samples, job_id)

        card_path = await exporter.generate_dataset_card(samples)
        quality_report = await exporter.generate_quality_report(samples)
        lineage_report = await exporter.generate_lineage_report(samples)

        return {
            "status": "success",
            "agent": self.name,
            "output_paths": {k: str(v) for k, v in output_paths.items()},
            "card_path": str(card_path),
            "quality_report": quality_report,
            "lineage_report": lineage_report,
        }


class MultiAgentGraph:
    """Multi-agent graph orchestration system."""

    def __init__(self, router):
        self.router = router
        self.agents = {
            "web_crawler": WebCrawlerAgent("web_crawler", router),
            "extraction": ExtractionAgent("extraction", router),
            "quality": QualityAgent("quality", router),
            "augmentation": AugmentationAgent("augmentation", router),
            "export": ExportAgent("export", router),
        }
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the multi-agent graph."""
        workflow = StateGraph(MultiAgentState)

        workflow.add_node("coordinator", self._coordinator_node)
        workflow.add_node("web_crawler", self._agent_node("web_crawler"))
        workflow.add_node("extraction", self._agent_node("extraction"))
        workflow.add_node("quality", self._agent_node("quality"))
        workflow.add_node("augmentation", self._agent_node("augmentation"))
        workflow.add_node("export", self._agent_node("export"))

        workflow.add_edge("coordinator", "web_crawler")
        workflow.add_edge("web_crawler", "extraction")
        workflow.add_edge("extraction", "quality")
        workflow.add_edge("quality", "augmentation")
        workflow.add_edge("augmentation", "export")
        workflow.add_edge("export", END)

        workflow.set_entry_point("coordinator")
        return workflow.compile()

    async def _coordinator_node(self, state: MultiAgentState) -> MultiAgentState:
        """Coordinator node that manages the workflow."""
        return {
            **state,
            "current_agent": "coordinator",
            "messages": state["messages"] + [{
                "sender": "system",
                "content": "Pipeline started",
                "timestamp": datetime.utcnow().timestamp(),
            }]
        }

    def _agent_node(self, agent_name: str):
        """Create an agent node."""
        async def node(state: MultiAgentState) -> MultiAgentState:
            agent = self.agents[agent_name]
            task = state["task"]

            try:
                result = await agent.run(task)

                return {
                    **state,
                    "current_agent": agent_name,
                    "result": result,
                    "completed_agents": state["completed_agents"] + [agent_name],
                    "messages": state["messages"] + [{
                        "sender": agent_name,
                        "content": result,
                        "timestamp": datetime.utcnow().timestamp(),
                    }]
                }
            except Exception as e:
                return {
                    **state,
                    "current_agent": agent_name,
                    "errors": state["errors"] + [str(e)],
                }

        return node

    async def run(self, task: dict) -> dict:
        """Run the multi-agent pipeline."""
        initial_state = {
            "messages": [],
            "current_agent": "",
            "task": task,
            "result": None,
            "errors": [],
            "completed_agents": [],
        }

        result = await self.graph.astream(initial_state)
        return result

    async def run_parallel(self, tasks: list[dict]) -> list[dict]:
        """Run multiple tasks in parallel."""
        results = await asyncio.gather(*[
            self.run(task) for task in tasks
        ])
        return results

    def get_agent_status(self) -> dict:
        """Get status of all agents."""
        return {
            name: {
                "healthy": asyncio.run(agent.health_check()),
                "name": agent.name,
            }
            for name, agent in self.agents.items()
        }