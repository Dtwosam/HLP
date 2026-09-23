from pathlib import Path

WORKFLOW = Path(
    ".github/workflows/"
    "phase2-pools-trade-instant-source-coverage.yml"
)


def test_pools_trade_instant_coverage_reuses_shared_surfaces():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "registry_run_id:" in text
    assert "v4_swap_run_id:" in text
    assert "supply_delta_run_id:" in text
    assert "quote_run_id:" in text
    assert "phase2-direct-v4-swap-${{ matrix.shard }}" in text
    assert "phase2-direct-supply-delta-manifest" in text
    assert "phase2-pools-trade-instant-market-window" in text


def test_pools_trade_instant_coverage_is_fail_closed():
    text = WORKFLOW.read_text()
    assert "pools.trade launcher scan is not continuous" in text
    assert "pools.trade Instant launch scan is not continuous" in text
    assert "Initialize population incomplete" in text
    assert "shard has unpriced points" in text
    assert "summary does not cover every registry token" in text
    assert "Initialize point population drift" in text
    assert "merged summary has missing/unpriced history" in text
    assert "validate_pools_trade_instant_coverage_report" in text
    assert '"coverage_status": "complete"' in text


def test_pools_trade_instant_coverage_uses_initialized_supply_registry():
    text = WORKFLOW.read_text()
    assert "pools-trade-instant-initialized-registry.jsonl" in text
    assert "initialized_registry_sha256" in text
    assert "v4_initialize_sha256" in text
    assert "launch_state_sha256" not in text
    assert "same_transaction_initialize_complete" not in text


def test_pools_trade_instant_coverage_proposes_without_mutating():
    text = WORKFLOW.read_text()
    assert "apply_phase2_source_coverage_report" in text
    assert (
        "pools-trade-instant-source-coverage-proposed-ledger.json"
        in text
    )
    assert "expected_source_id: pools_trade_instant" in text
    assert "git commit" not in text
    assert "git push" not in text
