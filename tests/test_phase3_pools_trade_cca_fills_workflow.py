from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-pools-trade-cca-fills.yml")


def test_cca_fill_backfill_is_dispatch_only_and_sharded():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "SHARD_COUNT: '128'" in text
    assert "rpc-pools-trade-lbp-cca-bid-window" in text
    assert "phase3-pools-trade-cca-fill-setup" in text


def test_cca_fill_backfill_binds_registry_and_wallet_identity():
    text = WORKFLOW.read_text()

    assert "phase2-pools-trade-lbp-registry" in text
    assert "EXPECTED_REGISTRY_ARTIFACT_DIGEST" in text
    assert "EXPECTED_REGISTRY_SHA256" in text
    assert "reconcile_cca_bid_fills" in text
    assert "adapt_pools_trade_cca_fills_to_phase3" in text
    assert "wallet_identity_kind" in text
    assert "cca_bid_owner" in text


def test_cca_fill_backfill_is_fail_closed_not_source_complete():
    text = WORKFLOW.read_text()

    assert "validate_shard_block_coverage" in text
    assert "complete_fill_attribution" in text
    assert "unresolved_bids" in text
    assert '"source_coverage_complete": False' in text
    assert "phase2-outcome-labels" not in text
    assert "git push" not in text
    assert "contents: write" not in text



def test_cca_fill_backfill_publishes_compact_handoff():
    text = WORKFLOW.read_text()

    assert "build_phase3_cca_fill_handoff" in text
    assert "phase3-pools-trade-cca-fill-handoff.json" in text
    assert "phase3-pools-trade-cca-fills-handoff" in text
    assert "handoff_sha256" in text
