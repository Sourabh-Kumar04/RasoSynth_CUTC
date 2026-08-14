"""
Intelligent Dataset Packaging System

Handles dynamic packaging of datasets based on size, type, and destination.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional
import asyncio
import json
import os
import subprocess
import tempfile
from datetime import datetime
import hashlib


class CompressionType(Enum):
    """Supported compression types."""
    NONE = "none"
    ZIP = "zip"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_ZSTD = "tar.zstd"
    PARQUET = "parquet"
    CHUNKED_JSONL = "chunked_jsonl"
    SHARDED = "sharded"
    STREAMING = "streaming"


class PartitionStrategy(Enum):
    """Data partitioning strategies."""
    NONE = "none"
    BY_SIZE = "by_size"  # Fixed size chunks
    BY_ROWS = "by_rows"  # Row-based partitioning
    BY_TIME = "by_time"  # Temporal partitioning
    BY_CATEGORY = "by_category"  # Category-based
    BY_LANGUAGE = "by_language"  # Language-based
    BY_MODALITY = "by_modality"  # Modality-based


class ShardStrategy(Enum):
    """Sharding strategies for distributed storage."""
    SINGLE = "single"  # No sharding
    HASH_BASED = "hash_based"  # Hash-based partitioning
    RANGE_BASED = "range_based"  # Range-based partitioning
    ADAPTIVE = "adaptive"  # Smart sharding based on data


@dataclass
class PackagingConfig:
    """Configuration for dataset packaging."""
    compression: CompressionType = CompressionType.TAR_ZSTD
    partition_strategy: PartitionStrategy = PartitionStrategy.BY_SIZE
    shard_strategy: ShardStrategy = ShardStrategy.ADAPTIVE
    # Size settings
    chunk_size_mb: int = 100
    shard_size_mb: int = 500
    max_file_size_gb: int = 50
    # Format settings
    output_format: str = "jsonl"
    include_checksums: bool = True
    include_metadata: bool = True
    # Optimization
    compression_level: int = 3
    verify_after_compress: bool = True
    delete_source: bool = False


@dataclass
class PackageManifest:
    """Manifest for packaged dataset."""
    package_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    dataset_name: str = ""
    version: str = "1.0.0"
    total_size_bytes: int = 0
    compressed_size_bytes: int = 0
    compression_ratio: float = 0.0
    file_count: int = 0
    chunk_count: int = 0
    shard_count: int = 0
    checksum: str = ""
    checksum_algorithm: str = "sha256"
    compression: str = ""
    partitioning: str = ""
    files: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    distribution_info: dict = field(default_factory=dict)
    # For incremental updates
    base_version: Optional[str] = None
    delta_size_bytes: Optional[int] = None


class DatasetPackager:
    """Intelligent dataset packaging with dynamic optimization."""

    def __init__(self, config: PackagingConfig = None):
        self.config = config or PackagingConfig()

    async def package(
        self,
        data: list[dict],
        dataset_name: str,
        version: str = "1.0.0"
    ) -> PackageManifest:
        """Package dataset with intelligent optimization."""
        import uuid

        package_id = str(uuid.uuid4())
        total_size = sum(len(json.dumps(item)) for item in data)

        # Determine optimal settings based on size
        optimal_settings = self._determine_packaging_strategy(total_size, len(data))

        manifest = PackageManifest(
            package_id=package_id,
            created_at=datetime.utcnow(),
            dataset_name=dataset_name,
            version=version,
            total_size_bytes=total_size,
            compressed_size_bytes=0,  # Will be updated
            compression_ratio=0,
            file_count=0,
            chunk_count=0,
            shard_count=0,
            checksum="",
            compression=optimal_settings["compression"].value,
            partitioning=optimal_settings["partition"].value,
        )

        # Create chunks
        chunks = self._create_chunks(
            data,
            optimal_settings["chunk_size"],
            optimal_settings["partition"]
        )
        manifest.chunk_count = len(chunks)

        # Apply compression and create archive
        archive_path, compressed_size = await self._create_archive(
            chunks,
            dataset_name,
            optimal_settings["compression"]
        )

        manifest.compressed_size_bytes = compressed_size
        manifest.compression_ratio = compressed_size / max(total_size, 1)
        manifest.file_count = len(chunks)
        manifest.archive_path = archive_path

        # Calculate checksum
        manifest.checksum = await self._calculate_archive_checksum(archive_path)

        # Add file manifest
        manifest.files = await self._generate_file_manifest(chunks, archive_path)

        return manifest

    async def package_streaming(
        self,
        data_iterator: AsyncIterator[dict],
        dataset_name: str,
        total_items: int = 0
    ) -> tuple[AsyncIterator[bytes], PackageManifest]:
        """Create a streaming package for very large datasets."""
        import uuid

        package_id = str(uuid.uuid4())
        manifest = PackageManifest(
            package_id=package_id,
            created_at=datetime.utcnow(),
            dataset_name=dataset_name,
            version="1.0.0",
            total_size_bytes=0,
            compressed_size_bytes=0,
            compression_ratio=0,
            file_count=0,
            chunk_count=0,
            shard_count=0,
            checksum="",
            compression=CompressionType.STREAMING.value,
            partitioning=PartitionStrategy.BY_SIZE.value,
        )

        # Stream through compressor
        async def stream_compressed():
            compressor = ZstdCompressor(level=self.config.compression_level)
            byte_count = 0

            async for item in data_iterator:
                item_bytes = json.dumps(item).encode()
                compressed = await compressor.compress(item_bytes)
                byte_count += len(compressed)
                yield compressed

            # Finalize
            final = await compressor.finalize()
            manifest.total_size_bytes = byte_count

        return stream_compressed(), manifest

    async def create_sharded_dataset(
        self,
        data: list[dict],
        shard_size_mb: int = 500
    ) -> list[str]:
        """Create sharded dataset for distributed storage."""
        import uuid

        # Calculate items per shard
        avg_item_size = sum(len(json.dumps(d)) for d in data) / max(len(data), 1)
        items_per_shard = max(1, int((shard_size_mb * 1024 * 1024) / avg_item_size))

        shard_paths = []
        for i in range(0, len(data), items_per_shard):
            shard_data = data[i:i + items_per_shard]
            shard_id = str(uuid.uuid4())[:8]
            shard_path = f"shard_{shard_id}.jsonl"

            with open(shard_path, 'w') as f:
                for item in shard_data:
                    f.write(json.dumps(item) + '\n')

            shard_paths.append(shard_path)

        return shard_paths

    async def create_incremental_package(
        self,
        current_data: list[dict],
        previous_version: str,
        new_version: str
    ) -> tuple[PackageManifest, list[dict]]:
        """Create incremental package with only changes from previous version."""
        # This would compare with previous version
        # For now, return full package marked as incremental
        manifest = await self.package(current_data, f"dataset_v{new_version}", new_version)
        manifest.base_version = previous_version

        # Identify changes
        changes = current_data  # In real implementation, compare with previous

        manifest.delta_size_bytes = sum(len(json.dumps(c)) for c in changes)

        return manifest, changes

    def _determine_packaging_strategy(self, total_size: int, item_count: int) -> dict:
        """Determine optimal packaging strategy based on dataset characteristics."""
        size_gb = total_size / (1024**3)

        if size_gb < 0.001:  # <1MB
            return {
                "compression": CompressionType.NONE,
                "partition": PartitionStrategy.NONE,
                "chunk_size": 0,
                "shard_size": 0,
            }
        elif size_gb < 1:  # <1GB
            return {
                "compression": CompressionType.TAR_ZSTD,
                "partition": PartitionStrategy.BY_SIZE,
                "chunk_size": 100 * 1024 * 1024,  # 100MB
                "shard_size": 0,
            }
        elif size_gb < 20:  # 1-20GB
            return {
                "compression": CompressionType.TAR_ZSTD,
                "partition": PartitionStrategy.BY_SIZE,
                "chunk_size": self.config.chunk_size_mb * 1024 * 1024,
                "shard_size": 0,
            }
        elif size_gb < 100:  # 20-100GB
            return {
                "compression": CompressionType.TAR_ZSTD,
                "partition": PartitionStrategy.BY_SIZE,
                "chunk_size": self.config.chunk_size_mb * 1024 * 1024,
                "shard_size": self.config.shard_size_mb * 1024 * 1024,
            }
        else:  # >100GB - Use sharding
            return {
                "compression": CompressionType.CHUNKED_JSONL,
                "partition": PartitionStrategy.BY_SIZE,
                "chunk_size": self.config.chunk_size_mb * 1024 * 1024,
                "shard_size": self.config.shard_size_mb * 1024 * 1024,
            }

    def _create_chunks(
        self,
        data: list[dict],
        chunk_size: int,
        partition_strategy: PartitionStrategy
    ) -> list[list[dict]]:
        """Create data chunks based on strategy."""
        if partition_strategy == PartitionStrategy.NONE or chunk_size == 0:
            return [data]

        chunks = []
        current_chunk = []
        current_size = 0

        for item in data:
            item_size = len(json.dumps(item))
            if current_size + item_size > chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
                current_size = 0
            current_chunk.append(item)
            current_size += item_size

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def _create_archive(
        self,
        chunks: list[list[dict]],
        dataset_name: str,
        compression: CompressionType
    ) -> tuple[str, int]:
        """Create compressed archive."""
        import uuid
        import tempfile

        archive_id = str(uuid.uuid4())[:8]
        temp_dir = tempfile.mkdtemp()

        # Write chunks
        chunk_files = []
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(temp_dir, f"chunk_{i:04d}.jsonl")
            with open(chunk_path, 'w') as f:
                for item in chunk:
                    f.write(json.dumps(item) + '\n')
            chunk_files.append(chunk_path)

        # Create archive based on compression type
        if compression == CompressionType.ZIP:
            archive_path = os.path.join(temp_dir, f"{dataset_name}.zip")
            await self._create_zip_archive(chunk_files, archive_path)
        elif compression in [CompressionType.TAR_GZ, CompressionType.TAR_ZSTD]:
            ext = "tar.zstd" if compression == CompressionType.TAR_ZSTD else "tar.gz"
            archive_path = os.path.join(temp_dir, f"{dataset_name}.{ext}")
            await self._create_tar_archive(chunk_files, archive_path, compression)
        else:
            # Just use first chunk as archive for non-compressed
            archive_path = chunk_files[0]

        # Get compressed size
        compressed_size = os.path.getsize(archive_path) if os.path.exists(archive_path) else sum(
            os.path.getsize(f) for f in chunk_files
        )

        return archive_path, compressed_size

    async def _create_zip_archive(self, files: list[str], output: str) -> None:
        """Create ZIP archive."""
        import zipfile

        loop = asyncio.get_event_loop()

        def create():
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, os.path.basename(f))

        await loop.run_in_executor(None, create)

    async def _create_tar_archive(
        self,
        files: list[str],
        output: str,
        compression: CompressionType
    ) -> None:
        """Create TAR archive with optional compression."""
        import tarfile

        loop = asyncio.get_event_loop()

        def create():
            mode = 'w:gz' if compression == CompressionType.TAR_GZ else 'w:zstd'
            with tarfile.open(output, mode) as tf:
                for f in files:
                    tf.add(f, arcname=os.path.basename(f))

        await loop.run_in_executor(None, create)

    async def _calculate_archive_checksum(self, archive_path: str) -> str:
        """Calculate SHA256 checksum of archive."""
        loop = asyncio.get_event_loop()

        async def calc():
            sha256 = hashlib.sha256()
            with open(archive_path, 'rb') as f:
                while chunk := f.read(8192):
                    sha256.update(chunk)
            return sha256.hexdigest()

        return await loop.run_in_executor(None, lambda: asyncio.run(calc()))

    async def _generate_file_manifest(self, chunks: list[list[dict]], archive_path: str) -> list[dict]:
        """Generate file manifest for the package."""
        manifest = []
        for i, chunk in enumerate(chunks):
            chunk_file = f"chunk_{i:04d}.jsonl"
            size = sum(len(json.dumps(item)) for item in chunk)
            manifest.append({
                "filename": chunk_file,
                "size_bytes": size,
                "item_count": len(chunk),
                "checksum": hashlib.sha256(json.dumps(chunk).encode()).hexdigest(),
            })
        return manifest


class ZstdCompressor:
    """Streaming Zstd compression."""

    def __init__(self, level: int = 3):
        self.level = level
        self._buffer = b""
        self._compressor = None

    async def compress(self, data: bytes) -> bytes:
        """Compress data."""
        loop = asyncio.get_event_loop()

        def compress_sync():
            import zstandard
            if self._compressor is None:
                self._compressor = zstandard.ZstdCompressor(level=self.level)
            return self._compressor.compress(data)

        return await loop.run_in_executor(None, compress_sync)

    async def finalize(self) -> bytes:
        """Finalize compression."""
        if self._compressor:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._compressor.flush())
        return b""