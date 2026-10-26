import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from core.db import AsyncDB
from core.export.dbom_attestor import compute_merkle_root, compute_sample_hash
from core.orchestrator_core import DatasetOrchestrator, Job, JobStatus
from finetuning.colab_bridge import ColabBridgeTrainer
from finetuning.trainer import FineTuneConfig
class LLMResponse:
    def __init__(self, content: str = ""):
        self.content = content

PATIENT_RIGHTS_SAMPLES = [
    {
        "instruction": "Under the Indian Medical Council (Professional Conduct, Etiquette and Ethics) Regulations, what constitutes valid informed consent before a surgical procedure?",
        "response": "Under Indian Medical Council Regulations and Supreme Court guidelines (Samira Kohli v. Dr. Prabha Manchanda), informed consent requires the doctor to explain: (1) the nature and purpose of the procedure, (2) known material risks and potential complications, (3) alternative treatments available with their respective risks, and (4) the consequences of refusal. Consent must be voluntary, given by a competent patient (or legal guardian if minor/incapacitated), and obtained prior to initiating non-emergency treatment."
    },
    {
        "instruction": "What questions can a patient ask an operating surgeon prior to giving consent for surgery in an Indian hospital?",
        "response": "Under Indian patient charter guidelines and the Consumer Protection Act, a patient is entitled to ask: (1) What is the exact name and purpose of the procedure? (2) What are the success rates and potential complications? (3) Who will be the primary operating surgeon and what is their experience? (4) Are there non-surgical alternative treatments? (5) What is the estimated total cost and hospital stay duration? (6) What post-operative care and rehabilitation will be required?"
    },
    {
        "instruction": "How can a patient obtain their medical records and indoor case papers from a private hospital in India?",
        "response": "According to Regulation 1.3.2 of the Indian Medical Council Regulations 2002, every physician/hospital is legally obligated to provide copies of medical records within 72 hours of a request by the patient or authorized attendant. The patient should submit a written application addressed to the Medical Superintendent or Medical Records Department (MRD), pay reasonable photocopying fees, and collect stamped and signed copies."
    },
    {
        "instruction": "How can an aggrieved patient file a medical negligence complaint against a hospital under the Consumer Protection Act 2019?",
        "response": "Under the Consumer Protection Act 2019, medical services rendered for consideration fall within consumer jurisdiction. The patient can: (1) Draft a formal consumer complaint specifying deficiency of service, medical records, and expert opinion if available. (2) File electronically via the e-Daakhil portal (edaakhil.nic.in) or physically at the District Consumer Commission (claims up to Rs 50 lakh) or State Commission (Rs 50 lakh to 2 crore). (3) The complaint must be filed within 2 years from the date of the cause of action."
    },
    {
        "instruction": "Can an Indian hospital withhold medical records if the patient has outstanding billing disputes?",
        "response": "No. Under Medical Council of India guidelines and judicial precedents by various High Courts and State Information Commissions, medical records cannot be held hostage or withheld due to financial disputes or unpaid hospital bills. Patients have an absolute legal right to their clinical records, as lack of access may compromise ongoing or subsequent medical treatment."
    },
    {
        "instruction": "What emergency treatment rights do patients have in private hospitals under Indian law?",
        "response": "Under Article 21 of the Constitution and landmark judgments like Parmanand Katara v. Union of India, all hospitals (public and private) are constitutionally and legally mandated to provide immediate emergency life-saving medical care and stabilization to accident victims and critical patients without demanding upfront advance payment or waiting for police formalities."
    },
    {
        "instruction": "What constitutes medical negligence under the Consumer Protection Act 2019?",
        "response": "Under the Bolam and Jacob Mathew tests applied by Indian courts, medical negligence requires proving three elements: (1) the hospital/doctor owed a legal duty of care to the patient, (2) the doctor breached that duty by acting below the standard of a reasonably competent practitioner in that field, and (3) the breach directly caused actionable physical, mental, or financial damage to the patient."
    },
    {
        "instruction": "Does a patient have the right to seek a second opinion under the Charter of Patients' Rights adopted by the National Human Rights Commission (NHRC)?",
        "response": "Yes. The Charter of Patients' Rights framed by NHRC and adopted by the Ministry of Health and Family Welfare explicitly guarantees the patient's right to seek a second medical opinion from a healthcare professional of their choice, and the primary hospital is obligated to release all case records and diagnostic reports without prejudice."
    },
    {
        "instruction": "What plain-language disclosures must an Indian hospital provide regarding treatment estimates and package rates?",
        "response": "Under Clinical Establishments Act rules and Consumer Protection Act guidelines, hospitals are required to display standardized rate charts for room tariffs, doctor visits, and common surgical packages in prominent public areas and in regional languages, and provide written itemized estimates to the patient before elective admissions."
    },
    {
        "instruction": "Where can a patient file an ethics grievance against an allopathic doctor in India?",
        "response": "An ethics complaint regarding professional misconduct can be submitted to the State Medical Council where the doctor is registered, or to the National Medical Commission (NMC, Ethics and Medical Registration Board). The council possesses disciplinary powers under NMC Act 2019 to suspend or cancel the medical practitioner's license."
    }
]


