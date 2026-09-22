from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-dump-detector-freeze.yml"
)


def test_dump_detector_freeze_is_dispatch_only_and_requires_explicit_choice():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "selected_candidate_id:" in text
    assert "selected_candidate_id must be supplied explicitly" in text
    assert "materialize_phase2_dump_detector_freeze" in text
    assert "build_phase2_dump_detector_freeze_handoff" in text
    assert "selection_mode: explicit_candidate_id" in text


def test_dump_detector_freeze_never_ranks_or_computes_outcomes():
    text = WORKFLOW.read_text()

    assert "best_candidate" not in text
    assert "winner" not in text
    assert "score_candidate" not in text
    assert "candidate_selected: true" in text
    assert "phase2_dump_detector_frozen: true" in text
    assert "outcome_labels_computed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
