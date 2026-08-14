"""
Streaming Dataset Access System

Supports streaming, chunked, and range-based access for large datasets.
"""

import asyncio
import io
import json
from typing import AsyncIterator, Optional, Callable
from dataclasses import dataclass
from enum import Enum


class StreamType(Enum):
    """Types of streaming access."""
    FULL_STREAM = "full_stream"  # Complete data as stream
    CHUNKED = "chunked"  # Chunked data
    RANGE = "range"  # Range-based access
    ITERABLE = "iterable"  # Row-by-row iteration
    LAZY = "lazy"  # Lazy loading


@dataclass
class StreamConfig:
    """Configuration for streaming."""
    stream_type: StreamType = StreamType.CHUNKED
    chunk_size: int = 1024 * 1024  # 1MB default
    buffer_size: int = 10  # Number of chunks to buffer
    prefetch: bool = True
    compression: Optional[str] = None


@dataclass
class StreamProgress:
    """Streaming progress information."""
    bytes_streamed: int
    total_bytes: int
    chunks_completed: int
    total_chunks: int
    speed_mbps: float
    eta_seconds: float


class ChunkIterator:
    """Iterator for chunked data access."""

    def __init__(
        self,
        source: str | bytes,
        chunk_size: int = 1024 * 1024,
        stream_type: StreamType = StreamType.CHUNKED
    ):
        self.source = source
        self.chunk_size = chunk_size
        self.stream_type = stream_type
        self._position = 0

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        """Get next chunk."""
        if self.stream_type == StreamType.RANGE:
            raise NotImplementedError("Range requests need special handling")
        elif isinstance(self.source, bytes):
            return await self._get_chunk_from_bytes()
        else:
            return await self._get_chunk_from_file()

    async def _get_chunk_from_bytes(self) -> bytes:
        """Get chunk from bytes."""
        if self._position >= len(self.source):
            raise StopAsyncIteration

        chunk = self.source[self._position:self._position + self.chunk_size]
        self._position += self.chunk_size
        return chunk

    async def _get_chunk_from_file(self) -> bytes:
        """Get chunk from file."""
        import os

        if not os.path.exists(self.source):
            raise StopAsyncIteration

        with open(self.source, 'rb') as f:
            f.seek(self._position)
            chunk = f.read(self.chunk_size)
            self._position += len(chunk)

        if not chunk:
            raise StopAsyncIteration

        return chunk

    def seek(self, position: int) -> None:
        """Seek to position."""
        self._position = position

    def tell(self) -> int:
        """Get current position."""
        return self._position


class RangeRequestHandler:
    """Handle HTTP range requests for partial data access."""

    def __init__(self, source: str):
        self.source = source
        self._file_size = self._get_file_size()

    def _get_file_size(self) -> int:
        """Get total file size."""
        import os
        if os.path.exists(self.source):
            return os.path.getsize(self.source)
        return 0

    async def get_range(self, start: int, end: int) -> bytes:
        """Get byte range."""
        with open(self.source, 'rb') as f:
            f.seek(start)
            return f.read(end - start + 1)

    def parse_range_header(self, header: str) -> tuple[int, int]:
        """Parse HTTP Range header."""
        # Format: bytes=start-end
        if header.startswith("bytes="):
            parts = header[6:].split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else self._file_size - 1
            return start, min(end, self._file_size - 1)
        return 0, self._file_size - 1

    def get_content_range_header(self, start: int, end: int) -> str:
        """Generate Content-Range header."""
        return f"bytes {start}-{end}/{self._file_size}"


