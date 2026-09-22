"""Fail-closed validation for the initial Phase-2 execution wave."""

from __future__ import annotations

from typing import Mapping


PHASE2_FIRST_WAVE_LAUNCH_VERSION = "phase2-first-wave-launch-v1"
PHASE2_FIRST_WAVE_NODE_IDS = (
    "preflight:archive_authenticated",
    "shared:quote_registry",
)
PHASE2_INITIAL_COMPLETE_SOURCE_IDS = (
    "pons_v1",
    "pons_v2",
)


def validate_phase2_first_wave_launch(
    execution_plan: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Validate the exact initial 2/14 planner state before launching work."""

    execution = dict(execution_plan)
    dispatch = dict(dispatch_plan)

    complete_ids = execution.get("canonical_complete_source_ids")
    if complete_ids != list(PHASE2_INITIAL_COMPLETE_SOURCE_IDS):
        raise ValueError(
            "Phase-2 first wave requires the exact Pons-only canonical "
            f"completion set: {list(PHASE2_INITIAL_COMPLETE_SOURCE_IDS)}"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError("Phase-2 first wave requires exactly 2 complete sources")
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 first wave requires exactly 12 incomplete sources"
        )
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "Phase-2 first wave must precede universe coverage completion"
        )

    ready = execution.get("ready_to_dispatch_node_ids")
    if not isinstance(ready, list):
        raise ValueError("Phase-2 execution plan ready-node list is missing")
    missing_ready = sorted(set(PHASE2_FIRST_WAVE_NODE_IDS) - set(ready))
    if missing_ready:
        raise ValueError(
            f"Phase-2 first-wave nodes are not ready: {missing_ready}"
        )

    if dispatch.get("run_id_inputs_generated_from_verified_receipts") is not True:
        raise ValueError(
            "Phase-2 dispatch plan lacks verified dependency run inputs"
        )
    if dispatch.get("non_run_inputs_left_explicit") is not True:
        raise ValueError(
            "Phase-2 dispatch plan hides unresolved manual inputs"
        )
    if dispatch.get("workflow_dispatch_performed") is not False:
        raise ValueError(
            "Phase-2 dispatch plan already claims workflow dispatch"
        )
    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError("Phase-2 dispatch plan nodes are missing")
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }

    validated = []
    for node_id in PHASE2_FIRST_WAVE_NODE_IDS:
        row = by_id.get(node_id)
        if row is None:
            raise ValueError(
                f"Phase-2 dispatch plan lacks first-wave node: {node_id}"
            )
        if str(row.get("status") or "") != "ready_to_dispatch":
            raise ValueError(
                f"Phase-2 first-wave node is not ready_to_dispatch: {node_id}"
            )
        if row.get("requires_explicit_approval") is not False:
            raise ValueError(
                f"Phase-2 first-wave node unexpectedly requires approval: "
                f"{node_id}"
            )
        if dict(row.get("run_id_inputs") or {}):
            raise ValueError(
                f"Phase-2 first-wave node unexpectedly has run inputs: "
                f"{node_id}"
            )
        if list(row.get("remaining_manual_inputs") or []):
            raise ValueError(
                f"Phase-2 first-wave node unexpectedly has manual inputs: "
                f"{node_id}"
            )
        if list(row.get("all_dispatch_input_names") or []):
            raise ValueError(
                f"Phase-2 first-wave target workflow unexpectedly has "
                f"dispatch inputs: {node_id}"
            )
        validated.append({
            "node_id": node_id,
            "workflow": str(row.get("workflow") or ""),
            "requires_archive_secret": bool(
                row.get("requires_archive_secret")
            ),
        })

    expected_secret = {
        "preflight:archive_authenticated": True,
        "shared:quote_registry": False,
    }
    for row in validated:
        if row["requires_archive_secret"] is not expected_secret[
            row["node_id"]
        ]:
            raise ValueError(
                "Phase-2 first-wave archive-secret contract drift: "
                f"{row['node_id']}"
            )

    return {
        "version": PHASE2_FIRST_WAVE_LAUNCH_VERSION,
        "complete_sources": 2,
        "incomplete_sources": 12,
        "canonical_complete_source_ids": list(
            PHASE2_INITIAL_COMPLETE_SOURCE_IDS
        ),
        "first_wave_node_ids": list(PHASE2_FIRST_WAVE_NODE_IDS),
        "first_wave_nodes": validated,
        "archive_preflight_required": True,
        "manual_inputs_required": False,
        "approval_gated_nodes_present": False,
        "canonical_ledger_write_authorized": False,
        "first_wave_launch_authorized": True,
    }
