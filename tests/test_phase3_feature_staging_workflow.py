from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-feature-staging.yml")


def test_phase3_staging_requires_coverage_price_and_trade_artifacts():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-coverage" in text
    assert "phase3-price-features" in text
    assert "phase3-trade-features" in text
    assert "materialize_phase3_feature_staging" in text


def test_phase3_staging_never_claims_final_feature_store():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "outcome_rows_consumed: false" in text
    assert "outcome_fields_exposed: false" in text
    assert "future_state_allowed: false" in text
    assert "staging_bundle_ready: true" in text
    assert "final_checkpoint_name: hlp-v1-phase3-feature-store" in text
    assert "final_checkpoint_claimed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text
