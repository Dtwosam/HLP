from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-feature-staging.yml")


def test_phase3_staging_requires_coverage_price_and_trade_artifacts():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-coverage" in text
    assert "phase3-early-recipient-features" in text
    assert "phase3-chain-regime-features" in text
    assert "phase3-venue-mechanics-features" in text
    assert "phase3-holder-features" in text
    assert "phase3-lifecycle-features" in text
    assert "phase3-redistribution-features" in text
    assert "phase3-retention-features" in text
    assert "phase3-price-features" in text
    assert "phase3-trade-features" in text
    assert "phase3-trade-size-flow-features" in text
    assert "materialize_phase3_feature_staging" in text


def test_phase3_staging_never_claims_final_feature_store():
    text = WORKFLOW.read_text()

    assert "phase2-outcome-labels" not in text
    assert "outcome_rows_consumed: false" in text
    assert "outcome_fields_exposed: false" in text
    assert "future_state_allowed: false" in text
    assert (
        "included_families: "
        "chain_regime,early_recipient_activity,holder_state,"
        "lifecycle_age,participant_retention,"
        "price_drawdown,supply_redistribution,trade_flow,"
        "trade_size_flow,venue_mechanics"
    ) in text
    assert "staging_bundle_ready: true" in text
    assert "final_checkpoint_name: hlp-v1-phase3-feature-store" in text
    assert "final_checkpoint_claimed: false" in text
    assert "git push" not in text
    assert "contents: write" not in text



def test_phase3_staging_stays_within_dispatch_input_limit():
    text = WORKFLOW.read_text()

    assert "early_recipient_feature_handoff_json:" in text
    assert "chain_regime_handoff_json:" in text
    assert "holder_feature_handoff_json:" in text
    assert "lifecycle_feature_handoff_json:" in text
    assert "trade_size_flow_handoff_json:" in text
    assert "trade_size_flow_run_id:" not in text
    assert "expected_trade_size_flow_artifact_digest:" not in text
    assert "expected_trade_size_flow_handoff_sha256:" not in text
    assert "chain_regime_run_id:" not in text
    assert "expected_chain_regime_artifact_digest:" not in text
    assert "expected_chain_regime_handoff_sha256:" not in text



def test_phase3_staging_compacts_holder_identity():
    text = WORKFLOW.read_text()

    assert "holder_feature_run_id:" not in text
    assert "expected_holder_feature_artifact_digest:" not in text
    assert "expected_holder_feature_handoff_sha256:" not in text



def test_phase3_staging_leaves_dispatch_headroom():
    text = WORKFLOW.read_text()

    input_lines = [
        line for line in text.splitlines()
        if line.startswith("      ")
        and not line.startswith("        ")
        and line.endswith(":")
    ]
    assert len(input_lines) == 23
    assert len(input_lines) < 25
