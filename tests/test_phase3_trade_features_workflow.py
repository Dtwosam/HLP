from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-trade-features.yml")


def test_phase3_trade_features_require_complete_canonical_trade_tape():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase3-canonical-trade-tape" in text
    assert "materialize_phase3_trade_features" in text
    assert "trade_coverage_complete" in text
    assert "Phase-3 canonical trade coverage incomplete" in text


def test_phase3_trade_feature_workflow_remains_outcome_blind():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "outcome_rows_consumed: false" in text
    assert "future_trade_rows_used: false" in text
    assert "phase3_trade_features_ready: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
