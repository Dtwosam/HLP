from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-research-price-path.yml"
)


def test_research_price_path_workflow_is_dispatch_only_and_streaming():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "materialize_phase2_research_price_path" in text
    assert "iter_validated_jsonl" in text
    assert "heapq.merge" in text
    assert "phase2-research-materialized-" in text
    assert "research path universe SHA disagrees with materialization" in text


def test_research_price_path_workflow_publishes_heavy_and_compact_artifacts():
    text = WORKFLOW.read_text()

    assert "name: phase2-research-price-path" in text
    assert "name: phase2-research-price-path-handoff" in text
    assert "build_phase2_research_price_path_handoff" in text
    assert "research_price_path_ready: true" in text
    assert "dump_threshold_frozen: false" in text
    assert "phase2_dump_detector_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
