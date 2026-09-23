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


def test_phase3_trade_plan_has_14_adapter_ready_sources():
    plan = build_phase3_trade_source_plan()
    summary = summarize_phase3_trade_source_plan()

    assert summary["inventory_sources"] == 14
    assert summary["adapter_ready_sources"] == 14
    assert summary["blocked_sources"] == 0
    assert summary["blocked_source_ids"] == []
    assert summary["blocking_gaps"] == {}
    assert summary["canonical_trade_backfill_ready"] is True
    assert summary["trade_coverage_complete"] is False

    lbp = next(
        row for row in plan
        if row["source_id"] == "pools_trade_lbp"
    )
    assert lbp["wallet_identity_kind"] == "cca_bid_owner"
    assert lbp["wallet_identity_required"] is True
    assert lbp["transaction_initiator_required"] is False
    assert lbp["ready_for_canonical_trade_backfill"] is True