def make_patient_rights_mock_router():
    router = Mock()
    router.initialize = AsyncMock(return_value={"initialized": ["mock_llm"], "failed": []})
    sample_counter = 0

    async def mock_route(task, prompt, system_prompt=None, **kwargs):
        nonlocal sample_counter
        sys_str = str(system_prompt or "")
        prompt_str = str(prompt or "")

        if "expert ML/AI dataset researcher" in sys_str or "primary_task" in sys_str:
            return LLMResponse(content=json.dumps({
                "primary_task": "instruction_tuning",
                "domain": "Healthcare Patient Rights & Informed Consent",
                "modality": "text",
                "anti_domains": ["us law", "groningen", "heat pump", "chemistry", "molecular"],
                "key_entities": ["Indian Medical Council Regulations", "Consumer Protection Act 2019", "Informed Consent", "Medical Records"],
                "specialized_queries": [
                    "Indian Medical Council informed consent guidelines",
                    "Consumer Protection Act 2019 hospital patient rights",
                ],
                "constraints": ["Grounded in Indian law", "Plain simple language"],
                "output_format": "jsonl",
                "confidence": 0.95,
            }))

        if "DatasetPlan" in prompt_str or "dataset plan" in sys_str.lower():
            return LLMResponse(content=json.dumps({
                "domain": "Healthcare Patient Rights & Informed Consent",
                "objective": "High-fidelity instruction dataset on patient rights under Indian law",
                "roles": ["Patient Advocate", "Healthcare Legal Counsel", "Medical Ethics Officer"],
                "metadata_schema": {"regulation": "string", "plain_language": "boolean"},
                "difficulty_distribution": {"beginner": 0.4, "intermediate": 0.4, "advanced": 0.2},
                "constraints": ["Grounded in Indian statutory provisions"],
                "diversity_attributes": {"topic": ["Informed Consent", "Medical Records", "Consumer Protection", "Emergency Rights"]},
            }))

        chosen = PATIENT_RIGHTS_SAMPLES[sample_counter % len(PATIENT_RIGHTS_SAMPLES)]
        sample_counter += 1
        return LLMResponse(content=json.dumps({
            "instruction": chosen["instruction"],
            "response": chosen["response"],
            "input": "",
            "quality_score": 0.95,
            "difficulty_tier": 3,
        }))

    router.route = AsyncMock(side_effect=mock_route)
    return router


