"""Exact Phase-2 planner contract after the archive fan-out completes."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase2_first_wave import (
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
    PHASE2_INITIAL_COMPLETE_SOURCE_IDS,
)


PHASE2_POST_FANOUT_AUTO_NODE_IDS = (
    "shared:direct_market_registry",
    "coverage:pools_fun",
    "registry:pools_trade_instant",
    "registry:pools_trade_lbp",
    "registry:doppler",
    "derive:flap_curve",
    "derive:trench_curve",
    "coverage:hood_fun_previous",
    "coverage:noxa",
)
PHASE2_POST_FANOUT_MANUAL_NODE_IDS = (
    "promote:hood_fun_current",
)


def validate_phase2_post_fanout_stage(
    execution_plan: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze the nine-node automatic wave and one manual promotion stop."""

    execution = dict(execution_plan)
    dispatch = dict(dispatch_plan)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 post-fan-out stage changed canonical source state"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 post-fan-out stage requires exactly 2 complete sources"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 post-fan-out stage requires exactly 12 incomplete sources"
        )

    expected_completed = set(PHASE2_FIRST_WAVE_NODE_IDS) | set(
        PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
    )
    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    if not isinstance(completed, list) or not isinstance(ready, list):
        raise ValueError(
            "Phase-2 post-fan-out stage lacks execution node-state lists"
        )
    if set(completed) != expected_completed:
        raise ValueError(
            "Phase-2 post-fan-out completed-node set drift"
        )

    expected_ready = set(PHASE2_POST_FANOUT_AUTO_NODE_IDS) | set(
        PHASE2_POST_FANOUT_MANUAL_NODE_IDS
    )
    if set(ready) != expected_ready:
        raise ValueError(
            "Phase-2 post-fan-out ready-node set drift: "
            f"{sorted(ready)}"
        )

    if dispatch.get("run_id_inputs_generated_from_verified_receipts") is not True:
        raise ValueError(
            "Phase-2 post-fan-out dispatch plan lacks verified run inputs"
        )
    if dispatch.get("non_run_inputs_left_explicit") is not True:
        raise ValueError(
            "Phase-2 post-fan-out dispatch plan hides manual inputs"
        )
    if dispatch.get("workflow_dispatch_performed") is not False:
        raise ValueError(
            "Phase-2 post-fan-out dispatch plan already claims dispatch"
        )
    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError(
            "Phase-2 post-fan-out dispatch rows are missing"
        )
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != expected_ready:
        raise ValueError(
            "Phase-2 post-fan-out dispatch row set drift"
        )

    auto = []
    for node_id in PHASE2_POST_FANOUT_AUTO_NODE_IDS:
        row = by_id[node_id]
        if str(row.get("status") or "") != "ready_to_dispatch":
            raise ValueError(
                f"Phase-2 post-fan-out auto node not ready: {node_id}"
            )
        if row.get("requires_explicit_approval") is not False:
            raise ValueError(
                f"Phase-2 post-fan-out auto node requires approval: "
                f"{node_id}"
            )
        if row.get("requires_archive_secret") is not True:
            raise ValueError(
                f"Phase-2 post-fan-out auto node lost archive-secret gate: "
                f"{node_id}"
            )
        run_inputs = row.get("run_id_inputs")
        all_inputs = row.get("all_dispatch_input_names")
        if not isinstance(run_inputs, Mapping) or not run_inputs:
            raise ValueError(
                f"Phase-2 post-fan-out auto node lacks generated run inputs: "
                f"{node_id}"
            )
        if list(row.get("remaining_manual_inputs") or []):
            raise ValueError(
                f"Phase-2 post-fan-out auto node has manual inputs: {node_id}"
            )
        if set(str(value) for value in all_inputs or []) != set(run_inputs):
            raise ValueError(
                f"Phase-2 post-fan-out auto node input schema drift: "
                f"{node_id}"
            )
        auto.append({
            "node_id": node_id,
            "workflow": str(row.get("workflow") or ""),
            "run_id_inputs": dict(run_inputs),
        })

    promotion = by_id["promote:hood_fun_current"]
    if str(promotion.get("status") or "") != "ready_to_dispatch":
        raise ValueError(
            "Phase-2 hood.fun current promotion is not ready"
        )
    if str(promotion.get("workflow") or "") != (
        "phase2-source-coverage-promotion.yml"
    ):
        raise ValueError(
            "Phase-2 hood.fun current promotion workflow drift"
        )
    if promotion.get("requires_explicit_approval") is not False:
        raise ValueError(
            "Phase-2 hood.fun current promotion unexpectedly requires "
            "dispatcher approval"
        )
    promotion_run_inputs = dict(
        promotion.get("run_id_inputs") or {}
    )
    if set(promotion_run_inputs) != {"coverage_run_id"}:
        raise ValueError(
            "Phase-2 hood.fun current promotion coverage-run binding drift"
        )
    manual_inputs = sorted(
        str(value)
        for value in promotion.get("remaining_manual_inputs") or []
    )
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    if manual_inputs != expected_manual:
        raise ValueError(
            "Phase-2 hood.fun current promotion manual-input contract drift"
        )

    return {
        "version": "phase2-post-fanout-stage-v1",
        "auto_node_ids": list(PHASE2_POST_FANOUT_AUTO_NODE_IDS),
        "auto_nodes": auto,
        "auto_nodes_count": len(auto),
        "manual_promotion_node_ids": list(
            PHASE2_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "manual_promotion_inputs": manual_inputs,
        "hood_fun_current_promotion_held_for_operator": True,
        "selector_approval_performed": False,
        "canonical_ledger_write_authorized": False,
        "post_fanout_auto_wave_authorized": True,
    }
