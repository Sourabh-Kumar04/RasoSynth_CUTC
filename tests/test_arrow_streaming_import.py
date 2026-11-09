"""
Test Bi-directional Streaming PyArrow and Parquet Ingestion Pipeline.
"""

import io
import json
import pytest
import pyarrow as pa
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

from pipeline.import_pipeline import ArrowDatasetImporter


@pytest.mark.asyncio
async def test_arrow_ipc_streaming_import(tmp_path):
    # 1. Create Arrow IPC table
    schema = pa.schema([
        ("instruction", pa.string()),
        ("response", pa.string()),
        ("input", pa.string()),
        ("quality_score", pa.float64()),
        ("difficulty_tier", pa.int32()),
        ("metadata_json", pa.string()),
    ])

    instructions = [f"Instruction {i}" for i in range(100)]
    responses = [f"Response {i}" for i in range(100)]
    inputs = ["" for _ in range(100)]
    scores = [0.85 + (i % 15) * 0.01 for i in range(100)]
    tiers = [(i % 5) + 1 for i in range(100)]
    meta = [json.dumps({"source": "unit_test", "index": i}) for i in range(100)]

    table = pa.Table.from_arrays(
        [
            pa.array(instructions),
            pa.array(responses),
            pa.array(inputs),
            pa.array(scores),
            pa.array(tiers),
            pa.array(meta),
        ],
        schema=schema,
    )

    arrow_file = tmp_path / "test_dataset.arrow"
    with ipc.new_file(str(arrow_file), schema) as writer:
        writer.write_table(table)

    # 2. Mock database
    class MockDB:
        def __init__(self):
            self.created_batches = []

        async def create_samples_batch(self, dataset_id, records):
            self.created_batches.append(records)

    mock_db = MockDB()

    # 3. Stream import into dataset
    importer = ArrowDatasetImporter(batch_size=25)
    result = await importer.import_stream_to_dataset(
        source=str(arrow_file),
        dataset_id="test-ds-stream-001",
        db=mock_db,
        format_hint="arrow",
    )

    assert result["status"] == "success"
    assert result["total_imported"] == 100
    assert result["batches_processed"] >= 1
    assert result["throughput_records_sec"] >= 0

    total_records = sum(len(b) for b in mock_db.created_batches)
    assert total_records == 100
    first_record = mock_db.created_batches[0][0]
    assert first_record["instruction"] == "Instruction 0"
    assert first_record["response"] == "Response 0"
    assert first_record["metadata"]["source"] == "unit_test"


@pytest.mark.asyncio
async def test_parquet_streaming_import(tmp_path):
    schema = pa.schema([
        ("prompt", pa.string()),
        ("completion", pa.string()),
        ("score", pa.float64()),
    ])

    table = pa.Table.from_arrays(
        [
            pa.array(["P1", "P2", "P3"]),
            pa.array(["C1", "C2", "C3"]),
            pa.array([0.9, 0.95, 0.88]),
        ],
        schema=schema,
    )

    pq_file = tmp_path / "test_dataset.parquet"
    pq.write_table(table, str(pq_file))

    class MockDB:
        def __init__(self):
            self.samples = []

        async def create_samples(self, dataset_id, records):
            self.samples.extend(records)

    mock_db = MockDB()
    importer = ArrowDatasetImporter()
    result = await importer.import_stream_to_dataset(
        source=str(pq_file),
        dataset_id="test-ds-pq-002",
        db=mock_db,
        format_hint="parquet",
    )

    assert result["total_imported"] == 3
    assert len(mock_db.samples) == 3
    assert mock_db.samples[0]["instruction"] == "P1"
    assert mock_db.samples[0]["response"] == "C1"
