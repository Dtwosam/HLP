from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-holder-features.yml")


def test_holder_workflow_requires_entry_and_complete_transfer_tape():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase3-canonical-transfer-tape" in text
    assert "materialize_phase3_holder_features" in text
    assert "transfer_coverage_complete" in text
    assert "initial_mint_coverage_complete" in text


def test_holder_workflow_remains_causal_and_outcome_blind():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "future_transfer_rows_used: false" in text
    assert "outcome_rows_consumed: false" in text
    assert "phase3_holder_features_ready: true" in text
    assert "features_per_subject: 8" in text
    assert "git push" not in text
    assert "contents: write" not in text