class StreamManager:
    """Manages streaming operations for large datasets."""

    def __init__(self, config: StreamConfig = None):
        self.config = config or StreamConfig()
        self._active_streams: dict[str, ChunkIterator] = {}

    async def create_stream(
        self,
        source: str | bytes,
        stream_type: StreamType = StreamType.CHUNKED
    ) -> AsyncIterator[bytes]:
        """Create a stream for dataset access."""
        chunk_size = self.config.chunk_size

        iterator = ChunkIterator(source, chunk_size, stream_type)
        stream_id = f"stream_{id(source)}"
        self._active_streams[stream_id] = iterator

        try:
            async for chunk in iterator:
                yield chunk
        finally:
            if stream_id in self._active_streams:
                del self._active_streams[stream_id]

    async def stream_parquet(
        self,
        file_path: str,
        batch_size: int = 1000
    ) -> AsyncIterator[list[dict]]:
        """Stream parquet file in batches."""
        try:
            import pandas as pd

            # For large parquet, read in chunks
            import pyarrow.parquet as pq

            parquet_file = pq.ParquetFile(file_path)

            for batch in parquet_file.iter_batches(batch_size=batch_size):
                df = batch.to_pandas()
                yield df.to_dict('records')

        except ImportError:
            # Fallback: read entire file
            df = pd.read_parquet(file_path)
            for i in range(0, len(df), batch_size):
                yield df.iloc[i:i + batch_size].to_dict('records')

    async def stream_jsonl(
        self,
        file_path: str,
        buffer_size: int = 100
    ) -> AsyncIterator[dict]:
        """Stream JSONL file line by line."""
        with open(file_path, 'r') as f:
            buffer = []
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    buffer.append(json.loads(line))
                    if len(buffer) >= buffer_size:
                        yield buffer
                        buffer = []
                except json.JSONDecodeError:
                    continue

            if buffer:
                yield buffer

    async def stream_sharded(
        self,
        shard_paths: list[str],
        merge: bool = True
    ) -> AsyncIterator[dict]:
        """Stream from multiple shards."""
        if merge:
            # Interleave shards
            iterators = [self.stream_jsonl(path) for path in shard_paths]
            active = list(iterators)

            while active:
                for it in active[:]:
                    try:
                        chunk = await it.__anext__()
                        yield chunk
                    except StopAsyncIteration:
                        active.remove(it)

        else:
            # Sequential shards
            for path in shard_paths:
                async for item in self.stream_jsonl(path):
                    yield item

    async def stream_compressed(
        self,
        archive_path: str,
        decompress: bool = True
    ) -> AsyncIterator[bytes]:
        """Stream from compressed archive."""
        import zipfile
        import tarfile

        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zf:
                for name in zf.namelist():
                    if name.endswith('.jsonl') or name.endswith('.json'):
                        with zf.open(name) as f:
                            while chunk := f.read(self.config.chunk_size):
                                if decompress:
                                    yield chunk
                                else:
                                    yield chunk

        elif archive_path.endswith(('.tar.gz', '.tar.zstd')):
            with tarfile.open(archive_path, 'r:*') as tf:
                for member in tf:
                    if member.isfile() and (member.name.endswith('.jsonl') or member.name.endswith('.json')):
                        f = tf.extractfile(member)
                        while chunk := f.read(self.config.chunk_size):
                            yield chunk

    async def range_stream(
        self,
        file_path: str,
        start: int,
        end: int
    ) -> AsyncIterator[bytes]:
        """Stream specific byte range."""
        handler = RangeRequestHandler(file_path)

        chunk_start = start
        chunk_end = min(start + self.config.chunk_size, end)

        while chunk_start <= end:
            chunk = await handler.get_range(chunk_start, chunk_end)
            yield chunk

            chunk_start = chunk_end + 1
            chunk_end = min(chunk_start + self.config.chunk_size, end)

    async def create_memory_mapped_stream(
        self,
        file_path: str
    ) -> AsyncIterator[bytes]:
        """Create memory-mapped stream for large files."""
        import mmap

        with open(file_path, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                while True:
                    chunk = mm.read(self.config.chunk_size)
                    if not chunk:
                        break
                    yield chunk

    def get_stream_info(self, stream_id: str) -> Optional[StreamProgress]:
        """Get progress information for a stream."""
        if stream_id in self._active_streams:
            iterator = self._active_streams[stream_id]
            return StreamProgress(
                bytes_streamed=iterator.tell(),
                total_bytes=0,  # Unknown for streaming
                chunks_completed=iterator.tell() // iterator.chunk_size,
                total_chunks=0,
                speed_mbps=0.0,
                eta_seconds=0.0,
            )
        return None

    def cancel_stream(self, stream_id: str) -> bool:
        """Cancel an active stream."""
        if stream_id in self._active_streams:
            del self._active_streams[stream_id]
            return True
        return False


class StreamingDataset:
    """Wrapper for streaming dataset access."""

    def __init__(
        self,
        source: str,
        config: StreamConfig = None,
        stream_manager: StreamManager = None
    ):
        self.source = source
        self.config = config or StreamConfig()
        self.manager = stream_manager or StreamManager(self.config)
        self._iterator = None

    async def __aiter__(self):
        """Async iteration."""
        async for chunk in self.manager.create_stream(self.source):
            yield chunk

    async def collect(self) -> list[bytes]:
        """Collect all chunks into memory (use carefully)."""
        chunks = []
        async for chunk in self:
            chunks.append(chunk)
        return chunks

    async def to_file(self, destination: str):
        """Write stream to file."""
        with open(destination, 'wb') as f:
            async for chunk in self:
                f.write(chunk)

    def estimate_size(self) -> int:
        """Estimate total dataset size."""
        import os
        if os.path.exists(self.source):
            return os.path.getsize(self.source)
        return 0