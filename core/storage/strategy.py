"""
Intelligent Delivery Strategy Selection

Automatically selects optimal delivery strategy based on dataset and user requirements.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from core.storage.base import DeliveryStrategy, StorageProviderType


@dataclass
class StrategyCriteria:
    """Criteria for strategy selection."""
    dataset_size_bytes: int
    dataset_type: str = "jsonl"
    modality: str = "text"  # text, image, video, multimodal
    user_bandwidth_mbps: float = 100.0
    geographic_regions: list[str] = field(default_factory=list)
    cost_budget_usd: float = 100.0
    urgency: str = "normal"  # low, normal, high
    privacy_level: str = "private"  # public, private, sensitive
    update_frequency: str = "one_time"  # one_time, daily, weekly, continuous
    storage_providers: list[StorageProviderType] = field(default_factory=list)


@dataclass
class StrategyRecommendation:
    """Recommended delivery strategy."""
    strategy: DeliveryStrategy
    reasoning: list[str]
    estimated_time_minutes: float
    estimated_cost_usd: float
    recommended_chunk_size_mb: int
    compression_recommended: str
    fallback_strategies: list[DeliveryStrategy]
    warnings: list[str] = field(default_factory=list)


class DeliveryStrategySelector:
    """Intelligently select optimal delivery strategy."""

    # Size thresholds in bytes
    DIRECT_THRESHOLD = 1 * 1024 * 1024 * 1024  # 1GB
    ARCHIVE_THRESHOLD = 20 * 1024 * 1024 * 1024  # 20GB
    CLOUD_THRESHOLD = 1000 * 1024 * 1024 * 1024  # 1TB

    def __init__(self):
        self._history: list[dict] = []

    def select_strategy(
        self,
        criteria: StrategyCriteria
    ) -> StrategyRecommendation:
        """Select optimal delivery strategy based on criteria."""

        reasoning = []
        warnings = []
        fallback_strategies = []

        size_gb = criteria.dataset_size_bytes / (1024**3)
        size_mb = criteria.dataset_size_bytes / (1024**2)

        # Base strategy selection on size
        if criteria.dataset_size_bytes < self.DIRECT_THRESHOLD:
            strategy = DeliveryStrategy.DIRECT_DOWNLOAD
            reasoning.append(f"Dataset ({size_gb:.2f}GB) is small enough for direct download")

        elif criteria.dataset_size_bytes < self.ARCHIVE_THRESHOLD:
            strategy = DeliveryStrategy.COMPRESSED_ARCHIVE
            reasoning.append(f"Dataset ({size_gb:.2f}GB) benefits from compression")

        elif criteria.dataset_size_bytes < self.CLOUD_THRESHOLD:
            strategy = DeliveryStrategy.CLOUD_STORAGE
            reasoning.append(f"Dataset ({size_gb:.2f}GB) requires cloud storage with chunking")

        else:
            strategy = DeliveryStrategy.DISTRIBUTED_STREAM
            reasoning.append(f"Dataset ({size_gb:.2f}GB) requires distributed streaming")
            warnings.append("Very large dataset - consider data sampling for initial use")

        # Adjust for update frequency
        if criteria.update_frequency != "one_time":
            reasoning.append(f"Dataset updates ({criteria.update_frequency}) - using registry sync")
            strategy = DeliveryStrategy.REGISTRY_SYNC

            if criteria.update_frequency == "continuous":
                warnings.append("Continuous updates require additional infrastructure")

        # Adjust for privacy
        if criteria.privacy_level == "sensitive":
            reasoning.append("Sensitive data - enhanced encryption and access control required")
            warnings.append("Encryption may increase processing time")

        # Adjust for urgency
        if criteria.urgency == "high" and criteria.dataset_size_bytes > self.ARCHIVE_THRESHOLD:
            reasoning.append("High urgency - prioritizing speed over compression")
            # Consider using faster compression
            fallback_strategies = [DeliveryStrategy.CLOUD_STORAGE]

        # Adjust for cost budget
        if criteria.cost_budget_usd < 10 and criteria.dataset_size_bytes > self.ARCHIVE_THRESHOLD:
            warnings.append("Low budget for large dataset - consider free storage tiers")
            fallback_strategies.append(DeliveryStrategy.CLOUD_STORAGE)

        # Multiple destinations
        if len(criteria.storage_providers) > 1:
            strategy = DeliveryStrategy.MULTI_DESTINATION
            reasoning.append(f"Multiple destinations configured ({len(criteria.storage_providers)})")

        # Estimate time and cost
        estimated_time = self._estimate_time(criteria, strategy)
        estimated_cost = self._estimate_cost(criteria, strategy)

        # Determine chunk size
        chunk_size = self._determine_chunk_size(criteria, strategy)

        # Determine compression
        compression = self._determine_compression(criteria, strategy)

        return StrategyRecommendation(
            strategy=strategy,
            reasoning=reasoning,
            estimated_time_minutes=estimated_time,
            estimated_cost_usd=estimated_cost,
            recommended_chunk_size_mb=chunk_size,
            compression_recommended=compression,
            fallback_strategies=fallback_strategies,
            warnings=warnings
        )

    def _estimate_time(
        self,
        criteria: StrategyCriteria,
        strategy: DeliveryStrategy
    ) -> float:
        """Estimate delivery time in minutes."""
        size_mb = criteria.dataset_size_bytes / (1024**2)
        bandwidth_mbps = criteria.user_bandwidth_mbps

        if strategy == DeliveryStrategy.DIRECT_DOWNLOAD:
            # Direct download time
            return (size_mb / 1024) / bandwidth_mbps * 60

        elif strategy == DeliveryStrategy.COMPRESSED_ARCHIVE:
            # Compressed + download
            compression_overhead = 1.5  # Compression adds 50% time
            upload_time = (size_mb / 1024) / 50  # Assume 50 Mbps upload
            download_time = (size_mb / 1024) / bandwidth_mbps
            return (compression_overhead * upload_time) + download_time

        elif strategy == DeliveryStrategy.CLOUD_STORAGE:
            # Chunked upload/download
            chunks = size_mb / 500  # 500MB chunks
            return chunks * 2  # Upload + download per chunk

        else:
            # Distributed/streaming
            return size_mb / 100 / bandwidth_mbps * 60  # Streaming at lower speed

    def _estimate_cost(
        self,
        criteria: StrategyCriteria,
        strategy: DeliveryStrategy
    ) -> float:
        """Estimate delivery cost in USD."""
        size_gb = criteria.dataset_size_bytes / (1024**3)

        if strategy == DeliveryStrategy.DIRECT_DOWNLOAD:
            return 0  # Direct download is free

        elif strategy == DeliveryStrategy.COMPRESSED_ARCHIVE:
            # Cloud storage for temporary hosting
            return size_gb * 0.01  # $0.01/GB

        elif strategy == DeliveryStrategy.CLOUD_STORAGE:
            # S3/GCS storage + transfer
            storage_cost = size_gb * 0.023  # S3 standard
            transfer_cost = size_gb * 0.09  # Data transfer
            return storage_cost + transfer_cost

        else:
            # Distributed - multiple storage costs
            return size_gb * 0.05  # Estimated

    def _determine_chunk_size(
        self,
        criteria: StrategyCriteria,
        strategy: DeliveryStrategy
    ) -> int:
        """Determine optimal chunk size in MB."""
        size_gb = criteria.dataset_size_bytes / (1024**3)

        if strategy == DeliveryStrategy.DIRECT_DOWNLOAD:
            return 0  # No chunking

        elif strategy == DeliveryStrategy.COMPRESSED_ARCHIVE:
            if size_gb < 5:
                return 100
            return 500

        elif strategy == DeliveryStrategy.CLOUD_STORAGE:
            if size_gb > 100:
                return 1000  # 1GB chunks for very large
            return 500

        else:
            # Streaming - smaller chunks for responsiveness
            return 100

    def _determine_compression(
        self,
        criteria: StrategyCriteria,
        strategy: DeliveryStrategy
    ) -> str:
        """Determine optimal compression."""
        if criteria.urgency == "high":
            return "gzip"  # Faster compression

        if criteria.modality == "text":
            return "zstd"  # Better compression for text

        if criteria.dataset_type in ["parquet", "arrow"]:
            return "none"  # Already compressed

        return "zstd"  # Default

    def log_selection(
        self,
        criteria: StrategyCriteria,
        recommendation: StrategyRecommendation
    ) -> None:
        """Log strategy selection for learning."""
        self._history.append({
            "timestamp": datetime.utcnow(),
            "criteria": {
                "size_bytes": criteria.dataset_size_bytes,
                "dataset_type": criteria.dataset_type,
                "user_bandwidth_mbps": criteria.user_bandwidth_mbps,
            },
            "selected_strategy": recommendation.strategy.value,
            "actual_outcome": None  # Would be updated after delivery
        })

    def get_selection_history(self) -> list[dict]:
        """Get strategy selection history."""
        return self._history


class SmartRouter:
    """Route datasets to optimal destinations."""

    def __init__(self, strategy_selector: DeliveryStrategySelector):
        self.strategy_selector = strategy_selector
        self._routing_rules: list[dict] = []

    def add_routing_rule(
        self,
        condition: dict,
        destination: StorageProviderType,
        priority: int = 0
    ) -> None:
        """Add a routing rule."""
        self._routing_rules.append({
            "condition": condition,
            "destination": destination,
            "priority": priority
        })
        self._routing_rules.sort(key=lambda x: x["priority"], reverse=True)

    def route(
        self,
        dataset_id: str,
        criteria: StrategyCriteria
    ) -> list[tuple[StorageProviderType, DeliveryStrategy]]:
        """Determine routing for a dataset."""
        results = []

        # Check routing rules first
        for rule in self._routing_rules:
            if self._matches_condition(criteria, rule["condition"]):
                recommendation = self.strategy_selector.select_strategy(criteria)
                results.append((rule["destination"], recommendation.strategy))

        # If no rules match, use default
        if not results:
            recommendation = self.strategy_selector.select_strategy(criteria)

            # Default routing based on criteria
            if criteria.storage_providers:
                for provider in criteria.storage_providers:
                    results.append((provider, recommendation.strategy))
            else:
                # Default to S3
                results.append((StorageProviderType.AWS_S3, recommendation.strategy))

        return results

    def _matches_condition(
        self,
        criteria: StrategyCriteria,
        condition: dict
    ) -> bool:
        """Check if criteria matches condition."""
        for key, value in condition.items():
            criteria_value = getattr(criteria, key, None)
            if criteria_value is None:
                return False

            if isinstance(value, list):
                if criteria_value not in value:
                    return False
            elif criteria_value != value:
                return False

        return True

    def optimize_routing(
        self,
        dataset_id: str,
        success_metrics: dict
    ) -> None:
        """Optimize routing based on success metrics."""
        # Analyze success metrics and adjust routing rules
        if success_metrics.get("failure_rate", 0) > 0.1:
            # Reduce priority for failing destinations
            pass  # Would implement adjustment logic