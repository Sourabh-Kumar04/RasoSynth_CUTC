"""End-to-End Live Job Run Verification Suite.

Tests complete end-to-end dataset generation jobs:
1. End-to-end job execution via `orchestrator.run()` with real SQLite database persistence.
2. Construction of realistic samples (Indian Taxation & GST Compliance).
3. Export pipeline writing JSONL files to disk.
4. Cryptographic DBOM attestation generation and Merkle root verification.
"""

import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import BaseModel
from unittest.mock import AsyncMock, Mock

from core.db import AsyncDB
from core.export.dbom_attestor import verify_dataset_dbom
from core.orchestrator_core import DatasetOrchestrator, Job, JobStatus
from providers.core_lib.base import LLMResponse


class MockJobRequest(BaseModel):
    target_domain: str = "Indian Taxation & GST Compliance"
    dataset_size: int = 3
    dataset_type: str = "sft"
    language: str = "hinglish"
    export_format: str = "jsonl"
    generation_mode: str = "synthetic"
    cost_budget_usd: float = 5.0
    quality_level: str = "enterprise"
    human_review: bool = False
    allow_seedless_generation: bool = True
    approved_examples: list = []
    approved_examples_token: str | None = None
    approved_example_indices: list | None = None


# ---------------------------------------------------------------------------
# Deterministic GST sample bank (4 unique instruction/response pairs)
# ---------------------------------------------------------------------------
GST_SAMPLES = [
    {
        "instruction": "What are the core conditions for claiming Input Tax Credit (ITC) under Section 16(2) of the CGST Act?",
        "response": "Under Section 16(2) of the CGST Act 2017, a registered taxpayer can claim ITC only if: 1. They possess a valid tax invoice or debit note. 2. The goods or services have been received. 3. The tax charged has actually been paid to the Government (and reflected in GSTR-2B). 4. They have furnished the return under Section 39 (GSTR-3B). Additional condition: Payment must be made to the supplier within 180 days.",
    },
    {
        "instruction": "Humari company ka aggregate turnover 12 crore INR hai. Kya humare liye e-invoicing mandatory hai?",
        "response": "Haan, aapke liye e-invoicing mandatory hai. CBIC ke latest notification ke anusar, jin businesses ka aggregate annual turnover kisi bhi financial year me 5 Crore INR se exceed karta hai, unhe B2B supplies aur exports ke liye e-invoices generate karna mandatory hai.",
    },
    {
        "instruction": "Explain the difference between Nil Rated, Exempted, and Zero Rated supplies under GST.",
        "response": "1. Nil Rated Supplies: Goods/services attracting 0% GST rate. 2. Exempted Supplies: Supplies exempted via specific government notifications under Section 11 of CGST Act; no ITC can be claimed. 3. Zero Rated Supplies: Exports or supplies to SEZ under Section 16 of IGST Act; full ITC can be claimed or refunded.",
    },
    {
        "instruction": "What is the penalty for late filing of GSTR-3B under Section 47 of the CGST Act?",
        "response": "For nil tax liability returns, the late fee is Rs 20 per day (Rs 10 CGST + Rs 10 SGST). For returns with tax liability, the late fee is Rs 50 per day (Rs 25 CGST + Rs 25 SGST), subject to a maximum cap depending on the taxpayer aggregate turnover.",
    },
]

# Counter to cycle through samples deterministically
_sample_counter = 0


def make_deterministic_mock_router():
    """Create a mock router capable of handling Intent Extraction, Dataset Planning, and Sample Synthesis."""
    router = Mock()
    router.initialize = AsyncMock(return_value={"initialized": ["mock_llm"], "failed": []})

    async def mock_route_handler(task, prompt, system_prompt=None, **kwargs):
        global _sample_counter
        sys_str = str(system_prompt or "")
        prompt_str = str(prompt or "")

        # 1. Intent Extraction
        if "expert ML/AI dataset researcher" in sys_str or "primary_task" in sys_str:
            intent_json = json.dumps({
                "primary_task": "instruction_tuning",
                "domain": "Indian Taxation & GST Compliance",
                "modality": "text",
                "anti_domains": ["us taxation", "crypto", "forex"],
                "key_entities": ["CGST Act 2017", "CBIC", "GSTR-3B", "Section 16 ITC"],
                "specialized_queries": [
                    "CGST Act 2017 Section 16 input tax credit eligibility",
                    "CBIC notifications e-invoicing turnover thresholds",
                    "GSTR-3B vs GSTR-2B ITC reconciliation procedures",
                ],
                "constraints": ["Follow Indian tax regulations", "Include English and Hinglish"],
                "output_format": "jsonl",
                "confidence": 0.95,
            })
            return LLMResponse(content=intent_json)

        # 2. Dataset Planning
        if "DatasetPlan" in prompt_str or "dataset plan" in sys_str.lower() or "metadata_schema" in sys_str:
            plan_json = json.dumps({
                "domain": "Indian Taxation & GST Compliance",
                "objective": "Build high-precision instruction dataset for GST compliance",
                "roles": ["Chartered Accountant", "Tax Consultant", "GST Practitioner"],
                "metadata_schema": {"section": "string", "state": "string"},
                "difficulty_distribution": {"beginner": 0.33, "intermediate": 0.33, "advanced": 0.34},
                "constraints": ["Strict adherence to CGST/IGST Act 2017"],
                "diversity_attributes": {"taxpayer_category": ["Regular", "Composition", "SEZ", "E-Commerce Operator"]},
            })
            return LLMResponse(content=plan_json)

        # 3. Seedless Sample Synthesis — cycle through bank deterministically
        chosen = GST_SAMPLES[_sample_counter % len(GST_SAMPLES)]
        _sample_counter += 1
        sample_json = json.dumps({
            "instruction": chosen["instruction"],
            "response": chosen["response"],
            "input": "",
            "reasoning": "Sourced from CGST Act 2017 and CBIC notifications.",
            "quality_score": 0.95,
            "difficulty_tier": 3,
        })
        return LLMResponse(content=sample_json)

    router.route = AsyncMock(side_effect=mock_route_handler)
    return router


@pytest.fixture
def temp_job_dir():
    """Create a temporary workspace directory for job outputs and database."""
    tmp_dir = tempfile.mkdtemp(prefix="rasosynth_job_test_")
    data_dir = os.path.join(tmp_dir, "data")
    outputs_dir = os.path.join(tmp_dir, "outputs")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)
    yield tmp_dir, data_dir, outputs_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_live_job_run_end_to_end(temp_job_dir):
    """Execute a complete end-to-end job from creation to export and DBOM verification."""
    global _sample_counter
    _sample_counter = 0

    tmp_dir, data_dir, outputs_dir = temp_job_dir
    db_url = f"sqlite+aiosqlite:///{data_dir}/test_live_run.db"

    db = await AsyncDB.create(db_url)
    assert db is not None

    router = make_deterministic_mock_router()

    config = {"output_dir": outputs_dir, "environment": "test", "default_model": "test-mock-llm"}
    orchestrator = DatasetOrchestrator(config, router, db=db)

    # 1. Create Job in DB
    job_id = str(uuid.uuid4())
    job_req = MockJobRequest()
    await db.create_job({"id": job_id, "config": job_req.model_dump(), "status": "pending"})

    # 2. Run the job
    job = Job(
        id=job_id,
        status=JobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        current_stage="analyzing_constraints",
        progress=0.0,
        samples_processed=0,
        samples_generated=0,
        sources_discovered=0,
        sources_extracted=0,
        samples_filtered=0,
        cost_usd=0.0,
        error=None,
        config=job_req.model_dump(),
    )

    await orchestrator.run(job)

    # 3. Job completed on the in-memory object
    assert job.status == JobStatus.COMPLETED, f"Job status: {job.status}, error: {job.error}"
    assert job.samples_generated >= 3
    assert job.progress == 1.0

    # 4. Job persisted in DB
    db_job = await db.get_job_status(job_id)
    assert db_job is not None
    assert db_job["status"] == "completed"
    assert db_job["samples_generated"] >= 3

    # 5. Dataset record persisted
    datasets = await db.get_datasets_by_job(job_id)
    assert len(datasets) >= 1
    dataset = datasets[0]
    assert dataset["size"] >= 3
    metadata = dataset["metadata"]
    assert "export_path" in metadata
    assert "dbom" in metadata

    # 6. Export JSONL file exists on disk
    export_path = metadata["export_path"]
    assert os.path.exists(export_path), f"Export file {export_path} does not exist"

    with open(export_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    assert len(lines) >= 3
    first_sample = json.loads(lines[0])
    assert "instruction" in first_sample
    assert "response" in first_sample
    assert len(first_sample["instruction"]) > 5
    assert len(first_sample["response"]) > 10

    # 7. Cryptographic DBOM Attestation
    dbom_cert = metadata["dbom"]
    assert dbom_cert["certificate_id"].startswith("DBOM-")
    assert "merkle_root_hash" in dbom_cert
    assert len(dbom_cert["merkle_root_hash"]) == 64  # SHA-256 hex string
    assert dbom_cert["total_samples"] >= 3

    # DBOM sidecar file on disk
    dbom_disk_path = f"{export_path}.dbom.json"
    assert os.path.exists(dbom_disk_path)

    # 8. Cryptographic verification against DB samples
    samples_in_db = await db.get_samples(dataset["id"])
    assert len(samples_in_db) >= 3

    # Verify against the stored rows as-is (content + domain metadata):
    # generation hashes content+metadata, so stripping metadata here would
    # compute a different root whenever stored metadata is non-empty. The
    # reviewed-preview test below verifies the same way.
    verification = verify_dataset_dbom(
        samples=samples_in_db,
        dbom_certificate=dbom_cert,
    )
    assert verification["is_valid"] is True
    assert verification["computed_root"] == dbom_cert["merkle_root_hash"]
    assert verification["status"] == "cryptographically_verified"


@pytest.mark.asyncio
async def test_live_job_with_reviewed_preview_batch(temp_job_dir):
    """Test job execution with user-approved preview examples flowing through to export."""
    global _sample_counter
    _sample_counter = 0

    tmp_dir, data_dir, outputs_dir = temp_job_dir
    db_url = f"sqlite+aiosqlite:///{data_dir}/test_preview_run.db"

    db = await AsyncDB.create(db_url)
    router = make_deterministic_mock_router()
    config = {"output_dir": outputs_dir, "environment": "test"}
    orchestrator = DatasetOrchestrator(config, router, db=db)

    approved_samples = [
        {
            "instruction": "Explain Section 54 refund procedure for inverted duty structure under CGST Act.",
            "response": "Under Section 54(3)(ii) of CGST Act, refund of unutilized ITC is allowed where credit has accumulated on account of rate of tax on inputs being higher than the rate of tax on output supplies.",
            "input": "",
            "quality_score": 0.98,
            "difficulty_tier": 4,
            "source_text": "CGST Act 2017 Section 54",
            "metadata": {"topic": "GST Refunds"},
        },
        {
            "instruction": "Calculate GST payable if taxable value is 50000 INR at 18% IGST.",
            "response": "The IGST is computed as: 50000 x 18% = 9000 INR. Total invoice amount is 59000 INR.",
            "input": "",
            "quality_score": 0.96,
            "difficulty_tier": 2,
            "source_text": "IGST Act Section 5",
            "metadata": {"topic": "Tax Calculation"},
        },
    ]

    job_id = str(uuid.uuid4())
    job_config = {
        "target_domain": "Indian Taxation & GST Compliance",
        "dataset_size": 2,
        "dataset_type": "sft",
        "language": "en",
        "export_format": "jsonl",
        "generation_mode": "synthetic",
        "approved_examples": approved_samples,
    }

    await db.create_job({"id": job_id, "config": job_config, "status": "pending"})

    job = Job(
        id=job_id,
        status=JobStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        current_stage="analyzing_constraints",
        progress=0.0,
        samples_processed=0,
        samples_generated=0,
        sources_discovered=0,
        sources_extracted=0,
        samples_filtered=0,
        cost_usd=0.0,
        error=None,
        config=job_config,
    )

    await orchestrator.run(job)

    assert job.status == JobStatus.COMPLETED
    assert job.samples_generated == 2

    # Verify DB records via get_job_status (returns dict)
    db_job = await db.get_job_status(job_id)
    assert db_job["status"] == "completed"
    assert db_job["samples_generated"] == 2

    datasets = await db.get_datasets_by_job(job_id)
    assert len(datasets) == 1
    dataset = datasets[0]
    assert dataset["size"] == 2
    assert "dbom" in dataset["metadata"]

    # Verify cryptographic integrity
    dbom = dataset["metadata"]["dbom"]
    samples = await db.get_samples(dataset["id"])
    assert len(samples) == 2

    verification = verify_dataset_dbom(samples, dbom)
    assert verification["is_valid"] is True
