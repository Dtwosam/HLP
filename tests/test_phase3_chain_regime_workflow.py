from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-chain-regime-features.yml")


def test_chain_regime_workflow_is_price_path_only_and_dispatch_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase2-research-price-path" in text
    assert "materialize_phase3_chain_regime_features" in text
    assert "phase2-outcome-labels" not in text


def test_chain_regime_workflow_preserves_causal_guards():
    text = WORKFLOW.read_text()

    assert "regime_window_blocks: 1000" in text
    assert "future_price_rows_used: false" in text
    assert "outcome_rows_consumed: false" in text
    assert "phase3_chain_regime_features_ready: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
