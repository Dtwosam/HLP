"""Orchestration contracts for Phase-2 continuous outcome labels."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase2_dump_detector_dispatch import (
    validate_phase2_dump_detector_freeze_completion_receipt,
)


PHASE2_OUTCOME_LABEL_LAUNCH_VERSION = (
    "phase2-outcome-labels-launch-receipt-v1"
)
PHASE2_OUTCOME_LABEL_COMPLETION_VERSION = (
    "phase2-outcome-labels-completion-receipt-v1"
)
OUTCOME_WORKFLOW = "phase2-outcome-labels.yml"


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


def validate_phase2_outcome_label_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_OUTCOME_LABEL_LAUNCH_VERSION:
        raise ValueError("outcome-label launch version changed")
    control = _positive_run_id(
        row.get("outcome_label_control_run_id"),
        label="outcome-label control run ID",
    )
    completion_run = _positive_run_id(
        row.get("detector_freeze_completion_run_id"),
        label="outcome-label detector completion run ID",
    )
    completion_digest = _artifact_digest(
        row.get("detector_freeze_completion_artifact_digest"),
        label="outcome-label detector completion artifact",
    )
    target = _positive_run_id(
        row.get("outcome_label_run_id"),
        label="outcome-label target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="outcome-label launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="outcome-label launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("outcome-label launch branch/HEAD drift")
    detector_run = _positive_run_id(
        row.get("detector_freeze_run_id"),
        label="outcome-label detector run ID",
    )
    detector_digest = _artifact_digest(
        row.get("detector_freeze_artifact_digest"),
        label="outcome-label detector artifact",
    )
    detector_handoff = _sha256(
        row.get("detector_freeze_handoff_sha256"),
        label="outcome-label detector handoff",
    )
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="outcome-label price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="outcome-label price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="outcome-label price-path handoff",
    )
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("outcome-label launch target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("outcome-label launcher unexpectedly waited")
    if row.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("outcome-label launch lacks frozen detector proof")
    if row.get("outcome_labels_computed") is not False:
        raise ValueError("outcome-label launch claims labels early")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("outcome-label launch lacks dispatch proof")
    return {
        **row,
        "outcome_label_control_run_id": control,
        "detector_freeze_completion_run_id": completion_run,
        "detector_freeze_completion_artifact_digest": completion_digest,
        "outcome_label_run_id": target,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "detector_freeze_run_id": detector_run,
        "detector_freeze_artifact_digest": detector_digest,
        "detector_freeze_handoff_sha256": detector_handoff,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_outcome_label_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_OUTCOME_LABEL_COMPLETION_VERSION
    ):
        raise ValueError("outcome-label completion version changed")
    control = _positive_run_id(
        row.get("outcome_label_completion_control_run_id"),
        label="outcome-label completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("outcome_label_launch_run_id"),
        label="outcome-label launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("outcome_label_launch_artifact_digest"),
        label="outcome-label launch artifact",
    )
    target = _positive_run_id(
        row.get("outcome_label_run_id"),
        label="completed outcome-label run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("outcome_artifact_digest"),
        label="outcome-label artifact",
    )
    handoff_artifact_digest = _artifact_digest(
        row.get("outcome_handoff_artifact_digest"),
        label="outcome-label handoff artifact",
    )
    rows_sha = _sha256(
        row.get("outcome_rows_sha256"),
        label="outcome-label rows",
    )
    summary_sha = _sha256(
        row.get("outcome_summary_sha256"),
        label="outcome-label summary",
    )
    handoff_sha = _sha256(
        row.get("outcome_handoff_sha256"),
        label="outcome-label handoff",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="outcome-label completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="outcome-label completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("outcome-label completion branch/HEAD drift")
    detector_run = _positive_run_id(
        row.get("detector_freeze_run_id"),
        label="outcome-label completion detector run ID",
    )
    detector_digest = _artifact_digest(
        row.get("detector_freeze_artifact_digest"),
        label="outcome-label completion detector artifact",
    )
    detector_handoff = _sha256(
        row.get("detector_freeze_handoff_sha256"),
        label="outcome-label completion detector handoff",
    )
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="outcome-label completion price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="outcome-label completion price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="outcome-label completion price-path handoff",
    )
    tokens = int(row.get("tokens", -1))
    confirmed = int(row.get("confirmed_dump_tokens", -1))
    comeback = int(row.get("comeback_5x_tokens", -1))
    if tokens <= 0 or confirmed < 0 or comeback < 0:
        raise ValueError("outcome-label completion counts are invalid")
    if confirmed > tokens or comeback > confirmed:
        raise ValueError("outcome-label completion count hierarchy drift")
    if row.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("outcome-label completion lost detector freeze")
    if row.get("outcome_labels_computed") is not True:
        raise ValueError("outcome-label completion lacks label proof")
    if row.get("max_post_dump_multiple_retained") is not True:
        raise ValueError("outcome-label completion lost continuous target")
    if row.get("target_run_completed") is not True:
        raise ValueError("outcome-label target is not completed")
    if row.get("target_run_successful") is not True:
        raise ValueError("outcome-label target is not successful")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("outcome-label completion dispatches workflow")
    return {
        **row,
        "outcome_label_completion_control_run_id": control,
        "outcome_label_launch_run_id": launch_run,
        "outcome_label_launch_artifact_digest": launch_digest,
        "outcome_label_run_id": target,
        "outcome_artifact_digest": artifact_digest,
        "outcome_handoff_artifact_digest": handoff_artifact_digest,
        "outcome_rows_sha256": rows_sha,
        "outcome_summary_sha256": summary_sha,
        "outcome_handoff_sha256": handoff_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "detector_freeze_run_id": detector_run,
        "detector_freeze_artifact_digest": detector_digest,
        "detector_freeze_handoff_sha256": detector_handoff,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "tokens": tokens,
        "confirmed_dump_tokens": confirmed,
        "comeback_5x_tokens": comeback,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "max_post_dump_multiple_retained": True,
        "target_run_completed": True,
        "target_run_successful": True,
        "workflow_dispatch_performed": False,
    }
