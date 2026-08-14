"""
Category-Specific Cache Implementations

Specialized caches for LLM responses, embeddings, web crawls, OCR,
deduplication, validation, synthetic data, agents, workflows, and search.
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import json
import hashlib


class LLMCache:
    """Specialized cache for LLM responses with semantic awareness."""

    def __init__(
        self,
        redis_client: Any,
        semantic_cache: Optional[Any] = None,
        default_ttl: float = 7200.0
    ):
        self.redis = redis_client
        self.semantic_cache = semantic_cache
        self.default_ttl = default_ttl

    async def get(
        self,
        provider: str,
        model: str,
        prompt_hash: str
    ) -> Optional[Dict]:
        """Get cached LLM response."""
        key = f"llm:{provider}:{model}:{prompt_hash}"
        data = await self.redis.get(key)

        if data:
            return json.loads(data)
        return None

    async def get_similar(
        self,
        prompt: str,
        embedding: Optional[List[float]] = None,
        threshold: float = 0.95
    ) -> Optional[Dict]:
        """Get semantically similar cached response."""
        if not self.semantic_cache:
            return None

        similar = await self.semantic_cache.get_similar(prompt, embedding, threshold)
        if similar:
            return similar[0].entry.response
        return None

    async def store(
        self,
        provider: str,
        model: str,
        prompt: str,
        prompt_hash: str,
        response: Dict,
        embedding: Optional[List[float]] = None,
        usage: Optional[Dict] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Store LLM response."""
        key = f"llm:{provider}:{model}:{prompt_hash}"

        cache_data = {
            "provider": provider,
            "model": model,
            "prompt_hash": prompt_hash,
            "response": response,
            "usage": usage or {},
            "cached_at": datetime.utcnow().isoformat(),
            "tokens_saved": usage.get("total_tokens", 0) if usage else 0
        }

        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(cache_data, default=str)
        )

        # Also store in semantic cache if embedding provided
        if embedding and self.semantic_cache:
            await self.semantic_cache.store(
                key=key,
                query=prompt,
                response=cache_data,
                embedding=embedding
            )

    async def invalidate_model(self, provider: str, model: str) -> int:
        """Invalidate all cached responses for a model."""
        pattern = f"llm:{provider}:{model}:*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def get_stats(self, provider: str, model: str) -> Dict:
        """Get cache statistics for a model."""
        pattern = f"llm:{provider}:{model}:*"
        count = 0
        total_tokens = 0

        async for key in self.redis.scan_iter(match=pattern):
            count += 1
            data = await self.redis.get(key)
            if data:
                try:
                    parsed = json.loads(data)
                    total_tokens += parsed.get("tokens_saved", 0)
                except:
                    pass

        return {
            "cached_responses": count,
            "tokens_saved": total_tokens,
            "estimated_cost_saved_usd": total_tokens * 0.00001  # Rough estimate
        }


class WebCache:
    """Specialized cache for web crawl results."""

    def __init__(self, redis_client: Any, default_ttl: float = 3600.0):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Get cached web content."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        key = f"web:{url_hash}"

        if params:
            param_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
            key = f"{key}:{param_hash}"

        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def store(
        self,
        url: str,
        content: Any,
        content_type: str = "html",
        metadata: Optional[Dict] = None,
        params: Optional[Dict] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Store web content."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        key = f"web:{url_hash}"

        if params:
            param_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
            key = f"{key}:{param_hash}"

        cache_data = {
            "url": url,
            "content": content,
            "content_type": content_type,
            "cached_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }

        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(cache_data, default=str)
        )

    async def invalidate_domain(self, domain: str) -> int:
        """Invalidate all cached content from a domain."""
        pattern = f"web:*"
        keys_to_delete = []

        async for key in self.redis.scan_iter(match=pattern):
            data = await self.redis.get(key)
            if data:
                try:
                    parsed = json.loads(data)
                    if domain in parsed.get("url", ""):
                        keys_to_delete.append(key)
                except:
                    pass

        if keys_to_delete:
            return await self.redis.delete(*keys_to_delete)
        return 0


class EmbeddingCache:
    """Specialized cache for embedding results."""

    def __init__(self, redis_client: Any, default_ttl: float = 604800.0):
        self.redis = redis_client
        self.default_ttl = default_ttl
        self._local_cache: Dict[str, List[float]] = {}

    async def get(self, text: str, model: str = "default") -> Optional[List[float]]:
        """Get cached embedding."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        key = f"embedding:{model}:{text_hash}"

        # Check local cache first
        if key in self._local_cache:
            return self._local_cache[key]

        # Check Redis
        data = await self.redis.get(key)
        if data:
            embedding = json.loads(data)
            self._local_cache[key] = embedding
            return embedding

        return None

    async def store(
        self,
        text: str,
        embedding: List[float],
        model: str = "default",
        ttl: Optional[float] = None
    ) -> None:
        """Store embedding."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        key = f"embedding:{model}:{text_hash}"

        # Store locally and in Redis
        self._local_cache[key] = embedding
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(embedding)
        )

    async def get_many(
        self,
        texts: List[str],
        model: str = "default"
    ) -> Dict[str, List[float]]:
        """Get multiple embeddings."""
        results = {}
        missing = []

        for text in texts:
            embedding = await self.get(text, model)
            if embedding:
                results[text] = embedding
            else:
                missing.append(text)

        return results, missing

    def clear_local(self) -> None:
        """Clear local cache."""
        self._local_cache.clear()

    def get_stats(self) -> Dict:
        """Get embedding cache statistics."""
        return {
            "local_cache_size": len(self._local_cache),
            "estimated_memory_mb": sum(
                len(e) * 4 for e in self._local_cache.values()
            ) / (1024 * 1024)
        }


