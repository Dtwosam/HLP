from pathlib import Path


WORKFLOW = Path(".github/workflows/phase3-curve-trade-coverage.yml")


def test_curve_trade_coverage_supports_all_native_sources():
    text = WORKFLOW.read_text()

    for source_id in (
        "flap",
        "trench_today",
        "hood_fun_current",
        "hood_fun_previous",
    ):
        assert f"- {source_id}" in text
    assert "rpc-transaction-identity-enrich" in text
    assert "materialize_phase3_curve_trade_coverage" in text


def test_curve_trade_coverage_uses_native_event_shards():
    text = WORKFLOW.read_text()

    assert "event_registry_descriptor_json" in text
    assert "phase3-curve-event-shards.manifest.json" in text
    assert "validate_shard_block_coverage" in text
    assert "TRADE_EVENT_TYPES" in text
    assert "upstream_event_shard_sha256" in text


def test_curve_trade_coverage_is_fail_closed_and_descriptor_ready():
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
