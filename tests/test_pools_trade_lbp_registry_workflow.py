from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-pools-trade-lbp-registry-backfill.yml"
)


def test_lbp_registry_backfill_is_dispatch_only_and_sharded():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "launcher_run_id:" in text
    assert "SHARD_COUNT: '256'" in text
    assert "rpc-pools-trade-lbp-initializer-tape" in text
    assert "--state-out" in text
    assert "validate_shard_block_coverage" in text


def test_lbp_registry_backfill_binds_launcher_and_state():
    text = WORKFLOW.read_text()
    assert "phase2-pools-trade-launcher-merged" in text
    assert "pools.trade launcher coverage is incomplete" in text
    assert "pools-trade-lbp-registry" in text
    assert "--states artifacts/pools-trade-lbp-state.jsonl" in text
    assert "initializer_state_sha256" in text
    assert "distribution exceeds supply" in text


def test_lbp_registry_backfill_remains_nonfinal():
    text = WORKFLOW.read_text()
    assert '"source_id": "pools_trade_lbp"' in text
    assert '"continuous_initializer_scan": True' in text
    assert '"source_coverage_complete": False' in text
    assert "apply_phase2_source_coverage_report" not in text
    assert "git commit" not in text
    assert "git push" not in text
