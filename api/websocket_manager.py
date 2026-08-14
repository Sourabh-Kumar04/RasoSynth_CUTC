"""Production-grade WebSocket manager with Redis pub/sub support."""
import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types."""
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LOG = "log"
    METRIC = "metric"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class WebSocketMessage:
    """Structured WebSocket message."""
    type: MessageType
    job_id: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class ConnectionManager:
    """Centralized WebSocket connection manager with Redis pub/sub."""

    def __init__(self, redis_url: Optional[str] = None):
        # Active connections by job_id
        self._connections: Dict[str, Set[Any]] = {}
        # Connection metadata
        self._connection_metadata: Dict[str, Dict[str, Any]] = {}
        # Redis for distributed broadcasting
        self._redis_url = redis_url
        self._redis_client = None
        self._pubsub_task: Optional[asyncio.Task] = None
        # Message handlers
        self._handlers: Dict[MessageType, List[Callable]] = {
            msg_type: [] for msg_type in MessageType
        }
        # Heartbeat configuration
        self._heartbeat_interval = 30  # seconds
        self._connection_timeouts: Dict[str, float] = {}
        self._connection_websockets: Dict[str, Any] = {}  # connection_id -> websocket
        self._cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize Redis connection for distributed messaging."""
        if self._redis_url:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                # Test connection
                await self._redis_client.ping()
                logger.info("WebSocket Redis connection established")

                # Start listening for broadcast messages
                self._pubsub_task = asyncio.create_task(self._listen_broadcasts())
            except Exception as e:
                logger.warning(f"Redis unavailable for WebSocket: {e}")
                self._redis_client = None

        # Start periodic cleanup of stale connections
        self._start_cleanup_task()

    async def _listen_broadcasts(self) -> None:
        """Listen for messages from Redis pub/sub (for distributed workers).

        Includes automatic reconnection on Redis connection drops (R7 fix).
        """
        while True:
            try:
                if not self._redis_client:
                    logger.debug("Redis client not available, waiting 5s before retry")
                    await asyncio.sleep(5)
                    continue

                pubsub = self._redis_client.pubsub()
                await pubsub.subscribe("ws:broadcast")
                logger.info("Subscribed to ws:broadcast")

                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        await self._handle_broadcast_message(data)
            except asyncio.CancelledError:
                logger.info("Redis pubsub listener cancelled")
                break
            except Exception as e:
                logger.warning(f"Redis pubsub error (reconnecting in 5s): {e}")
                await asyncio.sleep(5)

    async def _handle_broadcast_message(self, data: Dict[str, Any]) -> None:
        """Handle incoming broadcast from Redis."""
        job_id = data.get("job_id")
        if job_id and job_id in self._connections:
            await self._broadcast_to_connections(job_id, data)

    async def connect(self, websocket: Any, job_id: str) -> str:
        """Register a new WebSocket connection."""
        connection_id = str(uuid.uuid4())

        if job_id not in self._connections:
            self._connections[job_id] = set()

        self._connections[job_id].add(websocket)
        self._connection_metadata[connection_id] = {
            "job_id": job_id,
            "connected_at": datetime.utcnow(),
            "last_heartbeat": datetime.utcnow()
        }
        self._connection_timeouts[connection_id] = datetime.utcnow().timestamp()
        self._connection_websockets[connection_id] = websocket

        logger.info(f"WebSocket connected: {connection_id} for job {job_id}")

        # Send connection confirmation
        await self.send_personal_message(
            websocket,
            WebSocketMessage(
                type=MessageType.HEARTBEAT,
                job_id=job_id,
                data={"connection_id": connection_id, "status": "connected"}
            )
        )

        return connection_id

    async def disconnect(self, websocket: Any, job_id: str, connection_id: str) -> None:
        """Unregister a WebSocket connection."""
        if job_id in self._connections:
            self._connections[job_id].discard(websocket)

            # Clean up empty job connections
            if not self._connections[job_id]:
                del self._connections[job_id]

        if connection_id in self._connection_metadata:
            del self._connection_metadata[connection_id]

        if connection_id in self._connection_timeouts:
            del self._connection_timeouts[connection_id]

        if connection_id in self._connection_websockets:
            del self._connection_websockets[connection_id]

        logger.info(f"WebSocket disconnected: {connection_id}")

    async def send_personal_message(self, websocket: Any, message: WebSocketMessage) -> bool:
        """Send message to a specific WebSocket."""
        try:
            await websocket.send_json(message.__dict__)
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def send_to_job(self, job_id: str, message: WebSocketMessage) -> int:
        """Send message to all connections for a job."""
        # Store in Redis for persistence/distribution
        if self._redis_client and job_id in self._connections:
            try:
                await self._redis_client.publish(
                    "ws:broadcast",
                    json.dumps({
                        "job_id": job_id,
                        **message.__dict__,
                        "timestamp": message.timestamp.isoformat()
                    })
                )
            except Exception as e:
                logger.warning(f"Redis publish failed: {e}")

        return await self._broadcast_to_connections(job_id, message.__dict__)

    async def _broadcast_to_connections(self, job_id: str, message_data: Dict[str, Any]) -> int:
        """Broadcast message to all connections for a job."""
        sent_count = 0

        if job_id not in self._connections:
            return 0

        # Create list to avoid modification during iteration
        dead_connections = []

        for websocket in list(self._connections[job_id]):
            try:
                await websocket.send_json(message_data)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                dead_connections.append(websocket)

        # Remove dead connections
        for ws in dead_connections:
            self._connections[job_id].discard(ws)

        return sent_count

    async def broadcast_progress(
        self,
        job_id: str,
        stage: str,
        progress: float,
        samples_generated: int,
        metadata: Optional[Dict] = None
    ) -> int:
        """Broadcast progress update to all job connections."""
        message = WebSocketMessage(
            type=MessageType.PROGRESS,
            job_id=job_id,
            data={
                "stage": stage,
                "progress": progress,
                "samples_generated": samples_generated,
                "metadata": metadata or {}
            }
        )
        return await self.send_to_job(job_id, message)

    async def broadcast_completion(
        self,
        job_id: str,
        samples_generated: int,
        output_path: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """Broadcast job completion."""
        message = WebSocketMessage(
            type=MessageType.COMPLETED,
            job_id=job_id,
            data={
                "samples_generated": samples_generated,
                "output_path": output_path,
                "metadata": metadata or {}
            }
        )
        return await self.send_to_job(job_id, message)

    async def broadcast_failure(
        self,
        job_id: str,
        error: str,
        stage: Optional[str] = None
    ) -> int:
        """Broadcast job failure."""
        message = WebSocketMessage(
            type=MessageType.FAILED,
            job_id=job_id,
            data={
                "error": error,
                "stage": stage
            }
        )
        return await self.send_to_job(job_id, message)

    async def broadcast_log(
        self,
        job_id: str,
        log_message: str,
        level: str = "info"
    ) -> int:
        """Broadcast log message."""
        message = WebSocketMessage(
            type=MessageType.LOG,
            job_id=job_id,
            data={
                "message": log_message,
                "level": level
            }
        )
        return await self.send_to_job(job_id, message)

    def get_connection_count(self, job_id: Optional[str] = None) -> int:
        """Get number of active connections."""
        if job_id:
            return len(self._connections.get(job_id, set()))
        return sum(len(conns) for conns in self._connections.values())

    def get_active_jobs(self) -> List[str]:
        """Get list of jobs with active connections."""
        return list(self._connections.keys())

    async def health_check(self) -> Dict[str, Any]:
        """Health check for WebSocket manager."""
        return {
            "status": "healthy",
            "total_connections": self.get_connection_count(),
            "active_jobs": len(self._connections),
            "redis_connected": self._redis_client is not None
        }

    async def touch_connection(self, connection_id: str) -> None:
        """Update the last heartbeat time for a connection."""
        self._connection_timeouts[connection_id] = datetime.utcnow().timestamp()

    async def cleanup_stale_connections(self) -> int:
        """Remove connections that haven't sent heartbeat within threshold."""
        now = datetime.utcnow().timestamp()
        timeout_threshold = self._heartbeat_interval * 3
        removed_count = 0

        stale_connection_ids = [
            conn_id for conn_id, last_time in self._connection_timeouts.items()
            if now - last_time > timeout_threshold
        ]

        for connection_id in stale_connection_ids:
            # Find and remove the websocket for this connection
            job_id = None
            if connection_id in self._connection_metadata:
                job_id = self._connection_metadata[connection_id].get("job_id")

            if job_id and job_id in self._connections:
                # Remove the specific stale websocket
                ws = self._connection_websockets.get(connection_id)
                if ws:
                    self._connections[job_id].discard(ws)

            # Clean up connection metadata, websockets, and timeouts
            if connection_id in self._connection_timeouts:
                del self._connection_timeouts[connection_id]
            if connection_id in self._connection_metadata:
                del self._connection_metadata[connection_id]
            if connection_id in self._connection_websockets:
                del self._connection_websockets[connection_id]

            removed_count += 1
            logger.info(f"Removed stale connection: {connection_id}")

        # Also clean up any empty job connection sets
        dead_jobs = [
            job_id for job_id, conns in self._connections.items()
            if not conns
        ]
        for job_id in dead_jobs:
            del self._connections[job_id]

        return removed_count

    def _start_cleanup_task(self) -> None:
        """Start the periodic cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None

        async def _cleanup_loop():
            while True:
                await asyncio.sleep(60)
                try:
                    removed = await self.cleanup_stale_connections()
                    if removed > 0:
                        logger.info(f"Cleaned up {removed} stale connections")
                except Exception as e:
                    logger.warning(f"Error in connection cleanup: {e}")

        self._cleanup_task = asyncio.create_task(_cleanup_loop())

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass

        if self._redis_client:
            await self._redis_client.close()

        self._connections.clear()
        logger.info("WebSocket manager shut down")


# Global connection manager instance
ws_manager: Optional[ConnectionManager] = None


async def get_ws_manager(redis_url: Optional[str] = None) -> ConnectionManager:
    """Get or create the global WebSocket manager."""
    global ws_manager

    if ws_manager is None:
        ws_manager = ConnectionManager(redis_url)
        await ws_manager.initialize()

    return ws_manager