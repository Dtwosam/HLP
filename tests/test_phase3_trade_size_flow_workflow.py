from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase3-trade-size-flow-features.yml"
)


def test_size_flow_workflow_requires_both_canonical_tapes():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase3-canonical-trade-tape" in text
    assert "phase3-canonical-transfer-tape" in text
    assert "materialize_phase3_trade_size_flow_features" in text
    assert "build_phase3_trade_size_flow_handoff" in text
    assert "trade_coverage_complete" in text
    assert "transfer_coverage_complete" in text


def test_size_flow_workflow_is_label_free_and_causal():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "future_trade_rows_used: false" in text
    assert "future_transfer_rows_used: false" in text
    assert "outcome_rows_consumed: false" in text
    assert "phase3_trade_size_flow_features_ready: true" in text
    assert "features_per_subject: 9" in text
    assert "git push" not in text
    assert "contents: write" not in text
