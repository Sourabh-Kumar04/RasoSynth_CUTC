"""Unit tests for PostgreSQL NoSQL document storage (JSONB) and GIN indexes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

def test_postgresql_jsonb_variant_and_gin_indexes():
    """Verify that JSON_DOCUMENT uses JSONB under PostgreSQL and GIN indexes exist on document models."""
    from core.db import JSON_DOCUMENT, Job, Dataset, Sample
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB, dialect as pg_dialect_cls
    from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect_cls

    # Test dialect resolution
    pg_dialect = pg_dialect_cls()
    sqlite_dialect = sqlite_dialect_cls()

    pg_type = JSON_DOCUMENT.dialect_impl(pg_dialect)
    sqlite_type = JSON_DOCUMENT.dialect_impl(sqlite_dialect)

    assert isinstance(pg_type, PG_JSONB), f"Expected PG_JSONB under postgresql, got {type(pg_type)}"
    assert not isinstance(sqlite_type, PG_JSONB), f"Expected standard JSON under sqlite, got {type(sqlite_type)}"

    # Check GIN indexes on models
    job_indexes = [idx for idx in Job.__table__.indexes if "gin" in idx.name.lower()]
    assert len(job_indexes) >= 1, "Expected GIN index on Job.config"
    assert job_indexes[0].dialect_options["postgresql"]["using"] == "gin"

    dataset_indexes = [idx for idx in Dataset.__table__.indexes if "gin" in idx.name.lower()]
    assert len(dataset_indexes) >= 1, "Expected GIN index on Dataset.metadata"
    assert dataset_indexes[0].dialect_options["postgresql"]["using"] == "gin"

    sample_indexes = [idx for idx in Sample.__table__.indexes if "gin" in idx.name.lower()]
    assert len(sample_indexes) >= 1, "Expected GIN index on Sample.metadata"
    assert sample_indexes[0].dialect_options["postgresql"]["using"] == "gin"


def test_database_manager_postgresql_pooling():
    """Verify DatabaseManager configures asyncpg connection pooling parameters."""
    from core.db import DatabaseManager

    with patch("core.db.create_async_engine") as mock_create_engine, \
         patch("core.db.async_sessionmaker") as mock_sessionmaker:
        
        # Test PostgreSQL connection URL
        pg_url = "postgresql+asyncpg://user:pass@localhost:5432/dataset_engine"
        db = DatabaseManager(pg_url)

        call_kwargs = mock_create_engine.call_args.kwargs
        assert call_kwargs.get("pool_size") == 10
        assert call_kwargs.get("max_overflow") == 20
        assert call_kwargs.get("pool_pre_ping") is True
        assert call_kwargs.get("pool_recycle") == 3600
        assert call_kwargs["connect_args"].get("statement_cache_size") == 0


def test_api_datasets_nosql_query_endpoint():
    """Verify that the datasets router exports the NoSQL query endpoint."""
    from api.routers.datasets import router

    route_paths = [r.path for r in router.routes]
    assert "/datasets/{dataset_id}/records/query" in route_paths


@pytest.mark.asyncio
async def test_nosql_document_queries_and_patch(tmp_path):
    """Test creating tables, inserting document records, querying with containment, and patching in-place."""
    from core.db import DatabaseManager

    db_path = tmp_path / "test_nosql.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.create_tables()

    # Create job with NoSQL config document
    job = await db.create_job(config={"domain": "tax", "tier": "expert", "tags": ["itc", "gst"]})
    assert job.id is not None

    # Query jobs by document
    found_jobs = await db.query_jobs_by_document(config_filter={"domain": "tax"})
    assert len(found_jobs) == 1
    assert found_jobs[0].config["domain"] == "tax"

    # Create dataset
    ds = await db.create_dataset(
        job_id=job.id,
        name="Tax Corpus",
        type="sft",
        size=2,
        metadata={"domain": "tax", "language": "hinglish"},
        output_path="/tmp/tax.jsonl",
    )

    # Insert sample with NoSQL metadata document
    s1 = await db.create_sample(
        dataset_id=ds.id,
        data={
            "instruction": "Explain GSTR-2B ITC reconciliation under Section 16(4)",
            "response": "Under Section 16(4), ITC must be claimed before the statutory deadline...",
            "metadata": {"statute": "CGST", "section": "16(4)", "verified": True},
            "quality_score": 0.95,
        },
    )

    s2 = await db.create_sample(
        dataset_id=ds.id,
        data={
            "instruction": "Calculate GST on restaurant services",
            "response": "Restaurant services are taxed at 5% without ITC...",
            "metadata": {"statute": "CGST", "rate": 5, "verified": False},
            "quality_score": 0.88,
        },
    )

    # Query samples by NoSQL document filter
    cgst_samples = await db.query_samples_by_document(ds.id, document_filter={"section": "16(4)"})
    assert len(cgst_samples) == 1
    assert cgst_samples[0].id == s1.id

    # Test partial NoSQL document patching
    patched = await db.patch_sample_document(s1.id, patch={"audited_by": "tax_counsel", "verified": True})
    assert patched is not None
    assert patched.metadata_["audited_by"] == "tax_counsel"
    assert patched.metadata_["section"] == "16(4)"

    await db.close()


@pytest.mark.asyncio
async def test_batch_sample_ingestion_and_index_optimization(tmp_path):
    """Verify high-throughput batch sample ingestion and dynamic expression index autotuning."""
    from core.db import DatabaseManager
    from api.routers.datasets import router

    # Verify optimize endpoint is registered
    route_paths = [r.path for r in router.routes]
    assert "/datasets/{dataset_id}/indexes/optimize" in route_paths

    db_path = tmp_path / "test_batch.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.create_tables()

    job = await db.create_job(config={"domain": "biomedical"})
    ds = await db.create_dataset(job_id=job.id, name="BioCorpus", type="jsonl", size=200, metadata={}, output_path="/tmp/bio.jsonl")

    # Generate 150 batch samples
    samples_payload = [
        {
            "instruction": f"Biomedical prompt #{i}",
            "response": f"Clinical response #{i}",
            "input": "",
            "metadata": {"gene": f"BRCA{i % 5}", "organism": "human", "batch_idx": i},
            "quality_score": 0.80 + (i % 20) * 0.01,
            "difficulty_tier": (i % 3) + 1,
        }
        for i in range(150)
    ]

    # Ingest in chunks of 50
    inserted = await db.create_samples_batch(ds.id, samples_payload, batch_size=50)
    assert len(inserted) == 150

    # Retrieve samples
    samples = await db.get_samples(ds.id, limit=200)
    assert len(samples) == 150
    assert samples[0].metadata_["organism"] == "human"

    # Test dynamic targeted expression index creation
    idx_result = await db.create_nosql_path_index("samples", "metadata", "gene")
    assert idx_result["created"] is True
    assert idx_result["path"] == "gene"

    # Test path_ops index creation
    path_ops_result = await db.create_nosql_path_ops_index("samples", "metadata")
    assert "index_name" in path_ops_result

    await db.close()


