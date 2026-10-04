"""Explicit outcome-blind detector selection and freeze orchestration."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase2_dump_candidate_dispatch import (
    DETECTOR_FREEZE_WORKFLOW,
    RESEARCH_CANDIDATE_SPECS,
    candidate_specs_sha256,
    validate_phase2_dump_diagnostics_completion_receipt,
)


PHASE2_DUMP_DETECTOR_SELECTION_PLAN_VERSION = (
    "phase2-dump-detector-selection-plan-v1"
)
PHASE2_DUMP_DETECTOR_FREEZE_LAUNCH_VERSION = (
    "phase2-dump-detector-freeze-launch-receipt-v1"
)
PHASE2_DUMP_DETECTOR_FREEZE_COMPLETION_VERSION = (
    "phase2-dump-detector-freeze-completion-receipt-v1"
)

SELECTED_CANDIDATE_ID = "dd40-rb25"
SELECTION_POLICY = "central_grid_outcome_blind_v1"


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


def _selected_spec() -> dict:
    specs = {
        str(row["candidate_id"]): dict(row)
        for row in RESEARCH_CANDIDATE_SPECS
    }
    if SELECTED_CANDIDATE_ID not in specs:
        raise ValueError("predeclared detector candidate is missing")
    return specs[SELECTED_CANDIDATE_ID]


def build_phase2_dump_detector_selection_plan(
    diagnostics_completion: Mapping[str, object],
) -> dict:
    diagnostics = validate_phase2_dump_diagnostics_completion_receipt(
        diagnostics_completion
    )
    spec = _selected_spec()
    base = dict(diagnostics["detector_freeze_base_inputs"])
    inputs = {
        **base,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
    }
    return {
        "version": PHASE2_DUMP_DETECTOR_SELECTION_PLAN_VERSION,
        "workflow": DETECTOR_FREEZE_WORKFLOW,
        "execution_branch": diagnostics["execution_branch"],
        "execution_head_sha": diagnostics["execution_head_sha"],
        "canonical_ledger_commit_sha": diagnostics[
            "canonical_ledger_commit_sha"
        ],
        "diagnostics_completion_control_run_id": diagnostics[
            "diagnostics_completion_control_run_id"
        ],
        "candidate_research_run_id": diagnostics[
            "candidate_research_run_id"
        ],
        "candidate_artifact_digest": diagnostics[
            "candidate_artifact_digest"
        ],
        "candidate_handoff_sha256": diagnostics[
            "candidate_handoff_sha256"
        ],
        "diagnostics_run_id": diagnostics["diagnostics_run_id"],
        "diagnostics_artifact_digest": diagnostics[
            "diagnostics_artifact_digest"
        ],
        "diagnostics_handoff_sha256": diagnostics[
            "diagnostics_handoff_sha256"
        ],
        "candidate_specs_sha256": diagnostics[
            "candidate_specs_sha256"
        ],
        "price_path_run_id": diagnostics["price_path_run_id"],
        "price_path_artifact_digest": diagnostics[
            "price_path_artifact_digest"
        ],
        "price_path_handoff_sha256": diagnostics[
            "price_path_handoff_sha256"
        ],
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selected_candidate_spec": spec,
        "selection_policy": SELECTION_POLICY,
        "selection_policy_rationale": (
            "predeclared midpoint of the 3x3 drawdown/rebound research grid; "
            "no outcome labels or post-selection return data used"
        ),
        "inputs": inputs,
        "uses_outcome_labels": False,
        "candidate_selected": True,
        "detector_freeze_ready": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_dump_detector_selection_plan(
    plan: Mapping[str, object],
) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_DETECTOR_SELECTION_PLAN_VERSION
    ):
        raise ValueError("dump-detector selection-plan version changed")
    if str(row.get("workflow") or "") != DETECTOR_FREEZE_WORKFLOW:
        raise ValueError("dump-detector selection workflow drift")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="detector selection execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="detector selection canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("detector selection branch/HEAD drift")
    completion = _positive_run_id(
        row.get("diagnostics_completion_control_run_id"),
        label="detector selection diagnostics completion run ID",
    )
    candidate_run = _positive_run_id(
        row.get("candidate_research_run_id"),
        label="detector selection candidate run ID",
    )
    candidate_digest = _artifact_digest(
        row.get("candidate_artifact_digest"),
        label="detector selection candidate artifact",
    )
    candidate_handoff = _sha256(
        row.get("candidate_handoff_sha256"),
        label="detector selection candidate handoff",
    )
    diagnostics_run = _positive_run_id(
        row.get("diagnostics_run_id"),
        label="detector selection diagnostics run ID",
    )
    diagnostics_digest = _artifact_digest(
        row.get("diagnostics_artifact_digest"),
        label="detector selection diagnostics artifact",
    )
    diagnostics_handoff = _sha256(
        row.get("diagnostics_handoff_sha256"),
        label="detector selection diagnostics handoff",
    )
    specs_sha = _sha256(
        row.get("candidate_specs_sha256"),
        label="detector selection candidate specs",
    )
    if specs_sha != candidate_specs_sha256():
        raise ValueError("detector selection candidate-spec SHA drift")
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="detector selection price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="detector selection price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="detector selection price-path handoff",
    )
    if str(row.get("selected_candidate_id") or "") != SELECTED_CANDIDATE_ID:
        raise ValueError("detector selection candidate ID drift")
    if dict(row.get("selected_candidate_spec") or {}) != _selected_spec():
        raise ValueError("detector selection candidate spec drift")
    if str(row.get("selection_policy") or "") != SELECTION_POLICY:
        raise ValueError("detector selection policy drift")
    expected_inputs = {
        "candidate_research_run_id": str(candidate_run),
        "expected_candidate_artifact_digest": candidate_digest,
        "expected_candidate_handoff_sha256": candidate_handoff,
        "diagnostics_run_id": str(diagnostics_run),
        "expected_diagnostics_artifact_digest": diagnostics_digest,
        "expected_diagnostics_handoff_sha256": diagnostics_handoff,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
    }
    if row.get("inputs") != expected_inputs:
        raise ValueError("detector selection input binding drift")
    for field, expected in (
        ("uses_outcome_labels", False),
        ("candidate_selected", True),
        ("detector_freeze_ready", True),
        ("dump_threshold_frozen", False),
        ("phase2_dump_detector_frozen", False),
        ("outcome_labels_computed", False),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"detector selection {field} drift")
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "diagnostics_completion_control_run_id": completion,
        "candidate_research_run_id": candidate_run,
        "candidate_artifact_digest": candidate_digest,
        "candidate_handoff_sha256": candidate_handoff,
        "diagnostics_run_id": diagnostics_run,
        "diagnostics_artifact_digest": diagnostics_digest,
        "diagnostics_handoff_sha256": diagnostics_handoff,
        "candidate_specs_sha256": specs_sha,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selected_candidate_spec": _selected_spec(),
        "selection_policy": SELECTION_POLICY,
        "inputs": expected_inputs,
    }


def validate_phase2_dump_detector_freeze_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_DETECTOR_FREEZE_LAUNCH_VERSION
    ):
        raise ValueError("dump-detector freeze launch version changed")
    control = _positive_run_id(
        row.get("detector_freeze_control_run_id"),
        label="detector-freeze control run ID",
    )
    plan_run = _positive_run_id(
        row.get("selection_plan_run_id"),
        label="detector selection-plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("selection_plan_artifact_digest"),
        label="detector selection-plan artifact",
    )
    target = _positive_run_id(
        row.get("detector_freeze_run_id"),
        label="detector-freeze target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="detector-freeze launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="detector-freeze launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("detector-freeze launch branch/HEAD drift")
    if str(row.get("selected_candidate_id") or "") != SELECTED_CANDIDATE_ID:
        raise ValueError("detector-freeze launch candidate drift")
    if str(row.get("selection_policy") or "") != SELECTION_POLICY:
        raise ValueError("detector-freeze launch policy drift")
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="detector-freeze launch price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="detector-freeze launch price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="detector-freeze launch price-path handoff",
    )
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("detector-freeze launch target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("detector-freeze launcher unexpectedly waited")
    if row.get("uses_outcome_labels") is not False:
        raise ValueError("detector-freeze launcher uses outcomes")
    if row.get("phase2_dump_detector_frozen") is not False:
        raise ValueError("detector-freeze launcher claims freeze early")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("detector-freeze launch lacks dispatch proof")
    return {
        **row,
        "detector_freeze_control_run_id": control,
        "selection_plan_run_id": plan_run,
        "selection_plan_artifact_digest": plan_digest,
        "detector_freeze_run_id": target,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selection_policy": SELECTION_POLICY,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "uses_outcome_labels": False,
        "phase2_dump_detector_frozen": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_dump_detector_freeze_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_DETECTOR_FREEZE_COMPLETION_VERSION
    ):
        raise ValueError("dump-detector freeze completion version changed")
    control = _positive_run_id(
        row.get("detector_freeze_completion_control_run_id"),
        label="detector-freeze completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("detector_freeze_launch_run_id"),
        label="detector-freeze launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("detector_freeze_launch_artifact_digest"),
        label="detector-freeze launch artifact",
    )
    target = _positive_run_id(
        row.get("detector_freeze_run_id"),
        label="completed detector-freeze run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("detector_freeze_artifact_digest"),
        label="detector-freeze artifact",
    )
    handoff_artifact_digest = _artifact_digest(
        row.get("detector_freeze_handoff_artifact_digest"),
        label="detector-freeze handoff artifact",
    )
    rows_sha = _sha256(
        row.get("detector_rows_sha256"),
        label="detector-freeze rows",
    )
    summary_sha = _sha256(
        row.get("freeze_summary_sha256"),
        label="detector-freeze summary",
    )
    handoff_sha = _sha256(
        row.get("detector_freeze_handoff_sha256"),
        label="detector-freeze handoff",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="detector-freeze completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="detector-freeze completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("detector-freeze completion branch/HEAD drift")
    price_run = _positive_run_id(
        row.get("price_path_run_id"),
        label="detector-freeze completion price-path run ID",
    )
    price_digest = _artifact_digest(
        row.get("price_path_artifact_digest"),
        label="detector-freeze completion price-path artifact",
    )
    price_handoff = _sha256(
        row.get("price_path_handoff_sha256"),
        label="detector-freeze completion price-path handoff",
    )
    tokens = int(row.get("tokens", -1))
    confirmed = int(row.get("confirmed_tokens", -1))
    if tokens <= 0 or confirmed < 0 or confirmed > tokens:
        raise ValueError("detector-freeze completion token counts invalid")
    if str(row.get("selected_candidate_id") or "") != SELECTED_CANDIDATE_ID:
        raise ValueError("detector-freeze completion candidate drift")
    if str(row.get("selection_policy") or "") != SELECTION_POLICY:
        raise ValueError("detector-freeze completion policy drift")
    outcome_inputs = {
        "detector_freeze_run_id": str(target),
        "expected_detector_artifact_digest": artifact_digest,
        "expected_detector_handoff_sha256": handoff_sha,
        "price_path_run_id": str(price_run),
        "expected_price_path_artifact_digest": price_digest,
        "expected_price_path_handoff_sha256": price_handoff,
    }
    if row.get("outcome_label_inputs") != outcome_inputs:
        raise ValueError("outcome-label input binding drift")
    for field, expected in (
        ("target_run_completed", True),
        ("target_run_successful", True),
        ("uses_outcome_labels", False),
        ("candidate_selected", True),
        ("detector_freeze_ready", True),
        ("dump_threshold_frozen", True),
        ("phase2_dump_detector_frozen", True),
        ("outcome_labels_computed", False),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"detector-freeze completion {field} drift")
    return {
        **row,
        "detector_freeze_completion_control_run_id": control,
        "detector_freeze_launch_run_id": launch_run,
        "detector_freeze_launch_artifact_digest": launch_digest,
        "detector_freeze_run_id": target,
        "detector_freeze_artifact_digest": artifact_digest,
        "detector_freeze_handoff_artifact_digest": handoff_artifact_digest,
        "detector_rows_sha256": rows_sha,
        "freeze_summary_sha256": summary_sha,
        "detector_freeze_handoff_sha256": handoff_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "price_path_run_id": price_run,
        "price_path_artifact_digest": price_digest,
        "price_path_handoff_sha256": price_handoff,
        "tokens": tokens,
        "confirmed_tokens": confirmed,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selection_policy": SELECTION_POLICY,
        "outcome_label_inputs": outcome_inputs,
    }
