from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase3-early-recipient-features.yml"
)


def test_early_recipient_workflow_requires_complete_transfer_tape():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase3-canonical-transfer-tape" in text
    assert "materialize_phase3_early_recipient_features" in text
    assert "build_phase3_early_recipient_feature_handoff" in text
    assert "transfer_coverage_complete" in text
    assert "initial_mint_coverage_complete" in text


def test_early_recipient_workflow_avoids_creator_or_eoa_assumptions():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "creator_identity_not_assumed: true" in text
    assert "address_type_not_assumed: true" in text
    assert "future_transfer_rows_used: false" in text
    assert "outcome_rows_consumed: false" in text
    assert "phase3_early_recipient_features_ready: true" in text
    assert "features_per_subject: 6" in text
    assert "git push" not in text
    assert "contents: write" not in text
