"""Final Phase-2 universe/outcome checkpoint orchestration."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase2_outcome_dispatch import (
    validate_phase2_outcome_label_completion_receipt,
)
from hlp.data.phase2_universe_freeze_dispatch import (
    validate_phase2_universe_freeze_completion_receipt,
)


PHASE2_DATASET_DISPATCH_PLAN_VERSION = (
    "phase2-universe-outcome-dataset-plan-v1"
)
PHASE2_DATASET_LAUNCH_VERSION = (
    "phase2-universe-outcome-dataset-launch-receipt-v1"
)
PHASE2_DATASET_COMPLETION_VERSION = (
    "phase2-universe-outcome-dataset-completion-receipt-v1"
)
DATASET_WORKFLOW = "phase2-universe-outcome-dataset.yml"


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


def build_phase2_dataset_dispatch_plan(
    universe_completion: Mapping[str, object],
    outcome_completion: Mapping[str, object],
) -> dict:
    universe = validate_phase2_universe_freeze_completion_receipt(
        universe_completion
    )
    outcome = validate_phase2_outcome_label_completion_receipt(
        outcome_completion
    )
    if universe["execution_branch"] != outcome["execution_branch"]:
        raise ValueError("dataset plan execution branch drift")
    if universe["execution_head_sha"] != outcome["execution_head_sha"]:
        raise ValueError("dataset plan execution HEAD drift")
    if universe["canonical_ledger_commit_sha"] != outcome[
        "canonical_ledger_commit_sha"
    ]:
        raise ValueError("dataset plan canonical commit drift")
    if int(universe["eligible_tokens"]) != int(outcome["tokens"]):
        raise ValueError("dataset plan universe/outcome token count drift")
    inputs = {
        "universe_run_id": str(universe["universe_freeze_run_id"]),
        "expected_universe_artifact_digest": universe[
            "universe_freeze_artifact_digest"
        ],
        "expected_universe_handoff_sha256": universe[
            "universe_freeze_handoff_sha256"
        ],
        "outcome_run_id": str(outcome["outcome_label_run_id"]),
        "expected_outcome_artifact_digest": outcome[
            "outcome_artifact_digest"
        ],
        "expected_outcome_handoff_sha256": outcome[
            "outcome_handoff_sha256"
        ],
    }
    return {
        "version": PHASE2_DATASET_DISPATCH_PLAN_VERSION,
        "workflow": DATASET_WORKFLOW,
        "execution_branch": universe["execution_branch"],
        "execution_head_sha": universe["execution_head_sha"],
        "canonical_ledger_commit_sha": universe[
            "canonical_ledger_commit_sha"
        ],
        "universe_completion_control_run_id": universe[
            "universe_freeze_completion_control_run_id"
        ],
        "universe_run_id": universe["universe_freeze_run_id"],
        "universe_artifact_digest": universe[
            "universe_freeze_artifact_digest"
        ],
        "universe_handoff_sha256": universe[
            "universe_freeze_handoff_sha256"
        ],
        "eligible_universe_sha256": universe[
            "eligible_universe_sha256"
        ],
        "outcome_completion_control_run_id": outcome[
            "outcome_label_completion_control_run_id"
        ],
        "outcome_run_id": outcome["outcome_label_run_id"],
        "outcome_artifact_digest": outcome["outcome_artifact_digest"],
        "outcome_handoff_sha256": outcome["outcome_handoff_sha256"],
        "outcome_rows_sha256": outcome["outcome_rows_sha256"],
        "tokens": int(universe["eligible_tokens"]),
        "confirmed_dump_tokens": int(outcome["confirmed_dump_tokens"]),
        "comeback_5x_tokens": int(outcome["comeback_5x_tokens"]),
        "inputs": inputs,
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
        "phase2_dataset_ready": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_dataset_dispatch_plan(
    plan: Mapping[str, object],
) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != PHASE2_DATASET_DISPATCH_PLAN_VERSION:
        raise ValueError("Phase-2 dataset plan version changed")
    if str(row.get("workflow") or "") != DATASET_WORKFLOW:
        raise ValueError("Phase-2 dataset workflow drift")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 dataset plan execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-2 dataset plan canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-2 dataset plan branch/HEAD drift")
    universe_completion = _positive_run_id(
        row.get("universe_completion_control_run_id"),
        label="dataset universe completion run ID",
    )
    universe_run = _positive_run_id(
        row.get("universe_run_id"),
        label="dataset universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="dataset universe artifact",
    )
    universe_handoff = _sha256(
        row.get("universe_handoff_sha256"),
        label="dataset universe handoff",
    )
    universe_sha = _sha256(
        row.get("eligible_universe_sha256"),
        label="dataset eligible universe",
    )
    outcome_completion = _positive_run_id(
        row.get("outcome_completion_control_run_id"),
        label="dataset outcome completion run ID",
    )
    outcome_run = _positive_run_id(
        row.get("outcome_run_id"),
        label="dataset outcome run ID",
    )
    outcome_digest = _artifact_digest(
        row.get("outcome_artifact_digest"),
        label="dataset outcome artifact",
    )
    outcome_handoff = _sha256(
        row.get("outcome_handoff_sha256"),
        label="dataset outcome handoff",
    )
    outcome_rows = _sha256(
        row.get("outcome_rows_sha256"),
        label="dataset outcome rows",
    )
    tokens = int(row.get("tokens", -1))
    confirmed = int(row.get("confirmed_dump_tokens", -1))
    comeback = int(row.get("comeback_5x_tokens", -1))
    if tokens <= 0 or confirmed < 0 or comeback < 0:
        raise ValueError("Phase-2 dataset plan counts invalid")
    if confirmed > tokens or comeback > confirmed:
        raise ValueError("Phase-2 dataset plan count hierarchy drift")
    expected_inputs = {
        "universe_run_id": str(universe_run),
        "expected_universe_artifact_digest": universe_digest,
        "expected_universe_handoff_sha256": universe_handoff,
        "outcome_run_id": str(outcome_run),
        "expected_outcome_artifact_digest": outcome_digest,
        "expected_outcome_handoff_sha256": outcome_handoff,
    }
    if row.get("inputs") != expected_inputs:
        raise ValueError("Phase-2 dataset input binding drift")
    for field, expected in (
        ("phase2_universe_frozen", True),
        ("phase2_dump_detector_frozen", True),
        ("outcome_labels_computed", True),
        ("phase3_features_attached", False),
        ("phase2_dataset_ready", False),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"Phase-2 dataset plan {field} drift")
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "universe_completion_control_run_id": universe_completion,
        "universe_run_id": universe_run,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff,
        "eligible_universe_sha256": universe_sha,
        "outcome_completion_control_run_id": outcome_completion,
        "outcome_run_id": outcome_run,
        "outcome_artifact_digest": outcome_digest,
        "outcome_handoff_sha256": outcome_handoff,
        "outcome_rows_sha256": outcome_rows,
        "tokens": tokens,
        "confirmed_dump_tokens": confirmed,
        "comeback_5x_tokens": comeback,
        "inputs": expected_inputs,
    }


def validate_phase2_dataset_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_DATASET_LAUNCH_VERSION:
        raise ValueError("Phase-2 dataset launch version changed")
    control = _positive_run_id(
        row.get("dataset_control_run_id"),
        label="Phase-2 dataset control run ID",
    )
    plan_run = _positive_run_id(
        row.get("dataset_plan_run_id"),
        label="Phase-2 dataset plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("dataset_plan_artifact_digest"),
        label="Phase-2 dataset plan artifact",
    )
    target = _positive_run_id(
        row.get("dataset_run_id"),
        label="Phase-2 dataset target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 dataset launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-2 dataset launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-2 dataset launch branch/HEAD drift")
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("Phase-2 dataset launch target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("Phase-2 dataset launcher unexpectedly waited")
    if row.get("phase2_dataset_ready") is not False:
        raise ValueError("Phase-2 dataset launcher claims readiness early")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("Phase-2 dataset launch lacks dispatch proof")
    return {
        **row,
        "dataset_control_run_id": control,
        "dataset_plan_run_id": plan_run,
        "dataset_plan_artifact_digest": plan_digest,
        "dataset_run_id": target,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "phase2_dataset_ready": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_dataset_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_DATASET_COMPLETION_VERSION:
        raise ValueError("Phase-2 dataset completion version changed")
    control = _positive_run_id(
        row.get("dataset_completion_control_run_id"),
        label="Phase-2 dataset completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("dataset_launch_run_id"),
        label="Phase-2 dataset launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("dataset_launch_artifact_digest"),
        label="Phase-2 dataset launch artifact",
    )
    target = _positive_run_id(
        row.get("dataset_run_id"),
        label="completed Phase-2 dataset run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("dataset_artifact_digest"),
        label="Phase-2 dataset artifact",
    )
    handoff_artifact_digest = _artifact_digest(
        row.get("dataset_handoff_artifact_digest"),
        label="Phase-2 dataset handoff artifact",
    )
    rows_sha = _sha256(
        row.get("dataset_rows_sha256"),
        label="Phase-2 dataset rows",
    )
    summary_sha = _sha256(
        row.get("dataset_summary_sha256"),
        label="Phase-2 dataset summary",
    )
    handoff_sha = _sha256(
        row.get("dataset_handoff_sha256"),
        label="Phase-2 dataset handoff",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="Phase-2 dataset completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="Phase-2 dataset completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("Phase-2 dataset completion branch/HEAD drift")
    tokens = int(row.get("tokens", -1))
    confirmed = int(row.get("confirmed_dump_tokens", -1))
    comeback = int(row.get("comeback_5x_tokens", -1))
    if tokens <= 0 or confirmed < 0 or comeback < 0:
        raise ValueError("Phase-2 dataset completion counts invalid")
    if confirmed > tokens or comeback > confirmed:
        raise ValueError("Phase-2 dataset completion count hierarchy drift")
    if row.get("checkpoint_name") != "hlp-v1-phase2-universe-labels":
        raise ValueError("Phase-2 dataset checkpoint name drift")
    for field, expected in (
        ("target_run_completed", True),
        ("target_run_successful", True),
        ("phase2_universe_frozen", True),
        ("phase2_dump_detector_frozen", True),
        ("outcome_labels_computed", True),
        ("phase3_features_attached", False),
        ("phase2_dataset_ready", True),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"Phase-2 dataset completion {field} drift")
    return {
        **row,
        "dataset_completion_control_run_id": control,
        "dataset_launch_run_id": launch_run,
        "dataset_launch_artifact_digest": launch_digest,
        "dataset_run_id": target,
        "dataset_artifact_digest": artifact_digest,
        "dataset_handoff_artifact_digest": handoff_artifact_digest,
        "dataset_rows_sha256": rows_sha,
        "dataset_summary_sha256": summary_sha,
        "dataset_handoff_sha256": handoff_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "tokens": tokens,
        "confirmed_dump_tokens": confirmed,
        "comeback_5x_tokens": comeback,
        "checkpoint_name": "hlp-v1-phase2-universe-labels",
        "target_run_completed": True,
        "target_run_successful": True,
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
        "phase2_dataset_ready": True,
        "workflow_dispatch_performed": False,
    }
