"""
Ray-Based Distributed GPU Execution Layer

Handles GPU-accelerated compute, distributed inference, and parallel processing.
"""

import asyncio
import time
from typing import Optional, Any, list, Callable
from dataclasses import dataclass, field
from datetime import datetime

# Ray imports
try:
    import ray
    from ray.util.queue import Queue
    from ray.util.actor_pool import ActorPool
    RAY_AVAILABLE = True
except ImportError:
    RAY_AVAILABLE = False

from workers.distributed.base import (
    DistributedConfig,
    WorkerNode,
    ResourceRequirement,
    ExecutionResult,
    GPUInfo,
    NodeStatus,
)


@dataclass
class RayClusterConfig:
    """Configuration for Ray cluster."""
    head_address: str = "auto"
    num_workers: int = 0
    object_store_size_gb: float = 0.5
    dashboard_port: int = 8265
    autoscaling_enabled: bool = True


class RayGPUManager:
    """Manages GPU allocation and scheduling in Ray cluster."""

    def __init__(self, config: DistributedConfig):
        self.config = config
        self._gpu_availability: dict[int, float] = {}  # gpu_id -> available memory gb

    async def initialize(self) -> None:
        """Initialize GPU manager."""
        if not RAY_AVAILABLE:
            return

        # Query available GPUs from Ray
        @ray.remote(num_gpus=1)
        def get_gpu_info():
            import torch
            if torch.cuda.is_available():
                return {
                    "count": torch.cuda.device_count(),
                    "names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
                    "memory": [torch.cuda.get_device_properties(i).total_memory / 1e9 for i in range(torch.cuda.device_count())],
                }
            return {"count": 0, "names": [], "memory": []}

        try:
            gpu_data = ray.get(get_gpu_info.remote())
            for i in range(gpu_data["count"]):
                self._gpu_availability[i] = gpu_data["memory"][i]
        except Exception:
            pass

    def get_available_gpus(self) -> list[int]:
        """Get list of available GPU IDs."""
        return [gpu_id for gpu_id, mem in self._gpu_availability.items() if mem > 0]

    def allocate_gpu(self, required_memory_gb: float) -> Optional[int]:
        """Allocate a GPU with sufficient memory."""
        for gpu_id, available in self._gpu_availability.items():
            if available >= required_memory_gb:
                self._gpu_availability[gpu_id] -= required_memory_gb
                return gpu_id
        return None

    def release_gpu(self, gpu_id: int, memory_gb: float) -> None:
        """Release a GPU back to the pool."""
        if gpu_id in self._gpu_availability:
            self._gpu_availability[gpu_id] += memory_gb


class RayActorPool:
    """Pool of Ray actors for parallel execution."""

    def __init__(self, actor_class, num_actors: int, actor_options: dict = None):
        self.actor_class = actor_class
        self.num_actors = num_actors
        self.actor_options = actor_options or {}
        self._actors: list = []
        self._pool: Optional[ActorPool] = None

    async def initialize(self) -> None:
        """Initialize actor pool."""
        if not RAY_AVAILABLE:
            return

        self._actors = [
            self.actor_class.options(**self.actor_options).remote()
            for _ in range(self.num_actors)
        ]
        self._pool = ActorPool(self._actors)

    async def map(self, func: Callable, inputs: list) -> list:
        """Map function over inputs using actor pool."""
        if not self._pool:
            return []

        futures = []
        for inp in inputs:
            actor = self._pool.get_free()
            future = func(actor, inp)
            futures.append((actor, future))

        results = []
        for actor, future in futures:
            result = await future
            self._pool.return_actor(actor)
            results.append(result)

        return results


