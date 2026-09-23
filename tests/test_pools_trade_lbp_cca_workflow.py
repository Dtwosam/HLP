from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-trade-lbp-cca-backfill.yml"
)


def test_lbp_cca_backfill_is_dispatch_only_and_sharded():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "SHARD_COUNT: '128'" in text
    assert "rpc-pools-trade-lbp-cca-window" in text
    assert "phase2-pools-trade-lbp-cca-market-window" in text
    assert "phase2-pools-trade-lbp-cca-setup" in text


def test_lbp_cca_backfill_binds_shared_supply_quotes_and_orientation():
    text = WORKFLOW.read_text()

    assert "phase2-direct-supply-delta-manifest" in text
    assert "phase2-direct-quote-registry" in text
    assert "phase2-pools-trade-cca-orientation.json" in text
    assert "validate_pools_trade_cca_orientation" in text
    assert "filtered_shared_supply_delta" in text
    assert "quote_feed_specs_sha256" in text


def test_lbp_cca_merge_is_fail_closed_but_not_source_complete():
    text = WORKFLOW.read_text()

    assert "validate_shard_block_coverage" in text
    assert "merge_cca_market_cap_summaries" in text
    assert "LBP CCA summary does not cover registry exactly" in text
    assert "LBP CCA merged summary has missing/unpriced history" in text
    assert '"cca_phase_coverage_complete": True' in text
    assert '"source_coverage_complete": False' in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
