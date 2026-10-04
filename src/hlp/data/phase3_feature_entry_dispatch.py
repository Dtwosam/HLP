"""Phase-3 feature-entry orchestration from the immutable Phase-2 checkpoint."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase2_dataset_dispatch import (
    validate_phase2_dataset_completion_receipt,
)


PHASE3_FEATURE_ENTRY_PLAN_VERSION = "phase3-feature-entry-plan-v1"
PHASE3_FEATURE_ENTRY_LAUNCH_VERSION = (
    "phase3-feature-entry-launch-receipt-v1"
)
PHASE3_FEATURE_ENTRY_COMPLETION_VERSION = (
    "phase3-feature-entry-completion-receipt-v1"
)
FEATURE_ENTRY_WORKFLOW = "phase3-feature-entry.yml"


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


def build_phase3_feature_entry_plan(
    phase2_completion: Mapping[str, object],
) -> dict:
    checkpoint = validate_phase2_dataset_completion_receipt(
        phase2_completion
    )
    inputs = {
        "phase2_dataset_run_id": str(checkpoint["dataset_run_id"]),
        "expected_phase2_handoff_artifact_digest": checkpoint[
            "dataset_handoff_artifact_digest"
        ],
        "expected_phase2_handoff_sha256": checkpoint[
            "dataset_handoff_sha256"
        ],
        "universe_run_id": str(checkpoint["universe_run_id"]),
        "expected_universe_artifact_digest": checkpoint[
            "universe_artifact_digest"
        ],
        "expected_universe_handoff_sha256": checkpoint[
            "universe_handoff_sha256"
        ],
        "detector_freeze_run_id": str(
            checkpoint["detector_freeze_run_id"]
        ),
        "expected_detector_artifact_digest": checkpoint[
            "detector_freeze_artifact_digest"
        ],
        "expected_detector_handoff_sha256": checkpoint[
            "detector_freeze_handoff_sha256"
        ],
    }
    return {
        "version": PHASE3_FEATURE_ENTRY_PLAN_VERSION,
        "workflow": FEATURE_ENTRY_WORKFLOW,
        "execution_branch": checkpoint["execution_branch"],
        "execution_head_sha": checkpoint["execution_head_sha"],
        "canonical_ledger_commit_sha": checkpoint[
            "canonical_ledger_commit_sha"
        ],
        "phase2_dataset_completion_control_run_id": checkpoint[
            "dataset_completion_control_run_id"
        ],
        "phase2_dataset_run_id": checkpoint["dataset_run_id"],
        "phase2_dataset_handoff_artifact_digest": checkpoint[
            "dataset_handoff_artifact_digest"
        ],
        "phase2_dataset_handoff_sha256": checkpoint[
            "dataset_handoff_sha256"
        ],
        "universe_run_id": checkpoint["universe_run_id"],
        "universe_artifact_digest": checkpoint[
            "universe_artifact_digest"
        ],
        "universe_handoff_sha256": checkpoint[
            "universe_handoff_sha256"
        ],
        "detector_freeze_run_id": checkpoint[
            "detector_freeze_run_id"
        ],
        "detector_freeze_artifact_digest": checkpoint[
            "detector_freeze_artifact_digest"
        ],
        "detector_freeze_handoff_sha256": checkpoint[
            "detector_freeze_handoff_sha256"
        ],
        "price_path_run_id": checkpoint["price_path_run_id"],
        "price_path_artifact_digest": checkpoint[
            "price_path_artifact_digest"
        ],
        "price_path_handoff_sha256": checkpoint[
            "price_path_handoff_sha256"
        ],
        "phase2_tokens": int(checkpoint["tokens"]),
        "inputs": inputs,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase3_feature_entry_plan(
    plan: Mapping[str, object],
) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != PHASE3_FEATURE_ENTRY_PLAN_VERSION:
        raise ValueError("Phase-3 feature-entry plan version changed")
    if str(row.get("workflow") or "") != FEATURE_ENTRY_WORKFLOW:
        raise ValueError("Phase-3 feature-entry workflow drift")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 feature-entry execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 feature-entry canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 feature-entry branch/HEAD drift")
    completion_run = _positive_run_id(
        row.get("phase2_dataset_completion_control_run_id"),
        label="Phase-3 Phase-2 completion run ID",
    )
    dataset_run = _positive_run_id(
        row.get("phase2_dataset_run_id"),
        label="Phase-3 dataset run ID",
    )
    dataset_handoff_digest = _artifact_digest(
        row.get("phase2_dataset_handoff_artifact_digest"),
        label="Phase-3 dataset handoff artifact",
    )
    dataset_handoff_sha = _sha256(
        row.get("phase2_dataset_handoff_sha256"),
        label="Phase-3 dataset handoff",
    )
    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="Phase-3 universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="Phase-3 universe artifact",
    )
    universe_handoff = _sha256(
        row.get("universe_handoff_sha256"),
        label="Phase-3 universe handoff",
    )
    detector_run = _positive_run_id(
        row.get("detector_freeze_run_id"),
        label="Phase-3 detector run ID",
    )
    detector_digest = _artifact_digest(
        row.get("detector_freeze_artifact_digest"),
        label="Phase-3 detector artifact",
    )
    detector_handoff = _sha256(
        row.get("detector_freeze_handoff_sha256"),
        label="Phase-3 detector handoff",
    )
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="Phase-3 price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="Phase-3 price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="Phase-3 price-path handoff",
    )
    tokens = int(row.get("phase2_tokens", -1))
    if tokens <= 0:
        raise ValueError("Phase-3 entry token count is invalid")
    expected_inputs = {
        "phase2_dataset_run_id": str(dataset_run),
        "expected_phase2_handoff_artifact_digest": dataset_handoff_digest,
        "expected_phase2_handoff_sha256": dataset_handoff_sha,
        "universe_run_id": str(universe_run),
        "expected_universe_artifact_digest": universe_digest,
        "expected_universe_handoff_sha256": universe_handoff,
        "detector_freeze_run_id": str(detector_run),
        "expected_detector_artifact_digest": detector_digest,
        "expected_detector_handoff_sha256": detector_handoff,
    }
    if row.get("inputs") != expected_inputs:
        raise ValueError("Phase-3 feature-entry input binding drift")
    for field, expected in (
        ("outcome_rows_consumed", False),
        ("outcome_fields_exposed", False),
        ("future_state_allowed", False),
        ("phase3_feature_values_computed", False),
        ("phase3_feature_entry_ready", False),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"Phase-3 feature-entry plan {field} drift")
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "phase2_dataset_completion_control_run_id": completion_run,
        "phase2_dataset_run_id": dataset_run,
        "phase2_dataset_handoff_artifact_digest": dataset_handoff_digest,
        "phase2_dataset_handoff_sha256": dataset_handoff_sha,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff,
        "detector_freeze_run_id": detector_run,
        "detector_freeze_artifact_digest": detector_digest,
        "detector_freeze_handoff_sha256": detector_handoff,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "phase2_tokens": tokens,
        "inputs": expected_inputs,
    }


def validate_phase3_feature_entry_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE3_FEATURE_ENTRY_LAUNCH_VERSION:
        raise ValueError("Phase-3 feature-entry launch version changed")
    control = _positive_run_id(
        row.get("feature_entry_control_run_id"),
        label="Phase-3 feature-entry control run ID",
    )
    plan_run = _positive_run_id(
        row.get("feature_entry_plan_run_id"),
        label="Phase-3 feature-entry plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("feature_entry_plan_artifact_digest"),
        label="Phase-3 feature-entry plan artifact",
    )
    target = _positive_run_id(
        row.get("feature_entry_run_id"),
        label="Phase-3 feature-entry target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 entry launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 entry launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 feature-entry launch branch/HEAD drift")
    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="Phase-3 entry launch universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="Phase-3 entry launch universe artifact",
    )
    universe_handoff = _sha256(
        row.get("universe_handoff_sha256"),
        label="Phase-3 entry launch universe handoff",
    )
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="Phase-3 entry launch price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="Phase-3 entry launch price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="Phase-3 entry launch price-path handoff",
    )
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("Phase-3 feature-entry target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("Phase-3 feature-entry launcher unexpectedly waited")
    if row.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 feature-entry launch consumed outcomes")
    if row.get("phase3_feature_entry_ready") is not False:
        raise ValueError("Phase-3 feature-entry launch claims readiness early")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("Phase-3 feature-entry launch lacks dispatch proof")
    return {
        **row,
        "feature_entry_control_run_id": control,
        "feature_entry_plan_run_id": plan_run,
        "feature_entry_plan_artifact_digest": plan_digest,
        "feature_entry_run_id": target,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "outcome_rows_consumed": False,
        "phase3_feature_entry_ready": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase3_feature_entry_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE3_FEATURE_ENTRY_COMPLETION_VERSION
    ):
        raise ValueError("Phase-3 feature-entry completion version changed")
    control = _positive_run_id(
        row.get("feature_entry_completion_control_run_id"),
        label="Phase-3 entry completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("feature_entry_launch_run_id"),
        label="Phase-3 entry launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("feature_entry_launch_artifact_digest"),
        label="Phase-3 entry launch artifact",
    )
    target = _positive_run_id(
        row.get("feature_entry_run_id"),
        label="completed Phase-3 entry run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("feature_entry_artifact_digest"),
        label="Phase-3 entry artifact",
    )
    handoff_artifact_digest = _artifact_digest(
        row.get("feature_entry_handoff_artifact_digest"),
        label="Phase-3 entry handoff artifact",
    )
    subjects_sha = _sha256(
        row.get("feature_subjects_sha256"),
        label="Phase-3 feature subjects",
    )
    summary_sha = _sha256(
        row.get("entry_summary_sha256"),
        label="Phase-3 entry summary",
    )
    handoff_sha = _sha256(
        row.get("entry_handoff_sha256"),
        label="Phase-3 entry handoff",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-3 entry completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-3 entry completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-3 entry completion branch/HEAD drift")
    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="Phase-3 entry completion universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="Phase-3 entry completion universe artifact",
    )
    universe_handoff = _sha256(
        row.get("universe_handoff_sha256"),
        label="Phase-3 entry completion universe handoff",
    )
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="Phase-3 entry completion price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="Phase-3 entry completion price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="Phase-3 entry completion price-path handoff",
    )
    subjects = int(row.get("feature_subjects", -1))
    if subjects <= 0:
        raise ValueError("Phase-3 feature subject count is invalid")
    if row.get("snapshot_kind") != "first_major_dump_confirmation":
        raise ValueError("Phase-3 feature-entry snapshot kind drift")
    for field, expected in (
        ("target_run_completed", True),
        ("target_run_successful", True),
        ("outcome_rows_consumed", False),
        ("outcome_fields_exposed", False),
        ("future_state_allowed", False),
        ("phase3_feature_values_computed", False),
        ("phase3_feature_entry_ready", True),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"Phase-3 feature-entry completion {field} drift")
    return {
        **row,
        "feature_entry_completion_control_run_id": control,
        "feature_entry_launch_run_id": launch_run,
        "feature_entry_launch_artifact_digest": launch_digest,
        "feature_entry_run_id": target,
        "feature_entry_artifact_digest": artifact_digest,
        "feature_entry_handoff_artifact_digest": handoff_artifact_digest,
        "feature_subjects_sha256": subjects_sha,
        "entry_summary_sha256": summary_sha,
        "entry_handoff_sha256": handoff_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "feature_subjects": subjects,
        "snapshot_kind": "first_major_dump_confirmation",
        "target_run_completed": True,
        "target_run_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": True,
        "workflow_dispatch_performed": False,
    }
