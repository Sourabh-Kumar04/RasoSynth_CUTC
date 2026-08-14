"""
Event-Driven Coordination

Redis Pub/Sub and Streams for distributed agent communication,
event broadcasting, workflow triggering, and real-time coordination.
"""

from typing import Dict, List, Optional, Any, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import uuid


class EventType(Enum):
    """System event types."""
    # Pipeline events
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"
    STAGE_COMPLETED = "stage.completed"

    # Data events
    DATA_READY = "data.ready"
    DATA_PROCESSED = "data.processed"
    DATASET_COMPLETED = "dataset.completed"

    # Agent events
    AGENT_REGISTERED = "agent.registered"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"
    AGENT_IDLE = "agent.idle"

    # Resource events
    GPU_AVAILABLE = "gpu.available"
    GPU_BUSY = "gpu.busy"
    WORKER_AVAILABLE = "worker.available"

    # Quality events
    QUALITY_CHECK_PASSED = "quality.passed"
    QUALITY_CHECK_FAILED = "quality.failed"
    VALIDATION_FAILED = "validation.failed"

    # Custom
    CUSTOM = "custom"


@dataclass
class Event:
    """A system event."""
    event_id: str
    event_type: EventType
    source: str  # Agent ID, pipeline ID, etc.
    timestamp: datetime
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "metadata": self.metadata,
            "correlation_id": self.correlation_id
        }


