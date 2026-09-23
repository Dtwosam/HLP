from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-research-materialize-component.yml"
)


def test_research_component_materializer_is_dispatch_only_and_fail_closed():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "build_phase2_research_rehydration_seed" in text
    assert "build_phase2_research_rehydration_plan" in text
    assert "validate_phase2_research_source_layouts" in text
    assert "materialize_single_jsonl_research_subset" in text
    assert "materialize_sharded_jsonl_research_subset" in text
    assert "specialized replay/composite materializer" in text


def test_research_component_materializer_validates_full_source_and_token_coverage():
    text = WORKFLOW.read_text()

    assert "artifact digest drift" in text
    assert "coverage report SHA drift" in text
    assert "coverage provenance drift" in text
    assert "materialized token coverage mismatch" in text
    assert "eligible_token_coverage_complete" in text
    assert "full_input_validated" not in text  # enforced by library report
    assert "research_component_ready: true" in text
    assert "dump_threshold_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
