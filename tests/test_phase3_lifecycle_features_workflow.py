from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-lifecycle-features.yml")


def test_lifecycle_workflow_uses_verified_transfer_boundaries():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase3-canonical-transfer-tape" in text
    assert "phase3-transfer-token-coverage.jsonl" in text
    assert "token_coverage_sha256" in text
    assert "materialize_phase3_lifecycle_features" in text
    assert "build_phase3_lifecycle_feature_handoff" in text


def test_lifecycle_workflow_is_causal_and_outcome_blind():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "deployment_boundary_verified: true" in text
    assert "future_state_used: false" in text
    assert "outcome_rows_consumed: false" in text
    assert "phase3_lifecycle_features_ready: true" in text
    assert "features_per_subject: 4" in text
    assert "git push" not in text
    assert "contents: write" not in text