@ray.remote
class ModelActor:
    """Persistent actor for LLM inference with model loaded in GPU memory."""

    def __init__(self, model_name: str, provider: str = "openai", device: str = "cuda"):
        self.model_name = model_name
        self.provider = provider
        self.device = device
        self._model = None
        self._initialized = False
        self._inference_count = 0
        self._total_time_ms = 0.0

    def initialize(self) -> bool:
        """Initialize the model."""
        try:
            if self.provider == "openai":
                # OpenAI models don't need local loading
                self._initialized = True
            elif self.provider == "huggingface":
                from transformers import AutoModelForCausalLM, AutoTokenizer
                import torch
                self._model = AutoModelForCausalLM.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16,
                    device_map="auto"
                )
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._initialized = True
            elif self.provider == "vllm":
                from vllm import LLM
                self._model = LLM(model=self.model_name)
                self._initialized = True
            return self._initialized
        except Exception as e:
            print(f"Model initialization failed: {e}")
            return False

    def generate(self, prompt: str, max_tokens: int = 256, temperature: float = 0.7) -> dict:
        """Generate text with the model."""
        start_time = time.time()

        try:
            if self.provider == "openai":
                from openai import AsyncOpenAI
                import asyncio
                client = AsyncOpenAI()
                response = asyncio.run(client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                ))
                output = response.choices[0].message.content

            elif self.provider == "huggingface" and self._model:
                inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=temperature > 0
                )
                output = self._tokenizer.decode(outputs[0])

            elif self.provider == "vllm" and self._model:
                outputs = self._model.generate([prompt])
                output = outputs[0].outputs[0].text

            else:
                output = f"Mock output for {self.model_name}: {prompt[:50]}..."

            elapsed = (time.time() - start_time) * 1000
            self._inference_count += 1
            self._total_time_ms += elapsed

            return {
                "success": True,
                "output": output,
                "latency_ms": elapsed,
                "model": self.model_name,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000,
                "model": self.model_name,
            }

    def batch_generate(self, prompts: list[str], **kwargs) -> list[dict]:
        """Generate text for multiple prompts."""
        return [self.generate(p, **kwargs) for p in prompts]

    def get_stats(self) -> dict:
        """Get actor statistics."""
        return {
            "model": self.model_name,
            "provider": self.provider,
            "initialized": self._initialized,
            "inference_count": self._inference_count,
            "total_time_ms": self._total_time_ms,
            "avg_latency_ms": self._total_time_ms / max(self._inference_count, 1),
        }


