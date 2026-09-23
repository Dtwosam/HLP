from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase3-pools-trade-lbp-trade-coverage.yml"
)


def test_lbp_trade_coverage_requires_exact_upstream_artifacts():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "phase3-feature-entry" in text
    assert "phase2-universe-freeze" in text
    assert "phase3-pools-trade-cca-fills" in text
    assert "EXPECTED_CCA_FILL_HANDOFF_SHA256" in text


def test_lbp_trade_coverage_binds_exact_source_membership():
    text = WORKFLOW.read_text()

    assert '"pools_trade_lbp" in set(row.get("source_ids") or [])' in text
    assert "build_phase3_trade_source_coverage" in text
    assert 'wallet_identity_kind="cca_bid_owner"' in text
    assert "submitted_sharded_sha256" in text
    assert "canonical_trade_rows_sha256" in text


def test_lbp_trade_coverage_is_fail_closed_and_label_free():
    text = WORKFLOW.read_text()

    assert "complete_fill_attribution" in text
    assert "historical_event_scan_complete=True" in text
    assert "wallet_identity_complete=True" in text
    assert "canonical_trade_adapter_complete=True" in text
    assert "trade_coverage_complete: true" in text
    assert "phase2-outcome-labels" not in text
    assert "git push" not in text
    assert "contents: write" not in text
