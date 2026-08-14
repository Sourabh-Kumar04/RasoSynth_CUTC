"""
Agent Communication System

Message passing, event system, and shared memory for inter-agent communication.
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json


class MessageType(Enum):
    """Types of messages between agents."""
    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    QUERY = "query"
    RESPONSE = "response"
    EVENT = "event"
    HEARTBEAT = "heartbeat"
    COORDINATION = "coordination"
    BROADCAST = "broadcast"


@dataclass
class AgentMessage:
    """Message between agents."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""
    receivers: List[str] = field(default_factory=list)  # Can be multiple for broadcast
    message_type: MessageType = MessageType.TASK
    subject: str = ""
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    priority: int = 5
    ttl_seconds: float = 300.0

    def is_expired(self) -> bool:
        """Check if message has expired."""
        age = (datetime.utcnow() - self.timestamp).total_seconds()
        return age > self.ttl_seconds


class Event:
    """Events for pub/sub messaging."""
    def __init__(
        self,
        event_type: str,
        source: str,
        data: Any = None,
        timestamp: datetime = None
    ):
        self.event_type = event_type
        self.source = source
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()
        self.event_id = str(uuid.uuid4())


class EventSystem:
    """Event-driven pub/sub system for agents."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Unsubscribe from an event type."""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        self._event_history.append(event)

        # Trim history
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Notify subscribers
        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                pass

    def get_history(self, event_type: Optional[str] = None, limit: int = 100) -> List[Event]:
        """Get event history."""
        history = self._event_history
        if event_type:
            history = [e for e in history if e.event_type == event_type]
        return history[-limit:]


class MessageQueue:
    """Message queue for async message handling."""

    def __init__(self, max_size: int = 10000):
        self._queue: List[AgentMessage] = []
        self._max_size = max_size
        self._waiting: Dict[str, asyncio.Queue] = {}

    async def enqueue(self, message: AgentMessage) -> bool:
        """Add message to queue."""
        if len(self._queue) >= self._max_size:
            return False

        self._queue.append(message)

        # Notify waiting receivers
        if message.receiver in self._waiting:
            self._waiting[message.receiver].put_nowait(message)

        return True

    async def dequeue(self, receiver: str, timeout: float = 30.0) -> Optional[AgentMessage]:
        """Dequeue a message for a specific receiver."""
        if receiver not in self._waiting:
            self._waiting[receiver] = asyncio.Queue()

        try:
            return await asyncio.wait_for(
                self._waiting[receiver].get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Check regular queue
            for i, msg in enumerate(self._queue):
                if receiver in msg.receivers or msg.receiver == receiver:
                    return self._queue.pop(i)
            return None

    def peek(self, receiver: str) -> Optional[AgentMessage]:
        """Peek at next message without removing."""
        for msg in self._queue:
            if receiver in msg.receivers or msg.receiver == receiver:
                return msg
        return None

    def get_messages(self, receiver: str) -> List[AgentMessage]:
        """Get all messages for a receiver."""
        return [
            msg for msg in self._queue
            if receiver in msg.receivers or msg.receiver == receiver
        ]

    def remove_expired(self) -> int:
        """Remove expired messages."""
        initial = len(self._queue)
        self._queue = [msg for msg in self._queue if not msg.is_expired()]
        return initial - len(self._queue)

    def clear(self) -> None:
        """Clear all messages."""
        self._queue.clear()


class SharedMemory:
    """Shared memory for agent communication and state."""

    def __init__(self):
        self._memory: Dict[str, Any] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._watchers: Dict[str, List[Callable]] = {}
        self._history: Dict[str, List[Any]] = {}

    async def set(self, key: str, value: Any, notify: bool = True) -> None:
        """Set a value in shared memory."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()

        async with self._locks[key]:
            old_value = self._memory.get(key)
            self._memory[key] = value

            # Track history
            if key not in self._history:
                self._history[key] = []
            self._history[key].append({
                "timestamp": datetime.utcnow(),
                "value": value,
                "old_value": old_value,
            })

        # Notify watchers
        if notify and key in self._watchers:
            for watcher in self._watchers[key]:
                try:
                    if asyncio.iscoroutinefunction(watcher):
                        await watcher(key, value, old_value)
                    else:
                        watcher(key, value, old_value)
                except Exception:
                    pass

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a value from shared memory."""
        async with self._locks.get(key, asyncio.Lock()):
            return self._memory.get(key, default)

    async def delete(self, key: str) -> bool:
        """Delete a value from shared memory."""
        if key in self._memory:
            del self._memory[key]
            return True
        return False

    def watch(self, key: str, watcher: Callable) -> None:
        """Watch for changes to a key."""
        if key not in self._watchers:
            self._watchers[key] = []
        self._watchers[key].append(watcher)

    def unwatch(self, key: str, watcher: Callable) -> bool:
        """Stop watching a key."""
        if key in self._watchers:
            try:
                self._watchers[key].remove(watcher)
                return True
            except ValueError:
                pass
        return False

    def keys(self) -> List[str]:
        """Get all memory keys."""
        return list(self._memory.keys())

    def get_history(self, key: str, limit: int = 100) -> List[Dict]:
        """Get history for a key."""
        return self._history.get(key, [])[-limit:]

    def clear(self) -> None:
        """Clear all memory."""
        self._memory.clear()
        self._history.clear()


class AgentBus:
    """Central message bus for all agents."""

    def __init__(self):
        self.message_queue = MessageQueue()
        self.event_system = EventSystem()
        self.shared_memory = SharedMemory()
        self._agents: Dict[str, Any] = {}
        self._routing_rules: List[Dict] = []

    def register_agent(self, agent_id: str, agent: Any) -> None:
        """Register an agent with the bus."""
        self._agents[agent_id] = agent

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False

    async def send(
        self,
        sender: str,
        receiver: str,
        content: Any,
        message_type: MessageType = MessageType.TASK,
        subject: str = "",
        priority: int = 5
    ) -> AgentMessage:
        """Send a message to a specific agent."""
        message = AgentMessage(
            sender=sender,
            receivers=[receiver],
            message_type=message_type,
            subject=subject,
            content=content,
            priority=priority,
        )

        await self.message_queue.enqueue(message)

        # Publish event
        await self.event_system.publish(Event(
            event_type=f"message:{message_type.value}",
            source=sender,
            data=message.to_dict() if hasattr(message, 'to_dict') else {"receiver": receiver, "content": content},
        ))

        return message

    async def broadcast(
        self,
        sender: str,
        content: Any,
        message_type: MessageType = MessageType.BROADCAST,
        subject: str = "",
        priority: int = 1
    ) -> AgentMessage:
        """Broadcast a message to all agents."""
        message = AgentMessage(
            sender=sender,
            receivers=list(self._agents.keys()),
            message_type=message_type,
            subject=subject,
            content=content,
            priority=priority,
        )

        await self.message_queue.enqueue(message)

        return message

    async def publish_event(self, event_type: str, source: str, data: Any) -> None:
        """Publish an event."""
        await self.event_system.publish(Event(event_type, source, data))

    def add_routing_rule(
        self,
        condition: Callable[[AgentMessage], bool],
        action: Callable[[AgentMessage], None]
    ) -> None:
        """Add a routing rule."""
        self._routing_rules.append({
            "condition": condition,
            "action": action,
        })

    async def route_message(self, message: AgentMessage) -> None:
        """Route a message according to rules."""
        for rule in self._routing_rules:
            if rule["condition"](message):
                rule["action"](message)

    def get_connected_agents(self) -> List[str]:
        """Get list of connected agent IDs."""
        return list(self._agents.keys())