"""Ray-based distributed pipeline for GPU-accelerated processing."""
import ray
from ray import remote
from typing import List, Dict, Any, Optional
import asyncio


ray.init(ignore_reinit_error=True)


@ray.remote
class DiscoveryWorker:
    """Ray worker for distributed discovery."""

    def __init__(self, config: dict):
        self.config = config

    def discover(self, query: str, domain: str, source_types: List[str]) -> List[Dict]:
        """Discover sources using this worker."""
        from pipeline.discovery import DiscoveryPipeline, SourceType

        discovery = DiscoveryPipeline(self.config)
        sources = []

        type_map = {
            "web_page": SourceType.WEB_PAGE,
            "github_repo": SourceType.GITHUB_REPO,
            "arxiv_paper": SourceType.ARXIV_PAPER,
        }

        types = [type_map.get(t, SourceType.WEB_PAGE) for t in source_types]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run():
            async for source in discovery.discover(query, domain, types):
                sources.append({
                    "url": source.url,
                    "source_type": source.source_type.value,
                    "title": source.title,
                    "metadata": source.metadata_,
                })

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

        return sources


@ray.remote
class ExtractionWorker:
    """Ray worker for distributed content extraction."""

    def __init__(self, config: dict):
        self.config = config

    def extract_batch(self, sources: List[Dict]) -> List[Dict]:
        """Extract content from a batch of sources."""
        from pipeline.extraction import ExtractionPipeline

        extraction = ExtractionPipeline(self.config)
        extracted = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run():
            for source in sources:
                url = source.get("url", "")
                try:
                    async for content in extraction.extract_from_url(url):
                        extracted.append({
                            "content": content.content,
                            "content_type": content.content_type,
                            "url": content.url,
                            "metadata": content.metadata,
                        })
                except Exception:
                    continue

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

        return extracted


@ray.remote
class QualityWorker:
    """Ray worker for distributed quality scoring."""

    def __init__(self, config: dict, router_config: dict):
        self.config = config
        self.router_config = router_config

    def score_batch(self, items: List[Dict]) -> List[Dict]:
        """Score a batch of items for quality."""
        from pipeline.filtering import FilteringPipeline
        from core.provider_router import ProviderRouter

        router = ProviderRouter(self.router_config)
        filtering = FilteringPipeline(router, self.config)

        results = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run():
            for item in items:
                sample = type('Content', (), item)()
                result = await filtering.filter(sample, self.config.get("target_domain", ""))
                if result:
                    results.append({
                        "content": result.content,
                        "quality_score": result.quality_score,
                        "relevance_score": result.relevance_score,
                        "toxicity_score": result.toxicity_score,
                        "issues": result.issues,
                    })

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

        return results


@ray.remote
class ConstructionWorker:
    """Ray worker for distributed sample construction."""

    def __init__(self, config: dict, router_config: dict):
        self.config = config
        self.router_config = router_config

    def construct_batch(self, filtered: List[Dict]) -> List[Dict]:
        """Construct training samples from filtered content."""
        from pipeline.construction import ConstructionPipeline
        from core.provider_router import ProviderRouter

        router = ProviderRouter(self.router_config)
        construction = ConstructionPipeline(router, self.config)

        samples = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def run():
            for item in filtered:
                sample = type('Sample', (), {
                    "content": item["content"],
                    "quality_score": item.get("quality_score", 0.5),
                })()

                async for constructed in construction.construct(sample, self.config.get("target_domain", "")):
                    samples.append({
                        "instruction": constructed.instruction,
                        "response": constructed.response,
                        "input": constructed.input,
                        "metadata": constructed.metadata,
                        "difficulty_tier": constructed.difficulty_tier,
                        "curriculum_order": constructed.curriculum_order,
                    })

        try:
            loop.run_until_complete(run())
        finally:
            loop.close()

        return samples


