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
    "phase1-pons-representative-sample-freeze.yml",
    "phase1-pons-v3-quote-fallback-full.yml",
    "phase1-pons-v4-quote-fallback-full.yml",
    "phase1-pons-quote-fallback-full.yml",
    "phase1-pons-v4-quote-continuation.yml",
    "phase1-pons-skhy-v4-known-pool-continuation.yml",
    "phase1-pons-skhy-v4-known-pool-segmented.yml",
    "phase1-pons-representative-transfers-full.yml",
    "phase1-pons-representative-evidence-chain.yml",
    "phase1-pons-acquisition-accounting.yml",
    "phase1-pons-viability-route-measurement.yml",
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
        if name == "phase1-pons-v2-v4-full.yml":
            assert "SHARD_COUNT: '192'" in content, name
            assert "timeout-minutes: 30" in content, name
        elif name == "phase1-pons-v1-v3-full.yml":
            assert "SHARD_COUNT: '240'" in content, name
            assert "timeout-minutes: 40" in content, name
        elif name == "phase1-pons-v2-curve-full.yml":
            assert "SHARD_COUNT: '64'" in content, name
            assert "timeout-minutes: 25" in content, name
        elif name == "phase1-pons-weth-usdg-anchor-full.yml":
            assert "SHARD_COUNT: '128'" in content, name
            assert "timeout-minutes: 25" in content, name
        else:
            assert "SHARD_COUNT: '16'" in content, name
            assert "timeout-minutes: 35" in content, name
        if name in {
            "phase1-pons-v1-v3-full.yml",
            "phase1-pons-v2-v4-full.yml",
            "phase1-pons-weth-usdg-anchor-full.yml",
        }:
            assert 'printf -v SHARD "%03d" "$SHARD_INDEX"' in content, name
            assert 'printf -v SHARD "%02d" "$SHARD_INDEX"' not in content, name
        assert "max-parallel: 4" not in content, name


def test_viability_route_measurement_is_manual_bounded_and_canonical():
    content = _workflow("phase1-pons-viability-route-measurement.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    for route in (
        "pons_registry",
        "pons_v1_v3",
        "pons_v2_curve",
        "pons_v2_transition",
        "pons_v2_v4",
        "weth_usdg_anchor",
        "stock_oracle",
        "quote_v3_fallback",
        "quote_v4_fallback",
    ):
        assert f"          - {route}" in content
    assert 'default: "54436036"' in content
    assert 'default: "54486035"' in content
    assert "viability measurement exceeds 50000-block ceiling" in content
    assert "hi - lo + 1 > 50_000" in content
    assert "rpc-v1-registry-window" in content
    assert "rpc-v2-registry-window" in content
    assert "rpc-v3-pons-tape" in content
    assert "rpc-v2-curve-tape" in content
    assert "rpc-v2-transition-tape" in content
    assert "rpc-v2-v4-tape" in content
    assert "rpc-v1-price-path" in content
    assert "rpc-pons-stock-oracle-lifecycle" in content
    assert "rpc-v3-quote-route-tape" in content
    assert "rpc-v4-quote-route-tape" in content
    assert "registry_v2:" in content
    assert "if: ${{ inputs.route == 'pons_registry' }}" in content
    assert "shared measurement range must postdate V2 deployment" in content
    assert "phase1-pons-v3-quote-fallback-full" in content
    assert "phase1-pons-v4-quote-fallback-full" in content
    assert "quote fallback measurement requires eligibility_run_id" in content
    assert "timeout-minutes: 30" in content

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
    "phase1-pons-representative-sample-freeze.yml",
    "phase1-pons-v3-quote-fallback-full.yml",
    "phase1-pons-v4-quote-fallback-full.yml",
    "phase1-pons-quote-fallback-full.yml",
    "phase1-pons-v4-quote-continuation.yml",
    "phase1-pons-skhy-v4-known-pool-continuation.yml",
    "phase1-pons-skhy-v4-known-pool-segmented.yml",
    "phase1-pons-v2-curve-recover-tail-one-shot.yml",
    "phase1-pons-weth-usdg-anchor-recover-tail-one-shot.yml",
    "phase1-pons-v2-transition-recover-gaps.yml",
    "phase1-pons-v2-v4-recover-gaps.yml",
    "phase1-pons-v1-v3-recover-gaps.yml",
    "phase1-pons-v3-quote-fallback-recover-gaps.yml",
    "phase1-pons-v4-quote-fallback-recover-gaps.yml",
    "phase1-pons-stock-oracle-promote-v2-delta.yml",
    "phase1-pons-representative-transfers-full.yml",
    "phase1-pons-representative-evidence-chain.yml",
    "phase1-pons-viability-route-measurement.yml",
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
    "phase1-pons-representative-dex-crosscheck.yml",
    "phase1-blockscout-transaction-smoke.yml",
    "phase1-blockscout-v2-smoke.yml",
}


def test_secondary_network_smokes_are_manual_only():
    for name in NETWORK_SMOKE_WORKFLOWS:
        content = _workflow(name)
        trigger_block = content.split("\npermissions:", 1)[0]
        assert "workflow_dispatch:" in trigger_block, name
        assert "\n  push:" not in trigger_block, (
            f"{name} must not consume RPC runners on ordinary pushes"
        )



def test_blockscout_transaction_smoke_is_bounded_and_identity_checked():
    content = _workflow("phase1-blockscout-transaction-smoke.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "MAX_BLOCK_LOOKBACK = 20" in content
    assert "https://rpc.mainnet.chain.robinhood.com" in content
    assert 'rpc("eth_chainId", [])' in content
    assert "int(chain_id, 16) != 4663" in content
    assert "/api/v2/transactions/" in content
    assert "blockscout_reachable" in content
    assert "transaction_identity_match" in content
    assert "Blockscout transaction hash does not match Robinhood RPC" in content
    assert "Blockscout transaction block does not match Robinhood RPC" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content


def test_v2_eligibility_fails_fast_on_uncovered_quote_assets():
    content = _workflow("phase1-pons-v2-lifecycle-eligibility.yml")
    assert "if uncovered:" in content
    assert "cannot replay V2 lifecycle with uncovered quote assets" in content
    assert '"owned_quote_assets": 30' in content
    assert '"v3_routes": 26' in content
    assert '"v4_routes": 4' in content
    assert '"v3_v4_overlap_assets": 0' in content
    assert "generic quote fallback ownership contract changed" in content



def test_curve_range_recovery_is_manual_small_and_bounded():
    content = _workflow("phase1-pons-v2-curve-recover-range.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "max-parallel: 2" in content
    assert "SHARD_COUNT: '4'" in content
    assert "recovery range exceeds 200000-block ceiling" in content
    assert "timeout-minutes: 20" in content
    assert "time.sleep(" not in content



def test_anchor_range_recovery_is_manual_small_and_bounded():
    content = _workflow("phase1-pons-weth-usdg-anchor-recover-range.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "artifact_suffix" in content
    assert "phase1-pons-anchor-range-${{ inputs.artifact_suffix }}-" in content
    assert (
        "phase1-pons-anchor-recovered-range-${{ inputs.artifact_suffix }}"
        in content
    )
    assert "max-parallel: 2" in content
    assert "SHARD_COUNT: '4'" in content
    assert "recovery range exceeds 200000-block ceiling" in content
    assert "timeout-minutes: 20" in content
    assert "time.sleep(" not in content



def test_cancelled_anchor_gap_repair_is_manual_sequential_and_exact():
    content = _workflow(
        "phase1-pons-weth-usdg-anchor-cancelled-gap-repair.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "confirm_repair" in content
    assert 'from_block: "52169619"' in content
    assert 'to_block: "52319618"' in content
    assert 'artifact_suffix: "gap-018"' in content
    assert 'from_block: "53219619"' in content
    assert 'to_block: "53369618"' in content
    assert 'artifact_suffix: "gap-025"' in content
    assert "needs: repair_018" in content
    assert "needs.repair_018.result == 'success'" in content
    assert (
        "./.github/workflows/"
        "phase1-pons-weth-usdg-anchor-recover-range.yml"
        in content
    )


def test_anchor_recovered_promotion_is_manual_exact_and_streaming():
    content = _workflow(
        "phase1-pons-weth-usdg-anchor-promote-recovered.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33912536839"' in content
    assert 'default: "33925648293"' in content
    assert 'default: "33957294304"' in content
    assert 'default: "33970898635"' in content
    assert "phase1-pons-anchor-recovered-range-*" in content
    assert "select_anchor_source_ranges" in content
    assert '"preserved": 14' in content
    assert '"partial_recovery": 1' in content
    assert '"gap_recovery": 32' in content
    assert '"range_repair": 2' in content
    assert "(52_169_619, 52_319_618)" in content
    assert "(53_219_619, 53_369_618)" in content
    assert "promoted_recovered_weth_usdg_anchor" in content
    assert "pons-weth-usdg-anchor-full.jsonl" in content
    assert "pons-weth-usdg-anchor-initial.json" in content
    assert "pons-weth-usdg-anchor-summary.json" in content
    assert "no_unexplained_block_gaps" in content
    assert "state_rpc_response_bytes" in content
    assert "state_rpc_route" in content
    assert "rows = []" not in content
    assert "time.sleep(" not in content


def test_curve_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v2-curve-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert 'Path("prior-gaps").glob("curve-gap-*.jsonl")' in content
    assert '"source": path.parent.name' in content
    assert 'default: "50000"' in content
    assert "max_gap_blocks must be between 1 and 50000" in content
    assert "V2 curve gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content



def test_anchor_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-weth-usdg-anchor-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "prior_gap_run_id_2" in content
    assert 'Path("prior-gaps").glob("anchor-gap-*.jsonl")' in content
    assert 'Path("prior-gaps-2").glob("anchor-gap-*.jsonl")' in content
    assert '"source": path.parent.name' in content
    assert 'default: "50000"' in content
    assert "max_gap_blocks must be between 1 and 50000" in content
    assert "anchor gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content



def test_transition_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v2-transition-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "graduations-gap" in content
    assert "registrations-gap" in content
    assert "transition artifact families disagree" in content
    assert "manifest_gap_aware_transition_recovery" in content
    assert 'default: "150000"' in content
    assert "max_gap_blocks must be between 1 and 150000" in content
    assert "transition gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_v4_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v2-v4-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "v4-events-gap" in content
    assert "manifest_gap_aware_v4_recovery" in content
    assert 'default: "100000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V4 gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 30" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_stock_oracle_delta_promotion_is_manual_bounded_and_fail_closed():
    content = _workflow("phase1-pons-stock-oracle-promote-v2-delta.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "MAX_DELTA_BLOCKS: '100000'" in content
    assert "prior_delta_run_id" in content
    assert "plan_missing_subranges" in content
    assert "prior_successful_ranges" in content
    assert "gap_count" in content
    assert "oracle delta plan exceeds 240 matrix jobs" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "expected_full={len(expected_rows)}" in content
    assert "existing_v2={len(existing_tokens)}" in content
    assert "expected exactly one full-Pons stock-feed delta" in content
    assert "promoted_v2_oracle_plus_full_pons_delta" in content
    assert "promoted oracle does not exactly cover full-Pons stock feeds" in content
    assert "time.sleep(" not in content


def test_v4_quote_fallback_uses_cumulative_forward_probe():
    content = _workflow("phase1-pons-v4-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33926428274"' in content
    assert 'default: "phase1-pons-residual-v4-forward-probe"' in content
    assert 'default: "pons-residual-v4-forward-probe.jsonl"' in content
    assert "select_v4_quote_routes" in content
    assert "phase1-pons-v3-quote-fallback-full" in content
    assert "v3_run_id" in content
    assert "skhy_v4_run_id" in content
    assert "phase1-pons-skhy-v4-known-pool-segmented" in content
    assert "25-route V3 fallback requires resolved SKHY V4" in content
    assert "V4 fallback must select four or five unique routes" in content
    assert "SKHY must be owned by exactly one of canonical V3 or V4" in content
    assert '"ownership_mode": ownership_mode' in content
    assert "externally_resolved_assets" in content
    assert "residual_quote_assets" in content
    assert (
        "- uses: actions/upload-artifact@v4\n"
        "      - uses: actions/upload-artifact@v4"
    ) not in content
    assert "SHARD_COUNT: '128'" in content
    assert 'printf -v SHARD "%03d" "$SHARD_INDEX"' in content
    assert "max-parallel: 2" in content


def test_v3_quote_fallback_is_reusable_with_frozen_route_runs():
    content = _workflow("phase1-pons-v3-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33921477647"' in content
    assert 'default: "33923160281"' in content
    assert "pons-select-v3-quote-routes" in content
    assert "phase1-pons-skhy-v3-weth-segmented" in content
    assert "phase1-pons-weth-usdg-anchor-full" in content
    assert "skhy_weth_run_id" in content
    assert "anchor_run_id" in content
    assert "merge_v3_quote_routes" in content
    assert "searched_to_snapshot_head" in content
    assert "canonical V3 fallback must select 25 or 26 unique routes" in content
    assert "SKHY must be owned by exactly one of V3 or the residual set" in content
    assert "causal_v3_routes_with_optional_delayed_skhy_weth" in content
    assert "--anchor-initial anchor/pons-weth-usdg-anchor-initial.json" in content
    assert "--anchor-events anchor/pons-weth-usdg-anchor-full.jsonl" in content
    assert "SHARD_COUNT: '128'" in content
    assert 'printf -v SHARD "%03d" "$SHARD_INDEX"' in content
    assert "max-parallel: 2" in content


def test_generic_quote_fallback_owns_exact_26_v3_plus_4_v4():
    content = _workflow("phase1-pons-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-v3-quote-fallback-full" in content
    assert "phase1-pons-v4-quote-fallback-full" in content
    assert "generic fallback requires exact 26/4 or 25/5 V3/V4" in content
    assert "generic fallback requires exactly one SKHY venue owner" in content
    assert "26/4 generic fallback requires SKHY ownership in V3" in content
    assert "25/5 generic fallback requires SKHY ownership in V4" in content
    assert "V3/V4 fallback ownership overlaps" in content
    assert "route ownership and merged quote/USD ownership disagree" in content
    assert "merged quote fallback must own exactly 30 feedless quote" in content


def test_v4_quote_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v4-quote-fallback-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "v4-quote-events-gap" in content
    assert "manifest_gap_aware_v4_quote_recovery" in content
    assert "activation_by_pool" in content
    assert 'int(row["block_number"]) >= (' in content
    assert 'default: "100000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V4 quote gap plan exceeds 240 matrix jobs" in content
    assert "phase1-pons-v4-quote-routes-selected" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 30" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_v3_quote_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v3-quote-fallback-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "v3-quote-events-gap" in content
    assert "manifest_gap_aware_v3_quote_recovery" in content
    assert 'default: "100000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V3 quote gap plan exceeds 240 matrix jobs" in content
    assert "phase1-pons-v3-quote-routes-selected" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 30" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_v1_v3_gap_recovery_is_manual_gap_aware_and_bounded():
    content = _workflow("phase1-pons-v1-v3-recover-gaps.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "plan_missing_subranges" in content
    assert "prior_gap_run_id" in content
    assert "v1-v3-events-gap" in content
    assert "manifest_gap_aware_v1_v3_recovery" in content
    assert 'default: "100000"' in content
    assert "max_gap_blocks must be between 1 and 100000" in content
    assert "V1 V3 gap plan exceeds 240 matrix jobs" in content
    assert "Pons V1 pools missing V3 Initialize" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 30" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_v1_v3_full_is_reusable_with_frozen_registry():
    content = _workflow("phase1-pons-v1-v3-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33911022718"' in content
    assert "SHARD_COUNT: '240'" in content
    assert "timeout-minutes: 40" in content
    assert "max-parallel: 2" in content


def test_v1_eligibility_is_reusable_with_frozen_quote_audit():
    content = _workflow("phase1-pons-v1-lifecycle-eligibility.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33911022718"' in content
    assert 'default: "33923299711"' in content
    assert 'default: "phase1-pons-full-quote-audit-current"' in content
    assert "V1 quote coverage is not complete" in content
    assert "Validate frozen V1 lifecycle input manifests" in content
    assert "required V1 lifecycle manifest is missing" in content
    assert "timeout-minutes: 60" in content
    assert 'provenance.get("storage_mode") != "sharded_artifacts"' in content
    assert 'for key in ("partial_run_id", "prior_gap_run_id")' in content
    assert "v3-shards/current" in content
    assert "v3-shards/partial" in content
    assert "v3-shards/prior" in content
    assert "--v3-events-dir v3-shards" in content
    assert "--v3-events-manifest v3/pons-v1-v3-full.jsonl.manifest.json" in content
    assert "V1 lifecycle manifest snapshot mismatch" in content
    assert "frozen V1 lifecycle SHA changed" in content
    assert "c75b93b5b8ace0caad3376b5e79c6dcdb9ba675fce9085f6db7458f3694d30ed" in content
    assert "c822fe8d66f6b24ee496ccd20203cc81023e113ba0f66fa4188a5be49dd346dc" in content


def test_v2_v4_full_is_reusable_with_frozen_transition():
    content = _workflow("phase1-pons-v2-v4-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33912452330"' in content
    assert "max-parallel: 2" in content
    assert "SHARD_COUNT: '192'" in content
    assert "timeout-minutes: 30" in content


def test_quote_fallback_merge_is_reusable_without_network_trigger():
    content = _workflow("phase1-pons-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "pons-merge-quote-usd-tapes" in content
    assert "merged quote fallback must have exactly 25 causal initial" in content
    assert "merged quote fallback must own exactly 30 feedless quote" in content
    assert "owned_quote_assets" in content
    assert "SNAPSHOT_HEAD: '54486035'" in content
    assert '--snapshot-head "$SNAPSHOT_HEAD"' in content


def test_v2_eligibility_is_reusable_with_frozen_known_inputs():
    content = _workflow("phase1-pons-v2-lifecycle-eligibility.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33912235341"' in content
    assert 'default: "33936232604"' in content
    assert 'default: "33912452330"' in content
    assert "cannot replay V2 lifecycle with uncovered quote assets" in content
    assert "Validate frozen V2 lifecycle input manifests" in content
    assert "required lifecycle manifest is missing" in content
    assert "timeout-minutes: 60" in content
    assert 'provenance.get("storage_mode") != "sharded_artifacts"' in content
    assert 'for key in ("partial_run_id", "prior_gap_run_id")' in content
    assert "v4-shards/current" in content
    assert "v4-shards/partial" in content
    assert "v4-shards/prior" in content
    assert "--v4-events-dir v4-shards" in content
    assert "--v4-events-manifest v4/pons-v2-v4-full.jsonl.manifest.json" in content
    assert "lifecycle manifest snapshot mismatch" in content
    assert "frozen lifecycle SHA changed" in content
    assert "validated_manifest_count" in content
    assert "771c9147ef1a84bd673532842972e16e0ee12cae1513a41b402f53b5c444c50b" in content


def test_eligible_universe_freeze_is_reusable_and_fails_closed():
    content = _workflow("phase1-pons-eligible-universe-freeze.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "cannot freeze complete $100k universe while eligibility" in content
    assert "required eligibility manifest is missing" in content
    assert "eligibility manifest snapshot mismatch" in content
    assert "eligibility manifest record mismatch" in content
    assert "268_688" in content
    assert "225_951" in content
    assert "eligibility artifact has invalid status values" in content


def test_skhy_known_pool_continuation_is_manual_bounded_and_frozen():
    content = _workflow("phase1-pons-skhy-v4-known-pool-continuation.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33926428274"' in content
    assert 'default: "100000"' in content
    assert "forward_blocks must be between 1 and 100000" in content
    assert "expected_prior_search_end" in content
    assert "output_artifact_name" in content
    assert "0x84cab63bc87912e71ad199ff14a0ba45de68fef8" in content
    assert "0x8107f97277321f2899eba8d6721411e34cf368c6e24c9f0abb1658733e548601" in content
    assert 'default: "52863525"' in content
    assert "--known-pool-only" in content
    assert 'row.get("continuation_mode") != "known_pool_only"' in content
    assert "continue_needed" in content
    assert "route_ready" in content
    assert "search_to_block" in content
    assert "GITHUB_OUTPUT" in content
    assert "timeout-minutes: 30" in content
    assert "time.sleep(" not in content


def test_full_eligibility_one_shot_is_guarded_and_pinned():
    content = _workflow(
        "phase1-pons-full-eligibility-acquisition-one-shot.yml"
    )
    assert "phase1-pons-full-eligibility-acquisition-chain.yml" in content
    assert "launch full eligibility acquisition" in content
    assert 'oracle_run_id: "33974681334"' in content
    assert 'anchor_run_id: "33972109927"' in content
    assert "workflow_dispatch:" not in content


def test_full_eligibility_acquisition_chain_serializes_heavy_market_tapes():
    content = _workflow(
        "phase1-pons-full-eligibility-acquisition-chain.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-stock-oracle-full" in content
    assert "canonical stock oracle must contain 23 feeds" in content
    assert 'summary.get("delta_symbols") != ["DELL"]' in content
    assert "needs: preflight" in content
    assert "needs.preflight.result == 'success'" in content
    assert "phase1-pons-v1-v3-full.yml" in content
    assert "phase1-pons-v1-v3-recover-gaps.yml" in content
    assert "phase1-pons-v2-v4-full.yml" in content
    assert "phase1-pons-v2-v4-recover-gaps.yml" in content
    assert "needs.v1_v3.result == 'failure'" in content
    assert "needs.v1_v3_recovery.result == 'success'" in content
    assert "needs.v2_v4.result == 'failure'" in content
    assert "needs.v2_v4_recovery.result == 'success'" in content
    assert content.count('partial_run_id: ${{ format(\'{0}\', github.run_id) }}') == 2
    assert content.count('max_gap_blocks: "100000"') == 2
    assert "phase1-pons-pricing-eligibility-chain.yml" in content
    assert content.count("format('{0}', github.run_id)") == 4
    assert "cancel-in-progress: false" in content


def test_pricing_eligibility_chain_branches_on_frozen_skhy_completion():
    content = _workflow("phase1-pons-pricing-eligibility-chain.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "needs.skhy_v3.outputs.completion_status" in content
    assert "searched_to_snapshot_head" in content
    assert "needs.skhy_v4.outputs.route_ready == 'true'" in content
    assert "needs.skhy_v3.outputs.completion_status == 'route_resolved'" in content
    assert "phase1-pons-skhy-v4-known-pool-segmented.yml" in content
    assert "phase1-pons-v3-quote-fallback-full.yml" in content
    assert "phase1-pons-v3-quote-fallback-recover-gaps.yml" in content
    assert "needs.v3_fallback_recovery.result == 'success'" in content
    assert "phase1-pons-v4-quote-fallback-full.yml" in content
    assert "phase1-pons-v4-quote-fallback-recover-gaps.yml" in content
    assert "needs.v4_fallback_recovery.result == 'success'" in content
    assert content.count('max_gap_blocks: "100000"') == 2
    assert "phase1-pons-quote-fallback-full.yml" in content
    assert "phase1-pons-v1-lifecycle-eligibility.yml" in content
    assert "phase1-pons-v2-lifecycle-eligibility.yml" in content
    assert "phase1-pons-eligible-universe-freeze.yml" in content
    assert "format('{0}', github.run_id)" in content
    assert "cancel-in-progress: false" in content


def test_skhy_v4_one_shot_launcher_is_explicit_and_guarded():
    content = _workflow(
        "phase1-pons-skhy-v4-known-pool-segmented-one-shot.yml"
    )
    assert "phase1-pons-skhy-v4-known-pool-segmented.yml" in content
    assert "launch SKHY V4 known-pool continuation" in content
    assert 'prior_probe_run_id: "33926428274"' in content
    assert "workflow_dispatch:" not in content


def test_skhy_segmented_continuation_is_manual_sequential_and_complete():
    content = _workflow(
        "phase1-pons-skhy-v4-known-pool-segmented.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert content.count(
        "uses: ./.github/workflows/"
        "phase1-pons-skhy-v4-known-pool-continuation.yml"
    ) == 17
    assert content.count('forward_blocks: "100000"') == 17
    for index in range(16):
        assert f"needs: segment_{index}" in content
        assert (
            f"needs.segment_{index}.outputs.continue_needed == 'true'"
            in content
        )
        assert f"phase1-pons-skhy-v4-segment-{index}" in content
    assert "phase1-pons-skhy-v4-segment-16" in content
    assert "pattern: phase1-pons-skhy-v4-segment-*" in content
    assert '"continuation_segments": latest_index + 1' in content
    assert '"max_blocks_per_segment": 100000' in content
    assert "phase1-pons-skhy-v4-known-pool-segmented" in content
    assert "segmented SKHY continuation ended before snapshot head" in content
    assert '"remaining_unsearched_blocks": remaining' in content
    assert "max_blocks_per_segment" in content
    assert "jobs.finalize.outputs.completion_status" in content
    assert "steps.freeze.outputs.route_ready" in content
    assert "GITHUB_OUTPUT" in content
    assert "time.sleep(" not in content


def test_v4_quote_continuation_is_reusable_without_push_trigger():
    content = _workflow("phase1-pons-v4-quote-continuation.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "known_pool_only" in content
    assert "EXTRA+=(--known-pool-only)" in content

def test_representative_evidence_chain_threads_one_parent_run_and_retries_transfers():
    content = _workflow("phase1-pons-representative-evidence-chain.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "cancel-in-progress: false" in content
    assert "phase1-pons-representative-sample-freeze.yml" in content
    assert "phase1-pons-representative-market-paths.yml" in content
    assert content.count("phase1-pons-representative-transfers-full.yml") == 2
    assert "phase1-pons-representative-priced-paths.yml" in content
    assert "phase1-pons-representative-dex-crosscheck.yml" in content
    assert "phase1-pons-representative-validation.yml" in content
    assert content.count("v1_eligibility_run_id: ${{ inputs.eligibility_run_id }}") == 3
    assert content.count("v2_eligibility_run_id: ${{ inputs.eligibility_run_id }}") == 3
    assert "v1_v3_run_id: ${{ inputs.eligibility_run_id }}" in content
    assert "v2_v4_run_id: ${{ inputs.eligibility_run_id }}" in content
    assert "fallback_run_id: ${{ inputs.eligibility_run_id }}" in content
    assert "prior_run_id: ${{ inputs.prior_transfer_run_id }}" in content
    assert "prior_run_id: ${{ format('{0}', github.run_id) }}" in content
    assert "needs.transfers.result == 'failure'" in content
    assert "needs.transfers_retry.result == 'success'" in content
    assert content.count("format('{0}', github.run_id)") >= 12

def test_representative_sample_freeze_is_reusable_and_pinned():
    content = _workflow("phase1-pons-representative-sample-freeze.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33920762592"' in content
    assert "4861b2af1d549eb41c53341a07f6de71dce4d9486b769543c1376beab9c19ab9" in content
    assert "6fb40693b77d7434d4e579a2225fed2c65061841a5ea9d0ba56f785071fc6ef2" in content
    assert "frozen runner smoke must contain exactly five eligible" in content
    assert 'versions != {"v1": 4, "v2": 1}' in content
    assert "--runners 5 --failures 5" in content
    assert "representative sample must freeze exactly five runners" in content
    assert "representative sample must contain both Pons generations" in content
    assert "time.sleep(" not in content

def test_representative_transfer_backfill_is_manual_resumable_and_bounded():
    content = _workflow("phase1-pons-representative-transfers-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "prior_run_id" in content
    assert "plan_missing_subranges" in content
    assert 'default: "200000"' in content
    assert "max_blocks must be between 1 and 200000" in content
    assert "representative transfer plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "time.sleep(" not in content


def test_phase1_acceptance_gate_is_manual_artifact_only_and_fail_closed():
    content = _workflow("phase1-pons-acceptance-gate.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-eligible-universe" in content
    assert "phase1-pons-representative-validation" in content
    assert "phase1-pons-acquisition-viability-projection" in content
    assert "build_phase1_acceptance_report" in content
    assert "REQUIRED_PHASE1_ACQUISITION_ROUTES" in content
    assert 'phase1_acceptance_status"] != "pass"' in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_phase1_viability_projection_is_manual_artifact_only_and_fail_closed():
    content = _workflow(
        "phase1-pons-acquisition-viability-projection.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-acquisition-accounting" in content
    assert "build_phase1_route_plan" in content
    assert "project_phase1_acquisition_plan" in content
    assert "route_plan_json" in content
    assert "route -> evidence run IDs" in content
    assert "zero_cost_route_evidence" in content
    assert "does not mark Phase 1 PASS" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_phase1_acquisition_accounting_is_manual_github_only_and_bounded():
    content = _workflow("phase1-pons-acquisition-accounting.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "actions: read" in content
    assert "run_ids_json" in content
    assert "at most 50 positive integer run IDs" in content
    assert "summarize_action_run" in content
    assert "summarize_phase1_runs" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "max-parallel:" not in content
    assert "time.sleep(" not in content

def test_skhy_v3_weth_continuation_is_manual_known_pool_and_bounded():
    content = _workflow(
        "phase1-pons-skhy-v3-weth-continuation.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33921477647"' in content
    assert "0x84cab63bc87912e71ad199ff14a0ba45de68fef8" in content
    assert "0x13f78b235d19141f572986afcaab66ce7744b4ef" in content
    assert "SKHY_WETH_FEE: '3000'" in content
    assert "SKHY_FIRST_PONS_USE: '52263525'" in content
    assert "forward_blocks must be between 1 and 100000" in content
    assert 'deployment-block "$SKHY_WETH_POOL"' in content
    assert "--archive" in content
    assert "rpc-pons-delayed-v3-weth-routes" in content
    assert '--quote-token "$SKHY_TOKEN"' in content
    assert "continue_needed" in content
    assert "next_from_block" in content
    assert "route_ready" in content
    assert "first_observed_usd_price" in content
    assert "deferred to event-ordered WETH/USD anchor replay" in content
    assert "timeout-minutes: 30" in content
    assert "max-parallel:" not in content
    assert "time.sleep(" not in content


def test_skhy_v3_weth_segmented_is_manual_sequential_and_early_stopping():
    content = _workflow(
        "phase1-pons-skhy-v3-weth-segmented.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert content.count(
        "phase1-pons-skhy-v3-weth-continuation.yml"
    ) == 23
    assert content.count('forward_blocks: "100000"') == 23
    for index in range(22):
        assert (
            f"needs.segment_{index}.outputs.continue_needed == 'true'"
            in content
        )
        assert (
            f"needs.segment_{index}.outputs.next_from_block"
            in content
        )
    assert '"max_blocks_per_segment": 100000' in content
    assert "if: ${{ always() }}" in content
    assert "searched_to_snapshot_head" in content
    assert "route_resolved" in content
    assert "jobs.finalize.outputs.completion_status" in content
    assert "steps.freeze.outputs.route_ready" in content
    assert "GITHUB_OUTPUT" in content
    assert "max_blocks_per_segment" in content
    assert "max-parallel:" not in content
    assert "time.sleep(" not in content


def test_representative_explorer_crosscheck_is_manual_public_and_bounded():
    content = _workflow(
        "phase1-pons-representative-explorer-crosscheck.yml"
    )
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "access_reverified" in content
    assert "known 403" in content
    assert "if: ${{ inputs.access_reverified == true }}" in content
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-representative-market-paths" in content
    assert "phase1-pons-representative-priced-paths" in content
    assert "BlockscoutClient" in content
    assert "build_representative_explorer_targets" in content
    assert "build_representative_explorer_token_summaries" in content
    assert "10 <= len(targets) <= 40" in content
    assert "blockscout_requests" in content
    assert "blockscout_response_bytes" in content
    assert "transaction_identity_and_block" in content
    assert "raw chain" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_representative_dex_crosscheck_is_manual_independent_and_bounded():
    content = _workflow("phase1-pons-representative-dex-crosscheck.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "GeckoTerminalClient" in content
    assert "geckoterminal_public_api" in content
    assert "not canonical historical truth" in content
    assert "phase1-pons-representative-priced-paths" in content
    assert "priced_path_run_id" in content
    assert "select_representative_dex_price_checkpoints" in content
    assert "targeted_swap_price_tokens" in content
    assert "targeted_swap_price_checkpoints" in content
    assert "representative DEX cross-check requires exactly 10" in content
    assert "independent DEX pool reconciliation failed" in content
    assert 'default: "33911022718"' in content
    assert 'default: "33912452330"' in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content



def test_representative_market_paths_are_manual_artifact_only_and_bounded():
    content = _workflow("phase1-pons-representative-market-paths.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-full-registry-recovered" in content
    assert "phase1-pons-v1-v3-full" in content
    assert "phase1-pons-v2-curve-full" in content
    assert "phase1-pons-v2-transition-full" in content
    assert "phase1-pons-v2-v4-full" in content
    assert "build_representative_market_path_rows" in content
    assert "summarize_representative_market_paths" in content
    assert "summarize_sharded_manifest_coverage" in content
    assert "pons-representative-market-source-coverage.json" in content
    assert "no provider requests" in content
    assert 'default: "33911022718"' in content
    assert 'default: "33936232604"' in content
    assert 'default: "33912452330"' in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_representative_priced_paths_are_manual_artifact_only_and_bounded():
    content = _workflow("phase1-pons-representative-priced-paths.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-representative-market-paths" in content
    assert "phase1-pons-weth-usdg-anchor-full" in content
    assert "phase1-pons-stock-oracle-full" in content
    assert "phase1-pons-quote-fallback-full" in content
    assert "build_v1_market_cap_points" in content
    assert "build_v2_curve_market_cap_points" in content
    assert "build_v2_graduation_seed_points" in content
    assert "build_v2_v4_market_cap_points" in content
    assert "validate_representative_priced_path_rows" in content
    assert "summarize_representative_priced_paths" in content
    assert "summarize_sharded_manifest_coverage" in content
    assert "summarize_snapshot_manifest_coverage" in content
    assert "pons-representative-pricing-source-coverage.json" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "RpcClient" not in content
    assert "GeckoTerminalClient" not in content
    assert "time.sleep(" not in content


def test_representative_validation_is_manual_artifact_only_and_fail_closed():
    content = _workflow("phase1-pons-representative-validation.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "phase1-pons-representative-sample" in content
    assert "phase1-pons-v1-lifecycle-eligibility" in content
    assert "phase1-pons-v2-lifecycle-eligibility" in content
    assert "phase1-pons-representative-transfers-full" in content
    assert "phase1-pons-representative-market-paths" in content
    assert "market_path_run_id" in content
    assert "phase1-pons-representative-priced-paths" in content
    assert "priced_path_run_id" in content
    assert "pons-representative-priced-path-summary.jsonl" in content
    assert "phase1-pons-representative-dex-crosscheck" in content
    assert "phase1-pons-representative-explorer-crosscheck" not in content
    assert "explorer_crosscheck_run_id" not in content
    assert "pons-representative-explorer-token-summary.jsonl" not in content
    assert "build_representative_validation_rows" in content
    assert "summarize_representative_validation" in content
    assert "validate_representative_coverage_report" in content
    assert "pons-representative-source-coverage.jsonl" in content
    assert "source_coverage_sha256" in content
    assert "representative validation must contain exactly 10" in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content
