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
PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS = (
    "coverage:doppler",
    "coverage:flap",
    "coverage:pools_trade_instant",
    "derive:pools_trade_lbp_cca",
    "derive:trench_market_evidence",
    "shared:direct_competition_cohort",
    "shared:direct_origin_attribution",
)
PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS = (
    "promote:pools_fun",
)
PHASE2_AFTER_POST_FANOUT_NEXT_AUTO_NODE_IDS = (
    "shared:direct_quality_evidence",
    "shared:direct_launch_population",
    "coverage:pools_trade_lbp",
    "derive:trench_handoff_freeze",
)
PHASE2_AFTER_POST_FANOUT_NEXT_MANUAL_NODE_IDS = (
    "promote:pools_fun",
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



def _post_fanout_commit_sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _post_fanout_artifact_digest(
    value: object,
    *,
    label: str,
) -> str:
    text = str(value or "").lower()
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{label} must be sha256:<64 hex chars>")
    try:
        int(text.split(":", 1)[1], 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _post_fanout_sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} must be 64 hex chars")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _post_fanout_run_map(
    value: object,
    *,
    label: str,
    expected_nodes: tuple[str, ...],
) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    if set(value) != set(expected_nodes):
        raise ValueError(f"{label} node set drift")
    output = {}
    for node_id in expected_nodes:
        run_id = int(value.get(node_id) or 0)
        if run_id <= 0:
            raise ValueError(f"{label} invalid run ID: {node_id}")
        output[node_id] = run_id
    if len(set(output.values())) != len(output):
        raise ValueError(f"{label} reuses a run ID")
    return output


