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
PHASE2_PRE_SELECTOR_AUTO_NODE_IDS = (
    "shared:direct_quality_evidence",
    "shared:direct_launch_population",
    "coverage:pools_trade_lbp",
    "derive:trench_handoff_freeze",
)
PHASE2_PRE_SELECTOR_MANUAL_NODE_IDS = (
    "promote:pools_fun",
)
PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS = (
    "coverage:trench_today",
)
PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS = (
    "promote:pools_fun",
)
PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS = (
    "shared:direct_selector_freeze",
)
PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS = (
    "shared:direct_source_population",
    "coverage:trench_today",
)
PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS = (
    "promote:pools_fun",
)
PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS = (
    "coverage:direct_uniswap_v3",
    "coverage:direct_sushiswap_v3",
    "coverage:direct_uniswap_v4",
)
PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS = (
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



def validate_phase2_after_post_fanout_wave_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable handoff after the seven-node wave completes."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-after-post-fanout-wave-completion-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 seven-node completion receipt version changed"
        )

    control_run_id = int(
        row.get("after_post_fanout_completion_control_run_id") or 0
    )
    launch_run_id = int(
        row.get("after_post_fanout_wave_launch_run_id") or 0
    )
    planner_run_id = int(row.get("planner_run_id") or 0)
    if min(control_run_id, launch_run_id, planner_run_id) <= 0:
        raise ValueError(
            "Phase-2 seven-node completion receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 seven-node completion receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 seven-node completion head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 seven-node completion coverage ledger",
    )
    launch_digest = _post_fanout_artifact_digest(
        row.get("after_post_fanout_wave_artifact_digest"),
        label="Phase-2 seven-node launch artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 seven-node completion planner artifact",
    )

    targets = _post_fanout_run_map(
        row.get("verified_target_run_ids"),
        label="Phase-2 seven-node verified target runs",
        expected_nodes=PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS,
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError(
            "Phase-2 seven-node completion control-run list is missing"
        )
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 31
        or len(set(controls)) != 31
        or min(controls) <= 0
    ):
        raise ValueError(
            "Phase-2 seven-node completion requires exactly 31 unique "
            "positive dispatcher control runs"
        )

    auto_nodes = row.get("auto_node_ids")
    if (
        not isinstance(auto_nodes, list)
        or sorted(str(value) for value in auto_nodes)
        != sorted(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
    ):
        raise ValueError(
            "Phase-2 seven-node completion pre-selector auto-node drift"
        )
    manual_nodes = row.get("manual_promotion_node_ids")
    if manual_nodes != list(PHASE2_PRE_SELECTOR_MANUAL_NODE_IDS):
        raise ValueError(
            "Phase-2 seven-node completion promotion-hold drift"
        )
    if row.get("pools_fun_promotion_held_for_operator") is not True:
        raise ValueError(
            "Phase-2 seven-node completion did not hold pools.fun promotion"
        )

    for field in (
        "after_post_fanout_targets_completed_successfully",
        "planner_refreshed",
    ):
        if row.get(field) is not True:
            raise ValueError(
                f"Phase-2 seven-node completion receipt violates {field}"
            )
    for field in (
        "coverage_promotion_performed",
        "selector_approval_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 seven-node completion receipt violates {field}"
            )

    return {
        "version": "phase2-after-post-fanout-wave-completion-receipt-v1",
        "after_post_fanout_completion_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "after_post_fanout_wave_launch_run_id": launch_run_id,
        "after_post_fanout_wave_artifact_digest": launch_digest,
        "verified_target_run_ids": targets,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "auto_node_ids": list(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_PRE_SELECTOR_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "after_post_fanout_targets_completed_successfully": True,
        "planner_refreshed": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def validate_phase2_pre_selector_wave_completion(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze the exact planner boundary immediately before selector approval."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 pre-selector completion changed canonical sources"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 pre-selector completion changed source count"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 pre-selector completion incomplete count drift"
        )

    expected_completed = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
    )
    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    approval = execution.get("awaiting_explicit_approval_node_ids")
    if (
        not isinstance(completed, list)
        or not isinstance(ready, list)
        or not isinstance(approval, list)
    ):
        raise ValueError(
            "Phase-2 pre-selector completion lacks node-state lists"
        )
    if set(completed) != expected_completed:
        raise ValueError(
            "Phase-2 pre-selector completion node-credit drift"
        )
    expected_ready = set(PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS) | set(
        PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS
    )
    if set(ready) != expected_ready:
        raise ValueError(
            "Phase-2 pre-selector ready-node set drift: "
            f"{sorted(ready)}"
        )
    if set(approval) != set(PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS):
        raise ValueError(
            "Phase-2 pre-selector approval-node set drift: "
            f"{sorted(approval)}"
        )

    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "Phase-2 pre-selector completion lacks lineage proof"
        )
    receipt_completed = verified.get("completed_node_ids")
    if not isinstance(receipt_completed, list):
        raise ValueError(
            "Phase-2 pre-selector verified node list is missing"
        )
    if set(receipt_completed) != expected_completed:
        raise ValueError(
            "Phase-2 pre-selector verified node-credit drift"
        )
    control_ids = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != 35
        or len(set(int(value) for value in control_ids)) != 35
    ):
        raise ValueError(
            "Phase-2 pre-selector completion requires exactly 35 "
            "dispatcher control runs"
        )

    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError(
            "Phase-2 pre-selector dispatch rows are missing"
        )
    expected_rows = (
        set(PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS)
        | set(PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS)
    )
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != expected_rows:
        raise ValueError(
            "Phase-2 pre-selector dispatch row set drift"
        )

    trench = by_id["coverage:trench_today"]
    if str(trench.get("status") or "") != "ready_to_dispatch":
        raise ValueError("Phase-2 trench coverage is not ready")
    trench_inputs = trench.get("run_id_inputs")
    if not isinstance(trench_inputs, Mapping) or not trench_inputs:
        raise ValueError(
            "Phase-2 trench coverage lacks generated run inputs"
        )
    if list(trench.get("remaining_manual_inputs") or []):
        raise ValueError(
            "Phase-2 trench coverage unexpectedly has manual inputs"
        )

    promotion = by_id["promote:pools_fun"]
    if str(promotion.get("status") or "") != "ready_to_dispatch":
        raise ValueError("Phase-2 pools.fun promotion is not ready")
    expected_promotion_manual = sorted([
        "coverage_artifact_name",
        "coverage_report_path",
        "expected_artifact_digest",
        "expected_report_sha256",
        "expected_source_id",
    ])
    actual_promotion_manual = sorted(
        str(value)
        for value in promotion.get("remaining_manual_inputs") or []
    )
    if actual_promotion_manual != expected_promotion_manual:
        raise ValueError(
            "Phase-2 pools.fun promotion manual-input drift"
        )

    selector = by_id["shared:direct_selector_freeze"]
    if str(selector.get("status") or "") != "awaiting_explicit_approval":
        raise ValueError(
            "Phase-2 direct selector is not awaiting explicit approval"
        )
    if selector.get("requires_explicit_approval") is not True:
        raise ValueError(
            "Phase-2 direct selector lost explicit-approval gate"
        )
    if set(dict(selector.get("run_id_inputs") or {})) != {
        "evidence_run_id"
    }:
        raise ValueError(
            "Phase-2 direct selector evidence-run binding drift"
        )
    expected_selector_manual = sorted([
        "expected_artifact_digest",
        "expected_handoff_sha256",
        "freeze_active_quote_liquidity_causal_v1",
    ])
    actual_selector_manual = sorted(
        str(value)
        for value in selector.get("remaining_manual_inputs") or []
    )
    if actual_selector_manual != expected_selector_manual:
        raise ValueError(
            "Phase-2 direct selector manual-input contract drift"
        )

    return {
        "version": "phase2-pre-selector-wave-completion-v1",
        "completed_execution_node_ids": sorted(expected_completed),
        "completed_execution_nodes": len(expected_completed),
        "node_dispatch_control_runs_consumed": len(control_ids),
        "auto_node_ids": list(PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS
        ),
        "approval_node_ids": list(
            PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS
        ),
        "selector_manual_inputs": actual_selector_manual,
        "pools_fun_promotion_held_for_operator": True,
        "selector_approval_performed": False,
        "coverage_promotion_performed": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_pre_selector_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable four-node pre-selector launch handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-pre-selector-wave-launch-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 pre-selector launch receipt version changed"
        )

    control_run_id = int(row.get("pre_selector_control_run_id") or 0)
    completion_run_id = int(
        row.get("after_post_fanout_wave_completion_run_id") or 0
    )
    planner_run_id = int(row.get("planner_run_id") or 0)
    if min(control_run_id, completion_run_id, planner_run_id) <= 0:
        raise ValueError(
            "Phase-2 pre-selector launch receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 pre-selector launch receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 pre-selector launch head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 pre-selector launch coverage ledger",
    )
    completion_digest = _post_fanout_artifact_digest(
        row.get("after_post_fanout_wave_completion_artifact_digest"),
        label="Phase-2 seven-node completion artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 pre-selector planner artifact",
    )

    controls = _post_fanout_run_map(
        row.get("node_dispatch_control_run_ids"),
        label="Phase-2 pre-selector control runs",
        expected_nodes=PHASE2_PRE_SELECTOR_AUTO_NODE_IDS,
    )
    targets = _post_fanout_run_map(
        row.get("target_run_ids"),
        label="Phase-2 pre-selector target runs",
        expected_nodes=PHASE2_PRE_SELECTOR_AUTO_NODE_IDS,
    )
    auto_nodes = row.get("auto_node_ids")
    if (
        not isinstance(auto_nodes, list)
        or sorted(str(value) for value in auto_nodes)
        != sorted(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
    ):
        raise ValueError(
            "Phase-2 pre-selector launch receipt auto-node drift"
        )
    manual_nodes = row.get("manual_promotion_node_ids")
    if manual_nodes != list(PHASE2_PRE_SELECTOR_MANUAL_NODE_IDS):
        raise ValueError(
            "Phase-2 pre-selector launch promotion-hold drift"
        )
    if row.get("pools_fun_promotion_held_for_operator") is not True:
        raise ValueError(
            "Phase-2 pre-selector launch did not hold pools.fun promotion"
        )
    if int(row.get("target_runs_created", -1)) != len(
        PHASE2_PRE_SELECTOR_AUTO_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 pre-selector launch target count drift"
        )

    for field in (
        "target_runs_waited_for_completion",
        "coverage_promotion_performed",
        "selector_approval_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 pre-selector launch receipt violates {field}"
            )
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError(
            "Phase-2 pre-selector launch receipt lacks dispatch proof"
        )

    return {
        "version": "phase2-pre-selector-wave-launch-receipt-v1",
        "pre_selector_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "after_post_fanout_wave_completion_run_id": completion_run_id,
        "after_post_fanout_wave_completion_artifact_digest": (
            completion_digest
        ),
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "node_dispatch_control_run_ids": controls,
        "target_run_ids": targets,
        "auto_node_ids": list(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_PRE_SELECTOR_MANUAL_NODE_IDS
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



def validate_phase2_pre_selector_wave_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable handoff at the selector approval boundary."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-pre-selector-wave-completion-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 pre-selector completion receipt version changed"
        )

    control_run_id = int(
        row.get("pre_selector_completion_control_run_id") or 0
    )
    launch_run_id = int(row.get("pre_selector_wave_launch_run_id") or 0)
    planner_run_id = int(row.get("planner_run_id") or 0)
    if min(control_run_id, launch_run_id, planner_run_id) <= 0:
        raise ValueError(
            "Phase-2 pre-selector completion receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 pre-selector completion receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 pre-selector completion head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 pre-selector completion coverage ledger",
    )
    launch_digest = _post_fanout_artifact_digest(
        row.get("pre_selector_wave_artifact_digest"),
        label="Phase-2 pre-selector launch artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 pre-selector completion planner artifact",
    )

    targets = _post_fanout_run_map(
        row.get("verified_target_run_ids"),
        label="Phase-2 pre-selector verified target runs",
        expected_nodes=PHASE2_PRE_SELECTOR_AUTO_NODE_IDS,
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError(
            "Phase-2 pre-selector completion control-run list is missing"
        )
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 35
        or len(set(controls)) != 35
        or min(controls) <= 0
    ):
        raise ValueError(
            "Phase-2 pre-selector completion requires exactly 35 unique "
            "positive dispatcher control runs"
        )

    auto_nodes = row.get("auto_node_ids")
    if auto_nodes != list(PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS):
        raise ValueError(
            "Phase-2 pre-selector completion auto-node drift"
        )
    manual_nodes = row.get("manual_promotion_node_ids")
    if manual_nodes != list(PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS):
        raise ValueError(
            "Phase-2 pre-selector completion promotion-hold drift"
        )
    approval_nodes = row.get("approval_node_ids")
    if approval_nodes != list(PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS):
        raise ValueError(
            "Phase-2 pre-selector completion approval-node drift"
        )
    expected_selector_manual = sorted([
        "expected_artifact_digest",
        "expected_handoff_sha256",
        "freeze_active_quote_liquidity_causal_v1",
    ])
    actual_selector_manual = sorted(
        str(value)
        for value in row.get("selector_manual_inputs") or []
    )
    if actual_selector_manual != expected_selector_manual:
        raise ValueError(
            "Phase-2 pre-selector completion selector-input drift"
        )
    if row.get("pools_fun_promotion_held_for_operator") is not True:
        raise ValueError(
            "Phase-2 pre-selector completion did not hold pools.fun promotion"
        )

    for field in (
        "pre_selector_targets_completed_successfully",
        "planner_refreshed",
    ):
        if row.get(field) is not True:
            raise ValueError(
                f"Phase-2 pre-selector completion receipt violates {field}"
            )
    for field in (
        "coverage_promotion_performed",
        "selector_approval_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 pre-selector completion receipt violates {field}"
            )

    return {
        "version": "phase2-pre-selector-wave-completion-receipt-v1",
        "pre_selector_completion_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "pre_selector_wave_launch_run_id": launch_run_id,
        "pre_selector_wave_artifact_digest": launch_digest,
        "verified_target_run_ids": targets,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "auto_node_ids": list(PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS
        ),
        "approval_node_ids": list(
            PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS
        ),
        "selector_manual_inputs": actual_selector_manual,
        "pools_fun_promotion_held_for_operator": True,
        "pre_selector_targets_completed_successfully": True,
        "planner_refreshed": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_selector_freeze_completion(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze the exact planner boundary after approved selector freeze."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 selector freeze completion changed canonical sources"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 selector freeze completion changed source count"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 selector freeze completion incomplete count drift"
        )

    expected_completed = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        | {"shared:direct_selector_freeze"}
    )
    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    approval = execution.get("awaiting_explicit_approval_node_ids")
    if (
        not isinstance(completed, list)
        or not isinstance(ready, list)
        or not isinstance(approval, list)
    ):
        raise ValueError(
            "Phase-2 selector freeze completion lacks node-state lists"
        )
    if set(completed) != expected_completed:
        raise ValueError(
            "Phase-2 selector freeze completion node-credit drift"
        )
    expected_ready = set(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS) | set(
        PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS
    )
    if set(ready) != expected_ready:
        raise ValueError(
            "Phase-2 post-selector ready-node set drift: "
            f"{sorted(ready)}"
        )
    if approval:
        raise ValueError(
            "Phase-2 selector approval node remains after approved freeze"
        )

    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "Phase-2 selector freeze completion lacks lineage proof"
        )
    receipt_completed = verified.get("completed_node_ids")
    if not isinstance(receipt_completed, list):
        raise ValueError(
            "Phase-2 selector freeze verified node list is missing"
        )
    if set(receipt_completed) != expected_completed:
        raise ValueError(
            "Phase-2 selector freeze verified node-credit drift"
        )
    control_ids = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != 35
        or len(set(int(value) for value in control_ids)) != 35
    ):
        raise ValueError(
            "Phase-2 selector freeze completion requires exactly 35 "
            "dispatcher control runs"
        )

    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError(
            "Phase-2 post-selector dispatch rows are missing"
        )
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != expected_ready:
        raise ValueError(
            "Phase-2 post-selector dispatch row set drift"
        )

    auto_rows = []
    for node_id in PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS:
        row = by_id[node_id]
        if str(row.get("status") or "") != "ready_to_dispatch":
            raise ValueError(
                f"Phase-2 post-selector auto node not ready: {node_id}"
            )
        if row.get("requires_explicit_approval") is not False:
            raise ValueError(
                f"Phase-2 post-selector auto node requires approval: {node_id}"
            )
        run_inputs = row.get("run_id_inputs")
        if not isinstance(run_inputs, Mapping) or not run_inputs:
            raise ValueError(
                f"Phase-2 post-selector auto node lacks generated run inputs: "
                f"{node_id}"
            )
        if list(row.get("remaining_manual_inputs") or []):
            raise ValueError(
                f"Phase-2 post-selector auto node has manual inputs: {node_id}"
            )
        if set(str(value) for value in row.get(
            "all_dispatch_input_names"
        ) or []) != set(run_inputs):
            raise ValueError(
                f"Phase-2 post-selector auto input schema drift: {node_id}"
            )
        auto_rows.append({
            "node_id": node_id,
            "workflow": str(row.get("workflow") or ""),
            "run_id_inputs": dict(run_inputs),
        })

    promotion = by_id["promote:pools_fun"]
    if str(promotion.get("status") or "") != "ready_to_dispatch":
        raise ValueError(
            "Phase-2 pools.fun promotion is not ready after selector freeze"
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
            "Phase-2 pools.fun promotion manual-input drift after selector"
        )

    return {
        "version": "phase2-selector-freeze-completion-v1",
        "completed_execution_node_ids": sorted(expected_completed),
        "completed_execution_nodes": len(expected_completed),
        "node_dispatch_control_runs_consumed": len(control_ids),
        "auto_node_ids": list(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS),
        "auto_nodes": auto_rows,
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS
        ),
        "manual_promotion_inputs": actual_manual,
        "pools_fun_promotion_held_for_operator": True,
        "selector_approval_performed": True,
        "selector_freeze_completed": True,
        "canonical_coverage_sources_unchanged": True,
        "coverage_promotion_performed": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_post_selector_wave_completion(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    dispatch_plan: Mapping[str, object],
) -> dict:
    """Freeze the planner boundary after the two post-selector nodes succeed."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)
    dispatch = dict(dispatch_plan)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 post-selector completion changed canonical sources"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 post-selector completion changed source count"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 post-selector completion incomplete count drift"
        )

    expected_completed = (
        set(PHASE2_FIRST_WAVE_NODE_IDS)
        | set(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        | set(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        | set(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        | {"shared:direct_selector_freeze"}
        | set(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS)
    )
    completed = execution.get("completed_node_ids")
    ready = execution.get("ready_to_dispatch_node_ids")
    approval = execution.get("awaiting_explicit_approval_node_ids")
    if (
        not isinstance(completed, list)
        or not isinstance(ready, list)
        or not isinstance(approval, list)
    ):
        raise ValueError(
            "Phase-2 post-selector completion lacks node-state lists"
        )
    if set(completed) != expected_completed:
        raise ValueError(
            "Phase-2 post-selector completion node-credit drift"
        )
    expected_ready = set(PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS) | set(
        PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS
    )
    if set(ready) != expected_ready:
        raise ValueError(
            "Phase-2 direct-coverage ready-node set drift: "
            f"{sorted(ready)}"
        )
    if approval:
        raise ValueError(
            "Phase-2 post-selector completion unexpectedly has approvals"
        )

    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "Phase-2 post-selector completion lacks lineage proof"
        )
    receipt_completed = verified.get("completed_node_ids")
    if not isinstance(receipt_completed, list):
        raise ValueError(
            "Phase-2 post-selector verified node list is missing"
        )
    if set(receipt_completed) != expected_completed:
        raise ValueError(
            "Phase-2 post-selector verified node-credit drift"
        )
    control_ids = verified.get("node_dispatch_run_ids_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != 37
        or len(set(int(value) for value in control_ids)) != 37
    ):
        raise ValueError(
            "Phase-2 post-selector completion requires exactly 37 "
            "dispatcher control runs"
        )

    rows = dispatch.get("nodes")
    if not isinstance(rows, list):
        raise ValueError(
            "Phase-2 direct-coverage dispatch rows are missing"
        )
    by_id = {
        str(row.get("node_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(by_id) != expected_ready:
        raise ValueError(
            "Phase-2 direct-coverage dispatch row set drift"
        )

    auto_rows = []
    for node_id in PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS:
        row = by_id[node_id]
        if str(row.get("status") or "") != "ready_to_dispatch":
            raise ValueError(
                f"Phase-2 direct coverage node not ready: {node_id}"
            )
        if row.get("requires_explicit_approval") is not False:
            raise ValueError(
                f"Phase-2 direct coverage node requires approval: {node_id}"
            )
        run_inputs = row.get("run_id_inputs")
        if not isinstance(run_inputs, Mapping) or not run_inputs:
            raise ValueError(
                f"Phase-2 direct coverage node lacks generated run inputs: "
                f"{node_id}"
            )
        if list(row.get("remaining_manual_inputs") or []):
            raise ValueError(
                f"Phase-2 direct coverage node has manual inputs: {node_id}"
            )
        if set(str(value) for value in row.get(
            "all_dispatch_input_names"
        ) or []) != set(run_inputs):
            raise ValueError(
                f"Phase-2 direct coverage input schema drift: {node_id}"
            )
        auto_rows.append({
            "node_id": node_id,
            "workflow": str(row.get("workflow") or ""),
            "run_id_inputs": dict(run_inputs),
        })

    promotion = by_id["promote:pools_fun"]
    if str(promotion.get("status") or "") != "ready_to_dispatch":
        raise ValueError(
            "Phase-2 pools.fun promotion is not ready after post-selector wave"
        )

    return {
        "version": "phase2-post-selector-wave-completion-v1",
        "completed_execution_node_ids": sorted(expected_completed),
        "completed_execution_nodes": len(expected_completed),
        "node_dispatch_control_runs_consumed": len(control_ids),
        "auto_node_ids": list(PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS),
        "auto_nodes": auto_rows,
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "selector_approval_performed": True,
        "selector_freeze_completed": True,
        "canonical_coverage_sources_unchanged": True,
        "coverage_promotion_performed": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_post_selector_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable two-node post-selector launch handoff."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-post-selector-wave-launch-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 post-selector launch receipt version changed"
        )

    control_run_id = int(row.get("post_selector_control_run_id") or 0)
    freeze_run_id = int(row.get("approved_freeze_run_id") or 0)
    selector_run_id = int(row.get("selector_run_id") or 0)
    planner_run_id = int(row.get("planner_run_id") or 0)
    if min(
        control_run_id,
        freeze_run_id,
        selector_run_id,
        planner_run_id,
    ) <= 0:
        raise ValueError(
            "Phase-2 post-selector launch receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 post-selector launch receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 post-selector launch head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 post-selector launch coverage ledger",
    )
    freeze_digest = _post_fanout_artifact_digest(
        row.get("approved_freeze_artifact_digest"),
        label="Phase-2 approved selector freeze artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 post-selector planner artifact",
    )
    controls = _post_fanout_run_map(
        row.get("node_dispatch_control_run_ids"),
        label="Phase-2 post-selector control runs",
        expected_nodes=PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS,
    )
    targets = _post_fanout_run_map(
        row.get("target_run_ids"),
        label="Phase-2 post-selector target runs",
        expected_nodes=PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS,
    )

    if row.get("auto_node_ids") != list(
        PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 post-selector launch auto-node drift"
        )
    if row.get("manual_promotion_node_ids") != list(
        PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 post-selector launch promotion-hold drift"
        )
    if row.get("pools_fun_promotion_held_for_operator") is not True:
        raise ValueError(
            "Phase-2 post-selector launch did not hold pools.fun promotion"
        )
    if int(row.get("target_runs_created", -1)) != len(
        PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 post-selector launch target count drift"
        )
    if row.get("target_runs_waited_for_completion") is not False:
        raise ValueError(
            "Phase-2 post-selector launch unexpectedly waited for targets"
        )
    if row.get("selector_approval_performed") is not True:
        raise ValueError(
            "Phase-2 post-selector launch lost selector approval proof"
        )
    if row.get("selector_freeze_completed") is not True:
        raise ValueError(
            "Phase-2 post-selector launch lost selector freeze proof"
        )
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError(
            "Phase-2 post-selector launch lacks workflow-dispatch proof"
        )
    for field in (
        "coverage_promotion_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 post-selector launch receipt violates {field}"
            )

    return {
        "version": "phase2-post-selector-wave-launch-receipt-v1",
        "post_selector_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "approved_freeze_run_id": freeze_run_id,
        "approved_freeze_artifact_digest": freeze_digest,
        "selector_run_id": selector_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "node_dispatch_control_run_ids": controls,
        "target_run_ids": targets,
        "auto_node_ids": list(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "target_runs_created": len(targets),
        "target_runs_waited_for_completion": False,
        "selector_approval_performed": True,
        "selector_freeze_completed": True,
        "coverage_promotion_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }



def validate_phase2_post_selector_wave_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable handoff before the direct coverage wave."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-post-selector-wave-completion-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 post-selector completion receipt version changed"
        )

    control_run_id = int(
        row.get("post_selector_completion_control_run_id") or 0
    )
    launch_run_id = int(row.get("post_selector_wave_launch_run_id") or 0)
    freeze_run_id = int(row.get("approved_freeze_run_id") or 0)
    selector_run_id = int(row.get("selector_run_id") or 0)
    planner_run_id = int(row.get("planner_run_id") or 0)
    if min(
        control_run_id,
        launch_run_id,
        freeze_run_id,
        selector_run_id,
        planner_run_id,
    ) <= 0:
        raise ValueError(
            "Phase-2 post-selector completion receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 post-selector completion receipt branch is empty"
        )
    head_sha = _post_fanout_commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 post-selector completion head",
    )
    ledger_sha = _post_fanout_sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 post-selector completion coverage ledger",
    )
    launch_digest = _post_fanout_artifact_digest(
        row.get("post_selector_wave_artifact_digest"),
        label="Phase-2 post-selector launch artifact",
    )
    planner_digest = _post_fanout_artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 direct-coverage planner artifact",
    )

    targets = _post_fanout_run_map(
        row.get("verified_target_run_ids"),
        label="Phase-2 post-selector verified target runs",
        expected_nodes=PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS,
    )
    controls_raw = row.get("node_dispatch_control_run_ids_consumed")
    if not isinstance(controls_raw, list):
        raise ValueError(
            "Phase-2 post-selector completion control-run list is missing"
        )
    controls = [int(value) for value in controls_raw]
    if (
        len(controls) != 37
        or len(set(controls)) != 37
        or min(controls) <= 0
    ):
        raise ValueError(
            "Phase-2 post-selector completion requires exactly 37 unique "
            "positive dispatcher control runs"
        )

    if row.get("auto_node_ids") != list(
        PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 post-selector completion auto-node drift"
        )
    if row.get("manual_promotion_node_ids") != list(
        PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 post-selector completion promotion-hold drift"
        )
    if row.get("pools_fun_promotion_held_for_operator") is not True:
        raise ValueError(
            "Phase-2 post-selector completion did not hold pools.fun promotion"
        )
    for field in (
        "post_selector_targets_completed_successfully",
        "planner_refreshed",
        "selector_approval_performed",
        "selector_freeze_completed",
    ):
        if row.get(field) is not True:
            raise ValueError(
                f"Phase-2 post-selector completion receipt violates {field}"
            )
    for field in (
        "coverage_promotion_performed",
        "canonical_coverage_ledger_mutated",
        "canonical_ledger_write_authorized",
    ):
        if row.get(field) is not False:
            raise ValueError(
                f"Phase-2 post-selector completion receipt violates {field}"
            )

    return {
        "version": "phase2-post-selector-wave-completion-receipt-v1",
        "post_selector_completion_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "post_selector_wave_launch_run_id": launch_run_id,
        "post_selector_wave_artifact_digest": launch_digest,
        "approved_freeze_run_id": freeze_run_id,
        "selector_run_id": selector_run_id,
        "verified_target_run_ids": targets,
        "node_dispatch_control_run_ids_consumed": sorted(controls),
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "auto_node_ids": list(
            PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS
        ),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "post_selector_targets_completed_successfully": True,
        "planner_refreshed": True,
        "selector_approval_performed": True,
        "selector_freeze_completed": True,
        "coverage_promotion_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }
