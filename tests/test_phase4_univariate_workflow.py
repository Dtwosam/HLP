from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-univariate.yml")


def test_phase4_univariate_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_univariate_requires_base_rate_and_exact_registry():
    text = WORKFLOW.read_text()

    assert "discovery_entry_handoff_json:" in text
    assert "base_rate_handoff_json:" in text
    assert "phase4-feature-registry.json" in text
    assert "validate_phase3_feature_registry" in text
    assert "build_phase4_discovery_entry_handoff" in text
    assert "build_phase4_base_rate_handoff" in text
    assert "build_phase4_univariate_report" in text
    assert "build_phase4_univariate_handoff" in text


def test_phase4_univariate_never_ranks_or_promotes_features():
    text = WORKFLOW.read_text()

    assert "univariate_relationships_tested: true" in text
    assert "candidate_features_ranked: false" in text
    assert "signal_promoted: false" in text
    assert "unseen_slice_validation_complete: false" in text
    assert "multiple_testing_control_applied: false" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
    assert "phase4_discovery_checkpoint_claimed: true" not in text
