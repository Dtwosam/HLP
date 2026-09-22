from hlp.data.phase2_sources import build_phase2_source_inventory
from hlp.data.phase3_trade_source_plan import (
    PHASE3_TRADE_SOURCE_PLAN_VERSION,
    build_phase3_trade_source_plan,
    summarize_phase3_trade_source_plan,
)


def test_phase3_trade_plan_covers_exact_frozen_source_inventory():
    plan = build_phase3_trade_source_plan()
    inventory = build_phase2_source_inventory()

    assert {row["source_id"] for row in plan} == {
        row["source_id"] for row in inventory
    }
    assert len(plan) == 14
    assert all(
        row["version"] == PHASE3_TRADE_SOURCE_PLAN_VERSION
        for row in plan
    )
    assert all(
        row["outcome_dependency_allowed"] is False
        and row["future_state_allowed"] is False
        for row in plan
    )


def test_phase3_trade_plan_keeps_lbp_wallet_attribution_blocked():
    summary = summarize_phase3_trade_source_plan()

    assert summary["inventory_sources"] == 14
    assert summary["adapter_ready_sources"] == 13
    assert summary["blocked_sources"] == 1
    assert summary["blocked_source_ids"] == ["pools_trade_lbp"]
    assert "wallet-level LBP/CCA fill attribution" in summary[
        "blocking_gaps"
    ]["pools_trade_lbp"]
    assert summary["canonical_trade_backfill_ready"] is False
    assert summary["trade_coverage_complete"] is False