class DeduplicationCache:
    """Specialized cache for deduplication fingerprints."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client

    async def check_fingerprint(self, fingerprint: str) -> Optional[str]:
        """Check if fingerprint exists, return original key if found."""
        key = f"dedup:{fingerprint}"
        original = await self.redis.get(key)
        return original.decode() if original else None

    async def add_fingerprint(
        self,
        fingerprint: str,
        original_key: str,
        ttl: float = 2592000.0  # 30 days
    ) -> None:
        """Add a fingerprint to the dedup cache."""
        key = f"dedup:{fingerprint}"
        await self.redis.setex(key, ttl, original_key)

    async def check_content_hash(
        self,
        content: str,
        hash_type: str = "sha256"
    ) -> bool:
        """Check if content hash exists."""
        if hash_type == "sha256":
            hash_val = hashlib.sha256(content.encode()).hexdigest()
        elif hash_type == "md5":
            hash_val = hashlib.md5(content.encode()).hexdigest()
        else:
            hash_val = hashlib.sha256(content.encode()).hexdigest()

        return await self.redis.exists(f"content_hash:{hash_val}") > 0

    async def add_content_hash(
        self,
        content: str,
        hash_type: str = "sha256",
        ttl: float = 2592000.0
    ) -> str:
        """Add content hash."""
        if hash_type == "sha256":
            hash_val = hashlib.sha256(content.encode()).hexdigest()
        elif hash_type == "md5":
            hash_val = hashlib.md5(content.encode()).hexdigest()
        else:
            hash_val = hashlib.sha256(content.encode()).hexdigest()

        key = f"content_hash:{hash_val}"
        await self.redis.setex(key, ttl, "1")
        return hash_val


class ValidationCache:
    """Specialized cache for validation results."""

    def __init__(self, redis_client: Any, default_ttl: float = 86400.0):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get_validation(
        self,
        content_hash: str,
        validation_type: str
    ) -> Optional[Dict]:
        """Get cached validation result."""
        key = f"validation:{validation_type}:{content_hash}"
        data = await self.redis.get(key)

        if data:
            return json.loads(data)
        return None

    async def store_validation(
        self,
        content_hash: str,
        validation_type: str,
        result: Dict,
        ttl: Optional[float] = None
    ) -> None:
        """Store validation result."""
        key = f"validation:{validation_type}:{content_hash}"
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(result, default=str)
        )

    async def invalidate_content(self, content_hash: str) -> int:
        """Invalidate all validations for a content."""
        pattern = f"validation:*:{content_hash}"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            return await self.redis.delete(*keys)
        return 0


class SyntheticCache:
    """Specialized cache for synthetic data generation."""

    def __init__(self, redis_client: Any, default_ttl: float = 604800.0):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get_generation(
        self,
        template_hash: str,
        parameters_hash: str
    ) -> Optional[List[Dict]]:
        """Get cached synthetic generation."""
        key = f"synthetic:{template_hash}:{parameters_hash}"
        data = await self.redis.get(key)

        if data:
            return json.loads(data)
        return None

    async def store_generation(
        self,
        template_hash: str,
        parameters_hash: str,
        generations: List[Dict],
        ttl: Optional[float] = None
    ) -> None:
        """Store synthetic generation."""
        key = f"synthetic:{template_hash}:{parameters_hash}"
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(generations, default=str)
        )


class AgentStateCache:
    """Specialized cache for agent state."""

    def __init__(self, redis_client: Any, default_ttl: float = 300.0):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get_state(self, agent_id: str) -> Optional[Dict]:
        """Get agent state."""
        key = f"agent:state:{agent_id}"
        data = await self.redis.get(key)

        if data:
            return json.loads(data)
        return None

    async def set_state(
        self,
        agent_id: str,
        state: Dict,
        ttl: Optional[float] = None
    ) -> None:
        """Set agent state."""
        key = f"agent:state:{agent_id}"
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(state, default=str)
        )

    async def delete_state(self, agent_id: str) -> bool:
        """Delete agent state."""
        key = f"agent:state:{agent_id}"
        result = await self.redis.delete(key)
        return result > 0

    async def heartbeat(self, agent_id: str, ttl: float = 60.0) -> None:
        """Update agent heartbeat."""
        key = f"agent:heartbeat:{agent_id}"
        await self.redis.setex(key, ttl, datetime.utcnow().isoformat())

    async def get_active_agents(self) -> List[str]:
        """Get list of active agents."""
        agents = []
        async for key in self.redis.scan_iter(match="agent:heartbeat:*"):
            agents.append(key.decode().split(":")[-1])
        return agents


class WorkflowCache:
    """Specialized cache for workflow state."""

    def __init__(self, redis_client: Any, default_ttl: float = 86400.0):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow state."""
        key = f"workflow:{workflow_id}"
        data = await self.redis.get(key)

        if data:
            return json.loads(data)
        return None

    async def set_workflow(
        self,
        workflow_id: str,
        state: Dict,
        ttl: Optional[float] = None
    ) -> None:
        """Set workflow state."""
        key = f"workflow:{workflow_id}"
        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(state, default=str)
        )

    async def update_stage(
        self,
        workflow_id: str,
        stage: str,
        result: Any
    ) -> None:
        """Update workflow stage."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return

        if "stages" not in workflow:
            workflow["stages"] = {}

        workflow["stages"][stage] = {
            "result": result,
            "updated_at": datetime.utcnow().isoformat()
        }

        await self.set_workflow(workflow_id, workflow)

    async def get_workflow_progress(self, workflow_id: str) -> Optional[Dict]:
        """Get workflow progress."""
        workflow = await self.get_workflow(workflow_id)
        if not workflow:
            return None

        stages = workflow.get("stages", {})
        total = len(stages)
        completed = sum(1 for s in stages.values() if "result" in s)

        return {
            "workflow_id": workflow_id,
            "total_stages": total,
            "completed_stages": completed,
            "progress_percent": (completed / max(total, 1)) * 100
        }


class SearchCache:
    """Specialized cache for search results."""

    def __init__(self, redis_client: Any, default_ttl: float = 1800.0):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get_search(
        self,
        query: str,
        filters: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Get cached search results."""
        query_hash = hashlib.sha256(query.encode()).hexdigest()

        if filters:
            filter_hash = hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest()
            key = f"search:{query_hash}:{filter_hash}"
        else:
            key = f"search:{query_hash}"

        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def store_search(
        self,
        query: str,
        results: Dict,
        filters: Optional[Dict] = None,
        ttl: Optional[float] = None
    ) -> None:
        """Store search results."""
        query_hash = hashlib.sha256(query.encode()).hexdigest()

        if filters:
            filter_hash = hashlib.sha256(json.dumps(filters, sort_keys=True).encode()).hexdigest()
            key = f"search:{query_hash}:{filter_hash}"
        else:
            key = f"search:{query_hash}"

        cache_data = {
            "query": query,
            "results": results,
            "cached_at": datetime.utcnow().isoformat(),
            "result_count": len(results.get("items", []))
        }

        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(cache_data, default=str)
        )

    async def invalidate_query(self, query: str) -> int:
        """Invalidate cached results for a query."""
        query_hash = hashlib.sha256(query.encode()).hexdigest()
        pattern = f"search:{query_hash}:*"
        keys = []

        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            return await self.redis.delete(*keys)
        return 0


