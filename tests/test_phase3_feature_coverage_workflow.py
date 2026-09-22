from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-feature-coverage.yml")


def test_phase3_feature_coverage_requires_price_trade_and_entry():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase3-chain-regime-features" in text
    assert "phase3-venue-mechanics-features" in text
    assert "phase3-holder-features" in text
    assert "phase3-retention-features" in text
    assert "phase3-price-features" in text
    assert "phase3-trade-features" in text
    assert "materialize_phase3_feature_coverage" in text
    assert (
        "required_families: "
        "chain_regime,holder_state,participant_retention,"
        "price_drawdown,trade_flow,venue_mechanics"
    ) in text
    assert "matched_subject_coverage_equal: true" in text


def test_phase3_feature_coverage_stays_outcome_blind():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "outcome_fields_exposed: false" in text
    assert "missingness_recorded: true" in text
    assert "feature_coverage_complete: true" in text
    assert "git push" not in text
    assert "contents: write" not in text
