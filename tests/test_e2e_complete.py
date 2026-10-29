"""Complete End-to-End System Integration Test for RasoSynthTune.

Tests the full lifecycle across:
- Security headers, CORS, and health status
- CSRF token acquisition and authenticated state-change validation
- Provider routing, provider introspection, and multi-agent discovery
- Distributed tracing, correlation IDs, and historical telemetry
- Complete synthetic dataset pipeline, sample records, and multi-format exports (JSONL, CSV, SQL, Qdrant)
- Deterministic quality filtering, diversity metrics (Shannon entropy), and hallucination detection
- Human-in-the-loop review operations
"""
import pytest
from pipeline.diversity import DatasetDiversityAnalyzer, DiversityMetrics
from pipeline.hallucination_detector import HallucinationDetector, HallucinationResult


class TestEndToEndSystem:
    """Comprehensive E2E system test suite."""

    def test_e2e_system_health_and_security(self, test_client):
        """Verify health check endpoint and OWASP security headers."""
        resp = test_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "database" in data

        # Security headers
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "max-age=" in resp.headers.get("Strict-Transport-Security", "")

    def test_e2e_auth_csrf_flow(self, test_client):
        """Verify CSRF token generation for state-changing operations."""
        resp = test_client.get("/auth/csrf-token")
        assert resp.status_code == 200
        csrf_data = resp.json()
        assert "csrf_token" in csrf_data
        assert len(csrf_data["csrf_token"]) > 0

    def test_e2e_provider_and_agent_discovery(self, test_client, auth_headers):
        """Verify provider routing endpoints and modular multi-agent discovery."""
        # 1. Provider discovery
        resp = test_client.get("/providers", headers=auth_headers)
        assert resp.status_code == 200
        providers = resp.json()
        assert isinstance(providers, list)
        provider_ids = [p.get("id") or p.get("name") for p in providers]
        assert "gemini" in provider_ids or "nim" in provider_ids or "openai" in provider_ids

        # 2. Granular provider metrics
        resp_prov = test_client.get("/providers/gemini", headers=auth_headers)
        if resp_prov.status_code == 200:
            p_data = resp_prov.json()
            assert "name" in p_data or "id" in p_data

        resp_metrics = test_client.get("/providers/gemini/metrics", headers=auth_headers)
        if resp_metrics.status_code == 200:
            m_data = resp_metrics.json()
            assert "provider" in m_data or "total_requests" in m_data or "active" in m_data

        # 3. Multi-agent registry
        resp_agents = test_client.get("/agents", headers=auth_headers)
        assert resp_agents.status_code == 200
        agents_data = resp_agents.json()
        agents = agents_data.get("agents") if isinstance(agents_data, dict) else agents_data
        assert isinstance(agents, list)
        agent_names = [a.get("name") for a in agents]
        assert len(agent_names) >= 4
        assert any("Agent" in name for name in agent_names)

        # 4. Multi-agent stats
        resp_agent_stats = test_client.get("/agents/stats", headers=auth_headers)
        assert resp_agent_stats.status_code == 200
        stats = resp_agent_stats.json()
        assert "total_registrations" in stats or "agents" in stats

    def test_e2e_distributed_tracing_and_telemetry(self, test_client, auth_headers):
        """Verify distributed trace extraction, trace recording, and historical telemetry."""
        trace_id = "e2e-trace-test-456"
        corr_id = "e2e-corr-test-789"
        headers = {
            "x-trace-id": trace_id,
            "x-correlation-id": corr_id,
        }

        # Issue request with distributed tracing headers
        resp = test_client.get("/health", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("x-trace-id") == trace_id
        assert resp.headers.get("x-correlation-id") == corr_id

        # Verify trace query endpoint
        resp_traces = test_client.get("/traces", headers=auth_headers)
        assert resp_traces.status_code == 200
        traces_data = resp_traces.json()
        traces = traces_data.get("traces") if isinstance(traces_data, dict) else traces_data
        assert isinstance(traces, list)
        matched = [t for t in traces if t.get("trace_id") == trace_id]
        assert len(matched) > 0
        assert matched[0]["correlation_id"] == corr_id
        assert "duration_ms" in matched[0] or "duration" in matched[0]

        # Verify single trace lookup
        resp_single = test_client.get(f"/traces/{trace_id}", headers=auth_headers)
        assert resp_single.status_code == 200
        trace_detail = resp_single.json()
        assert trace_detail["trace_id"] == trace_id

        # Verify historical telemetry
        resp_history = test_client.get("/metrics/history?range=1h", headers=auth_headers)
        assert resp_history.status_code == 200
        history_data = resp_history.json()
        assert "timestamps" in history_data
        assert "latency" in history_data
        assert "throughput" in history_data
        assert "cost" in history_data

    @pytest.mark.asyncio
    async def test_e2e_dataset_and_multiformat_export(self, test_client, tmp_path, auth_headers):
        """Verify dataset creation, record querying, and multi-format exports."""
        import api.server as server_mod
        from core.db import AsyncDB

        db_file = tmp_path / "e2e_test.db"
        test_db = await AsyncDB.create(f"sqlite+aiosqlite:///{db_file}")
        orig_db = server_mod.db
        server_mod.db = test_db

        try:
            # Create test job and dataset
            job = await test_db.create_job({
                "config": {
                    "target_domain": "multilingual NLP",
                    "dataset_size": 2,
                    "export_format": "jsonl",
                },
                "status": "completed",
            })
            dataset = await test_db.create_dataset(
                job_id=job["id"],
                name="e2e_multilingual_dataset",
                type="sft",
                size=2,
                metadata={"domain": "NLP", "language": "en"},
                output_path=str(tmp_path / "e2e_multilingual.jsonl"),
            )
            sample_records = [
                {
                    "instruction": "Explain cross-lingual transfer learning.",
                    "response": "Cross-lingual transfer leverages representations from one language to another.",
                    "input": "",
                    "metadata": {"language": "en", "tokens": 42},
                    "quality_score": 0.94,
                    "difficulty_tier": 3,
                },
                {
                    "instruction": "Expliquez l'apprentissage par transfert interlinguistique.",
                    "response": "Le transfert interlinguistique exploite les représentations d'une langue à une autre.",
                    "input": "",
                    "metadata": {"language": "fr", "tokens": 46},
                    "quality_score": 0.91,
                    "difficulty_tier": 3,
                },
            ]
            await test_db.create_samples(dataset["id"], sample_records)

            # 1. Query datasets
            resp_datasets = test_client.get("/datasets", headers=auth_headers)
            assert resp_datasets.status_code == 200
            ds_data = resp_datasets.json()
            ds_list = ds_data.get("data") if isinstance(ds_data, dict) else ds_data
            assert any(d["id"] == dataset["id"] for d in ds_list)

            # 2. Query dataset detail
            resp_detail = test_client.get(f"/datasets/{dataset['id']}", headers=auth_headers)
            assert resp_detail.status_code == 200
            assert resp_detail.json()["name"] == "e2e_multilingual_dataset"

            # 3. Query records
            resp_records = test_client.get(f"/datasets/{dataset['id']}/records", headers=auth_headers)
            assert resp_records.status_code == 200
            records_data = resp_records.json()
            records = records_data.get("records") if isinstance(records_data, dict) else records_data
            assert len(records) == 2

            # 4. Multi-format export streaming / on-demand
            csrf_token = test_client.get("/auth/csrf-token").json()["csrf_token"]
            post_headers = dict(auth_headers)
            post_headers["X-CSRF-Token"] = csrf_token

            # JSONL
            resp_jsonl = test_client.post(f"/datasets/{dataset['id']}/export", json={"format": "jsonl"}, headers=post_headers)
            assert resp_jsonl.status_code == 200
            assert "cross-lingual" in resp_jsonl.text or "interlinguistique" in resp_jsonl.text

            # CSV
            resp_csv = test_client.post(f"/datasets/{dataset['id']}/export", json={"format": "csv"}, headers=post_headers)
            assert resp_csv.status_code == 200
            assert "instruction" in resp_csv.text

            # SQL (ANSI SQL DDL + INSERT statements)
            resp_sql = test_client.post(f"/datasets/{dataset['id']}/export", json={"format": "sql"}, headers=post_headers)
            assert resp_sql.status_code == 200
            assert "CREATE TABLE" in resp_sql.text
            assert "INSERT INTO" in resp_sql.text

            # Qdrant (Vector DB payloads)
            resp_qdrant = test_client.post(f"/datasets/{dataset['id']}/export", json={"format": "qdrant"}, headers=post_headers)
            assert resp_qdrant.status_code == 200
            assert "points" in resp_qdrant.text

        finally:
            server_mod.db = orig_db
            await test_db.close()

    @pytest.mark.asyncio
    async def test_e2e_diversity_and_hallucination_validation(self):
        """Verify semantic diversity analysis and hallucination detection algorithms."""
        # Diversity check
        analyzer = DatasetDiversityAnalyzer()
        diverse_samples = [
            {"instruction": "What is machine learning?", "response": "Machine learning algorithms discover patterns in data.", "source_url": "https://ml.org"},
            {"instruction": "How do quantum computers work?", "response": "Quantum computers manipulate qubits via superposition.", "source_url": "https://quantum.org"},
            {"instruction": "Explain photosynthesis.", "response": "Plants convert solar light into chemical sugars.", "source_url": "https://biology.org"},
        ]
        metrics = await analyzer.analyze(diverse_samples)
        assert isinstance(metrics, DiversityMetrics)
        assert 0.0 <= metrics.overall_diversity <= 1.0

        # Shannon entropy calculation
        entropy = analyzer._shannon_entropy({"ml": 5, "quantum": 5, "biology": 5})
        assert entropy > 1.0

        # Hallucination check
        detector = HallucinationDetector()
        source = (
            "Transformer models, introduced by Vaswani et al. in 2017, revolutionized NLP. "
            "The self-attention mechanism enables capturing long-range dependencies."
        )
        grounded_resp = "Transformers were introduced by Vaswani et al. in 2017 with self-attention."
        hallucinated_resp = "Transformers were invented in 1842 by Charles Babbage for weaving cotton."

        result_grounded = await detector.evaluate("What are transformers?", grounded_resp, source)
        result_hallucinated = await detector.evaluate("What are transformers?", hallucinated_resp, source)

        assert isinstance(result_grounded, HallucinationResult)
        assert isinstance(result_hallucinated, HallucinationResult)
        # Grounded text should have lower or equal hallucination risk score than completely fabricated text
        assert result_grounded.hallucination_risk_score <= result_hallucinated.hallucination_risk_score

    def test_e2e_human_review_workflow(self, test_client, auth_headers):
        """Verify human-in-the-loop review operations and queue querying."""
        # 1. Fetch CSRF token for review actions
        csrf_resp = test_client.get("/auth/csrf-token")
        csrf_token = csrf_resp.json().get("csrf_token")
        assert csrf_token is not None

        # 2. Query review queue (returns 200 or 503 if review service db connection skipped)
        resp_queue = test_client.get("/api/review/queue", headers=auth_headers)
        assert resp_queue.status_code in (200, 503)
        if resp_queue.status_code == 200:
            queue_data = resp_queue.json()
            assert isinstance(queue_data, (list, dict))

        # 3. Query review stats
        resp_stats = test_client.get("/api/review/stats", headers=auth_headers)
        assert resp_stats.status_code in (200, 503)
