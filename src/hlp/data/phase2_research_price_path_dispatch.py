"""Orchestration contracts for the Phase-2 canonical research price path."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase2_research_materialization_dispatch import (
    validate_phase2_research_materialization_freeze_completion_receipt,
)


PHASE2_RESEARCH_PRICE_PATH_LAUNCH_VERSION = (
    "phase2-research-price-path-launch-receipt-v1"
)
PHASE2_RESEARCH_PRICE_PATH_COMPLETION_VERSION = (
    "phase2-research-price-path-completion-receipt-v1"
)
PRICE_PATH_WORKFLOW = "phase2-research-price-path.yml"


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


def validate_phase2_research_price_path_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the single-run price-path dispatch receipt."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_RESEARCH_PRICE_PATH_LAUNCH_VERSION
    ):
        raise ValueError("research price-path launch version changed")
    control = _positive_run_id(
        row.get("price_path_control_run_id"),
        label="price-path control run ID",
    )
    completion_run = _positive_run_id(
        row.get("materialization_freeze_completion_run_id"),
        label="materialization-freeze completion run ID",
    )
    completion_digest = _artifact_digest(
        row.get("materialization_freeze_completion_artifact_digest"),
        label="materialization-freeze completion artifact",
    )
    target_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="price-path target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="price-path launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="price-path launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("price-path launch branch/HEAD drift")

    materialization_run = _positive_run_id(
        row.get("materialization_freeze_run_id"),
        label="price-path materialization-freeze run ID",
    )
    materialization_digest = _artifact_digest(
        row.get("materialization_freeze_artifact_digest"),
        label="price-path materialization-freeze artifact",
    )
    bundle_sha = _sha256(
        row.get("materialization_bundle_sha256"),
        label="price-path materialization bundle",
    )
    materialization_handoff_sha = _sha256(
        row.get("materialization_handoff_sha256"),
        label="price-path materialization handoff",
    )
    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="price-path universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="price-path universe artifact",
    )
    universe_handoff_sha = _sha256(
        row.get("universe_handoff_sha256"),
        label="price-path universe handoff",
    )

    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("price-path target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("price-path launcher unexpectedly waited")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("price-path launch lacks dispatch proof")

    return {
        **row,
        "price_path_control_run_id": control,
        "materialization_freeze_completion_run_id": completion_run,
        "materialization_freeze_completion_artifact_digest": (
            completion_digest
        ),
        "price_path_run_id": target_run,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "materialization_freeze_run_id": materialization_run,
        "materialization_freeze_artifact_digest": materialization_digest,
        "materialization_bundle_sha256": bundle_sha,
        "materialization_handoff_sha256": materialization_handoff_sha,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff_sha,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_research_price_path_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate immutable canonical price-path evidence for dump geometry."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_RESEARCH_PRICE_PATH_COMPLETION_VERSION
    ):
        raise ValueError("research price-path completion version changed")
    control = _positive_run_id(
        row.get("price_path_completion_control_run_id"),
        label="price-path completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("price_path_launch_run_id"),
        label="price-path launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("price_path_launch_artifact_digest"),
        label="price-path launch artifact",
    )
    target_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="completed price-path run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="price-path artifact",
    )
    handoff_sha = _sha256(
        row.get("price_path_handoff_sha256"),
        label="price-path handoff",
    )
    path_sha = _sha256(
        row.get("normalized_price_path_sha256"),
        label="normalized price path",
    )
    report_sha = _sha256(
        row.get("price_path_report_sha256"),
        label="price-path report",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="price-path completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="price-path completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("price-path completion branch/HEAD drift")

    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="price-path completion universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="price-path completion universe artifact",
    )
    universe_handoff_sha = _sha256(
        row.get("universe_handoff_sha256"),
        label="price-path completion universe handoff",
    )
    snapshot = int(row.get("snapshot_head_block", 0))
    if snapshot <= 0:
        raise ValueError("price-path completion snapshot is invalid")
    eligible_tokens = int(row.get("eligible_tokens", -1))
    price_points = int(row.get("price_points", -1))
    if eligible_tokens < 0 or price_points < 0:
        raise ValueError("price-path completion counts are invalid")

    geometry_inputs = {
        "price_path_run_id": str(target_run),
        "expected_price_path_artifact_digest": artifact_digest,
        "expected_price_path_handoff_sha256": handoff_sha,
        "universe_run_id": str(universe_run),
        "expected_universe_artifact_digest": universe_digest,
        "expected_universe_handoff_sha256": universe_handoff_sha,
    }
    if row.get("geometry_inputs") != geometry_inputs:
        raise ValueError("dump-geometry input binding drift")
    if row.get("target_run_completed") is not True:
        raise ValueError("price-path target run is not completed")
    if row.get("target_run_successful") is not True:
        raise ValueError("price-path target run is not successful")
    if row.get("research_price_path_ready") is not True:
        raise ValueError("price-path completion lacks path-ready proof")
    if row.get("dump_threshold_frozen") is not False:
        raise ValueError("price-path completion freezes dump threshold")
    if row.get("phase2_dump_detector_frozen") is not False:
        raise ValueError("price-path completion freezes detector")
    if row.get("outcome_labels_computed") is not False:
        raise ValueError("price-path completion contains outcomes")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("price-path completion unexpectedly dispatches")

    return {
        **row,
        "price_path_completion_control_run_id": control,
        "price_path_launch_run_id": launch_run,
        "price_path_launch_artifact_digest": launch_digest,
        "price_path_run_id": target_run,
        "price_path_artifact_digest": artifact_digest,
        "price_path_handoff_sha256": handoff_sha,
        "normalized_price_path_sha256": path_sha,
        "price_path_report_sha256": report_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff_sha,
        "snapshot_head_block": snapshot,
        "eligible_tokens": eligible_tokens,
        "price_points": price_points,
        "geometry_inputs": geometry_inputs,
        "target_run_completed": True,
        "target_run_successful": True,
        "research_price_path_ready": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def build_price_path_launch_receipt(
    materialization_completion: Mapping[str, object],
    *,
    control_run_id: int,
    completion_run_id: int,
    completion_artifact_digest: str,
    price_path_run_id: int,
) -> dict:
    """Create a validated launch receipt from the materialization checkpoint."""

    materialization = (
        validate_phase2_research_materialization_freeze_completion_receipt(
            materialization_completion
        )
    )
    return validate_phase2_research_price_path_launch_receipt({
        "version": PHASE2_RESEARCH_PRICE_PATH_LAUNCH_VERSION,
        "price_path_control_run_id": control_run_id,
        "materialization_freeze_completion_run_id": completion_run_id,
        "materialization_freeze_completion_artifact_digest": (
            completion_artifact_digest
        ),
        "price_path_run_id": price_path_run_id,
        "execution_branch": materialization["execution_branch"],
        "execution_head_sha": materialization["execution_head_sha"],
        "canonical_ledger_commit_sha": materialization[
            "canonical_ledger_commit_sha"
        ],
        "materialization_freeze_run_id": materialization[
            "materialization_freeze_run_id"
        ],
        "materialization_freeze_artifact_digest": materialization[
            "materialization_freeze_artifact_digest"
        ],
        "materialization_bundle_sha256": materialization[
            "materialization_bundle_sha256"
        ],
        "materialization_handoff_sha256": materialization[
            "materialization_handoff_sha256"
        ],
        "universe_run_id": materialization["universe_run_id"],
        "universe_artifact_digest": materialization[
            "universe_artifact_digest"
        ],
        "universe_handoff_sha256": materialization[
            "universe_handoff_sha256"
        ],
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "workflow_dispatch_performed": True,
    })
