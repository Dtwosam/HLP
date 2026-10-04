"""Orchestration contracts for Phase-2 outcome-blind dump geometry research."""

from __future__ import annotations

from typing import Mapping


PHASE2_DUMP_GEOMETRY_LAUNCH_VERSION = (
    "phase2-dump-geometry-launch-receipt-v1"
)
PHASE2_DUMP_GEOMETRY_COMPLETION_VERSION = (
    "phase2-dump-geometry-completion-receipt-v1"
)
GEOMETRY_WORKFLOW = "phase2-dump-geometry-research.yml"
CANDIDATE_WORKFLOW = "phase2-dump-candidate-research.yml"


def _positive_run_id(value: object, *, label: str) -> int:
    run_id = int(value or 0)
    if run_id <= 0:
        raise ValueError(f"{label} must be positive")
    return run_id


def _artifact_digest(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("sha256:") or len(text) != 71:
        raise ValueError(f"{label} must use sha256:<64 hex chars>")
    try:
        int(text.removeprefix("sha256:"), 16)
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


def _commit_sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def validate_phase2_dump_geometry_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_DUMP_GEOMETRY_LAUNCH_VERSION:
        raise ValueError("dump-geometry launch version changed")
    control = _positive_run_id(
        row.get("dump_geometry_control_run_id"),
        label="dump-geometry control run ID",
    )
    completion_run = _positive_run_id(
        row.get("price_path_completion_run_id"),
        label="dump-geometry price-path completion run ID",
    )
    completion_digest = _artifact_digest(
        row.get("price_path_completion_artifact_digest"),
        label="dump-geometry price-path completion artifact",
    )
    target = _positive_run_id(
        row.get("dump_geometry_run_id"),
        label="dump-geometry target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="dump-geometry launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="dump-geometry launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("dump-geometry launch branch/HEAD drift")
    price_path_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="dump-geometry price-path run ID",
    )
    price_path_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="dump-geometry price-path artifact",
    )
    price_path_handoff_sha = _sha256(
        row.get("price_path_handoff_sha256"),
        label="dump-geometry price-path handoff",
    )
    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="dump-geometry universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="dump-geometry universe artifact",
    )
    universe_handoff_sha = _sha256(
        row.get("universe_handoff_sha256"),
        label="dump-geometry universe handoff",
    )
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("dump-geometry target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("dump-geometry launcher unexpectedly waited")
    if row.get("candidate_selected") is not False:
        raise ValueError("dump-geometry launcher selects a candidate")
    if row.get("dump_threshold_frozen") is not False:
        raise ValueError("dump-geometry launcher freezes a threshold")
    if row.get("phase2_dump_detector_frozen") is not False:
        raise ValueError("dump-geometry launcher freezes detector")
    if row.get("outcome_labels_computed") is not False:
        raise ValueError("dump-geometry launcher contains outcome labels")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("dump-geometry launch lacks dispatch proof")
    return {
        **row,
        "dump_geometry_control_run_id": control,
        "price_path_completion_run_id": completion_run,
        "price_path_completion_artifact_digest": completion_digest,
        "dump_geometry_run_id": target,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "price_path_run_id": price_path_run,
        "price_path_artifact_digest": price_path_digest,
        "price_path_handoff_sha256": price_path_handoff_sha,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff_sha,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_dump_geometry_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_GEOMETRY_COMPLETION_VERSION
    ):
        raise ValueError("dump-geometry completion version changed")
    control = _positive_run_id(
        row.get("dump_geometry_completion_control_run_id"),
        label="dump-geometry completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("dump_geometry_launch_run_id"),
        label="dump-geometry launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("dump_geometry_launch_artifact_digest"),
        label="dump-geometry launch artifact",
    )
    target = _positive_run_id(
        row.get("dump_geometry_run_id"),
        label="completed dump-geometry run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("dump_geometry_artifact_digest"),
        label="dump-geometry artifact",
    )
    handoff_artifact_digest = _artifact_digest(
        row.get("dump_geometry_handoff_artifact_digest"),
        label="dump-geometry handoff artifact",
    )
    geometry_sha = _sha256(
        row.get("geometry_sha256"),
        label="dump-geometry tape",
    )
    summary_sha = _sha256(
        row.get("geometry_summary_sha256"),
        label="dump-geometry summary",
    )
    handoff_sha = _sha256(
        row.get("geometry_handoff_sha256"),
        label="dump-geometry handoff",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="dump-geometry completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="dump-geometry completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("dump-geometry completion branch/HEAD drift")
    price_path_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="dump-geometry completion price-path run ID",
    )
    price_path_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="dump-geometry completion price-path artifact",
    )
    price_path_handoff_sha = _sha256(
        row.get("price_path_handoff_sha256"),
        label="dump-geometry completion price-path handoff",
    )
    snapshot = int(row.get("snapshot_head_block", 0))
    tokens = int(row.get("tokens", -1))
    price_points = int(row.get("price_points", -1))
    if snapshot <= 0 or tokens <= 0 or price_points <= 0:
        raise ValueError("dump-geometry dimensions are invalid")
    candidate_base_inputs = {
        "geometry_run_id": str(target),
        "expected_geometry_artifact_digest": artifact_digest,
        "expected_geometry_handoff_sha256": handoff_sha,
    }
    if row.get("candidate_research_base_inputs") != candidate_base_inputs:
        raise ValueError("dump-candidate base-input binding drift")
    if row.get("target_run_completed") is not True:
        raise ValueError("dump-geometry target is not completed")
    if row.get("target_run_successful") is not True:
        raise ValueError("dump-geometry target is not successful")
    if row.get("uses_price_path_only") is not True:
        raise ValueError("dump-geometry is not price-path only")
    if row.get("dump_geometry_ready") is not True:
        raise ValueError("dump-geometry completion lacks ready proof")
    if row.get("candidate_selected") is not False:
        raise ValueError("dump-geometry completion selects candidate")
    if row.get("dump_threshold_frozen") is not False:
        raise ValueError("dump-geometry completion freezes threshold")
    if row.get("phase2_dump_detector_frozen") is not False:
        raise ValueError("dump-geometry completion freezes detector")
    if row.get("outcome_labels_computed") is not False:
        raise ValueError("dump-geometry completion contains outcomes")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("dump-geometry completion dispatches workflow")
    return {
        **row,
        "dump_geometry_completion_control_run_id": control,
        "dump_geometry_launch_run_id": launch_run,
        "dump_geometry_launch_artifact_digest": launch_digest,
        "dump_geometry_run_id": target,
        "dump_geometry_artifact_digest": artifact_digest,
        "dump_geometry_handoff_artifact_digest": handoff_artifact_digest,
        "geometry_sha256": geometry_sha,
        "geometry_summary_sha256": summary_sha,
        "geometry_handoff_sha256": handoff_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "price_path_run_id": price_path_run,
        "price_path_artifact_digest": price_path_digest,
        "price_path_handoff_sha256": price_path_handoff_sha,
        "snapshot_head_block": snapshot,
        "tokens": tokens,
        "price_points": price_points,
        "candidate_research_base_inputs": candidate_base_inputs,
        "target_run_completed": True,
        "target_run_successful": True,
        "uses_price_path_only": True,
        "dump_geometry_ready": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }
