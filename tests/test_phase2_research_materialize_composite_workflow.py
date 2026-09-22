from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-research-materialize-composite.yml"
)


def test_composite_materializer_is_dispatch_only_and_limited_to_three_sources():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert '{"flap", "trench_today", "pools_trade_lbp"}' in text
    assert "normalize_flat_sharded_research_manifest" in text
    assert "rebuild_report_sharded_research_manifest" in text
    assert "materialize_sharded_jsonl_research_subset" in text


def test_composite_materializer_binds_source_provenance_and_union_coverage():
    text = WORKFLOW.read_text()

    assert "source provenance SHA drift" in text
    assert "coverage/source provenance drift" in text
    assert "artifact digest drift" in text
    assert "composite token coverage mismatch" in text
    assert "eligible_token_coverage_complete" in text
    assert "research_component_ready: true" in text
    assert "dump_threshold_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