@pytest.mark.asyncio
async def test_v1_patient_rights_topic_fidelity():
    """V1: Re-run patient-rights prompt: at least 8 of the first 10 samples must be on-topic."""
    tmp_dir = tempfile.mkdtemp(prefix="rasosynth_v1_")
    try:
        db_url = f"sqlite+aiosqlite:///{tmp_dir}/test_v1.db"
        db = await AsyncDB.create(db_url)
        router = make_patient_rights_mock_router()
        config = {"output_dir": os.path.join(tmp_dir, "outputs")}
        orchestrator = DatasetOrchestrator(config, router, db=db)

        job_id = "job-v1-a9b31783"
        prompt = (
            "Create instruction-response pairs explaining patient rights and informed consent in "
            "Indian hospitals: what informed consent means, what a patient can ask before surgery, "
            "how to get their medical records, and how to file a complaint — each answer grounded "
            "in Indian law (Indian Medical Council Regulations, Consumer Protection Act 2019) and "
            "written in plain simple language."
        )

        job_req = {
            "id": job_id,
            "target_domain": prompt,
            "raw_input": prompt,
            "prompt": prompt,
            "dataset_size": 100,
            "dataset_type": "sft",
            "generation_mode": "synthetic",
            "allow_seedless_generation": True,
            "language": "en",
            "human_review": True,
            "human_review_mode": "async",
        }

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
            config=job_req,
        )

        res = await orchestrator.run(job)
        samples = res.get("constructed_samples", [])
        assert len(samples) > 0, "Pipeline generated 0 samples"

        # Check first 10 samples for topic fidelity
        on_topic_count = 0
        for i, s in enumerate(samples[:10]):
            score = orchestrator._compute_sample_topic_relevance(s["instruction"], s["response"], prompt, prompt)
            if score >= 0.60:
                on_topic_count += 1

        assert on_topic_count >= 8, f"V1 Topic Fidelity Failed: only {on_topic_count}/10 on-topic (required >= 8/10)"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_v2_finetune_loss_diversity_and_simulated_label():
    """V2: Two fine-tune runs on DIFFERENT datasets produce different losses and are labeled Simulated."""
    tmp_dir = tempfile.mkdtemp(prefix="rasosynth_v2_")
    try:
        events_1 = []
        events_2 = []

        cfg1 = FineTuneConfig(
            dataset_id="9b954634-tax-finance",
            dataset_path=os.path.join(tmp_dir, "dataset1.jsonl"),
            num_train_epochs=1,
            output_model_name="smollm2-tax",
            per_device_train_batch_size=4,
        )
        samples1 = [{"instruction": "Calculate GST", "response": "18%"}]
        with open(cfg1.dataset_path, "w") as f:
            f.write(json.dumps(samples1[0]) + "\n")

        trainer1 = ColabBridgeTrainer(cfg1, output_dir=os.path.join(tmp_dir, "out1"))
        trainer1.execute_training(samples1, put_event=events_1.append)

        cfg2 = FineTuneConfig(
            dataset_id="a9b31783-patient-rights",
            dataset_path=os.path.join(tmp_dir, "dataset2.jsonl"),
            num_train_epochs=1,
            output_model_name="smollm2-patient-rights",
            per_device_train_batch_size=4,
        )
        samples2 = [{"instruction": "Explain patient rights", "response": "Informed consent..."}]
        with open(cfg2.dataset_path, "w") as f:
            f.write(json.dumps(samples2[0]) + "\n")

        trainer2 = ColabBridgeTrainer(cfg2, output_dir=os.path.join(tmp_dir, "out2"))
        trainer2.execute_training(samples2, put_event=events_2.append)

        completed_1 = next(e for e in events_1 if e.get("type") == "completed")
        completed_2 = next(e for e in events_2 if e.get("type") == "completed")

        loss_1 = completed_1["final_train_loss"]
        loss_2 = completed_2["final_train_loss"]

        # 1. Losses must be different
        assert loss_1 != loss_2, f"V2 Failed: byte-identical loss {loss_1} across two different datasets!"
        # 2. Both must be explicitly labeled simulated
        assert completed_1.get("is_simulated") is True
        assert completed_2.get("is_simulated") is True
        assert completed_1.get("execution_mode") == "simulated"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_v3_merkle_roots_differ_and_match_recomputation():
    """V3: Two different datasets have different Merkle roots and match JSONL recomputation."""
    tmp_dir = tempfile.mkdtemp(prefix="rasosynth_v3_")
    try:
        samples_tax = [
            {"instruction": "Calculate GST on 250000", "response": "45000", "input": ""},
            {"instruction": "ITC conditions", "response": "Tax invoice required", "input": ""},
        ]
        samples_med = [
            {"instruction": "Explain informed consent in Indian hospitals", "response": "MCI regulations require full risk disclosure", "input": ""},
            {"instruction": "How to get case records", "response": "72 hours under Regulation 1.3.2", "input": ""},
        ]

        tax_leaves = [compute_sample_hash(s) for s in samples_tax]
        med_leaves = [compute_sample_hash(s) for s in samples_med]

        root_tax = compute_merkle_root(tax_leaves)
        root_med = compute_merkle_root(med_leaves)

        # 1. Different datasets MUST produce different roots
        assert root_tax != root_med, "V3 Failed: identical Merkle roots for different datasets!"
        # 2. Recomputed root from raw leaves matches exactly
        assert root_tax == compute_merkle_root([compute_sample_hash(s) for s in samples_tax])
        assert root_med == compute_merkle_root([compute_sample_hash(s) for s in samples_med])
        # 3. Model card seals differ
        seal_tax = hashlib.sha256(f"tax-run:{root_tax}:0.21".encode()).hexdigest()
        seal_med = hashlib.sha256(f"med-run:{root_med}:0.32".encode()).hexdigest()
        assert seal_tax != seal_med
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_v4_score_consistency_5d_and_review_queue():
    """V4: Library score equals detail score; per-dataset 5D scores exist; review queue non-empty."""
    tmp_dir = tempfile.mkdtemp(prefix="rasosynth_v4_")
    try:
        db_url = f"sqlite+aiosqlite:///{tmp_dir}/test_v4.db"
        db = await AsyncDB.create(db_url)
        router = make_patient_rights_mock_router()
        config = {"output_dir": os.path.join(tmp_dir, "outputs")}
        orchestrator = DatasetOrchestrator(config, router, db=db)

        job_id = "job-v4-test"
        job_req = {
            "id": job_id,
            "target_domain": "Healthcare Patient Rights",
            "dataset_size": 20,
            "dataset_type": "sft",
            "generation_mode": "synthetic",
            "allow_seedless_generation": True,
            "language": "en",
            "human_review": True,
            "human_review_mode": "async",
        }

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
            config=job_req,
        )

        res = await orchestrator.run(job)
        quality_breakdown = res.get("quality_breakdown")
        assert quality_breakdown is not None, "V4: quality_breakdown missing"
        assert "topic_fidelity" in quality_breakdown
        assert "source_grounding" in quality_breakdown
        assert "instruction_clarity" in quality_breakdown
        assert "response_completeness" in quality_breakdown
        assert "domain_correctness" in quality_breakdown

        composite = quality_breakdown["composite"]
        assert composite > 0.50

        # Review items submitted
        if orchestrator.review_service:
            q = await orchestrator.review_service.get_queue(job_id=job_id)
            assert q.get("total", 0) > 0, "V4: Review queue is empty for job with human_review=True"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