def validate_phase2_post_fanout_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable nine-node wave handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-post-fanout-wave-launch-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 post-fan-out launch receipt version changed"
        )

    control_run_id = int(row.get("post_fanout_control_run_id") or 0)
    completion_run_id = int(
        row.get("archive_fanout_completion_run_id") or 0
    )
    planner_run_id = int(row.get("planner_run_id") or 0)
    if (
        control_run_id <= 0
        or completion_run_id <= 0
        or planner_run_id <= 0
    ):
        raise ValueError(
            "Phase-2 post-fan-out launch receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 post-fan-out launch receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 post-fan-out launch head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 post-fan-out launch coverage ledger",
    )
    completion_digest = _post_fanout_artifact_digest(
        row.get("archive_fanout_completion_artifact_digest"),
        label="Phase-2 archive fan-out completion artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 post-fan-out planner artifact",
    )

    controls = _post_fanout_run_map(
        row.get("node_dispatch_control_run_ids"),
        label="Phase-2 post-fan-out control runs",
        expected_nodes=PHASE2_POST_FANOUT_AUTO_NODE_IDS,
    )
    targets = _post_fanout_run_map(
        row.get("target_run_ids"),
        label="Phase-2 post-fan-out target runs",
        expected_nodes=PHASE2_POST_FANOUT_AUTO_NODE_IDS,
    )
    auto_nodes = row.get("auto_node_ids")
    if (
        not isinstance(auto_nodes, list)
        or sorted(str(value) for value in auto_nodes)
        != sorted(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
    ):
        raise ValueError(
            "Phase-2 post-fan-out launch receipt auto-node drift"
        )
    manual_nodes = row.get("manual_promotion_node_ids")
    if manual_nodes != list(PHASE2_POST_FANOUT_MANUAL_NODE_IDS):
        raise ValueError(
            "Phase-2 post-fan-out launch receipt promotion hold drift"
        )

    if row.get(
        "hood_fun_current_promotion_held_for_operator"
    ) is not True:
        raise ValueError(
            "Phase-2 post-fan-out launch did not hold hood.fun promotion"
        )
    if int(row.get("target_runs_created", -1)) != len(
        PHASE2_POST_FANOUT_AUTO_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 post-fan-out launch target count drift"
        )
    required_false = (
        "target_runs_waited_for_completion",
        "coverage_promotion_performed",
        "selector_approval_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    )
    for field in required_false:
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 post-fan-out launch receipt violates {field}"
            )
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError(
            "Phase-2 post-fan-out launch receipt lacks dispatch proof"
        )

    return {
        "version": "phase2-post-fanout-wave-launch-receipt-v1",
        "post_fanout_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "archive_fanout_completion_run_id": completion_run_id,
        "archive_fanout_completion_artifact_digest": completion_digest,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "node_dispatch_control_run_ids": controls,
        "target_run_ids": targets,
        "auto_node_ids": list(PHASE2_POST_FANOUT_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "hood_fun_current_promotion_held_for_operator": True,
        "target_runs_created": len(targets),
        "target_runs_waited_for_completion": False,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_post_fanout_wave_completion(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze the exact planner boundary after the nine-node wave succeeds."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 post-fan-out completion changed canonical sources"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 post-fan-out completion changed source count"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 post-fan-out completion incomplete count drift"
        )

    expected_completed = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
    )
    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    if not isinstance(completed, list) or not isinstance(ready, list):
        raise ValueError(
            "Phase-2 post-fan-out completion lacks node-state lists"
        )
    if set(completed) != expected_completed:
        raise ValueError(
            "Phase-2 post-fan-out completion node-credit drift"
        )

    expected_ready = set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS) | set(
        PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS
    )
    if set(ready) != expected_ready:
        raise ValueError(
            "Phase-2 after-post-fan-out ready-node set drift: "
            f"{sorted(ready)}"
        )

    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "Phase-2 post-fan-out completion lacks lineage proof"
        )
    receipt_completed = verified.get("completed_node_ids")
    if not isinstance(receipt_completed, list):
        raise ValueError(
            "Phase-2 post-fan-out verified node list is missing"
        )
    if set(receipt_completed) != expected_completed:
        raise ValueError(
            "Phase-2 post-fan-out verified node-credit drift"
        )
    control_ids = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != len(expected_completed)
        or len(set(int(value) for value in control_ids))
        != len(expected_completed)
    ):
        raise ValueError(
            "Phase-2 post-fan-out completion requires exactly 24 "
            "dispatcher control runs"
        )

    if dispatch.get("run_id_inputs_generated_from_verified_receipts") is not True:
        raise ValueError(
            "Phase-2 after-post-fan-out dispatch plan lacks verified inputs"
        )
    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError(
            "Phase-2 after-post-fan-out dispatch rows are missing"
        )
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != expected_ready:
        raise ValueError(
            "Phase-2 after-post-fan-out dispatch row set drift"
        )

    auto_rows = []
    for node_id in PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS:
        row = by_id[node_id]
        if str(row.get("status") or "") != "ready_to_dispatch":
            raise ValueError(
                f"Phase-2 after-post-fan-out auto node not ready: {node_id}"
            )
        if row.get("requires_explicit_approval") is not False:
            raise ValueError(
                f"Phase-2 after-post-fan-out auto node requires approval: "
                f"{node_id}"
            )
        run_inputs = row.get("run_id_inputs")
        if not isinstance(run_inputs, Mapping) or not run_inputs:
            raise ValueError(
                f"Phase-2 after-post-fan-out auto node lacks generated "
                f"run inputs: {node_id}"
            )
        if list(row.get("remaining_manual_inputs") or []):
            raise ValueError(
                f"Phase-2 after-post-fan-out auto node has manual inputs: "
                f"{node_id}"
            )
        if set(str(value) for value in row.get(
            "all_dispatch_input_names"
        ) or []) != set(run_inputs):
            raise ValueError(
                f"Phase-2 after-post-fan-out auto input schema drift: "
                f"{node_id}"
            )
        auto_rows.append({
            "node_id": node_id,
            "workflow": str(row.get("workflow") or ""),
            "run_id_inputs": dict(run_inputs),
        })

    promotion = by_id["promote:pools_fun"]
    if str(promotion.get("status") or "") != "ready_to_dispatch":
        raise ValueError(
            "Phase-2 pools.fun promotion is not ready"
        )
    if str(promotion.get("workflow") or "") != (
        "phase2-source-coverage-promotion.yml"
    ):
        raise ValueError(
            "Phase-2 pools.fun promotion workflow drift"
        )
    if set(dict(promotion.get("run_id_inputs") or {})) != {
        "coverage_run_id"
    }:
        raise ValueError(
            "Phase-2 pools.fun promotion coverage-run binding drift"
        )
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value)
        for value in promotion.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError(
            "Phase-2 pools.fun promotion manual-input contract drift"
        )

    return {
        "version": "phase2-post-fanout-wave-completion-v1",
        "completed_execution_node_ids": sorted(expected_completed),
        "completed_execution_nodes": len(expected_completed),
        "node_dispatch_control_runs_consumed": len(control_ids),
        "auto_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS
        ),
        "auto_nodes": auto_rows,
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "manual_promotion_inputs": actual_manual,
        "pools_fun_promotion_held_for_operator": True,
        "canonical_coverage_sources_unchanged": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_post_fanout_wave_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable handoff after the nine-node wave completes."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-post-fanout-wave-completion-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 post-fan-out completion receipt version changed"
        )

    control_run_id = int(
        row.get("post_fanout_completion_control_run_id") or 0
    )
    launch_run_id = int(
        row.get("post_fanout_wave_launch_run_id") or 0
    )
    planner_run_id = int(row.get("planner_run_id") or 0)
    if min(control_run_id, launch_run_id, planner_run_id) <= 0:
        raise ValueError(
            "Phase-2 post-fan-out completion receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 post-fan-out completion receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 post-fan-out completion head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 post-fan-out completion coverage ledger",
    )
    launch_digest = _post_fanout_artifact_digest(
        row.get("post_fanout_wave_artifact_digest"),
        label="Phase-2 post-fan-out launch artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 post-fan-out completion planner artifact",
    )

    targets = _post_fanout_run_map(
        row.get("verified_target_run_ids"),
        label="Phase-2 post-fan-out verified target runs",
        expected_nodes=PHASE2_POST_FANOUT_AUTO_NODE_IDS,
    )
    control_ids_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(control_ids_raw, list):
        raise ValueError(
            "Phase-2 post-fan-out completion control-run list is missing"
        )
    control_ids = [int(value) for value in control_ids_raw]
    if (
        len(control_ids) != 24
        or len(set(control_ids)) != 24
        or min(control_ids) <= 0
    ):
        raise ValueError(
            "Phase-2 post-fan-out completion requires exactly 24 unique "
            "positive dispatcher control runs"
        )

    auto_nodes = row.get("auto_node_ids")
    if (
        not isinstance(auto_nodes, list)
        or sorted(str(value) for value in auto_nodes)
        != sorted(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
    ):
        raise ValueError(
            "Phase-2 post-fan-out completion auto-node drift"
        )
    manual_nodes = row.get("manual_promotion_node_ids")
    if manual_nodes != list(PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS):
        raise ValueError(
            "Phase-2 post-fan-out completion promotion-hold drift"
        )
    if row.get("pools_fun_promotion_held_for_operator") is not True:
        raise ValueError(
            "Phase-2 post-fan-out completion did not hold pools.fun promotion"
        )

    required_true = (
        "post_fanout_targets_completed_successfully",
        "planner_refreshed",
    )
    for field in required_true:
        if row.get(field) is not True:
            raise ValueError(
                f"Phase-2 post-fan-out completion receipt violates {field}"
            )
    required_false = (
        "coverage_promotion_performed",
        "selector_approval_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    )
    for field in required_false:
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 post-fan-out completion receipt violates {field}"
            )

    return {
        "version": "phase2-post-fanout-wave-completion-receipt-v1",
        "post_fanout_completion_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "post_fanout_wave_launch_run_id": launch_run_id,
        "post_fanout_wave_artifact_digest": launch_digest,
        "verified_target_run_ids": targets,
        "node_dispatch_control_run_ids_consumed": sorted(control_ids),
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "auto_node_ids": list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "post_fanout_targets_completed_successfully": True,
        "planner_refreshed": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_after_post_fanout_wave_completion(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze the exact planner boundary after the seven-node wave succeeds."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 after-post-fan-out completion changed canonical sources"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 after-post-fan-out completion changed source count"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 after-post-fan-out completion incomplete count drift"
        )

    expected_completed = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
    )
    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    if not isinstance(completed, list) or not isinstance(ready, list):
        raise ValueError(
            "Phase-2 after-post-fan-out completion lacks node-state lists"
        )
    if set(completed) != expected_completed:
        raise ValueError(
            "Phase-2 after-post-fan-out completion node-credit drift"
        )

    expected_ready = set(
        PHASE2_AFTER_POST_FANOUT_NEXT_AUTO_NODE_IDS
    ) | set(PHASE2_AFTER_POST_FANOUT_NEXT_MANUAL_NODE_IDS)
    if set(ready) != expected_ready:
        raise ValueError(
            "Phase-2 next-wave ready-node set drift: "
            f"{sorted(ready)}"
        )

    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "Phase-2 after-post-fan-out completion lacks lineage proof"
        )
    receipt_completed = verified.get("completed_node_ids")
    if not isinstance(receipt_completed, list):
        raise ValueError(
            "Phase-2 after-post-fan-out verified node list is missing"
        )
    if set(receipt_completed) != expected_completed:
        raise ValueError(
            "Phase-2 after-post-fan-out verified node-credit drift"
        )
    control_ids = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != len(expected_completed)
        or len(set(int(value) for value in control_ids))
        != len(expected_completed)
    ):
        raise ValueError(
            "Phase-2 after-post-fan-out completion requires exactly 31 "
            "dispatcher control runs"
        )

    if dispatch.get("run_id_inputs_generated_from_verified_receipts") is not True:
        raise ValueError(
            "Phase-2 next-wave dispatch plan lacks verified inputs"
        )
    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError(
            "Phase-2 next-wave dispatch rows are missing"
        )
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != expected_ready:
        raise ValueError(
            "Phase-2 next-wave dispatch row set drift"
        )

    auto_rows = []
    for node_id in PHASE2_AFTER_POST_FANOUT_NEXT_AUTO_NODE_IDS:
        row = by_id[node_id]
        if str(row.get("status") or "") != "ready_to_dispatch":
            raise ValueError(
                f"Phase-2 next-wave auto node not ready: {node_id}"
            )
        if row.get("requires_explicit_approval") is not False:
            raise ValueError(
                f"Phase-2 next-wave auto node requires approval: {node_id}"
            )
        run_inputs = row.get("run_id_inputs")
        if not isinstance(run_inputs, Mapping) or not run_inputs:
            raise ValueError(
                f"Phase-2 next-wave auto node lacks generated run inputs: "
                f"{node_id}"
            )
        if list(row.get("remaining_manual_inputs") or []):
            raise ValueError(
                f"Phase-2 next-wave auto node has manual inputs: {node_id}"
            )
        if set(str(value) for value in row.get(
            "all_dispatch_input_names"
        ) or []) != set(run_inputs):
            raise ValueError(
                f"Phase-2 next-wave auto input schema drift: {node_id}"
            )
        auto_rows.append({
            "node_id": node_id,
            "workflow": str(row.get("workflow") or ""),
            "run_id_inputs": dict(run_inputs),
        })

    promotion = by_id["promote:pools_fun"]
    if str(promotion.get("status") or "") != "ready_to_dispatch":
        raise ValueError(
            "Phase-2 pools.fun promotion is not ready after seven-node wave"
        )
    if str(promotion.get("workflow") or "") != (
        "phase2-source-coverage-promotion.yml"
    ):
        raise ValueError(
            "Phase-2 pools.fun promotion workflow drift after seven-node wave"
        )
    expected_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_manual = sorted(
        str(value)
        for value in promotion.get("remaining_manual_inputs") or []
    )
    if actual_manual != expected_manual:
        raise ValueError(
            "Phase-2 pools.fun promotion manual-input drift after seven-node "
            "wave"
        )

    return {
        "version": "phase2-after-post-fanout-wave-completion-v1",
        "completed_execution_node_ids": sorted(expected_completed),
        "completed_execution_nodes": len(expected_completed),
        "node_dispatch_control_runs_consumed": len(control_ids),
        "auto_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_NEXT_AUTO_NODE_IDS
        ),
        "auto_nodes": auto_rows,
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_NEXT_MANUAL_NODE_IDS
        ),
        "manual_promotion_inputs": actual_manual,
        "pools_fun_promotion_held_for_operator": True,
        "canonical_coverage_sources_unchanged": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_after_post_fanout_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable seven-node wave launch handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-after-post-fanout-wave-launch-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 after-post-fan-out launch receipt version changed"
        )

    control_run_id = int(
        row.get("after_post_fanout_control_run_id") or 0
    )
    completion_run_id = int(
        row.get("post_fanout_wave_completion_run_id") or 0
    )
    planner_run_id = int(row.get("planner_run_id") or 0)
    if min(control_run_id, completion_run_id, planner_run_id) <= 0:
        raise ValueError(
            "Phase-2 after-post-fan-out launch receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 after-post-fan-out launch receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 after-post-fan-out launch head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 after-post-fan-out launch coverage ledger",
    )
    completion_digest = _post_fanout_artifact_digest(
        row.get("post_fanout_wave_completion_artifact_digest"),
        label="Phase-2 post-fan-out completion artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 after-post-fan-out planner artifact",
    )

    controls = _post_fanout_run_map(
        row.get("node_dispatch_control_run_ids"),
        label="Phase-2 after-post-fan-out control runs",
        expected_nodes=PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS,
    )
    targets = _post_fanout_run_map(
        row.get("target_run_ids"),
        label="Phase-2 after-post-fan-out target runs",
        expected_nodes=PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS,
    )
    auto_nodes = row.get("auto_node_ids")
    if (
        not isinstance(auto_nodes, list)
        or sorted(str(value) for value in auto_nodes)
        != sorted(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
    ):
        raise ValueError(
            "Phase-2 after-post-fan-out launch receipt auto-node drift"
        )
    manual_nodes = row.get("manual_promotion_node_ids")
    if manual_nodes != list(PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS):
        raise ValueError(
            "Phase-2 after-post-fan-out launch promotion-hold drift"
        )

    if row.get("pools_fun_promotion_held_for_operator") is not True:
        raise ValueError(
            "Phase-2 after-post-fan-out launch did not hold pools.fun promotion"
        )
    if int(row.get("target_runs_created", -1)) != len(
        PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 after-post-fan-out launch target count drift"
        )
    required_false = (
        "target_runs_waited_for_completion",
        "coverage_promotion_performed",
        "selector_approval_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    )
    for field in required_false:
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 after-post-fan-out launch receipt violates {field}"
            )
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError(
            "Phase-2 after-post-fan-out launch receipt lacks dispatch proof"
        )

    return {
        "version": "phase2-after-post-fanout-wave-launch-receipt-v1",
        "after_post_fanout_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "post_fanout_wave_completion_run_id": completion_run_id,
        "post_fanout_wave_completion_artifact_digest": completion_digest,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "node_dispatch_control_run_ids": controls,
        "target_run_ids": targets,
        "auto_node_ids": list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "target_runs_created": len(targets),
        "target_runs_waited_for_completion": False,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }
