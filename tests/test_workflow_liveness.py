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
    "phase1-pons-representative-transfers-full.yml",
    "phase1-pons-acquisition-accounting.yml",
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
        if name in {
            "phase1-pons-v2-curve-full.yml",
            "phase1-pons-v2-v4-full.yml",
        }:
            assert "SHARD_COUNT: '64'" in content, name
            assert "timeout-minutes: 25" in content, name
        elif name in {
            "phase1-pons-weth-usdg-anchor-full.yml",
            "phase1-pons-v1-v3-full.yml",
        }:
            assert "SHARD_COUNT: '128'" in content, name
            assert "timeout-minutes: 25" in content, name
        else:
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
    "phase1-pons-representative-sample-freeze.yml",
    "phase1-pons-v3-quote-fallback-full.yml",
    "phase1-pons-v4-quote-fallback-full.yml",
    "phase1-pons-quote-fallback-full.yml",
    "phase1-pons-v4-quote-continuation.yml",
    "phase1-pons-skhy-v4-known-pool-continuation.yml",
    "phase1-pons-v2-curve-recover-tail-one-shot.yml",
    "phase1-pons-weth-usdg-anchor-recover-tail-one-shot.yml",
    "phase1-pons-v2-transition-recover-gaps.yml",
    "phase1-pons-v2-v4-recover-gaps.yml",
    "phase1-pons-v1-v3-recover-gaps.yml",
    "phase1-pons-v3-quote-fallback-recover-gaps.yml",
    "phase1-pons-v4-quote-fallback-recover-gaps.yml",
    "phase1-pons-stock-oracle-promote-v2-delta.yml",
    "phase1-pons-representative-transfers-full.yml",
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
}


def test_secondary_network_smokes_are_manual_only():
    for name in NETWORK_SMOKE_WORKFLOWS:
        content = _workflow(name)
        trigger_block = content.split("\npermissions:", 1)[0]
        assert "workflow_dispatch:" in trigger_block, name
        assert "\n  push:" not in trigger_block, (
            f"{name} must not consume RPC runners on ordinary pushes"
        )



def test_v2_eligibility_fails_fast_on_uncovered_quote_assets():
    content = _workflow("phase1-pons-v2-lifecycle-eligibility.yml")
    assert "if uncovered:" in content
    assert "cannot replay V2 lifecycle with uncovered quote assets" in content



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
    assert "\n  push:" not in trigger_block
    assert "max-parallel: 2" in content
    assert "SHARD_COUNT: '4'" in content
    assert "recovery range exceeds 600000-block ceiling" in content
    assert "timeout-minutes: 20" in content
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
    assert 'Path("prior-gaps").glob("anchor-gap-*.jsonl")' in content
    assert '"source": path.parent.name' in content
    assert 'default: "150000"' in content
    assert "max_gap_blocks must be between 1 and 150000" in content
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
    assert 'default: "150000"' in content
    assert "max_gap_blocks must be between 1 and 150000" in content
    assert "V4 gap plan exceeds 240 matrix jobs" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_stock_oracle_delta_promotion_is_manual_bounded_and_fail_closed():
    content = _workflow("phase1-pons-stock-oracle-promote-v2-delta.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "MAX_DELTA_BLOCKS: '500000'" in content
    assert "split_range" in content
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
    assert "pons-select-v4-quote-routes" in content
    assert "cannot freeze V4 quote fallback with unresolved residual" in content
    assert "selected V4 routes do not exactly cover residual probe" in content
    assert "residual_quote_assets" in content


def test_v3_quote_fallback_is_reusable_with_frozen_route_runs():
    content = _workflow("phase1-pons-v3-quote-fallback-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33921477647"' in content
    assert 'default: "33923160281"' in content
    assert "pons-select-v3-quote-routes" in content
    assert "frozen V3 fallback audit must contain 30 unique feedless" in content
    assert "frozen V3 fallback must select exactly 25 unique causal" in content
    assert "frozen V3 fallback must leave exactly five residual" in content
    assert "delayed V3 probe does not exactly cover the five residual" in content
    assert "frozen delayed V3 probe unexpectedly resolves a residual" in content


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
    assert 'default: "150000"' in content
    assert "max_gap_blocks must be between 1 and 150000" in content
    assert "V4 quote gap plan exceeds 240 matrix jobs" in content
    assert "phase1-pons-v4-quote-routes-selected" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
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
    assert 'default: "150000"' in content
    assert "max_gap_blocks must be between 1 and 150000" in content
    assert "V3 quote gap plan exceeds 240 matrix jobs" in content
    assert "phase1-pons-v3-quote-routes-selected" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
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
    assert 'default: "150000"' in content
    assert "max_gap_blocks must be between 1 and 150000" in content
    assert "V1 V3 gap plan exceeds 240 matrix jobs" in content
    assert "Pons V1 pools missing V3 Initialize" in content
    assert "max-parallel: 2" in content
    assert "timeout-minutes: 20" in content
    assert "matrix: ${{ fromJSON(needs.plan.outputs.matrix) }}" in content
    assert "time.sleep(" not in content


def test_v1_v3_full_is_reusable_with_frozen_registry():
    content = _workflow("phase1-pons-v1-v3-full.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert 'default: "33911022718"' in content
    assert "SHARD_COUNT: '128'" in content
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
    assert "SHARD_COUNT: '64'" in content


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
    assert 'default: "2000000"' in content
    assert "forward_blocks must be between 1 and 2000000" in content
    assert "0x84cab63bc87912e71ad199ff14a0ba45de68fef8" in content
    assert "0x8107f97277321f2899eba8d6721411e34cf368c6e24c9f0abb1658733e548601" in content
    assert "EXPECTED_PRIOR_SEARCH_END: '52863525'" in content
    assert "--known-pool-only" in content
    assert 'row.get("continuation_mode") != "known_pool_only"' in content
    assert "timeout-minutes: 20" in content
    assert "time.sleep(" not in content


def test_v4_quote_continuation_is_reusable_without_push_trigger():
    content = _workflow("phase1-pons-v4-quote-continuation.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "known_pool_only" in content
    assert "EXTRA+=(--known-pool-only)" in content

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

def test_representative_dex_crosscheck_is_manual_independent_and_bounded():
    content = _workflow("phase1-pons-representative-dex-crosscheck.yml")
    trigger_block = content.split("\npermissions:", 1)[0]
    assert "workflow_dispatch:" in trigger_block
    assert "workflow_call:" in trigger_block
    assert "\n  push:" not in trigger_block
    assert "GeckoTerminalClient" in content
    assert "geckoterminal_public_api" in content
    assert "not canonical historical truth" in content
    assert "representative DEX cross-check requires exactly 10" in content
    assert "independent DEX pool reconciliation failed" in content
    assert 'default: "33911022718"' in content
    assert 'default: "33912452330"' in content
    assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" not in content
    assert "time.sleep(" not in content

