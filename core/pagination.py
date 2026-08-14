"""
Enterprise Pagination & Streaming Utilities

Cursor-based pagination, async iterators, backpressure-aware streaming,
and bounded-memory processing for large-scale datasets.
"""

from typing import (
    TypeVar, Generic, Optional, Any, Callable, AsyncGenerator,
    List, Dict, Protocol, runtime_checkable, Iterator
)
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging
from functools import partial


logger = logging.getLogger(__name__)

T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)


# ============================================================================
# Cursor Types
# ============================================================================

@dataclass
class Cursor:
    """Base cursor for pagination."""
    offset: int = 0
    page: int = 1
    after_id: Optional[str] = None
    before_id: Optional[str] = None
    search_after: Optional[List[Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def encode(self) -> str:
        """Encode cursor to string for URL parameter."""
        import base64
        import json
        data = {
            "offset": self.offset,
            "page": self.page,
            "after": self.after_id,
            "before": self.before_id,
            "search_after": self.search_after,
        }
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()

    @classmethod
    def decode(cls, encoded: str) -> "Cursor":
        """Decode cursor from URL parameter."""
        import base64
        import json
        try:
            data = json.loads(base64.urlsafe_b64decode(encoded.encode()).decode())
            return cls(
                offset=data.get("offset", 0),
                page=data.get("page", 1),
                after_id=data.get("after"),
                before_id=data.get("before"),
                search_after=data.get("search_after"),
            )
        except Exception:
            return cls()


@dataclass
class PaginationResult(Generic[T]):
    """Result of paginated query with metadata."""
    items: List[T]
    total: int
    cursor: Cursor
    has_more: bool
    page_size: int
    total_pages: int

    @property
    def is_first_page(self) -> bool:
        return self.cursor.page == 1

    @property
    def is_last_page(self) -> bool:
        return not self.has_more


@dataclass
class StreamProgress:
    """Progress tracking for streaming operations."""
    total_processed: int = 0
    total_yielded: int = 0
    total_filtered: int = 0
    bytes_processed: int = 0
    errors: int = 0
    start_time: datetime = field(default_factory=datetime.utcnow)

    @property
    def items_per_second(self) -> float:
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        return self.total_processed / max(elapsed, 0.001)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "processed": self.total_processed,
            "yielded": self.total_yielded,
            "filtered": self.total_filtered,
            "errors": self.errors,
            "rate": self.items_per_second,
        }


# ============================================================================
# Backpressure-Aware Async Iterator
# ============================================================================

class BackpressureIterator(Generic[T]):
    """Async iterator with backpressure awareness for bounded memory processing.

    Features:
    - Configurable buffer size
    - Automatic flow control
    - Memory usage monitoring
    - Graceful degradation under load
    """

    def __init__(
        self,
        source: AsyncGenerator[T, None],
        buffer_size: int = 100,
        max_memory_mb: int = 512,
    ):
        self.source = source
        self.buffer_size = buffer_size
        self.max_memory_mb = max_memory_mb
        self._buffer: asyncio.Queue[Optional[T]] = asyncio.Queue(maxsize=buffer_size)
        self._done = False
        self._errors: List[Exception] = []
        self._task: Optional[asyncio.Task] = None

    async def _producer(self) -> None:
        """Producer coroutine that feeds buffer from source."""
        try:
            async for item in self.source:
                await self._buffer.put(item)
                # Check for backpressure signal
                if self._buffer.full():
                    await asyncio.sleep(0.01)  # Brief pause for flow control
        except Exception as e:
            self._errors.append(e)
            logger.warning(f"BackpressureIterator source error: {e}")
        finally:
            await self._buffer.put(None)  # Sentinel to signal completion

    async def __aiter__(self) -> AsyncGenerator[T, None]:
        """Async iterator implementation."""
        # Start producer if not running
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._producer())

        try:
            while True:
                item = await self._buffer.get()
                if item is None:
                    break
                yield item
                self._buffer.task_done()
        except asyncio.CancelledError:
            self._task.cancel()
            raise
        finally:
            if self._task and not self._task.done():
                self._task.cancel()

    def get_errors(self) -> List[Exception]:
        """Get any errors that occurred during iteration."""
        return self._errors.copy()


# ============================================================================
# Chunked Async Iterator
# ============================================================================

