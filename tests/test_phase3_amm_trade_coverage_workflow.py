from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-amm-trade-coverage.yml")


def test_amm_trade_coverage_supports_all_v3_v4_sources():
    text = WORKFLOW.read_text()

    for source_id in (
        "pools_fun",
        "noxa",
        "direct_uniswap_v3",
        "direct_sushiswap_v3",
        "pools_trade_instant",
        "doppler",
        "direct_uniswap_v4",
    ):
        assert f"- {source_id}" in text
    assert "rpc-transaction-identity-enrich" in text
    assert "materialize_phase3_amm_trade_coverage" in text


def test_amm_trade_coverage_binds_frozen_membership_and_shared_scan():
    text = WORKFLOW.read_text()

    assert "phase2-universe-freeze" in text
    assert "market_registry_descriptor_json" in text
    assert "phase2-direct-" in text
    assert "-swap-manifest" in text
    assert "validate_shard_block_coverage" in text
    assert "one-market-per-token" in text


def test_amm_trade_coverage_is_fail_closed_and_descriptor_ready():
    text = WORKFLOW.read_text()

    assert "wallet_identity_kind: transaction_from" in text
    assert "historical_event_scan_complete: true" in text
    assert "wallet_identity_complete: true" in text
    assert "canonical_trade_adapter_complete: true" in text
    assert "trade_coverage_complete: true" in text
    assert "phase3-trade-coverage-" in text
    assert "phase2-outcome-labels" not in text
    assert "git push" not in text
    assert "contents: write" not in text