class RayPipeline:
    """Ray-based distributed pipeline for dataset generation."""

    def __init__(self, config: dict, num_workers: int = 4):
        self.config = config
        self.num_workers = num_workers

        settings_config = config.get("settings", {})
        router_config = config.get("router", {})

        self.discovery_workers = [
            DiscoveryWorker.remote(config) for _ in range(num_workers)
        ]
        self.extraction_workers = [
            ExtractionWorker.remote(config) for _ in range(num_workers)
        ]
        self.quality_workers = [
            QualityWorker.remote(config, router_config) for _ in range(num_workers)
        ]
        self.construction_workers = [
            ConstructionWorker.remote(config, router_config) for _ in range(num_workers)
        ]

    def run_discovery(self, queries: List[str], domain: str, source_types: List[str]) -> List[Dict]:
        """Run distributed discovery across workers."""
        futures = [
            worker.discover.remote(query, domain, source_types)
            for worker, query in zip(self.discovery_workers, queries)
        ]

        results = ray.get(futures)

        all_sources = []
        for result in results:
            all_sources.extend(result)

        return all_sources

    def run_extraction(self, sources: List[Dict]) -> List[Dict]:
        """Run distributed extraction across workers."""
        batch_size = max(1, len(sources) // self.num_workers)
        batches = [
            sources[i:i + batch_size]
            for i in range(0, len(sources), batch_size)
        ]

        futures = []
        for worker, batch in zip(self.extraction_workers[:len(batches)], batches):
            futures.append(worker.extract_batch.remote(batch))

        results = ray.get(futures)

        all_extracted = []
        for result in results:
            all_extracted.extend(result)

        return all_extracted

    def run_quality(self, items: List[Dict]) -> List[Dict]:
        """Run distributed quality scoring across workers."""
        batch_size = max(1, len(items) // self.num_workers)
        batches = [
            items[i:i + batch_size]
            for i in range(0, len(items), batch_size)
        ]

        futures = []
        for worker, batch in zip(self.quality_workers[:len(batches)], batches):
            futures.append(worker.score_batch.remote(batch))

        results = ray.get(futures)

        all_scored = []
        for result in results:
            all_scored.extend(result)

        return all_scored

    def run_construction(self, filtered: List[Dict]) -> List[Dict]:
        """Run distributed construction across workers."""
        batch_size = max(1, len(filtered) // self.num_workers)
        batches = [
            filtered[i:i + batch_size]
            for i in range(0, len(filtered), batch_size)
        ]

        futures = []
        for worker, batch in zip(self.construction_workers[:len(batches)], batches):
            futures.append(worker.construct_batch.remote(batch))

        results = ray.get(futures)

        all_samples = []
        for result in results:
            all_samples.extend(result)

        return all_samples

    def run_full_pipeline(self, job_id: str, queries: List[str], domain: str) -> Dict:
        """Run the full pipeline using Ray."""
        source_types = ["web_page", "github_repo", "arxiv_paper"]

        sources = self.run_discovery(queries, domain, source_types)

        extracted = self.run_extraction(sources)

        filtered = self.run_quality(extracted)

        samples = self.run_construction(filtered)

        return {
            "job_id": job_id,
            "sources": len(sources),
            "extracted": len(extracted),
            "filtered": len(filtered),
            "samples": len(samples),
        }

    def scale_workers(self, num: int):
        """Scale the worker pool."""
        self.num_workers = num

        self.discovery_workers = [
            DiscoveryWorker.remote(self.config) for _ in range(num)
        ]
        self.extraction_workers = [
            ExtractionWorker.remote(self.config) for _ in range(num)
        ]
        self.quality_workers = [
            QualityWorker.remote(self.config, {}) for _ in range(num)
        ]
        self.construction_workers = [
            ConstructionWorker.remote(self.config, {}) for _ in range(num)
        ]


def get_ray_status() -> Dict:
    """Get Ray cluster status."""
    return {
        "available": ray.is_initialized(),
        "nodes": len(ray.nodes()) if ray.is_initialized() else 0,
        "available_cpus": ray.available_resources().get("CPU", 0),
        "available_gpus": ray.available_resources().get("GPU", 0),
    }