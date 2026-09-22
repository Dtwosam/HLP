"""Validation contracts for the Phase-2 archive fan-out lifecycle."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase2_first_wave import (
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
    PHASE2_INITIAL_COMPLETE_SOURCE_IDS,
)


PHASE2_ARCHIVE_FANOUT_RECEIPT_VERSION = (
    "phase2-archive-fanout-launch-receipt-v1"
)
PHASE2_ARCHIVE_FANOUT_COMPLETION_VERSION = (
    "phase2-archive-fanout-completion-v1"
)


def _commit_sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _artifact_digest(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{label} must be sha256:<64 hex chars>")
    try:
        int(text.split(":", 1)[1], 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} must be 64 hex chars")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _run_map(
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
            raise ValueError(f"{label} has invalid run ID for {node_id}")
        output[node_id] = run_id
    if len(set(output.values())) != len(output):
        raise ValueError(f"{label} reuses a run ID")
    return output


def validate_phase2_archive_fanout_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable handoff from fan-out launch to completion."""

    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_ARCHIVE_FANOUT_RECEIPT_VERSION:
        raise ValueError("Phase-2 archive fan-out receipt version changed")

    control_run_id = int(
        row.get("archive_fanout_control_run_id") or 0
    )
    first_wave_run_id = int(row.get("first_wave_launch_run_id") or 0)
    planner_run_id = int(row.get("planner_run_id") or 0)
    if control_run_id <= 0 or first_wave_run_id <= 0 or planner_run_id <= 0:
        raise ValueError(
            "Phase-2 archive fan-out receipt run IDs must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Phase-2 archive fan-out receipt branch is empty")
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 archive fan-out execution head",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 archive fan-out coverage ledger",
    )
    first_wave_digest = _artifact_digest(
        row.get("first_wave_artifact_digest"),
        label="Phase-2 archive fan-out first-wave artifact",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 archive fan-out planner artifact",
    )

    controls = _run_map(
        row.get("node_dispatch_control_run_ids"),
        label="Phase-2 archive fan-out control runs",
        expected_nodes=PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    )
    targets = _run_map(
        row.get("target_run_ids"),
        label="Phase-2 archive fan-out target runs",
        expected_nodes=PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    )

    node_ids = row.get("archive_fanout_node_ids")
    if (
        not isinstance(node_ids, list)
        or sorted(str(value) for value in node_ids)
        != sorted(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
    ):
        raise ValueError(
            "Phase-2 archive fan-out receipt node list drift"
        )

    contract = row.get("fanout_contract")
    if not isinstance(contract, Mapping):
        raise ValueError(
            "Phase-2 archive fan-out receipt contract is missing"
        )
    if contract.get("archive_fanout_launch_authorized") is not True:
        raise ValueError(
            "Phase-2 archive fan-out receipt lacks launch authorization"
        )
    if int(row.get("target_runs_created", -1)) != len(
        PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
    ):
        raise ValueError(
            "Phase-2 archive fan-out receipt target count drift"
        )

    required_true = ("workflow_dispatch_performed",)
    for field in required_true:
        if row.get(field) is not True:
            raise ValueError(
                f"Phase-2 archive fan-out receipt lacks {field}"
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
                f"Phase-2 archive fan-out receipt violates {field}"
            )

    return {
        "version": PHASE2_ARCHIVE_FANOUT_RECEIPT_VERSION,
        "archive_fanout_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "first_wave_launch_run_id": first_wave_run_id,
        "first_wave_artifact_digest": first_wave_digest,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "node_dispatch_control_run_ids": controls,
        "target_run_ids": targets,
        "archive_fanout_node_ids": list(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ),
        "target_runs_created": len(targets),
        "target_runs_waited_for_completion": False,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_archive_fanout_completion(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
) -> dict:
    """Validate the planner produced after all 13 archive targets succeed."""

    execution = dict(execution_plan)
    verified = dict(verified_receipts)

    if execution.get("canonical_complete_source_ids") != list(
        PHASE2_INITIAL_COMPLETE_SOURCE_IDS
    ):
        raise ValueError(
            "Phase-2 archive fan-out completion changed canonical sources"
        )
    if int(execution.get("complete_sources", -1)) != 2:
        raise ValueError(
            "Phase-2 archive fan-out completion changed source count"
        )
    if int(execution.get("incomplete_sources", -1)) != 12:
        raise ValueError(
            "Phase-2 archive fan-out completion incomplete count drift"
        )

    expected_completed = set(PHASE2_FIRST_WAVE_NODE_IDS) | set(
        PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
    )
    completed = execution.get("completed_node_ids")
    if not isinstance(completed, list):
        raise ValueError(
            "Phase-2 archive fan-out completion lacks completed nodes"
        )
    if set(completed) != expected_completed:
        raise ValueError(
            "Phase-2 archive fan-out completion node-credit drift: "
            f"{sorted(completed)}"
        )

    if verified.get("all_runs_current_or_ledger_only_ancestors") is not True:
        raise ValueError(
            "Phase-2 archive fan-out completion lacks lineage proof"
        )
    receipt_completed = verified.get("completed_node_ids")
    if not isinstance(receipt_completed, list):
        raise ValueError(
            "Phase-2 archive fan-out verified node list is missing"
        )
    if set(receipt_completed) != expected_completed:
        raise ValueError(
            "Phase-2 archive fan-out verified node-credit drift"
        )

    control_ids = verified.get("node_dispatch_run_ids_consumed")
    control_receipts = verified.get("node_dispatch_receipts_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != len(expected_completed)
        or len(set(control_ids)) != len(expected_completed)
    ):
        raise ValueError(
            "Phase-2 archive fan-out completion requires exactly 15 "
            "dispatcher control runs"
        )
    if not isinstance(control_receipts, list):
        raise ValueError(
            "Phase-2 archive fan-out completion receipt list is missing"
        )
    receipt_nodes = {
        str(row.get("node_id") or "")
        for row in control_receipts
        if isinstance(row, Mapping)
    }
    if receipt_nodes != expected_completed:
        raise ValueError(
            "Phase-2 archive fan-out completion receipt-node drift"
        )

    ready = execution.get("ready_to_dispatch_node_ids")
    if not isinstance(ready, list):
        raise ValueError(
            "Phase-2 archive fan-out completion ready-node list is missing"
        )
    still_ready = sorted(expected_completed & set(ready))
    if still_ready:
        raise ValueError(
            "Phase-2 completed archive nodes remain ready: "
            f"{still_ready}"
        )
    if not ready:
        raise ValueError(
            "Phase-2 archive fan-out completion unlocked no next-stage nodes"
        )

    return {
        "version": PHASE2_ARCHIVE_FANOUT_COMPLETION_VERSION,
        "completed_execution_node_ids": sorted(expected_completed),
        "completed_execution_nodes": len(expected_completed),
        "node_dispatch_control_runs_consumed": len(control_ids),
        "next_ready_node_ids": list(ready),
        "next_ready_nodes": len(ready),
        "archive_fanout_targets_credited": True,
        "canonical_coverage_sources_unchanged": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_ledger_write_authorized": False,
    }



def validate_phase2_archive_fanout_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the immutable handoff into the post-fan-out DAG stage."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        "phase2-archive-fanout-completion-receipt-v1"
    ):
        raise ValueError(
            "Phase-2 archive fan-out completion receipt version changed"
        )

    control_run_id = int(
        row.get("archive_fanout_completion_control_run_id") or 0
    )
    fanout_run_id = int(row.get("archive_fanout_launch_run_id") or 0)
    planner_run_id = int(row.get("planner_run_id") or 0)
    if control_run_id <= 0 or fanout_run_id <= 0 or planner_run_id <= 0:
        raise ValueError(
            "Phase-2 archive fan-out completion receipt run IDs "
            "must be positive"
        )

    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError(
            "Phase-2 archive fan-out completion receipt branch is empty"
        )
    head_sha = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 archive fan-out completion head",
    )
    ledger_sha = _sha256(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 archive fan-out completion coverage ledger",
    )
    fanout_digest = _artifact_digest(
        row.get("archive_fanout_artifact_digest"),
        label="Phase-2 archive fan-out launch artifact",
    )
    planner_digest = _artifact_digest(
        row.get("planner_artifact_digest"),
        label="Phase-2 post-fan-out planner artifact",
    )

    targets = _run_map(
        row.get("verified_target_run_ids"),
        label="Phase-2 archive fan-out verified targets",
        expected_nodes=PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    )
    control_ids = row.get("node_dispatch_control_run_ids_consumed")
    if (
        not isinstance(control_ids, list)
        or len(control_ids) != 15
        or len(set(int(value) for value in control_ids)) != 15
    ):
        raise ValueError(
            "Phase-2 archive fan-out completion receipt requires exactly "
            "15 dispatcher control runs"
        )
    normalized_controls = sorted(int(value) for value in control_ids)
    if normalized_controls[0] <= 0:
        raise ValueError(
            "Phase-2 archive fan-out completion control run ID is invalid"
        )

    next_ready = row.get("next_ready_node_ids")
    if not isinstance(next_ready, list) or not next_ready:
        raise ValueError(
            "Phase-2 archive fan-out completion receipt has no next-ready set"
        )
    normalized_ready = [str(value) for value in next_ready]
    if len(normalized_ready) != len(set(normalized_ready)):
        raise ValueError(
            "Phase-2 archive fan-out completion receipt repeats next-ready "
            "node"
        )

    contract = row.get("completion_contract")
    if not isinstance(contract, Mapping):
        raise ValueError(
            "Phase-2 archive fan-out completion contract is missing"
        )
    if contract.get("archive_fanout_targets_credited") is not True:
        raise ValueError(
            "Phase-2 archive fan-out completion lacks target-credit proof"
        )
    if contract.get("canonical_coverage_sources_unchanged") is not True:
        raise ValueError(
            "Phase-2 archive fan-out completion changed canonical sources"
        )

    required_true = (
        "archive_fanout_targets_completed_successfully",
        "planner_refreshed",
    )
    for field in required_true:
        if row.get(field) is not True:
            raise ValueError(
                f"Phase-2 archive fan-out completion receipt lacks {field}"
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
                "Phase-2 archive fan-out completion receipt violates "
                f"{field}"
            )

    return {
        "version": "phase2-archive-fanout-completion-receipt-v1",
        "archive_fanout_completion_control_run_id": control_run_id,
        "execution_branch": branch,
        "execution_head_sha": head_sha,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "archive_fanout_launch_run_id": fanout_run_id,
        "archive_fanout_artifact_digest": fanout_digest,
        "verified_target_run_ids": targets,
        "node_dispatch_control_run_ids_consumed": normalized_controls,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": planner_digest,
        "next_ready_node_ids": normalized_ready,
        "archive_fanout_targets_completed_successfully": True,
        "planner_refreshed": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }
