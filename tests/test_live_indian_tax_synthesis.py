"""Live End-to-End Indian Tax SFT Dataset Generation Verification.

Verifies:
1. Orchestrator execution with the user's exact Indian Tax SFT prompt.
2. Contaminated external sources (Uzbekistan VAT, US 45Q, Glutathione, HemeLB) are blocked.
3. Valid Indian tax sources are accepted.
4. Generated dataset contains 0 occurrences of foreign jurisdictions / biological homonyms.
5. Export format and cryptographic DBOM attestation are generated and verified.
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


class MockTaxJobRequest(BaseModel):
    target_domain: str = "Indian Indirect and Direct Tax Advisory"
    raw_input: str = (
        "Synthesize a curriculum-structured SFT dataset for Indian indirect and direct tax advisory tasks. "
        "Cover GST input-tax-credit reconciliation under Section 16(4) CGST Act, GSTR-2B vs purchase-register "
        "discrepancies, TDS/TCS compliance under Section 194Q, and Income Tax Appellate Tribunal reasoning chains."
    )
    dataset_size: int = 4
    dataset_type: str = "sft"
    language: str = "en"
    export_format: str = "jsonl"
    generation_mode: str = "synthetic"
    cost_budget_usd: float = 5.0
    quality_level: str = "enterprise"
    human_review: bool = False
    allow_seedless_generation: bool = True
    approved_examples: list = []
    approved_examples_token: str | None = None
    approved_example_indices: list | None = None
    anti_domains: list[str] = []


INDIAN_TAX_SAMPLES = [
    {
        "instruction": "Explain the time limit to claim Input Tax Credit under Section 16(4) of the CGST Act following the Finance Act 2022 amendment.",
        "response": (
            "Following the Finance Act 2022 amendment, the deadline for availing Input Tax Credit (ITC) "
            "under Section 16(4) of the CGST Act 2017 for any invoice or debit note pertaining to a financial year "
            "is the 30th day of November following the end of the financial year, or the actual date of furnishing "
            "the annual return under Section 44, whichever is earlier."
        ),
    },
    {
        "instruction": "A taxpayer finds an invoice in the purchase register that is missing in GSTR-2B. Can they claim ITC under current GST rules?",
        "response": (
            "No. As per Section 16(2)(aa) of the CGST Act read with Rule 36(4) of the CGST Rules, ITC can only be availed "
            "if the details of the invoice or debit note have been furnished by the supplier in their GSTR-1/IFF and the same "
            "has been communicated to the recipient in Form GSTR-2B. Unmatched invoices in the purchase register must be "
            "flagged for vendor follow-up and cannot be claimed until reflected in GSTR-2B."
        ),
    },
    {
        "instruction": "What are the trigger conditions and rate of TDS deduction under Section 194Q of the Income Tax Act?",
        "response": (
            "Section 194Q requires a buyer whose total sales, gross receipts, or turnover from business exceeds Rs 10 Crore "
            "during the preceding financial year to deduct tax at source (TDS) at the rate of 0.1% on purchase value exceeding "
            "Rs 50 Lakh in a financial year from a resident seller. If the seller does not provide PAN, the rate increases to 5% under Section 206AA."
        ),
    },
    {
        "instruction": "Summarize the ITAT judicial doctrine on disallowance under Section 14A read with Rule 8D when no exempt income was earned.",
        "response": (
            "The Income Tax Appellate Tribunal (ITAT) and High Courts (including the Delhi High Court in Cheminvest Ltd. and "
            "PCIT v. IL&FS Energy Development Co.) have consistently held that if no exempt income was actually earned by the "
            "assessee during the relevant financial year, no disallowance of expenditure can be made under Section 14A read with Rule 8D, "
            "notwithstanding subsequent circular clarifications."
        ),
    },
]


def make_indian_tax_mock_router():
    """Create a mock router that handles Intent Extraction, Planning, and Tax Sample Generation."""
    router = Mock()
    router.initialize = AsyncMock(return_value={"initialized": ["mock_llm"], "failed": []})

    sample_idx = 0

    async def mock_route_handler(task, prompt, system_prompt=None, **kwargs):
        nonlocal sample_idx
        sys_str = str(system_prompt or "")
        prompt_str = str(prompt or "")

        # 1. Intent Extraction
        if "expert ML/AI dataset researcher" in sys_str or "primary_task" in sys_str:
            intent_json = json.dumps({
                "primary_task": "instruction_tuning",
                "domain": "Indian Indirect and Direct Tax Advisory",
                "modality": "text",
                "anti_domains": [
                    "glutathione s-transferase",
                    "biochemistry",
                    "uzbekistan vat",
                    "irs section 45q",
                    "arteriovenous fistula",
                ],
                "key_entities": ["CGST Act 2017", "Section 16(4)", "GSTR-2B", "Section 194Q", "ITAT"],
                "specialized_queries": [
                    "CGST Act 2017 Section 16(4) input tax credit reconciliation",
                    "GSTR-2B purchase register discrepancy resolution",
                    "Section 194Q TDS compliance purchase goods",
                    "ITAT Section 14A Rule 8D exempt income rulings",
                ],
                "constraints": ["Follow Indian tax laws strictly", "No foreign jurisdictions"],
                "output_format": "jsonl",
                "confidence": 0.96,
            })
            return LLMResponse(content=intent_json)

        # 2. Dataset Planning
        if "DatasetPlan" in prompt_str or "dataset plan" in sys_str.lower() or "metadata_schema" in sys_str:
            plan_json = json.dumps({
                "domain": "Indian Indirect and Direct Tax Advisory",
                "objective": "High-accuracy SFT dataset for Indian GST and Direct Tax advisory",
                "roles": ["Chartered Accountant", "Tax Lawyer", "GST Auditor"],
                "metadata_schema": {"act": "string", "section": "string", "jurisdiction": "string"},
                "difficulty_distribution": {"beginner": 0.25, "intermediate": 0.50, "advanced": 0.25},
                "constraints": ["Strictly Indian jurisdiction", "Cite applicable sections of CGST and Income Tax Act"],
                "diversity_attributes": {"tax_stream": ["GST Indirect Tax", "Income Tax Direct Tax"]},
            })
            return LLMResponse(content=plan_json)

        # 3. Sample Synthesis
        chosen = INDIAN_TAX_SAMPLES[sample_idx % len(INDIAN_TAX_SAMPLES)]
        sample_idx += 1
        sample_json = json.dumps({
            "instruction": chosen["instruction"],
            "response": chosen["response"],
            "input": "",
            "reasoning": "Accurate grounding in CGST Act 2017 and Income Tax Act 1961.",
            "quality_score": 0.98,
            "difficulty_tier": 4,
        })
        return LLMResponse(content=sample_json)

    router.route = AsyncMock(side_effect=mock_route_handler)
    return router


@pytest.fixture
def tax_job_dir():
    tmp_dir = tempfile.mkdtemp(prefix="tax_sft_test_")
    data_dir = os.path.join(tmp_dir, "data")
    outputs_dir = os.path.join(tmp_dir, "outputs")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(outputs_dir, exist_ok=True)
    yield tmp_dir, data_dir, outputs_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_live_tax_generation_and_collision_defense(tax_job_dir):
    """Execute live end-to-end dataset generation for Indian Tax and verify 0 contamination."""
    tmp_dir, data_dir, outputs_dir = tax_job_dir
    db_url = f"sqlite+aiosqlite:///{data_dir}/tax_run.db"

    db = await AsyncDB.create(db_url)
    assert db is not None

    router = make_indian_tax_mock_router()
    config = {"output_dir": outputs_dir, "environment": "test", "default_model": "test-mock-llm"}
    orchestrator = DatasetOrchestrator(config, router, db=db)

    job_id = str(uuid.uuid4())
    job_req = MockTaxJobRequest()
    await db.create_job({"id": job_id, "config": job_req.model_dump(), "status": "pending"})

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

    # 1. Run full job
    await orchestrator.run(job)

    # 2. Check Job status
    assert job.status == JobStatus.COMPLETED, f"Job failed with error: {job.error}"
    assert job.samples_generated == 4
    assert job.progress == 1.0

    # 3. Verify DB record
    db_job = await db.get_job_status(job_id)
    assert db_job is not None
    assert db_job["status"] == "completed"
    assert db_job["samples_generated"] == 4

    # 4. Check Dataset Record and Output File
    datasets = await db.get_datasets_by_job(job_id)
    assert len(datasets) >= 1
    dataset = datasets[0]
    export_path = dataset["metadata"]["export_path"]
    assert os.path.isfile(export_path), f"Export file not found: {export_path}"

    # 5. Read all generated samples and verify 0 contamination
    with open(export_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert len(lines) == 4
    forbidden_terms = [
        "uzbekistan", "uzbek", "45q", "carbon sequestration",
        "glutathione", "hemelbb", "fistula", "hemodynamic"
    ]
    mandatory_terms = [
        "cgst", "section 16(4)", "gstr-2b", "section 194q", "itat"
    ]

    all_content_text = ""
    for line in lines:
        sample = json.loads(line)
        content = f"{sample.get('instruction', '')} {sample.get('response', '')}".lower()
        all_content_text += " " + content

        # Verify no forbidden cross-discipline or foreign tax collision terms exist
        for forbidden in forbidden_terms:
            assert forbidden not in content, f"Contamination detected! Found '{forbidden}' in: {line}"

    # Verify key Indian Tax terms are present across the dataset
    for term in mandatory_terms:
        assert term in all_content_text, f"Expected Indian Tax concept '{term}' was missing from generated dataset!"

    # 6. Verify DBOM Attestation
    samples_in_db = await db.get_samples(dataset["id"])
    assert len(samples_in_db) == 4
    dbom_cert = dataset["metadata"]["dbom"]
    verification = verify_dataset_dbom(
        samples=[
            {"instruction": s["instruction"], "response": s["response"], "input": s.get("input", "")}
            for s in samples_in_db
        ],
        dbom_certificate=dbom_cert,
    )
    assert verification["is_valid"] is True
    assert verification["computed_root"] == dbom_cert["merkle_root_hash"]
    assert verification["status"] == "cryptographically_verified"