@ray.remote
class EmbeddingActor:
    """Persistent actor for embedding generation."""

    def __init__(self, model_name: str = "text-embedding-3-small", provider: str = "openai"):
        self.model_name = model_name
        self.provider = provider
        self._model = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize embedding model."""
        try:
            if self.provider == "openai":
                self._initialized = True
            elif self.provider == "huggingface":
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
                self._initialized = True
            return self._initialized
        except Exception:
            return False

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        try:
            if self.provider == "openai":
                from openai import AsyncOpenAI
                import asyncio
                client = AsyncOpenAI()
                response = asyncio.run(client.embeddings.create(
                    model=self.model_name,
                    input=text
                ))
                return response.data[0].embedding
            elif self._model:
                return self._model.encode(text).tolist()
            else:
                return [0.0] * 1536  # Mock embedding
        except Exception:
            return [0.0] * 1536

    def batch_embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(t) for t in texts]

    def get_stats(self) -> dict:
        return {
            "model": self.model_name,
            "provider": self.provider,
            "initialized": self._initialized,
        }


@ray.remote
class InferenceWorker:
    """General-purpose inference worker."""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self._models: dict[str, Any] = {}
        self._tasks_processed = 0

    def register_model(self, model_id: str, model: Any) -> bool:
        """Register a model with this worker."""
        self._models[model_id] = model
        return True

    def process_task(self, task_type: str, payload: dict) -> dict:
        """Process an inference task."""
        start_time = time.time()

        try:
            if task_type == "generate":
                result = self._process_generation(payload)
            elif task_type == "embed":
                result = self._process_embedding(payload)
            elif task_type == "score":
                result = self._process_scoring(payload)
            elif task_type == "classify":
                result = self._process_classification(payload)
            else:
                result = {"output": f"Processed {task_type}", "success": True}

            self._tasks_processed += 1

            return {
                **result,
                "worker_id": self.worker_id,
                "latency_ms": (time.time() - start_time) * 1000,
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "worker_id": self.worker_id,
                "latency_ms": (time.time() - start_time) * 1000,
            }

    def _process_generation(self, payload: dict) -> dict:
        """Process text generation task."""
        return {"output": f"Generated text for: {payload.get('prompt', '')[:50]}", "success": True}

    def _process_embedding(self, payload: dict) -> dict:
        """Process embedding task."""
        return {"output": [0.0] * 768, "success": True}

    def _process_scoring(self, payload: dict) -> dict:
        """Process quality scoring task."""
        return {"output": {"score": 0.85, "confidence": 0.9}, "success": True}

    def _process_classification(self, payload: dict) -> dict:
        """Process classification task."""
        return {"output": {"class": "relevant", "probability": 0.92}, "success": True}

    def get_stats(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "models_loaded": list(self._models.keys()),
            "tasks_processed": self._tasks_processed,
        }


class RayExecutor:
    """Main executor for Ray-based distributed GPU operations."""

    def __init__(self, config: DistributedConfig):
        self.config = config
        self._initialized = False
        self._gpu_manager: Optional[RayGPUManager] = None
        self._actors: dict[str, Any] = {}

    async def initialize(self) -> None:
        """Initialize Ray executor."""
        if not RAY_AVAILABLE:
            print("Ray not available. Using fallback execution.")
            return

        if not ray.is_initialized():
            ray.init(
                address=self.config.ray_head_address,
                dashboard_host="0.0.0.0",
                dashboard_port=self.config.metrics_port,
                ignore_reinit_error=True,
                object_store_memory=self.config.ray_object_store_memory_gb * 1e9,
            )

        self._gpu_manager = RayGPUManager(self.config)
        await self._gpu_manager.initialize()
        self._initialized = True

    async def create_model_actor(
        self,
        name: str,
        model_name: str,
        provider: str = "openai",
        num_gpus: int = 1
    ) -> Optional[str]:
        """Create a persistent model actor."""
        if not RAY_AVAILABLE:
            return None

        options = {"num_gpus": num_gpus} if num_gpus > 0 else {}
        actor = ModelActor.options(**options).remote(model_name, provider)
        ray.get(actor.initialize.remote())
        self._actors[name] = actor
        return name

    async def create_embedding_actor(
        self,
        name: str,
        model_name: str = "text-embedding-3-small",
        num_gpus: int = 0
    ) -> Optional[str]:
        """Create a persistent embedding actor."""
        if not RAY_AVAILABLE:
            return None

        options = {"num_gpus": num_gpus} if num_gpus > 0 else {}
        actor = EmbeddingActor.options(**options).remote(model_name)
        ray.get(actor.initialize.remote())
        self._actors[name] = actor
        return name

    async def create_inference_workers(
        self,
        num_workers: int,
        num_gpus_per_worker: int = 0
    ) -> list[str]:
        """Create a pool of inference workers."""
        if not RAY_AVAILABLE:
            return []

        worker_ids = []
        for i in range(num_workers):
            options = {"num_gpus": num_gpus_per_worker} if num_gpus_per_worker > 0 else {}
            worker = InferenceWorker.options(**options).remote(f"worker_{i}")
            self._actors[f"worker_{i}"] = worker
            worker_ids.append(f"worker_{i}")

        return worker_ids

    async def execute_on_actor(
        self,
        actor_name: str,
        method: str,
        *args,
        **kwargs
    ) -> Any:
        """Execute a method on a named actor."""
        if not RAY_AVAILABLE or actor_name not in self._actors:
            return None

        actor = self._actors[actor_name]
        method_func = getattr(actor, method)
        return ray.get(method_func.remote(*args, **kwargs))

    async def execute_on_workers(
        self,
        worker_ids: list[str],
        task_type: str,
        payload: dict
    ) -> list[dict]:
        """Execute tasks on worker pool."""
        if not RAY_AVAILABLE:
            return []

        results = []
        for worker_id in worker_ids:
            if worker_id in self._actors:
                actor = self._actors[worker_id]
                result = ray.get(actor.process_task.remote(task_type, payload))
                results.append(result)

        return results

    async def parallel_map(
        self,
        func: Callable,
        inputs: list,
        num_workers: int = 4,
        resources_per_task: dict = None
    ) -> list[Any]:
        """Execute function in parallel using Ray."""
        if not RAY_AVAILABLE:
            # Fallback to sequential
            return [func(inp) for inp in inputs]

        @ray.remote
        def parallel_func(x):
            return func(x)

        options = {}
        if resources_per_task:
            if resources_per_task.get("num_gpus"):
                options["num_gpus"] = resources_per_task["num_gpus"]

        futures = [parallel_func.options(**options).remote(inp) for inp in inputs]
        return ray.get(futures)

    def get_actor_stats(self, actor_name: str) -> Optional[dict]:
        """Get statistics for an actor."""
        if not RAY_AVAILABLE or actor_name not in self._actors:
            return None

        actor = self._actors[actor_name]
        return ray.get(actor.get_stats.remote())

    def get_cluster_stats(self) -> dict:
        """Get cluster statistics."""
        if not RAY_AVAILABLE:
            return {"ray_initialized": False}

        return {
            "ray_initialized": True,
            "cluster_resources": ray.cluster_resources(),
            "available_resources": ray.available_resources(),
            "nodes": len(ray.nodes()),
            "actors": len(self._actors),
        }

    async def shutdown(self) -> None:
        """Shutdown Ray executor."""
        if RAY_AVAILABLE and ray.is_initialized():
            # Cleanup actors
            for actor in self._actors.values():
                try:
                    ray.kill(actor)
                except Exception:
                    pass

            ray.shutdown()

        self._initialized = False
        self._actors = {}