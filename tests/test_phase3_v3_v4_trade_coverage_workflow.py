from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-v3-v4-trade-coverage.yml")


def test_v3_v4_trade_coverage_handles_four_source_specific_surfaces():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    for source in (
        "pools_fun",
        "noxa",
        "doppler",
        "pools_trade_instant",
    ):
        assert f"- {source}" in text
    assert "SHARD_COUNT: '128'" in text


def test_v3_v4_trade_coverage_reuses_accepted_raw_swap_runs():
    text = WORKFLOW.read_text()

    assert "v3_swap_run_id" in text
    assert "v4_swap_run_id" in text
    assert "phase2-direct-{dex_version}-swap-manifest" in text
    assert "shared_swap_sha256" in text
    assert "validate_shard_block_coverage" in text
    assert "market_registry_sha256" in text


def test_v3_v4_trade_coverage_fetches_wallet_identity_only_after_filter():
    text = WORKFLOW.read_text()

    assert "fetch_transaction_identity_rows" in text
    assert "wallet_identity_kind" in text
    assert "transaction_from" in text
    assert "adapt_v3_swaps_to_phase3" in text
    assert "adapt_v4_swaps_to_phase3" in text
    assert "build_phase3_trade_source_coverage" in text


def test_v3_v4_trade_coverage_is_causal_and_assembler_ready():
    text = WORKFLOW.read_text()

    assert "phase3-{source_id}-canonical-trades.jsonl" in text
    assert "phase3-{source_id}-trade-coverage.jsonl" in text
    assert "trade_coverage_complete: true" in text
    assert "phase2-outcome-labels" not in text
    assert "git push" not in text
    assert "contents: write" not in text
