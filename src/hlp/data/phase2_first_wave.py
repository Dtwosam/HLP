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
PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS = (
    "shared:v3_pool_created",
    "shared:v3_initialize",
    "shared:v4_initialize",
    "shared:v3_swap",
    "shared:v4_swap",
    "shared:supply_delta",
    "registry:pools_fun",
    "registry:pools_trade_launcher",
    "registry:flap",
    "registry:trench",
    "coverage:hood_fun_current",
    "derive:hood_fun_previous_semantics",
    "registry:noxa",
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

    completed = execution.get("completed_node_ids")
    if not isinstance(completed, list):
        raise ValueError(
            "Phase-2 execution plan completed-node list is missing"
        )
    if completed:
        raise ValueError(
            "Phase-2 first wave requires zero credited execution nodes"
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
    if set(by_id) != set(PHASE2_FIRST_WAVE_NODE_IDS):
        raise ValueError(
            "Phase-2 initial dispatch plan must contain exactly the two "
            f"first-wave nodes: {sorted(by_id)}"
        )

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



def validate_phase2_first_wave_completion(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
) -> dict:
    """Prove both initial target runs were credited and fan-out unlocked."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 first-wave completion changed canonical source state"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 first-wave completion unexpectedly changed source count"
        )

    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    if not isinstance(completed, list) or not isinstance(ready, list):
        raise ValueError(
            "Phase-2 first-wave completion plan lacks node-state lists"
        )
    missing_completed = sorted(
        set(PHASE2_FIRST_WAVE_NODE_IDS) - set(completed)
    )
    if missing_completed:
        raise ValueError(
            f"Phase-2 first-wave nodes were not credited: {missing_completed}"
        )
    still_ready = sorted(
        set(PHASE2_FIRST_WAVE_NODE_IDS) & set(ready)
    )
    if still_ready:
        raise ValueError(
            f"Phase-2 credited first-wave nodes remain ready: {still_ready}"
        )

    missing_fanout = sorted(
        set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS) - set(ready)
    )
    if missing_fanout:
        raise ValueError(
            f"Phase-2 first wave did not unlock expected archive fan-out: "
            f"{missing_fanout}"
        )

    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "Phase-2 first-wave receipts lack verified run lineage"
        )
    receipt_completed = verified.get("completed_node_ids")
    if not isinstance(receipt_completed, list):
        raise ValueError(
            "Phase-2 first-wave verified receipt node list is missing"
        )
    missing_receipts = sorted(
        set(PHASE2_FIRST_WAVE_NODE_IDS) - set(receipt_completed)
    )
    if missing_receipts:
        raise ValueError(
            f"Phase-2 first-wave target receipts are missing: "
            f"{missing_receipts}"
        )

    control_ids = verified.get("node_dispatch_run_ids_consumed")
    control_receipts = verified.get("node_dispatch_receipts_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != 2
        or len(set(control_ids)) != 2
    ):
        raise ValueError(
            "Phase-2 first-wave completion requires exactly two "
            "node-dispatch control runs"
        )
    if not isinstance(control_receipts, list):
        raise ValueError(
            "Phase-2 first-wave dispatch receipt list is missing"
        )
    receipt_nodes = sorted(
        str(row.get("node_id") or "")
        for row in control_receipts
        if isinstance(row, Mapping)
    )
    if receipt_nodes != sorted(PHASE2_FIRST_WAVE_NODE_IDS):
        raise ValueError(
            "Phase-2 first-wave dispatch receipts do not match first-wave "
            f"nodes: {receipt_nodes}"
        )

    return {
        "version": "phase2-first-wave-completion-v1",
        "first_wave_node_ids": list(PHASE2_FIRST_WAVE_NODE_IDS),
        "node_dispatch_control_run_ids": sorted(
            int(value) for value in control_ids
        ),
        "expected_archive_fanout_node_ids": list(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ),
        "first_wave_targets_credited": True,
        "archive_fanout_unlocked": True,
        "canonical_coverage_sources_unchanged": True,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_archive_fanout_launch(
    execution_plan: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Validate the exact post-first-wave zero-input archive fan-out."""

    execution = dict(execution_plan)
    dispatch = dict(dispatch_plan)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 archive fan-out requires the exact Pons-only "
            "canonical completion set"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 archive fan-out requires exactly 2 complete sources"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 archive fan-out requires exactly 12 incomplete sources"
        )
    if execution.get("phase2_universe_coverage_complete") is not False:
        raise ValueError(
            "Phase-2 archive fan-out must precede universe completion"
        )

    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    if not isinstance(completed, list) or not isinstance(ready, list):
        raise ValueError(
            "Phase-2 archive fan-out plan lacks node-state lists"
        )
    if sorted(completed) != sorted(PHASE2_FIRST_WAVE_NODE_IDS):
        raise ValueError(
            "Phase-2 archive fan-out requires exactly the two credited "
            f"first-wave nodes: {sorted(completed)}"
        )
    if sorted(ready) != sorted(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS):
        raise ValueError(
            "Phase-2 archive fan-out ready-node set drift: "
            f"{sorted(ready)}"
        )

    if dispatch.get("run_id_inputs_generated_from_verified_receipts") is not True:
        raise ValueError(
            "Phase-2 archive fan-out lacks verified dependency run inputs"
        )
    if dispatch.get("non_run_inputs_left_explicit") is not True:
        raise ValueError(
            "Phase-2 archive fan-out hides unresolved manual inputs"
        )
    if dispatch.get("workflow_dispatch_performed") is not False:
        raise ValueError(
            "Phase-2 archive fan-out dispatch plan already claims dispatch"
        )
    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError("Phase-2 archive fan-out dispatch rows are missing")
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS):
        raise ValueError(
            "Phase-2 archive fan-out dispatch plan must contain exactly the "
            f"13 expected nodes: {sorted(by_id)}"
        )

    validated = []
    for node_id in PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS:
        row = by_id[node_id]
        if str(row.get("status") or "") != "ready_to_dispatch":
            raise ValueError(
                f"Phase-2 archive fan-out node is not ready: {node_id}"
            )
        if row.get("requires_explicit_approval") is not False:
            raise ValueError(
                f"Phase-2 archive fan-out node requires approval: {node_id}"
            )
        if row.get("requires_archive_secret") is not True:
            raise ValueError(
                f"Phase-2 archive fan-out node lost archive-secret gate: "
                f"{node_id}"
            )
        if dict(row.get("run_id_inputs") or {}):
            raise ValueError(
                f"Phase-2 archive fan-out node unexpectedly has run inputs: "
                f"{node_id}"
            )
        if list(row.get("remaining_manual_inputs") or []):
            raise ValueError(
                f"Phase-2 archive fan-out node unexpectedly has manual "
                f"inputs: {node_id}"
            )
        if list(row.get("all_dispatch_input_names") or []):
            raise ValueError(
                f"Phase-2 archive fan-out target workflow unexpectedly has "
                f"dispatch inputs: {node_id}"
            )
        workflow = str(row.get("workflow") or "")
        if not workflow.endswith(".yml"):
            raise ValueError(
                f"Phase-2 archive fan-out workflow identity invalid: "
                f"{node_id}"
            )
        validated.append({
            "node_id": node_id,
            "workflow": workflow,
            "requires_archive_secret": True,
        })

    return {
        "version": "phase2-archive-fanout-launch-v1",
        "complete_sources": 2,
        "incomplete_sources": 12,
        "credited_first_wave_node_ids": list(PHASE2_FIRST_WAVE_NODE_IDS),
        "archive_fanout_node_ids": list(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ),
        "archive_fanout_nodes": validated,
        "fanout_nodes": len(validated),
        "manual_inputs_required": False,
        "approval_gated_nodes_present": False,
        "canonical_ledger_write_authorized": False,
        "archive_fanout_launch_authorized": True,
    }
