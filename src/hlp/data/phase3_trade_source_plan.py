"""Frozen Phase-3 canonical trade adapter/readiness plan."""

from __future__ import annotations

from hlp.data.phase2_sources import build_phase2_source_inventory


PHASE3_TRADE_SOURCE_PLAN_VERSION = "phase3-trade-source-plan-v1"


PONS_SOURCES = frozenset({"pons_v1", "pons_v2"})
V3_SOURCES = frozenset({
    "pools_fun",
    "noxa",
    "direct_uniswap_v3",
    "direct_sushiswap_v3",
})
V4_SOURCES = frozenset({
    "pools_trade_instant",
    "doppler",
    "direct_uniswap_v4",
})
CURVE_SOURCES = frozenset({
    "flap",
    "trench_today",
    "hood_fun_current",
    "hood_fun_previous",
})
LBP_BLOCKED_SOURCES = frozenset({"pools_trade_lbp"})


def build_phase3_trade_source_plan() -> list[dict]:
    """Map every frozen Phase-2 source to its Phase-3 wallet-trade path."""

    inventory = {
        str(row["source_id"]): dict(row)
        for row in build_phase2_source_inventory()
    }
    planned = (
        PONS_SOURCES
        | V3_SOURCES
        | V4_SOURCES
        | CURVE_SOURCES
        | LBP_BLOCKED_SOURCES
    )
    if planned != set(inventory):
        raise ValueError(
            "Phase-3 trade source plan does not match frozen inventory: "
            f"missing={sorted(set(inventory) - planned)} "
            f"extra={sorted(planned - set(inventory))}"
        )

    rows = []
    for source_id in sorted(inventory):
        source = inventory[source_id]
        if source_id in PONS_SOURCES:
            strategy = "pons_normalized_trade_adapter"
            implementation = [
                "hlp.data.pons_trades.normalize_pons_trades",
                "hlp.data.phase3_trade_adapters.adapt_pons_trades_to_phase3",
            ]
            ready = True
            gap = None
        elif source_id in V3_SOURCES:
            strategy = "raw_v3_swap_plus_tx_identity"
            implementation = [
                "hlp.protocols.uniswap.decode_v3_swap",
                "hlp.data.transaction_identity",
                "hlp.data.phase3_trade_adapters.adapt_v3_swaps_to_phase3",
            ]
            ready = True
            gap = None
        elif source_id in V4_SOURCES:
            strategy = "raw_v4_swap_plus_tx_identity"
            implementation = [
                "hlp.protocols.uniswap.decode_v4_swap",
                "hlp.data.transaction_identity",
                "hlp.data.phase3_trade_adapters.adapt_v4_swaps_to_phase3",
            ]
            ready = True
            gap = None
        elif source_id in CURVE_SOURCES:
            strategy = "native_curve_trade_plus_tx_identity"
            implementation = [
                "hlp.data.transaction_identity",
                "hlp.data.phase3_trade_adapters",
            ]
            ready = True
            gap = None
        else:
            strategy = "lbp_wallet_fill_attribution_plus_migrated_v4"
            implementation = [
                "hlp.protocols.pools_trade_lbp",
                "hlp.data.pools_trade_cca",
                "hlp.data.phase3_trade_adapters.adapt_v4_swaps_to_phase3",
            ]
            ready = False
            gap = (
                "wallet-level LBP/CCA fill attribution is not frozen; "
                "checkpoint/clearing-price rows are state evidence, not "
                "user-trade rows"
            )

        rows.append({
            "version": PHASE3_TRADE_SOURCE_PLAN_VERSION,
            "source_id": source_id,
            "venue": str(source["venue"]),
            "source_kind": str(source["source_kind"]),
            "market_phases": list(source.get("market_phases") or []),
            "adapter_strategy": strategy,
            "implementation_evidence": implementation,
            "transaction_initiator_required": True,
            "historical_event_scan_required": True,
            "exact_frozen_source_membership_required": True,
            "ready_for_canonical_trade_backfill": ready,
            "blocking_gap": gap,
            "outcome_dependency_allowed": False,
            "future_state_allowed": False,
        })
    return rows


def summarize_phase3_trade_source_plan(
    rows: list[dict] | None = None,
) -> dict:
    """Return a fail-closed readiness summary without claiming coverage."""

    plan = (
        build_phase3_trade_source_plan()
        if rows is None
        else [dict(row) for row in rows]
    )
    inventory_ids = {
        str(row["source_id"])
        for row in build_phase2_source_inventory()
    }
    seen = set()
    ready_ids = []
    blocked = {}
    for row in plan:
        if (
            str(row.get("version") or "")
            != PHASE3_TRADE_SOURCE_PLAN_VERSION
        ):
            raise ValueError("Phase-3 trade source plan version changed")
        source_id = str(row.get("source_id") or "")
        if source_id not in inventory_ids or source_id in seen:
            raise ValueError(
                f"Phase-3 trade source plan id invalid/repeated: {source_id}"
            )
        seen.add(source_id)
        for flag in (
            "transaction_initiator_required",
            "historical_event_scan_required",
            "exact_frozen_source_membership_required",
        ):
            if row.get(flag) is not True:
                raise ValueError(
                    f"{source_id} Phase-3 trade plan lost {flag}"
                )
        if row.get("outcome_dependency_allowed") is not False:
            raise ValueError(
                f"{source_id} Phase-3 trade plan allows outcomes"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"{source_id} Phase-3 trade plan allows future state"
            )
        if row.get("ready_for_canonical_trade_backfill") is True:
            if row.get("blocking_gap") is not None:
                raise ValueError(
                    f"{source_id} Phase-3 trade plan is ready but blocked"
                )
            ready_ids.append(source_id)
        else:
            gap = str(row.get("blocking_gap") or "").strip()
            if not gap:
                raise ValueError(
                    f"{source_id} Phase-3 trade plan lacks blocking gap"
                )
            blocked[source_id] = gap

    if seen != inventory_ids:
        raise ValueError(
            "Phase-3 trade source plan coverage mismatch: "
            f"missing={sorted(inventory_ids - seen)} "
            f"extra={sorted(seen - inventory_ids)}"
        )
    return {
        "version": PHASE3_TRADE_SOURCE_PLAN_VERSION,
        "inventory_sources": len(inventory_ids),
        "adapter_ready_sources": len(ready_ids),
        "adapter_ready_source_ids": sorted(ready_ids),
        "blocked_sources": len(blocked),
        "blocked_source_ids": sorted(blocked),
        "blocking_gaps": dict(sorted(blocked.items())),
        "canonical_trade_backfill_ready": not blocked,
        "trade_coverage_complete": False,
        "outcome_dependency_allowed": False,
        "future_state_allowed": False,
    }