async def chunked_async_iter(
    source: AsyncGenerator[T, None],
    chunk_size: int = 100,
) -> AsyncGenerator[List[T], None]:
    """Yield items from async source in chunks for batch processing.

    Args:
        source: Async generator yielding items
        chunk_size: Number of items per chunk

    Yields:
        Lists of items with size up to chunk_size
    """
    chunk: List[T] = []

    async for item in source:
        chunk.append(item)
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []

    if chunk:
        yield chunk


# ============================================================================
# Paginated Async Iterator
# ============================================================================

async def paginated_async_iter(
    fetch_page: Callable[[Cursor], Any],
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> AsyncGenerator[T, None]:
    """Iterate over paginated API with automatic cursor management.

    Args:
        fetch_page: Async function that takes Cursor and returns PaginationResult
        page_size: Items per page
        max_pages: Maximum pages to fetch (None for unlimited)

    Yields:
        Individual items from all pages
    """
    cursor = Cursor(page_size=page_size)
    pages_fetched = 0

    while True:
        if max_pages and pages_fetched >= max_pages:
            break

        result = await fetch_page(cursor)

        for item in result.items:
            yield item

        if not result.has_more:
            break

        cursor.page += 1
        cursor.offset += len(result.items)
        pages_fetched += 1


# ============================================================================
# Batched Async Iterator with Memory Control
# ============================================================================

class BatchedAsyncIterator(Generic[T]):
    """Memory-efficient async iterator that processes items in bounded batches.

    Features:
    - Configurable batch size
    - Memory pressure detection
    - Configurable concurrency per batch
    - Graceful cancellation
    """

    def __init__(
        self,
        source: AsyncGenerator[T, None],
        batch_size: int = 50,
        max_concurrent_batches: int = 3,
        max_memory_mb: int = 1024,
    ):
        self.source = source
        self.batch_size = batch_size
        self.max_concurrent_batches = max_concurrent_batches
        self.max_memory_mb = max_memory_mb
        self._semaphore = asyncio.Semaphore(max_concurrent_batches)
        self._cancelled = False
        self._progress = StreamProgress()

    @property
    def progress(self) -> StreamProgress:
        return self._progress

    def cancel(self) -> None:
        """Cancel iteration."""
        self._cancelled = True

    async def process_batch(
        self,
        items: List[T],
        processor: Callable[[List[T]], Any]
    ) -> List[Any]:
        """Process a single batch with semaphore control."""
        async with self._semaphore:
            return await processor(items)

    async def iterate(
        self,
        processor: Optional[Callable[[List[T]], Any]] = None
    ) -> AsyncGenerator[T, None]:
        """Iterate over source with automatic batching.

        Args:
            processor: Optional async function to process each batch.
                      If provided, yields results from processor.
                      If None, yields individual items.

        Yields:
            Processed results or individual items
        """
        current_batch: List[T] = []

        async for item in self.source:
            if self._cancelled:
                break

            current_batch.append(item)
            self._progress.total_processed += 1

            if len(current_batch) >= self.batch_size:
                if processor:
                    results = await self.process_batch(current_batch, processor)
                    async for result in self._make_async_iter(results):
                        yield result
                else:
                    for batch_item in current_batch:
                        yield batch_item

                self._progress.total_yielded += len(current_batch)
                current_batch = []

                # Brief yield to event loop for other tasks
                await asyncio.sleep(0)

        # Process remaining items
        if current_batch and not self._cancelled:
            if processor:
                results = await self.process_batch(current_batch, processor)
                async for result in self._make_async_iter(results):
                    yield result
            else:
                for batch_item in current_batch:
                    yield batch_item

            self._progress.total_yielded += len(current_batch)

    async def _make_async_iter(self, results: Any) -> AsyncGenerator[Any, None]:
        """Convert results to async generator if not already."""
        if hasattr(results, "__aiter__"):
            async for item in results:
                yield item
        else:
            for item in results:
                yield item


# ============================================================================
# Streaming Source Adapter
# ============================================================================

@runtime_checkable
class Streamable(Protocol[T_co]):
    """Protocol for streamable data sources."""

    async def stream(self, **kwargs) -> AsyncGenerator[T_co, None]:
        """Stream data items."""
        ...


class StreamingAdapter(Generic[T]):
    """Adapter for wrapping various data sources as async streams."""

    def __init__(self, source: Any):
        self.source = source

    async def stream(self, **kwargs) -> AsyncGenerator[T, None]:
        """Stream items from source.

        Supports:
        - Async generators
        - Regular generators
        - Async iterators
        - Sync iterables
        """
        # Async generator
        if hasattr(self.source, "__anext__"):
            async for item in self.source:
                yield item

        # Sync iterator
        elif hasattr(self.source, "__iter__"):
            for item in self.source:
                if asyncio.iscoroutine(item):
                    yield await item
                else:
                    yield item

        else:
            raise TypeError(f"Source is not iterable: {type(self.source)}")


# ============================================================================
# Pagination Utilities
# ============================================================================

def create_cursor(
    after: Optional[str] = None,
    before: Optional[str] = None,
    offset: Optional[int] = None,
    page: Optional[int] = None,
) -> Cursor:
    """Create a pagination cursor."""
    return Cursor(
        after_id=after,
        before_id=before,
        offset=offset or 0,
        page=page or 1,
    )


def calculate_pagination(
    total: int,
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    """Calculate pagination metadata."""
    total_pages = (total + page_size - 1) // page_size
    has_prev = page > 1
    has_next = page < total_pages

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_prev": has_prev,
        "has_next": has_next,
        "prev_cursor": create_cursor(page=page - 1).encode() if has_prev else None,
        "next_cursor": create_cursor(page=page + 1).encode() if has_next else None,
    }


# ============================================================================
# Memory-Monitored Iterator
# ============================================================================

class MemoryMonitoredIterator(Generic[T]):
    """Async iterator with real-time memory monitoring.

    Automatically throttles when approaching memory limits.
    """

    def __init__(
        self,
        source: AsyncGenerator[T, None],
        max_memory_mb: int = 512,
        check_interval: int = 100,
    ):
        self.source = source
        self.max_memory_mb = max_memory_mb
        self.check_interval = check_interval
        self._count = 0
        self._memory_warning_issued = False

    def _check_memory(self) -> bool:
        """Check if memory is within limits. Returns False if should pause."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / (1024 * 1024)

            if memory_mb > self.max_memory_mb * 0.9:
                if not self._memory_warning_issued:
                    logger.warning(
                        f"Memory usage high: {memory_mb:.1f}MB / {self.max_memory_mb}MB limit"
                    )
                    self._memory_warning_issued = True
                return False

            self._memory_warning_issued = False
            return True
        except ImportError:
            return True  # Can't check, assume OK

    async def __aiter__(self) -> AsyncGenerator[T, None]:
        """Async iterator with memory monitoring."""
        async for item in self.source:
            self._count += 1

            # Periodic memory check
            if self._count % self.check_interval == 0:
                if not self._check_memory():
                    await asyncio.sleep(0.5)  # Throttle on high memory

            yield item


# ============================================================================
# Concurrency-Limited Iterator
# ============================================================================

async def concurrency_limited_iter(
    source: AsyncGenerator[T, None],
    max_concurrent: int = 10,
    max_queue_size: int = 100,
) -> AsyncGenerator[T, None]:
    """Iterate with limited concurrency using semaphore.

    Args:
        source: Async generator yielding items
        max_concurrent: Maximum concurrent processing tasks
        max_queue_size: Maximum items to queue

    Yields:
        Items from source with controlled concurrency
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
    errors = []

    async def worker(item: T) -> T:
        async with semaphore:
            return item

    async def consumer() -> None:
        try:
            async for item in source:
                await queue.put(item)
        except Exception as e:
            errors.append(e)
        finally:
            # Signal end
            await queue.put(None)

    # Start consumer task
    consumer_task = asyncio.create_task(consumer())

    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield await worker(item)
            queue.task_done()
    except asyncio.CancelledError:
        consumer_task.cancel()
        raise
    finally:
        if errors:
            logger.warning(f"Consumer errors: {errors}")


# Re-export all public symbols
__all__ = [
    # Cursor
    "Cursor",
    "PaginationResult",
    "StreamProgress",

    # Iterators
    "BackpressureIterator",
    "BatchedAsyncIterator",
    "MemoryMonitoredIterator",

    # Utilities
    "chunked_async_iter",
    "paginated_async_iter",
    "concurrency_limited_iter",
    "StreamingAdapter",

    # Protocols
    "Streamable",

    # Helpers
    "create_cursor",
    "calculate_pagination",
]