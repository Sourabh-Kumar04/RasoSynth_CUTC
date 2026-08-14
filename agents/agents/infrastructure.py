"""
Infrastructure Agents - GPU scheduling, storage, and distribution

Agents for managing GPU resources, storage optimization, and dataset
distribution across platforms.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from agents.base import Agent, AgentConfig, AgentType, AgentState, TaskResult, AgentContext


class GPUSchedulingAgent(Agent):
    """Agent for optimizing GPU allocation and scheduling."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._gpu_allocations: Dict[str, Any] = {}
        self._schedule_history: List[Dict] = []

    async def initialize(self) -> bool:
        """Initialize the GPU scheduling agent."""
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute GPU scheduling optimization."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"tasks": task}
            tasks = task_input.get("tasks", [])
            available_gpus = task_input.get("available_gpus", [{"id": 0, "memory_gb": 16}])
            strategy = task_input.get("strategy", "memory_balanced")

            schedule = await self._create_schedule(tasks, available_gpus, strategy)

            self._schedule_history.append({
                "tasks_count": len(tasks),
                "gpus_count": len(available_gpus),
                "strategy": strategy,
                "timestamp": datetime.utcnow().isoformat(),
            })

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "schedule": schedule["assignments"],
                    "utilization": schedule["utilization"],
                    "estimated_time": schedule["estimated_time"],
                },
                confidence=0.88,
                execution_time_ms=execution_time,
                metrics={
                    "tasks_scheduled": len(schedule["assignments"]),
                    "avg_utilization": schedule["avg_utilization"],
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

    async def _create_schedule(
        self,
        tasks: List[Dict],
        available_gpus: List[Dict],
        strategy: str
    ) -> Dict[str, Any]:
        """Create GPU schedule for tasks."""
        assignments = []
        utilization = []

        for i, task in enumerate(tasks[:100]):
            gpu_idx = i % len(available_gpus)
            gpu = available_gpus[gpu_idx]

            task_vram = task.get("vram_required_gb", 4)
            gpu_memory = gpu.get("memory_gb", 16)

            assignment = {
                "task_id": task.get("task_id", f"task_{i}"),
                "gpu_id": gpu["id"],
                "vram_allocated_gb": min(task_vram, gpu_memory),
                "estimated_duration_ms": task.get("estimated_duration_ms", 1000),
            }

            assignments.append(assignment)

        for gpu in available_gpus:
            gpu_tasks = [a for a in assignments if a["gpu_id"] == gpu["id"]]
            total_vram = sum(a["vram_allocated_gb"] for a in gpu_tasks)
            util = total_vram / gpu.get("memory_gb", 16)
            utilization.append({"gpu_id": gpu["id"], "utilization": util})

        avg_util = sum(u["utilization"] for u in utilization) / max(len(utilization), 1)
        total_time = sum(a["estimated_duration_ms"] for a in assignments)

        return {
            "assignments": assignments,
            "utilization": utilization,
            "avg_utilization": avg_util,
            "estimated_time": total_time / max(len(available_gpus), 1),
        }

    async def cleanup(self) -> None:
        """Cleanup GPU scheduling agent resources."""
        self._gpu_allocations.clear()
        self._schedule_history.clear()
        self.update_state(AgentState.TERMINATED)


class StorageOptimizationAgent(Agent):
    """Agent for dataset sharding and compression optimization."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._optimization_stats: Dict[str, Any] = {}

    async def initialize(self) -> bool:
        """Initialize the storage optimization agent."""
        self.update_state(AgentState.IDLE)
        self._optimization_stats = {
            "total_optimized_gb": 0,
            "compression_ratio": 1.0,
        }
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute storage optimization."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"dataset": task}
            dataset = task_input.get("dataset", [])
            compression_type = task_input.get("compression", "lz4")
            shard_size_mb = task_input.get("shard_size_mb", 100)

            results = await self._optimize_storage(dataset, compression_type, shard_size_mb)

            self._optimization_stats["total_optimized_gb"] += results["original_size_gb"]
            self._optimization_stats["compression_ratio"] = results["compression_ratio"]

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "shards": results["shards"],
                    "compression_ratio": results["compression_ratio"],
                    "total_size_gb": results["compressed_size_gb"],
                    "shard_count": len(results["shards"]),
                },
                confidence=0.9,
                execution_time_ms=execution_time,
                metrics={
                    "original_size_gb": results["original_size_gb"],
                    "compressed_size_gb": results["compressed_size_gb"],
                    "compression_ratio": results["compression_ratio"],
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

    async def _optimize_storage(
        self,
        dataset: List[Any],
        compression: str,
        shard_size_mb: int
    ) -> Dict[str, Any]:
        """Optimize storage with compression and sharding."""
        total_size_mb = len(dataset) * 0.1  # Simulated
        shard_size_samples = shard_size_mb * 10

        shards = []
        for i in range(0, len(dataset), shard_size_samples):
            shard_data = dataset[i:i + shard_size_samples]
            shard = {
                "shard_id": f"shard_{i // shard_size_samples}",
                "start_idx": i,
                "end_idx": min(i + shard_size_samples, len(dataset)),
                "sample_count": len(shard_data),
                "compressed_size_mb": len(shard_data) * 0.05,
            }
            shards.append(shard)

        compressed_size = sum(s["compressed_size_mb"] for s in shards)
        compression_ratio = total_size_mb / max(compressed_size, 0.1)

        return {
            "shards": shards,
            "original_size_gb": total_size_mb / 1024,
            "compressed_size_gb": compressed_size / 1024,
            "compression_ratio": compression_ratio,
            "compression_type": compression,
        }

    async def cleanup(self) -> None:
        """Cleanup storage optimization agent resources."""
        self.update_state(AgentState.TERMINATED)


class DistributionAgent(Agent):
    """Agent for managing dataset delivery to various platforms."""

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._distribution_history: List[Dict] = {}

    async def initialize(self) -> bool:
        """Initialize the distribution agent."""
        self.update_state(AgentState.IDLE)
        return True

    async def execute(self, task: Any, context: AgentContext) -> TaskResult:
        """Execute dataset distribution."""
        start_time = datetime.utcnow()
        self.update_state(AgentState.EXECUTING)

        try:
            task_input = task if isinstance(task, dict) else {"dataset": task}
            dataset = task_input.get("dataset", [])
            destinations = task_input.get("destinations", ["huggingface"])
            format_type = task_input.get("format", "parquet")

            results = await self._distribute_dataset(dataset, destinations, format_type)

            self._distribution_history.append({
                "dataset_size": len(dataset),
                "destinations": destinations,
                "timestamp": datetime.utcnow().isoformat(),
            })

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task_input.get("task_id", str(datetime.utcnow().timestamp())),
                agent_id=self.agent_id,
                success=True,
                output={
                    "destinations": results["results"],
                    "total_bytes": results["total_bytes"],
                    "failed_destinations": results["failed"],
                    "status": "completed",
                },
                confidence=0.92,
                execution_time_ms=execution_time,
                metrics={
                    "destinations_reached": len(results["results"]),
                    "total_bytes_transferred": results["total_bytes"],
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

    async def _distribute_dataset(
        self,
        dataset: List[Any],
        destinations: List[str],
        format_type: str
    ) -> Dict[str, Any]:
        """Distribute dataset to multiple destinations."""
        results = []
        failed = []
        total_bytes = 0

        for dest in destinations:
            try:
                result = {
                    "destination": dest,
                    "status": "success",
                    "bytes_transferred": len(dataset) * 100,
                    "endpoint": f"https://{dest}.com/datasets/uploaded",
                }
                results.append(result)
                total_bytes += result["bytes_transferred"]

            except Exception as e:
                failed.append({"destination": dest, "error": str(e)})

        return {
            "results": results,
            "failed": failed,
            "total_bytes": total_bytes,
            "format": format_type,
        }

    async def cleanup(self) -> None:
        """Cleanup distribution agent resources."""
        self._distribution_history.clear()
        self.update_state(AgentState.TERMINATED)