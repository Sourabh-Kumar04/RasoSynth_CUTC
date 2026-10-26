from pipeline.provenance import attach_provenance, has_reference_provenance


def test_source_provenance_contains_hash_and_citation_span():
    sample = {
        "source_text": "Evidence excerpt.",
        "metadata": {"source_url": "https://example.com/evidence", "license": "CC-BY-4.0"},
    }

    provenance = attach_provenance(sample)

    assert provenance["kind"] == "source"
    assert provenance["source_hash"]
    assert provenance["citations"] == [{"start": 0, "end": 17}]
    assert has_reference_provenance(sample)


def test_synthetic_provenance_is_not_grounded():
    sample = {"metadata": {}}

    assert attach_provenance(sample)["kind"] == "synthetic"
    assert not has_reference_provenance(sample)
