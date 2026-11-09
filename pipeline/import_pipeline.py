"""
Bi-directional Streaming Arrow & Parquet Ingestion Pipeline.

Provides memory-efficient, zero-copy streaming ingestion of large-scale
Arrow IPC (.arrow, .feather), Arrow Streaming (.arrows), Parquet (.parquet),
and JSONL datasets directly into RasoSynth database sample stores.
"""

from __future__ import annotations

import io
import json
import logging
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


class ArrowDatasetImporter:
    """
    Streaming ingestion engine leveraging PyArrow's zero-copy batch readers
    to stream dataset records directly to DatabaseManager.create_samples_batch.
    """

    def __init__(self, batch_size: int = 5000):
        self.batch_size = batch_size

    def iter_record_batches(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
        format_hint: Optional[str] = None,
    ):
        """
        Yield PyArrow RecordBatches from Arrow, Parquet, or Feather sources.
        Avoids loading full datasets into Python memory.
        """
        # Determine source type
        buf: Optional[pa.Buffer] = None
        if isinstance(source, (bytes, bytearray)):
            buf = pa.py_buffer(source)
            stream_reader = pa.BufferReader(buf)
        elif isinstance(source, io.BytesIO):
            buf = pa.py_buffer(source.getvalue())
            stream_reader = pa.BufferReader(buf)
        else:
            file_path = Path(source)
            if not file_path.exists():
                raise FileNotFoundError(f"Source file not found: {source}")
            ext = file_path.suffix.lower()
            if not format_hint:
                format_hint = "parquet" if ext == ".parquet" else "arrow"
            stream_reader = pa.memory_map(str(file_path), "r")

        # Try Arrow IPC File (Feather) first
        if format_hint in ("arrow", "feather", None):
            try:
                reader = ipc.open_file(stream_reader)
                for i in range(reader.num_record_batches):
                    yield reader.get_batch(i)
                return
            except Exception as e_file:
                logger.debug(f"Not an Arrow IPC file, trying Arrow IPC stream: {e_file}")
                try:
                    stream_reader.seek(0)
                    reader = ipc.open_stream(stream_reader)
                    for batch in reader:
                        yield batch
                    return
                except Exception as e_stream:
                    logger.debug(f"Not an Arrow IPC stream: {e_stream}")

        # Try Parquet
        try:
            stream_reader.seek(0)
            parquet_file = pq.ParquetFile(stream_reader)
            for batch in parquet_file.iter_batches(batch_size=self.batch_size):
                yield batch
            return
        except Exception as e_pq:
            logger.debug(f"Not Parquet format: {e_pq}")

        raise ValueError("Unsupported or unparseable binary Arrow/Parquet dataset format")

    def transform_batch(self, batch: pa.RecordBatch) -> List[Dict[str, Any]]:
        """
        Converts a PyArrow RecordBatch into normalized dictionary records
        conforming to the Sample schema with minimal Python object overhead.
        """
        col_names = [name.lower() for name in batch.schema.names]
        col_map = {name.lower(): name for name in batch.schema.names}

        # Resolve field column names
        instruction_col = col_map.get("instruction") or col_map.get("prompt") or col_map.get("query")
        response_col = col_map.get("response") or col_map.get("completion") or col_map.get("output")
        input_col = col_map.get("input") or col_map.get("context")
        quality_col = col_map.get("quality_score") or col_map.get("score")
        difficulty_col = col_map.get("difficulty_tier") or col_map.get("difficulty")
        metadata_col = col_map.get("metadata") or col_map.get("metadata_json")
        embedding_col = col_map.get("embedding") or col_map.get("vector")

        if not instruction_col or not response_col:
            raise ValueError(
                f"Batch schema missing required fields: expected 'instruction' and 'response', got {col_names}"
            )

        instructions = batch.column(instruction_col).to_pylist()
        responses = batch.column(response_col).to_pylist()
        inputs = batch.column(input_col).to_pylist() if input_col else [""] * len(instructions)
        qualities = batch.column(quality_col).to_pylist() if quality_col else [1.0] * len(instructions)
        difficulties = batch.column(difficulty_col).to_pylist() if difficulty_col else [1] * len(instructions)
        metadatas = batch.column(metadata_col).to_pylist() if metadata_col else [{}] * len(instructions)
        embeddings = batch.column(embedding_col).to_pylist() if embedding_col else [None] * len(instructions)

        records: List[Dict[str, Any]] = []
        for i in range(len(instructions)):
            raw_meta = metadatas[i]
            meta_dict: Dict[str, Any] = {}
            if isinstance(raw_meta, str):
                try:
                    meta_dict = json.loads(raw_meta)
                except Exception:
                    meta_dict = {"raw": raw_meta}
            elif isinstance(raw_meta, dict):
                meta_dict = raw_meta

            record: Dict[str, Any] = {
                "instruction": str(instructions[i] or ""),
                "response": str(responses[i] or ""),
                "input": str(inputs[i] or ""),
                "quality_score": float(qualities[i]) if qualities[i] is not None else 1.0,
                "difficulty_tier": int(difficulties[i]) if difficulties[i] is not None else 1,
                "metadata": meta_dict,
            }
            if embeddings[i] is not None:
                record["embedding"] = embeddings[i]

            records.append(record)

        return records

    async def import_stream_to_dataset(
        self,
        source: Union[str, Path, bytes, io.BytesIO],
        dataset_id: str,
        db: Any,
        format_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Stream records directly into the database using chunked Core batch ingestion.
        """
        start_time = time.perf_counter()
        total_records = 0
        batch_count = 0

        db_manager = getattr(db, "db", db)

        for pa_batch in self.iter_record_batches(source, format_hint=format_hint):
            records = self.transform_batch(pa_batch)
            if not records:
                continue

            if hasattr(db_manager, "create_samples_batch"):
                await db_manager.create_samples_batch(dataset_id, records)
            elif hasattr(db, "create_samples"):
                await db.create_samples(dataset_id, records)
            else:
                raise AttributeError("Database interface does not provide sample batch creation")

            total_records += len(records)
            batch_count += 1

        duration = time.perf_counter() - start_time
        throughput = total_records / duration if duration > 0 else 0.0

        logger.info(
            f"Successfully streamed {total_records} records into dataset {dataset_id} "
            f"in {batch_count} batches ({throughput:.1f} records/sec)"
        )

        return {
            "dataset_id": dataset_id,
            "total_imported": total_records,
            "batches_processed": batch_count,
            "elapsed_seconds": round(duration, 4),
            "throughput_records_sec": round(throughput, 2),
            "status": "success",
        }
