from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-dump-geometry-research.yml"
)


def test_dump_geometry_workflow_is_dispatch_only_and_streaming():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "materialize_phase2_dump_geometry" in text
    assert "iter_validated_jsonl" in text
    assert "normalized price-path manifest SHA drift" in text
    assert "dump geometry universe SHA disagrees with price path" in text


def test_dump_geometry_workflow_publishes_research_only_handoff():
    text = WORKFLOW.read_text()

    assert "phase2-dump-geometry-research" in text
    assert "phase2-dump-geometry-handoff" in text
    assert "build_phase2_dump_geometry_handoff" in text
    assert "uses_price_path_only: true" in text
    assert "candidate_selected: false" in text
    assert "dump_threshold_frozen: false" in text
    assert "phase2_dump_detector_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