class EventBus:
    """Central event bus for system-wide event handling."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000

    async def publish(
        self,
        event_type: EventType,
        source: str,
        data: Any,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """Publish an event."""
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            timestamp=datetime.utcnow(),
            data=data,
            correlation_id=correlation_id,
            metadata=metadata or {}
        )

        # Store in event history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Publish to Redis
        channel = f"events:{event_type.value}"
        await self.redis.publish(channel, json.dumps(event.to_dict(), default=str))

        # Trigger handlers
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                pass

        return event.event_id

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable
    ) -> None:
        """Subscribe to an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable
    ) -> bool:
        """Unsubscribe from an event type."""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False

    async def subscribe_redis(
        self,
        event_type: EventType,
        callback: Callable
    ) -> None:
        """Subscribe to Redis channel for event type."""
        pubsub = self.redis.pubsub()
        channel = f"events:{event_type.value}"
        await pubsub.subscribe(channel)

        async def listener():
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        event = Event(
                            event_id=event_data["event_id"],
                            event_type=EventType(event_data["event_type"]),
                            source=event_data["source"],
                            timestamp=datetime.fromisoformat(event_data["timestamp"]),
                            data=event_data["data"],
                            correlation_id=event_data.get("correlation_id"),
                            metadata=event_data.get("metadata", {})
                        )
                        await callback(event)
                    except Exception:
                        pass

        asyncio.create_task(listener())

    def get_history(
        self,
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get event history."""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]


class PubSubManager:
    """Redis Pub/Sub manager for real-time messaging."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._channels: Dict[str, Set[str]] = {}
        self._subscribers: Dict[str, Dict[str, Callable]] = {}

    async def publish(
        self,
        channel: str,
        message: Any
    ) -> int:
        """Publish message to channel."""
        data = json.dumps({
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": str(uuid.uuid4())
        }, default=str)

        count = await self.redis.publish(channel, data)
        return count

    async def subscribe(
        self,
        channel: str,
        handler: Callable,
        subscriber_id: Optional[str] = None
    ) -> None:
        """Subscribe to a channel."""
        if subscriber_id is None:
            subscriber_id = str(uuid.uuid4())

        if channel not in self._subscribers:
            self._subscribers[channel] = {}

        self._subscribers[channel][subscriber_id] = handler

        if channel not in self._channels:
            self._channels[channel] = set()

        self._channels[channel].add(subscriber_id)

        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        asyncio.create_task(self._listen(channel, pubsub, subscriber_id))

    async def _listen(
        self,
        channel: str,
        pubsub: Any,
        subscriber_id: str
    ) -> None:
        """Listen for messages on channel."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        handler = self._subscribers.get(channel, {}).get(subscriber_id)
                        if handler:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(data)
                            else:
                                handler(data)
                    except Exception:
                        pass
        except Exception:
            pass

    async def unsubscribe(
        self,
        channel: str,
        subscriber_id: str
    ) -> bool:
        """Unsubscribe from a channel."""
        if channel in self._subscribers:
            if subscriber_id in self._subscribers[channel]:
                del self._subscribers[channel][subscriber_id]
                return True
        return False

    async def get_subscriber_count(self, channel: str) -> int:
        """Get number of subscribers."""
        return len(self._channels.get(channel, set()))


class StreamProcessor:
    """Redis Streams processor for ordered event processing."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._consumers: Dict[str, Dict] = {}
        self._groups: Dict[str, Set[str]] = {}

    async def create_stream(
        self,
        stream_name: str,
        consumer_group: Optional[str] = None
    ) -> None:
        """Create a stream with optional consumer group."""
        if consumer_group:
            try:
                await self.redis.xgroup_create(
                    stream_name,
                    consumer_group,
                    id="0",
                    mkstream=True
                )
            except Exception:
                pass  # Group might already exist

    async def add_to_stream(
        self,
        stream_name: str,
        data: Dict[str, Any],
        max_len: int = 10000
    ) -> str:
        """Add entry to stream."""
        entry_id = await self.redis.xadd(
            stream_name,
            {**data, "timestamp": datetime.utcnow().isoformat()},
            maxlen=max_len,
            approximate=True
        )
        return entry_id

    async def read_from_stream(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 5000
    ) -> List[Dict]:
        """Read from stream using consumer group."""
        try:
            results = await self.redis.xreadgroup(
                consumer_group,
                consumer_name,
                [stream_name],
                count=count,
                block=block_ms
            )

            entries = []
            if results:
                for stream, messages in results:
                    for msg_id, data in messages:
                        entries.append({
                            "id": msg_id,
                            "data": data,
                            "stream": stream
                        })

            return entries

        except Exception:
            return []

    async def acknowledge(
        self,
        stream_name: str,
        consumer_group: str,
        message_id: str
    ) -> bool:
        """Acknowledge message processing."""
        try:
            await self.redis.xack(stream_name, consumer_group, message_id)
            return True
        except Exception:
            return False

    async def get_stream_info(
        self,
        stream_name: str
    ) -> Dict[str, Any]:
        """Get stream information."""
        try:
            info = await self.redis.xinfo_stream(stream_name)
            return dict(info) if info else {}
        except Exception:
            return {}

    async def delete_from_stream(
        self,
        stream_name: str,
        message_ids: List[str]
    ) -> int:
        """Delete messages from stream."""
        if not message_ids:
            return 0
        return await self.redis.xdel(stream_name, *message_ids)


class DistributedLockManager:
    """Distributed locking with Redis."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._locks: Dict[str, Dict] = {}
        self._acquired: Set[str] = set()

    async def acquire(
        self,
        lock_name: str,
        timeout: float = 10.0,
        ttl: float = 30.0,
        holder_id: Optional[str] = None
    ) -> bool:
        """Acquire a distributed lock."""
        if holder_id is None:
            holder_id = str(uuid.uuid4())

        lock_key = f"lock:{lock_name}"

        # Try to acquire with NX (only if not exists)
        acquired = await self.redis.set(
            lock_key,
            holder_id,
            nx=True,
            ex=int(ttl)
        )

        if acquired:
            self._locks[lock_name] = {
                "holder_id": holder_id,
                "acquired_at": datetime.utcnow(),
                "ttl": ttl
            }
            self._acquired.add(lock_name)
            return True

        # Check if we already hold it
        current_holder = await self.redis.get(lock_key)
        if current_holder == holder_id:
            self._locks[lock_name] = {
                "holder_id": holder_id,
                "acquired_at": datetime.utcnow(),
                "ttl": ttl
            }
            self._acquired.add(lock_name)
            return True

        # Wait for lock
        start = datetime.utcnow()
        while (datetime.utcnow() - start).total_seconds() < timeout:
            acquired = await self.redis.set(
                lock_key,
                holder_id,
                nx=True,
                ex=int(ttl)
            )
            if acquired:
                self._locks[lock_name] = {
                    "holder_id": holder_id,
                    "acquired_at": datetime.utcnow(),
                    "ttl": ttl
                }
                self._acquired.add(lock_name)
                return True
            await asyncio.sleep(0.1)

        return False

    async def release(
        self,
        lock_name: str,
        holder_id: Optional[str] = None
    ) -> bool:
        """Release a distributed lock."""
        lock_key = f"lock:{lock_name}"

        if holder_id:
            current = await self.redis.get(lock_key)
            if current != holder_id:
                return False

        result = await self.redis.delete(lock_key)
        if result:
            self._locks.pop(lock_name, None)
            self._acquired.discard(lock_name)
            return True

        return False

    async def extend(
        self,
        lock_name: str,
        ttl: float = 30.0,
        holder_id: Optional[str] = None
    ) -> bool:
        """Extend lock TTL."""
        lock_key = f"lock:{lock_name}"

        current = await self.redis.get(lock_key)
        if not current:
            return False

        if holder_id and current != holder_id:
            return False

        await self.redis.expire(lock_key, int(ttl))

        if lock_name in self._locks:
            self._locks[lock_name]["ttl"] = ttl

        return True

    async def is_locked(self, lock_name: str) -> bool:
        """Check if lock is held."""
        return await self.redis.exists(f"lock:{lock_name}") > 0


class RateLimitProtector:
    """Rate limiting and cost protection."""

    def __init__(self, redis_client: Any):
        self.redis = redis_client
        self._limits: Dict[str, Dict] = {}

    async def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: float,
        increment: int = 1
    ) -> Tuple[bool, int]:
        """Check if request is within rate limit."""
        rate_key = f"ratelimit:{key}"

        count = await self.redis.get(rate_key)
        current = int(count) if count else 0

        if current >= max_requests:
            return False, max_requests - current

        pipe = self.redis.pipeline()
        pipe.incrby(rate_key, increment)
        pipe.expire(rate_key, int(window_seconds))
        await pipe.execute()

        new_count = current + increment
        return True, max_requests - new_count

    async def get_remaining(
        self,
        key: str,
        max_requests: int
    ) -> int:
        """Get remaining requests."""
        rate_key = f"ratelimit:{key}"
        count = await self.redis.get(rate_key)
        current = int(count) if count else 0
        return max(0, max_requests - current)

    async def reset_limit(self, key: str) -> None:
        """Reset rate limit."""
        rate_key = f"ratelimit:{key}"
        await self.redis.delete(rate_key)

    async def set_provider_cooldown(
        self,
        provider: str,
        cooldown_seconds: float
    ) -> None:
        """Set provider cooldown period."""
        cooldown_key = f"cooldown:{provider}"
        await self.redis.setex(cooldown_key, cooldown_seconds, "1")

    async def is_provider_on_cooldown(self, provider: str) -> bool:
        """Check if provider is on cooldown."""
        cooldown_key = f"cooldown:{provider}"
        return await self.redis.exists(cooldown_key) > 0

    async def get_cooldown_remaining(self, provider: str) -> float:
        """Get remaining cooldown time."""
        cooldown_key = f"cooldown:{provider}"
        ttl = await self.redis.ttl(cooldown_key)
        return ttl if ttl > 0 else 0.0

    async def track_token_usage(
        self,
        provider: str,
        tokens_used: int,
        daily_limit: int
    ) -> Tuple[bool, int]:
        """Track daily token usage."""
        date = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"tokens:{provider}:{date}"

        current = await self.redis.get(key)
        used = int(current) if current else 0
        new_total = used + tokens_used

        if new_total > daily_limit:
            return False, daily_limit - used

        await self.redis.set(key, new_total, ex=86400)
        return True, daily_limit - new_total

    async def get_token_usage(self, provider: str) -> Dict[str, int]:
        """Get today's token usage."""
        date = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"tokens:{provider}:{date}"

        used = await self.redis.get(key)
        return {
            "date": date,
            "tokens_used": int(used) if used else 0
        }