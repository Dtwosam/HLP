from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-dump-candidate-diagnostics.yml"
)


def test_candidate_diagnostics_workflow_is_dispatch_only_and_outcome_blind():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "build_phase2_dump_candidate_diagnostics" in text
    assert "iter_validated_jsonl" in text
    assert "diagnostics cannot consume outcome labels" in text
    assert "uses_outcome_labels: false" in text


def test_candidate_diagnostics_cannot_approve_detector_freeze():
    text = WORKFLOW.read_text()

    assert "candidate_selected: false" in text
    assert "detector_freeze_ready: false" in text
    assert "phase2_dump_detector_frozen: false" in text
    assert "outcome_labels_computed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
