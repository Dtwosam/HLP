from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-outcome-labels.yml")


def test_outcome_labels_require_frozen_detector_and_exact_price_path():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase2-dump-detector-freeze" in text
    assert "phase2-research-price-path" in text
    assert "materialize_phase2_outcome_labels" in text
    assert "dump detector is not frozen" in text
    assert "outcome detector/price-path SHA linkage drift" in text


def test_outcome_labels_preserve_continuous_targets_and_semantics():
    text = WORKFLOW.read_text()

    assert "max_post_dump_multiple_retained: true" in text
    assert "post_dump_base_semantics: retrospective_trough" in text
    assert "live_signal_semantics: confirmation_event" in text
    assert "phase2_dump_detector_frozen: true" in text
    assert "outcome_labels_computed: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
