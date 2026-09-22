from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-research-materialization-freeze.yml"
)


def test_materialization_freeze_is_dispatch_only_and_uses_compact_handoffs():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "component_runs_json" in text
    assert "phase2-research-handoff-" in text
    assert "phase2-research-materialized-" not in text
    assert "build_phase2_research_materialization_bundle" in text
    assert "build_phase2_research_materialization_handoff" in text


def test_materialization_freeze_does_not_cross_dump_or_label_boundary():
    text = WORKFLOW.read_text()

    assert "research_price_paths_materialized: true" in text
    assert "phase2_dump_detector_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "component run map set changed" in text
    assert "rehydration plan content drift" in text
    assert "frozen-universe handoff SHA drift" in text
    assert "git push" not in text
    assert "contents: write" not in text
