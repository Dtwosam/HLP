from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/"
    "phase2-pools-trade-instant-registry-backfill.yml"
)


def test_pools_trade_instant_registry_backfill_is_dispatch_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "launcher_run_id:" in text
    assert "SHARD_COUNT: '256'" in text
    assert "rpc-pools-trade-instant-launch-tape" in text
    assert "pools-trade-instant-registry" in text


def test_pools_trade_instant_registry_requires_continuous_exact_history():
    text = WORKFLOW.read_text()

    assert "validate_shard_block_coverage" in text
    assert "pools_trade_instant_strategy_events" in text
    assert "Instant strategy set drift" in text
    assert "pools.trade launcher start drift" in text
    assert "pools.trade launcher snapshot drift" in text
    assert "pools.trade Instant merged bytes changed" in text


def test_pools_trade_instant_registry_remains_nonfinal():
    text = WORKFLOW.read_text()

    assert '"source_id": "pools_trade_instant"' in text
    assert '"source_coverage_complete": False' in text
    assert "phase2-pools-trade-instant-registry" in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
