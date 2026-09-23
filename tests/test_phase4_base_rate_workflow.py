from pathlib import Path


WORKFLOW = Path(".github/workflows/phase4-base-rate.yml")


def test_phase4_base_rate_is_manual_and_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text


def test_phase4_base_rate_requires_exact_discovery_entry():
    text = WORKFLOW.read_text()

    assert "discovery_entry_handoff_json:" in text
    assert "phase4-discovery-entry" in text
    assert "build_phase4_discovery_entry_handoff" in text
    assert "build_phase4_base_rate_report" in text
    assert "build_phase4_base_rate_handoff" in text


def test_phase4_base_rate_never_tests_or_promotes_features():
    text = WORKFLOW.read_text()

    assert "winner_failure_frequencies_reported: true" in text
    assert "continuous_outcome_distribution_reported: true" in text
    assert "feature_relationships_tested: false" in text
    assert "signal_promoted: false" in text
    assert "phase4_discovery_checkpoint_claimed: false" in text
    assert "phase4_discovery_checkpoint_claimed: true" not in text
