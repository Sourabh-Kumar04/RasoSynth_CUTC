"""Test streaming PyArrow IPC export pipeline."""
import os
from pathlib import Path
import pytest
import pyarrow.ipc as ipc
from pipeline.export import ExportPipeline, ExportConfig

@pytest.mark.asyncio
async def test_streaming_arrow_ipc_export(tmp_path):
    config = ExportConfig(
        format="arrow",
        output_dir=tmp_path,
        dataset_name="test_corpus",
    )
    pipeline = ExportPipeline(config)

    samples = [
        {
            "id": f"sample_{i}",
            "instruction": f"Instruction prompt {i}",
            "response": f"Model response {i}",
            "input": "",
            "quality_score": 0.95,
            "hallucination_risk": 0.05,
            "domain": "medical",
        }
        for i in range(25)
    ]

    export_map = await pipeline.export(samples, job_id="test_job")
    assert "dataset" in export_map
    result_path = str(export_map["dataset"])
    assert result_path.endswith(".arrow")
    assert os.path.exists(result_path)

    # Verify that the file is a valid Arrow IPC file / stream
    with open(result_path, "rb") as f:
        reader = ipc.open_file(f)
        table = reader.read_all()
        assert table.num_rows == 25
        assert "instruction" in table.column_names
        assert "response" in table.column_names
        assert "metadata" in table.column_names

