from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-dump-candidate-research.yml"
)


def test_dump_candidate_workflow_requires_explicit_specs_and_is_dispatch_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "candidate_specs_json" in text
    assert "must be a non-empty JSON array" in text
    assert "materialize_phase2_dump_candidate_research" in text
    assert "iter_validated_jsonl" in text


def test_dump_candidate_workflow_compares_without_selecting_or_labeling():
    text = WORKFLOW.read_text()

    assert "build_phase2_dump_candidate_handoff" in text
    assert "candidate_selected: false" in text
    assert "dump_threshold_frozen: false" in text
    assert "phase2_dump_detector_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "candidate research cannot consume outcome labels" in text
    assert "git push" not in text
    assert "contents: write" not in text
