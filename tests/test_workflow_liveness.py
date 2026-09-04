from pathlib import Path


WORKFLOWS = [
    "phase1-pons-v1-registry-recovery.yml",
    "phase1-pons-full-quote-audit.yml",
    "phase1-pons-v2-stock-oracle-full.yml",
    "phase1-pons-v2-curve-full.yml",
    "phase1-pons-v2-transition-full.yml",
    "phase1-pons-weth-usdg-anchor-full.yml",
    "phase1-pons-v2-v4-full.yml",
    "phase1-pons-v2-lifecycle-eligibility.yml",
    "phase1-pons-stock-oracle-full.yml",
    "phase1-pons-v1-v3-full.yml",
    "phase1-pons-v1-lifecycle-eligibility.yml",
    "phase1-pons-eligible-universe-freeze.yml",
]

MATRIX_WORKFLOWS = {
    "phase1-pons-v1-registry-recovery.yml",
    "phase1-pons-v2-stock-oracle-full.yml",
    "phase1-pons-v2-curve-full.yml",
    "phase1-pons-v2-transition-full.yml",
    "phase1-pons-weth-usdg-anchor-full.yml",
    "phase1-pons-v2-v4-full.yml",
    "phase1-pons-stock-oracle-full.yml",
    "phase1-pons-v1-v3-full.yml",
}


def _workflow(name: str) -> str:
    return (
        Path(__file__).parents[1] / ".github" / "workflows" / name
    ).read_text()


def test_pons_heavy_workflows_never_poll_other_runs():
    forbidden = (
        "time.sleep(",
        "for attempt in range",
        "Wait for recovered",
        "Wait for V2",
        "Wait for all original",
    )
    for name in WORKFLOWS:
        content = _workflow(name)
        for needle in forbidden:
            assert needle not in content, (
                f"{name} must fail fast on unavailable prerequisites; "
                f"runner-side polling is forbidden: {needle!r}"
            )


def test_pons_heavy_workflows_have_concurrency_locks():
    for name in WORKFLOWS:
        content = _workflow(name)
        assert "concurrency:" in content, name
        expected = "group: " + name.removesuffix(".yml") + "-${{ github.ref }}"
        assert expected in content, name
        assert "cancel-in-progress:" in content, name


def test_archive_matrix_workflows_are_small_and_bounded():
    for name in MATRIX_WORKFLOWS:
        content = _workflow(name)
        assert "max-parallel: 2" in content, name
        assert "SHARD_COUNT: '16'" in content, name
        assert "timeout-minutes: 35" in content, name
        assert "max-parallel: 4" not in content, name


def test_full_quote_audit_has_short_fail_fast_bound():
    content = _workflow("phase1-pons-full-quote-audit.yml")
    assert "timeout-minutes: 20" in content
    assert "timeout-minutes: 75" not in content



BACKFILL_WORKFLOWS = {
    "phase1-pons-full-registry.yml",
    "phase1-pons-full-census.yml",
    "phase1-pons-v1-registry-recovery.yml",
    "phase1-pons-v2-registry-freeze.yml",
    "phase1-pons-full-quote-audit.yml",
    "phase1-pons-v2-stock-oracle-full.yml",
    "phase1-pons-v2-curve-full.yml",
    "phase1-pons-v2-transition-full.yml",
    "phase1-pons-weth-usdg-anchor-full.yml",
    "phase1-pons-v2-v4-full.yml",
    "phase1-pons-v2-lifecycle-eligibility.yml",
    "phase1-pons-stock-oracle-full.yml",
    "phase1-pons-v1-v3-full.yml",
    "phase1-pons-v1-lifecycle-eligibility.yml",
    "phase1-pons-eligible-universe-freeze.yml",
    "phase1-pons-v3-quote-fallback-full.yml",
    "phase1-pons-v4-quote-fallback-full.yml",
    "phase1-pons-quote-fallback-full.yml",
}


def test_full_history_backfills_are_manual_only():
    for name in BACKFILL_WORKFLOWS:
        content = _workflow(name)
        trigger_block = content.split("\npermissions:", 1)[0]
        assert "workflow_dispatch:" in trigger_block, name
        assert "\n  push:" not in trigger_block, (
            f"{name} must not auto-start a full-history backfill on code pushes"
        )



NETWORK_SMOKE_WORKFLOWS = {
    "phase1-network-smoke.yml",
    "phase1-hoodfun-curve-mcap-smoke.yml",
    "phase1-v1-usd-path-smoke.yml",
    "phase1-v2-full-priced-smoke.yml",
    "phase1-pons-research-smoke.yml",
    "phase1-v2-shared-curve-smoke.yml",
    "phase1-v2-graduation-v4-smoke.yml",
    "phase1-dex-pool-census.yml",
    "phase1-pons-v1-multigen-smoke.yml",
    "phase1-v1-shared-tape-smoke.yml",
}


def test_secondary_network_smokes_are_manual_only():
    for name in NETWORK_SMOKE_WORKFLOWS:
        content = _workflow(name)
        trigger_block = content.split("\npermissions:", 1)[0]
        assert "workflow_dispatch:" in trigger_block, name
        assert "\n  push:" not in trigger_block, (
            f"{name} must not consume RPC runners on ordinary pushes"
        )
