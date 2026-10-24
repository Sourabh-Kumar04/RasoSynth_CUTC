"""Tests for tax collision, foreign jurisdiction, and homonym filtering."""
import pytest
from unittest.mock import MagicMock
from core.orchestrator_core import ConstraintAnalyzer, DatasetOrchestrator
from core.intent import UserIntent
from pipeline.filtering import FilteringPipeline
from pipeline.construction import _is_chunk_domain_relevant


def test_constraint_analyzer_rejects_homonyms_and_foreign_tax():
    analyzer = ConstraintAnalyzer({"target_domain": "tax law"})
    raw_prompt = "Synthesize curriculum SFT dataset for Indian GST ITC reconciliation under Section 16(4)"

    # Homonym: Glutathione S-Transferase (GST)
    biomed_src = {
        "title": "Glutathione S-transferase (GST) Polymorphisms and Susceptibility to Cancer",
        "description": "Expression of NRF2 and GST enzymes in human tissue cells",
        "url": "https://pubmed.ncbi.nlm.nih.gov/123456/",
        "text": "Glutathione S-transferase (GST) plays a critical role in detoxification."
    }
    assert not analyzer._is_source_domain_relevant(biomed_src, "tax law", raw_input=raw_prompt)

    # Foreign jurisdiction: Uzbekistan VAT
    uzbek_src = {
        "title": "Value Added Tax (VAT) in Uzbekistan: Modern Trends and Prospects",
        "description": "Tax Code reforms of 2020 in the Republic of Uzbekistan for VAT administration",
        "url": "https://zenodo.org/record/654321",
        "text": "In Uzbekistan, the new Tax Code introduced VAT invoice registration mechanisms."
    }
    assert not analyzer._is_source_domain_relevant(uzbek_src, "tax law", raw_input=raw_prompt)

    # Foreign jurisdiction: US 45Q Carbon Sequestration
    us_src = {
        "title": "Section 45Q Credit for Carbon Oxide Sequestration",
        "description": "IRS issues guidance under Section 45Q for carbon capture and underground storage",
        "url": "https://irs.gov/irb/2021-06_IRB",
        "text": "Internal Revenue Service guidance on 45Q carbon storage."
    }
    assert not analyzer._is_source_domain_relevant(us_src, "tax law", raw_input=raw_prompt)

    # Valid Indian GST source
    valid_gst_src = {
        "title": "CBIC Circular No. 183/15/2022-GST: Clarification on ITC under Section 16(4)",
        "description": "Reconciliation of ITC availed in Form GSTR-3B with GSTR-2A/2B for FY 2017-18 and 2018-19",
        "url": "https://cbic.gov.in/circular-183-gst.pdf",
        "text": "Section 16(4) of the CGST Act 2017 specifies the time limit for claiming input tax credit."
    }
    assert analyzer._is_source_domain_relevant(valid_gst_src, "tax law", raw_input=raw_prompt)


def test_is_chunk_domain_relevant_in_construction():
    target_domain = "tax law"
    brief = {"user_prompt": "Indian GST advisory Section 16(4)"}

    uzbek_chunk = "Uzbekistan ke 2020 Tax Code reforms ke antargat Value Added Tax (VAT) framework lagu kiya gaya."
    assert not _is_chunk_domain_relevant(uzbek_chunk, target_domain, brief)

    biomed_chunk = "HemeLB simulation of arteriovenous fistula flow using lattice Boltzmann methods."
    assert not _is_chunk_domain_relevant(biomed_chunk, target_domain, brief)

    gst_enzyme_chunk = "NRF2 regulates Glutathione S-Transferase (GST) expression in oxidative stress."
    assert not _is_chunk_domain_relevant(gst_enzyme_chunk, target_domain, brief)

    valid_chunk = "Under Section 16(4) of the CGST Act, a registered taxpayer cannot claim ITC after the 30th day of November."
    assert _is_chunk_domain_relevant(valid_chunk, target_domain, brief)


@pytest.mark.asyncio
async def test_filtering_pipeline_rejects_foreign_and_homonyms():
    config = {
        "quality_threshold": 0.0,
        "statistical_threshold": 0.0,
        "semantic_threshold": 0.0,
        "reasoning_threshold": 0.0,
        "grounding_threshold": 0.0,
        "toxicity_threshold": 1.0,
        "min_length": 10,
        "max_length": 1000000,
    }
    pipeline = FilteringPipeline(router=None, config=config)

    intent = UserIntent(
        primary_task="tax advisory",
        domain="tax law",
        modality="text",
        anti_domains=["uzbekistan", "glutathione", "hemelb"],
        key_entities=["Section 16(4) CGST"],
        specialized_queries=["Indian GST Section 16(4)"],
        constraints=[],
        output_format="jsonl",
        confidence=0.9,
        raw_input="Indian GST ITC reconciliation under Section 16(4)"
    )

    class MockContent:
        def __init__(self, content, url="https://example.com"):
            self.content = content
            self.url = url
            self.metadata = {}

    uzbek_sample = MockContent("Uzbekistan Tax Code 2020 reforms for VAT administration.")
    res_uzbek = await pipeline.filter(uzbek_sample, intent, return_all=True)
    assert not res_uzbek.passed
    assert "anti_domain" in res_uzbek.filter_reason or "domain_jurisdiction" in res_uzbek.filter_reason

    biomed_sample = MockContent("Glutathione S-transferase (GST) polymorphism analysis in clinical pharmacology.")
    res_biomed = await pipeline.filter(biomed_sample, intent, return_all=True)
    assert not res_biomed.passed

    valid_sample = MockContent("Section 16(4) of the CGST Act stipulates input tax credit reconciliation with GSTR-2B.")
    res_valid = await pipeline.filter(valid_sample, intent, return_all=True)
    assert res_valid.passed


def test_cross_discipline_rust_rejection():
    analyzer = ConstraintAnalyzer({"target_domain": "software engineering"})
    rust_prompt = "Synthesize an SFT dataset on Rust async programming with Tokio"

    wheat_rust_src = {
        "title": "Genome Sequencing of Puccinia graminis: The Causative Agent of Wheat Stem Rust",
        "description": "Analysis of fungal spores and foliar crop disease in wheat agriculture",
        "url": "https://arxiv.org/abs/2105.12345",
        "text": "Puccinia graminis causes severe wheat rust infection, destroying crop yield."
    }
    assert not analyzer._is_source_domain_relevant(wheat_rust_src, "software engineering", raw_input=rust_prompt)

    valid_rust_src = {
        "title": "Asynchronous Concurrency in Rust Using Tokio and Futures",
        "description": "Guide to building high-throughput network services with Tokio crate in Rust",
        "url": "https://crates.io/crates/tokio",
        "text": "Using async fn, tasks, and mpsc channels in Rust with Tokio runtime."
    }
    assert analyzer._is_source_domain_relevant(valid_rust_src, "software engineering", raw_input=rust_prompt)


def test_cross_discipline_pandas_rejection():
    analyzer = ConstraintAnalyzer({"target_domain": "data science"})
    pandas_prompt = "Dataset on Python Pandas dataframe vectorization and groupby operations"

    zoology_src = {
        "title": "Habitat Conservation and Bamboo Foraging of Ailuropoda melanoleuca",
        "description": "Studies on giant panda bear cubs in wildlife sanctuaries in Sichuan",
        "url": "https://nature.com/articles/giant-panda",
        "text": "The giant panda eats bamboo and lives in mountain ranges of China."
    }
    assert not analyzer._is_source_domain_relevant(zoology_src, "data science", raw_input=pandas_prompt)

    valid_pandas_src = {
        "title": "High-Performance Vectorization in Python Pandas DataFrames",
        "description": "Optimization techniques for groupby, apply, and rolling window computations in pandas",
        "url": "https://pandas.pydata.org/docs/",
        "text": "Pandas DataFrame indexing, series operations, and vectorization using NumPy backend."
    }
    assert analyzer._is_source_domain_relevant(valid_pandas_src, "data science", raw_input=pandas_prompt)


def test_cross_discipline_transformer_rejection():
    analyzer = ConstraintAnalyzer({"target_domain": "machine learning"})
    transformer_prompt = "Instruction tuning for Transformer attention architectures"

    substation_src = {
        "title": "Analysis of Core Loss and Electromagnetic Winding in High Voltage Substation Transformers",
        "description": "Thermal degradation of transformer oil in power grid step-down transformers",
        "url": "https://ieee.org/substation-transformer",
        "text": "The step-up transformer primary winding operates at 220kV in electrical grid distribution."
    }
    assert not analyzer._is_source_domain_relevant(substation_src, "machine learning", raw_input=transformer_prompt)

    valid_transformer_src = {
        "title": "Attention Is All You Need: The Transformer Architecture",
        "description": "Multi-head self-attention mechanisms and feed-forward layers for sequence transduction",
        "url": "https://arxiv.org/abs/1706.03762",
        "text": "Transformer models rely entirely on self-attention to compute representations."
    }
    assert analyzer._is_source_domain_relevant(valid_transformer_src, "machine learning", raw_input=transformer_prompt)


def test_universal_query_anchoring():
    from core.discipline_matrix import anchor_query
    
    assert "rust programming language" in anchor_query("rust async channels", "software engineering")
    assert "python pandas dataframe" in anchor_query("pandas groupby", "data science")
    assert "golang go programming" in anchor_query("go microservices", "software development")
    assert "deep learning transformer attention" in anchor_query("transformer attention heads", "machine learning")
    assert "goods and services tax" in anchor_query("gst itc reconciliation", "tax law")

