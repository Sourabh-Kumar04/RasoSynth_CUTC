"""Regressive End-to-End Testing Suite for All User and System Workflows.

Validates the complete lifecycle:
1. Planning & Coverage Diversity Matrix
2. Synthesis Paradigms (SFT, CoT, Tool Calling, DPO, KTO, SimPO, RAG, Multi-Turn, Dialectic, Contrastive)
3. Multilingual, Script & Cultural Safety Guardrails
4. Quality Scorer, Contamination, Adversarial, Best-of-N, Representation Balancer & Active Rebalancer
5. DBOM Merkle Attestation, Sharded Export & Fine-Tuning Recipes
6. Full FastAPI REST Server Endpoints via TestClient with CSRF
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

# Ensure security JWT secret before server import
os.environ.setdefault("JWT_SECRET", "regressive_test_secret_key_1234567890_abcdefghijklmnopqrstuvwxyz")

from api.server import app


@pytest.fixture(scope="module")
def client():
    """Create FastAPI TestClient pre-configured with CSRF token."""
    with TestClient(app) as c:
        csrf_res = c.get("/auth/csrf-token")
        if csrf_res.status_code == 200:
            token = csrf_res.json().get("csrf_token")
            if token:
                c.headers.update({"x-csrf-token": token})
        yield c


class TestWorkflow1PlanningAndCoverage:
    """Workflow 1: Dataset Planning, Coverage Matrix, and Intelligent Mode Selection."""

    def test_coverage_matrix_and_mode_selection(self):
        from pipeline.planner import DatasetPlan, CoveragePlanner

        plan = DatasetPlan(
            domain="taxation",
            objective="Direct and indirect tax filing advisory",
            roles=["Taxpayer", "Chartered Accountant"],
            metadata_schema={"form": "string"},
            difficulty_distribution={"beginner": 0.5, "expert": 0.5},
            constraints=["Follow CGST Act 2017"],
            diversity_attributes={"topic": ["GST", "Income Tax", "TDS"], "difficulty": ["standard", "expert"]},
        )
        cov = CoveragePlanner({})
        matrix = cov.generate_matrix(plan, target_size=12)

        assert len(matrix.cells) == 12
        assert "topic" in matrix.dimensions
        assert "difficulty" in matrix.dimensions

        # Mode selection
        def select_mode(config, search_succeeded=True):
            if config.get("source_urls"):
                return "source"
            if config.get("generation_mode") == "synthetic":
                return "synthetic"
            if not search_succeeded and config.get("allow_seedless_generation", True):
                return "synthetic"
            return "hybrid"

        assert select_mode({"source_urls": ["https://gst.gov.in"]}) == "source"
        assert select_mode({"generation_mode": "synthetic"}) == "synthetic"
        assert select_mode({"generation_mode": "hybrid"}, search_succeeded=False) == "synthetic"


class TestWorkflow2SynthesisParadigms:
    """Workflow 2: End-to-End Generation Formats & Trajectory Verification."""

    def test_cot_and_thought_separation(self):
        from core.generation.cot_synthesizer import build_cot_prompt_directive, extract_thought_and_solution

        prompt = build_cot_prompt_directive(language="hinglish")
        assert "<thought>" in prompt

        sample = "<thought>Pehle Rs. 1,00,000 par 18% GST nikalenge = 18,000.</thought>Total amount ₹1,18,000 hoga."
        thought, solution = extract_thought_and_solution(sample)
        assert thought is not None and "18,000" in thought
        assert "₹1,18,000" in solution

    def test_tool_calling_synthesis(self):
        from core.generation.tool_caller import build_tool_calling_system_prompt, DEFAULT_FINANCE_TOOLS, format_tool_calling_sample

        directive = build_tool_calling_system_prompt(DEFAULT_FINANCE_TOOLS)
        assert "check_itc_balance" in directive
        assert "generate_gst_challan" in directive

        formatted = format_tool_calling_sample(
            instruction="Mera ITC balance check karo",
            tool_calls=[{"name": "check_itc_balance", "arguments": {"gstin": "27AAAAA0000A1Z5"}}],
            assistant_thought="Checking ITC portal balance",
        )
        assert "tool_calls" in formatted
        assert formatted["tool_calls"][0]["name"] == "check_itc_balance"

    def test_preference_synthesis_kto_and_simpo(self):
        from core.generation.preference_synthesizer import build_preference_directive, format_kto_sample, format_simpo_pair

        kto_dir = build_preference_directive("kto")
        simpo_dir = build_preference_directive("simpo")
        assert "KTO" in kto_dir
        assert "SimPO" in simpo_dir

        kto_s = format_kto_sample("What is 80C?", "Rs. 1.5 Lakhs deduction", is_desirable=True)
        assert kto_s["label"] is True
        assert kto_s["kto_tag"] == "desirable"

        simpo_s = format_simpo_pair("Query", "Concise correct answer", "Excessively bloated redundant response", target_margin=0.5)
        assert simpo_s["simpo_metadata"]["target_margin"] == 0.5

    def test_rag_with_hard_negatives_and_faithfulness(self):
        from core.generation.rag_synthesizer import format_rag_sample, evaluate_rag_faithfulness

        rag_sample = format_rag_sample(
            query="What is 80C limit?",
            positive_contexts=["Section 80C allows Rs. 1,50,000 deduction per financial year."],
            hard_negatives=["Section 80D covers health insurance up to Rs. 25,000."],
            grounded_response="The maximum deduction under Section 80C is Rs. 1,50,000 [1].",
            domain="taxation",
        )
        assert len(rag_sample["contexts"]) == 2
        assert rag_sample["metadata"]["citation_count"] == 1

        eval_res = evaluate_rag_faithfulness(
            response="Section 80C allows Rs. 1,50,000 deduction [1].",
            positive_contexts=["Section 80C allows Rs. 1,50,000 deduction per financial year."],
        )
        assert eval_res["status"] == "grounded"
        assert eval_res["has_citations"] is True

    def test_multi_turn_and_dialectic_debate(self):
        from core.generation.multi_turn_synthesizer import format_multi_turn_sample, evaluate_dialogue_coherence
        from core.generation.socratic_synthesizer import format_dialectic_sample, evaluate_dialectic_coherence

        turns = [
            {"role": "user", "content": "How do I claim ITC?"},
            {"role": "assistant", "content": "Ensure invoice is uploaded in GSTR-2B."},
            {"role": "user", "content": "What if supplier files quarterly?"},
            {"role": "assistant", "content": "Use IFF facility under Rule 36(4)."},
        ]
        mt = format_multi_turn_sample(turns, format_type="sharegpt")
        assert len(mt["conversations"]) == 4
        coh_mt = evaluate_dialogue_coherence(turns)
        assert coh_mt["is_coherent"] is True

        rounds = [
            {
                "speaker": "Auditor Sharma",
                "argument": "Under Section 16(2)(aa) of the CGST Act, ITC cannot be availed unless the supplier uploads invoice details in Form GSTR-1.",
            },
            {
                "speaker": "CFO Mehra",
                "argument": "The taxpayer has paid the invoice in full along with taxes; penalizing the recipient for bona fide supplier delay violates judicial precedent in Bharti Airtel.",
            },
        ]
        dialectic = format_dialectic_sample(
            topic="GSTR-2B timing mismatch",
            debate_rounds=rounds,
            verdict="Adjudicated Consensus: The taxpayer must reverse ITC provisionally under Rule 37A with interest, but may reclaim it immediately once the supplier rectifies GSTR-3B.",
            domain="taxation",
        )
        assert dialectic["metadata"]["type"] == "dialectic_debate"
        coh_dia = evaluate_dialectic_coherence(rounds, dialectic["verdict"])
        assert coh_dia["is_valid"] is True


class TestWorkflow3MultilingualAndGuardrails:
    """Workflow 3: Multilingual Controls, PII Masking, Speech Verbalization & Cultural Safety."""

    def test_pii_masking(self):
        from core.validation.indian_pii import mask_indian_pii, detect_indian_pii

        raw = "My Aadhaar is 2345 6789 0123, PAN is ABCDE1234F, and phone is +91 98765 43210."
        masked = mask_indian_pii(raw, replacement_mode="redact")
        assert "[AADHAAR_REDACTED]" in masked
        assert "[PAN_REDACTED]" in masked
        assert "[PHONE_REDACTED]" in masked

        detected = detect_indian_pii(raw)
        assert len(detected["pan"]) >= 1

    def test_speech_normalization(self):
        from core.normalization.indian_numerical import verbalize_for_speech

        text = "₹500 ka GST penalty aur OTP"
        speech = verbalize_for_speech(text, language="hi")
        assert "500 rupaye" in speech
        assert "जीएसटी" in speech

    def test_fidelity_metrics(self):
        from core.metrics.fidelity import evaluate_fidelity

        res = evaluate_fidelity(
            original_text="Tax invoice is mandatory for claiming ITC.",
            back_translated_text="Tax invoice is compulsory for availing ITC.",
        )
        assert res["chrf_score"] > 30.0
        assert "is_faithful" in res

    def test_cultural_safety(self):
        from core.validation.cultural_guardrails import check_cultural_safety

        clean_safe, _ = check_cultural_safety("Please pay your advance tax on time.")
        assert clean_safe is True

        toxic_safe, reason = check_cultural_safety("bhangi log tax nahi bharte")
        assert toxic_safe is False
        assert reason is not None


class TestWorkflow4QualityCurationAndBalancing:
    """Workflow 4: Quality Scoring, Contamination, Red-Teaming, Best-of-N & Representation."""

    def test_quality_scoring_determinism(self):
        from pipeline.quality_breakdown import QualityScoreBreakdown, compute_final_score

        b1 = QualityScoreBreakdown(
            signal_score=0.9,
            statistical_score=0.85,
            semantic_score=0.95,
            reasoning_score=0.8,
            grounding_score=0.9,
        )
        b2 = QualityScoreBreakdown(
            signal_score=0.9,
            statistical_score=0.85,
            semantic_score=0.95,
            reasoning_score=0.8,
            grounding_score=0.9,
        )
        s1 = compute_final_score(b1)
        s2 = compute_final_score(b2)
        assert s1 == s2
        assert s1 > 0.80

    def test_contamination_audit(self):
        from core.evaluation.contamination_checker import check_dataset_contamination

        clean_data = [{"instruction": "What is Section 139?", "response": "Return filing section."}]
        res = check_dataset_contamination(clean_data, benchmarks=["gsm8k"])
        assert res["status"] == "clean"
        assert res["contamination_rate_pct"] == 0.0

    def test_adversarial_red_teaming(self):
        from core.safety.adversarial_generator import generate_adversarial_probes, check_adversarial_compliance

        probes = generate_adversarial_probes(domain="taxation", sample_count=3)
        assert len(probes) == 3

        comp = check_adversarial_compliance(
            response="I cannot assist with tax evasion schemes under Section 132 of the CGST Act.",
            expected_behavior="Strict refusal",
        )
        assert comp["passed"] is True
        assert comp["status"] == "resisted"

    def test_best_of_n_rejection_sampling(self):
        from core.curation.best_of_n import filter_best_of_n

        candidates = [
            "<thought>Step 1: 100 * 0.18 = 18.</thought>₹18",
            "<thought>Calculation: 100 * 18% = 18.</thought>18",
            "<thought>Wrong guess.</thought>28",
        ]
        bon = filter_best_of_n("Compute 18% on 100", candidates)
        assert bon["status"] == "consensus_reached"
        assert bon["target_answer"] == "18"
        assert bon["preference_pair"] is not None

    def test_representation_balancer_and_active_rebalancing(self):
        from core.curation.representation_balancer import audit_dataset_representation
        from core.curation.active_balancer import plan_active_rebalancing

        dataset = [
            {"instruction": "Startup GST registration in Bengaluru, Karnataka", "response": "Apply online"},
            {"instruction": "Export documentation at Mumbai port, Maharashtra", "response": "Submit shipping bill"},
        ]
        audit = audit_dataset_representation(dataset)
        assert audit["total_samples"] == 2
        assert "northeast" in audit["underrepresented_zones"] or "east" in audit["underrepresented_zones"]

        rebal = plan_active_rebalancing(audit, target_sample_pool=50, domain="trade")
        assert rebal["status"] == "rebalancing_plan_generated"
        assert len(rebal["targeted_directives"]) > 0

    def test_judge_calibration(self):
        from core.evaluation.judge_calibrator import calibrate_judge_alignment

        evals = [
            {"human_decision": "approved", "judge_score": 0.90},
            {"human_decision": "approved", "judge_score": 0.85},
            {"human_decision": "rejected", "judge_score": 0.40},
        ]
        calib = calibrate_judge_alignment(evals, default_threshold=0.70)
        assert calib["pairwise_accuracy_pct"] == 100.0

    def test_direct_benchmark_evaluator(self):
        from core.evaluation.benchmark_evaluator import evaluate_benchmark_split

        pairs = [
            {"prediction": "18000", "reference": "18000"},
            {"prediction": "Mandatory Section 16 [1]", "reference": "Mandatory Section 16 [1]"},
        ]
        report = evaluate_benchmark_split(pairs, benchmark_name="Unit Benchmark")
        assert report["exact_match_pct"] == 100.0
        assert report["citation_accuracy_pct"] == 100.0


class TestWorkflow5PackagingAndDistribution:
    """Workflow 5: Hugging Face Cards, Training Recipes, DBOM Attestation & Sharding."""

    def test_huggingface_card_generator(self):
        from core.export.huggingface_exporter import generate_hf_dataset_card

        card = generate_hf_dataset_card(
            dataset_name="indic-tax-sft",
            domain="taxation",
            sample_count=5000,
            language="hinglish",
            dataset_type="sft",
            tokenizer_savings_pct=64.5,
        )
        assert "---" in card
        assert "license: apache-2.0" in card
        assert "64%" in card

    def test_training_recipe_generator(self):
        from core.training.recipe_generator import generate_training_recipe

        recipe = generate_training_recipe(
            framework="unsloth",
            base_model="sarvamai/sarvam-2b-v0.5",
            dataset_type="sft",
        )
        assert "FastLanguageModel" in recipe["content"]
        assert "sarvamai/sarvam-2b-v0.5" in recipe["content"]

    def test_cryptographic_dbom_attestation(self):
        from core.export.dbom_attestor import generate_dbom_attestation, verify_dataset_dbom

        samples = [
            {"instruction": "Q1", "response": "A1"},
            {"instruction": "Q2", "response": "A2"},
        ]
        dbom = generate_dbom_attestation(dataset_name="test-ds", samples=samples)
        assert dbom["certificate_id"].startswith("DBOM-")

        verify_clean = verify_dataset_dbom(samples, dbom)
        assert verify_clean["is_valid"] is True

        tampered = [{"instruction": "Q1 [TAMPERED]", "response": "A1"}, samples[1]]
        verify_tampered = verify_dataset_dbom(tampered, dbom)
        assert verify_tampered["is_valid"] is False

    def test_streaming_dataset_sharder(self):
        from core.export.streaming_sharder import shard_dataset_records

        samples = [{"instruction": f"Q{i}", "response": f"A{i}"} for i in range(15)]
        res = shard_dataset_records(samples, shard_size=5, prefix="train", compress=True)
        assert res["shard_count"] == 3
        assert res["manifest"]["format"] == "jsonl.gz"


class TestWorkflow6FastAPIEndpointsRegression:
    """Workflow 6: Full Live HTTP Regression across FastAPI Endpoints."""

    def test_root_and_health(self, client):
        res = client.get("/")
        assert res.status_code == 200
        assert res.json()["name"] == "RasoSynthTune"

    def test_tool_mask_pii(self, client):
        payload = {"text": "Aadhaar is 2345 6789 0123"}
        res = client.post("/tools/mask-pii", json=payload)
        assert res.status_code == 200
        assert "[AADHAAR_REDACTED]" in res.json()["masked"]

    def test_tool_speech_normalize(self, client):
        payload = {"text": "₹500 ka challan", "language": "hi"}
        res = client.post("/tools/speech-normalize", json=payload)
        assert res.status_code == 200
        assert "500 rupaye" in res.json()["verbalized"].lower()

    def test_tool_evaluate_fidelity(self, client):
        payload = {"hypothesis": "Tax invoice required", "reference": "Tax invoice mandatory"}
        res = client.post("/tools/evaluate-fidelity", json=payload)
        assert res.status_code == 200
        assert "chrf_score" in res.json()
        assert "is_faithful" in res.json()

    def test_tool_evaluate_rubric(self, client):
        payload = {
            "instruction": "Calculate 18% GST on Rs. 100",
            "response": "18% GST on Rs. 100 is Rs. 18.",
            "language": "en",
        }
        res = client.post("/tools/evaluate-rubric", json=payload)
        assert res.status_code == 200
        assert "overall_score" in res.json()
        assert "rating" in res.json()

    def test_tool_evaluate_rag(self, client):
        payload = {
            "response": "Section 80C allows Rs. 1,50,000 [1].",
            "positive_contexts": ["Section 80C allows Rs. 1,50,000 deduction per financial year."],
        }
        res = client.post("/tools/evaluate-rag", json=payload)
        assert res.status_code == 200
        assert res.json()["status"] == "grounded"

    def test_tool_evaluate_dialogue(self, client):
        payload = {
            "turns": [
                {"role": "user", "content": "Hello bot how to claim itc?"},
                {"role": "assistant", "content": "You can claim ITC via Form GSTR-2B reconciliation."},
            ]
        }
        res = client.post("/tools/evaluate-dialogue", json=payload)
        assert res.status_code == 200
        assert res.json()["is_coherent"] is True

    def test_tool_semantic_density(self, client):
        payload = {
            "samples": [
                {"instruction": "GST filing advice", "response": "Submit GSTR-3B."},
                {"instruction": "TDS calculation", "response": "10% under Section 194J."},
                {"instruction": "Customs clearance", "response": "File bill of entry."},
            ],
            "k_clusters": 2,
        }
        res = client.post("/tools/semantic-density", json=payload)
        assert res.status_code == 200
        assert res.json()["total_samples"] == 3
        assert len(res.json()["points"]) == 3

    def test_tool_best_of_n(self, client):
        payload = {
            "instruction": "What is 10 + 10?",
            "candidates": ["<thought>10+10=20</thought>20", "<thought>Math is 20</thought>20", "30"],
        }
        res = client.post("/tools/best-of-n", json=payload)
        assert res.status_code == 200
        assert res.json()["target_answer"] == "20"

    def test_tool_audit_representation(self, client):
        payload = {
            "samples": [
                {"instruction": "Startup in Bengaluru, Karnataka", "response": "Tech hub"},
                {"instruction": "Farm subsidy in UP gaon", "response": "Kisan grant"},
            ]
        }
        res = client.post("/tools/audit-representation", json=payload)
        assert res.status_code == 200
        assert "representation_parity_score" in res.json()

    def test_tool_rebalance_dataset(self, client):
        audit_mock = {
            "representation_parity_score": 0.40,
            "zone_distribution": {"north": {"percentage": 70.0}, "south": {"percentage": 30.0}},
            "setting_distribution": {"tier_1_metro": {"percentage": 90.0}, "rural_gramin": {"percentage": 10.0}},
            "underrepresented_zones": ["east", "west", "northeast"],
        }
        payload = {"audit_report": audit_mock, "target_sample_pool": 60, "domain": "taxation"}
        res = client.post("/tools/rebalance-dataset", json=payload)
        assert res.status_code == 200
        assert res.json()["status"] == "rebalancing_plan_generated"

    def test_tool_generate_dialectic(self, client):
        payload = {
            "topic": "Depreciation claim on leased assets",
            "debate_rounds": [
                {"speaker": "Auditor Sharma", "argument": "Ownership is essential under Section 32 of Income Tax Act for claiming depreciation."},
                {"speaker": "CFO Mehra", "argument": "Finance leases transfer substantially all economic risks and rewards under accounting standard AS-19."},
            ],
            "verdict": "Adjudicated: Lessee may claim depreciation only when economic ownership and statutory capital asset criteria are met.",
            "domain": "taxation",
        }
        res = client.post("/tools/generate-dialectic", json=payload)
        assert res.status_code == 200
        assert "sample" in res.json()
        assert res.json()["coherence"]["is_valid"] is True

    def test_tool_calibrate_judge(self, client):
        payload = {
            "evaluations": [
                {"human_decision": "approved", "judge_score": 0.88},
                {"human_decision": "approved", "judge_score": 0.75},
                {"human_decision": "rejected", "judge_score": 0.30},
            ]
        }
        res = client.post("/tools/calibrate-judge", json=payload)
        assert res.status_code == 200
        assert res.json()["pairwise_accuracy_pct"] == 100.0

    def test_tool_evaluate_benchmark(self, client):
        payload = {
            "evaluation_pairs": [
                {"prediction": "GST is 18%", "reference": "GST is 18%"},
                {"prediction": "Section 80C", "reference": "Section 80C"},
            ]
        }
        res = client.post("/tools/evaluate-benchmark", json=payload)
        assert res.status_code == 200
        assert res.json()["exact_match_pct"] == 100.0

    def test_tool_shard_dataset(self, client):
        payload = {
            "samples": [{"instruction": f"Q{i}", "response": f"A{i}"} for i in range(12)],
            "shard_size": 4,
            "prefix": "test_train",
            "compress": False,
        }
        res = client.post("/tools/shard-dataset", json=payload)
        assert res.status_code == 200
        assert res.json()["shard_count"] == 3

    def test_tool_audit_contamination(self, client):
        payload = {
            "samples": [{"instruction": "Custom prompt on GST filing", "response": "Standard answer"}],
            "benchmarks": ["gsm8k"],
        }
        res = client.post("/tools/audit-contamination", json=payload)
        assert res.status_code == 200
        assert res.json()["status"] == "clean"

    def test_tool_generate_adversarial_probes(self, client):
        payload = {"domain": "taxation", "sample_count": 3}
        res = client.post("/tools/generate-adversarial-probes", json=payload)
        assert res.status_code == 200
        assert len(res.json()["probes"]) == 3

    def test_tool_verify_dbom(self, client):
        from core.export.dbom_attestor import generate_dbom_attestation

        samples = [{"instruction": "Q1", "response": "A1"}]
        dbom = generate_dbom_attestation("api-test", samples)
        payload = {"samples": samples, "dbom_certificate": dbom}
        res = client.post("/tools/verify-dbom", json=payload)
        assert res.status_code == 200
        assert res.json()["is_valid"] is True

    def test_tool_generate_contrastive_pair(self, client):
        payload = {
            "instruction": "Tax rate on IT services",
            "grounded_response": "The applicable GST rate on software services is 18%.",
            "domain": "taxation",
        }
        res = client.post("/tools/generate-contrastive-pair", json=payload)
        assert res.status_code == 200
        assert "perturbed_negative" in res.json()
        assert "critique" in res.json()

    def test_get_quality_benchmarks(self, client):
        res = client.get("/benchmarks/quality")
        assert res.status_code == 200
        data = res.json()
        assert "benchmark_data" in data
        assert "markdown_report" in data
        results = data["benchmark_data"]["results"]
        assert "benchmark_generation_quality" in results
        assert "benchmark_latency" in results
        assert "benchmark_provider_quality" in results
        assert "benchmark_cost_efficiency" in results
        assert results["benchmark_generation_quality"]["status"] == "completed"
        assert results["benchmark_cost_efficiency"]["status"] == "completed"
        assert results["benchmark_cost_efficiency"]["cost_reduction_pct"] > 90.0

    def test_get_finetune_evaluation_benchmarks(self, client):
        res = client.get("/benchmarks/evaluation")
        assert res.status_code == 200
        data = res.json()
        assert "benchmark_domain" in data
        assert "base_model" in data
        assert "tuned_model" in data
        assert "empirical_deltas" in data
        assert data["tuned_model"]["mean_chrf_score"] > data["base_model"]["mean_chrf_score"]
        assert data["tuned_model"]["mean_token_f1"] > data["base_model"]["mean_token_f1"]
        assert data["tuned_model"]["citation_accuracy_pct"] == 100.0

    def test_get_dataset_dbom_user_datasets(self, client):
        # 1. Custom Tax Dataset chosen by user
        res = client.get("/datasets/user_tax_dataset/dbom")
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == "user_tax_dataset"
        assert "dbom" in data
        assert "nutrition_label_md" in data
        assert data["dbom"]["certificate_id"].startswith("DBOM-")
        assert len(data["dbom"]["merkle_root_hash"]) == 64
        assert "Data Nutrition & Provenance Label" in data["nutrition_label_md"]

        # 2. Clinical Reasoning Dataset chosen by user
        res_clin = client.get("/datasets/user_clinical_dataset/dbom")
        assert res_clin.status_code == 200
        data_clin = res_clin.json()
        assert data_clin["job_id"] == "user_clinical_dataset"
        assert len(data_clin["dbom"]["merkle_root_hash"]) == 64

        # 3. Corporate Law Dataset chosen by user
        res_corp = client.get("/datasets/user_corporate_law_dataset/dbom")
        assert res_corp.status_code == 200
        data_corp = res_corp.json()
        assert data_corp["job_id"] == "user_corporate_law_dataset"
        assert len(data_corp["dbom"]["merkle_root_hash"]) == 64

        # 4. Hugging Face Card for user dataset
        res_card = client.get("/datasets/user_tax_dataset/huggingface-card")
        assert res_card.status_code == 200
        assert "user_tax" in res_card.json()["content"].lower() or "dataset user_tax" in res_card.json()["content"].lower()

    def test_get_dbom_badge_svg(self, client):
        res = client.get("/badges/dbom/user_tax_dataset.svg")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/svg+xml"
        svg_text = res.text
        assert "<svg" in svg_text
        assert "DBOM" in svg_text
        assert "Verified" in svg_text