class OCRCache:
    """Specialized cache for OCR results."""

    def __init__(self, redis_client: Any, default_ttl: float = 2592000.0):
        self.redis = redis_client
        self.default_ttl = default_ttl

    async def get_result(self, image_hash: str) -> Optional[Dict]:
        """Get cached OCR result."""
        key = f"ocr:{image_hash}"
        data = await self.redis.get(key)

        if data:
            return json.loads(data)
        return None

    async def store_result(
        self,
        image_hash: str,
        result: Dict,
        confidence: float,
        ttl: Optional[float] = None
    ) -> None:
        """Store OCR result."""
        key = f"ocr:{image_hash}"

        cache_data = {
            "result": result,
            "confidence": confidence,
            "cached_at": datetime.utcnow().isoformat()
        }

        await self.redis.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(cache_data, default=str)
        )

    async def get_stats(self) -> Dict:
        """Get OCR cache statistics."""
        pattern = "ocr:*"
        count = 0
        total_confidence = 0.0

        async for key in self.redis.scan_iter(match=pattern):
            count += 1
            data = await self.redis.get(key)
            if data:
                try:
                    parsed = json.loads(data)
                    total_confidence += parsed.get("confidence", 0)
                except:
                    pass

        return {
            "cached_ocr_results": count,
            "avg_confidence": total_confidence / max(count, 1) if count > 0 else 0
        }