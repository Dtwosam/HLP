"""Outcome-blind candidate research and diagnostics orchestration."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

from hlp.data.phase2_dump_geometry_dispatch import (
    validate_phase2_dump_geometry_completion_receipt,
)
from hlp.data.phase2_dump_research import PEAK_DRAWDOWN_REBOUND_FAMILY


PHASE2_DUMP_CANDIDATE_PLAN_VERSION = (
    "phase2-dump-candidate-research-plan-v1"
)
PHASE2_DUMP_CANDIDATE_LAUNCH_VERSION = (
    "phase2-dump-candidate-research-launch-receipt-v1"
)
PHASE2_DUMP_CANDIDATE_COMPLETION_VERSION = (
    "phase2-dump-candidate-research-completion-receipt-v1"
)
PHASE2_DUMP_DIAGNOSTICS_LAUNCH_VERSION = (
    "phase2-dump-candidate-diagnostics-launch-receipt-v1"
)
PHASE2_DUMP_DIAGNOSTICS_COMPLETION_VERSION = (
    "phase2-dump-candidate-diagnostics-completion-receipt-v1"
)

CANDIDATE_RESEARCH_WORKFLOW = "phase2-dump-candidate-research.yml"
CANDIDATE_DIAGNOSTICS_WORKFLOW = "phase2-dump-candidate-diagnostics.yml"
DETECTOR_FREEZE_WORKFLOW = "phase2-dump-detector-freeze.yml"


RESEARCH_CANDIDATE_SPECS = (
    {
        "candidate_id": "dd30-rb15",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.3",
        "confirmation_rebound_fraction": "0.15",
    },
    {
        "candidate_id": "dd30-rb25",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.3",
        "confirmation_rebound_fraction": "0.25",
    },
    {
        "candidate_id": "dd30-rb35",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.3",
        "confirmation_rebound_fraction": "0.35",
    },
    {
        "candidate_id": "dd40-rb15",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.4",
        "confirmation_rebound_fraction": "0.15",
    },
    {
        "candidate_id": "dd40-rb25",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.4",
        "confirmation_rebound_fraction": "0.25",
    },
    {
        "candidate_id": "dd40-rb35",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.4",
        "confirmation_rebound_fraction": "0.35",
    },
    {
        "candidate_id": "dd50-rb15",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.5",
        "confirmation_rebound_fraction": "0.15",
    },
    {
        "candidate_id": "dd50-rb25",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.5",
        "confirmation_rebound_fraction": "0.25",
    },
    {
        "candidate_id": "dd50-rb35",
        "family": PEAK_DRAWDOWN_REBOUND_FAMILY,
        "min_drawdown_fraction": "0.5",
        "confirmation_rebound_fraction": "0.35",
    },
)


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


def canonical_candidate_specs() -> list[dict]:
    return [
        dict(row)
        for row in sorted(
            RESEARCH_CANDIDATE_SPECS,
            key=lambda item: item["candidate_id"],
        )
    ]


def candidate_specs_json() -> str:
    return json.dumps(
        canonical_candidate_specs(),
        sort_keys=True,
        separators=(",", ":"),
    )


def candidate_specs_sha256() -> str:
    raw = (candidate_specs_json() + "\n").encode()
    return hashlib.sha256(raw).hexdigest()


def build_phase2_dump_candidate_research_plan(
    geometry_completion: Mapping[str, object],
) -> dict:
    """Freeze an explicit research-only grid without choosing a detector."""

    geometry = validate_phase2_dump_geometry_completion_receipt(
        geometry_completion
    )
    base = dict(geometry["candidate_research_base_inputs"])
    specs_json = candidate_specs_json()
    specs_sha = candidate_specs_sha256()
    inputs = {
        **base,
        "candidate_specs_json": specs_json,
    }
    return {
        "version": PHASE2_DUMP_CANDIDATE_PLAN_VERSION,
        "workflow": CANDIDATE_RESEARCH_WORKFLOW,
        "execution_branch": geometry["execution_branch"],
        "execution_head_sha": geometry["execution_head_sha"],
        "canonical_ledger_commit_sha": geometry[
            "canonical_ledger_commit_sha"
        ],
        "geometry_completion_control_run_id": geometry[
            "dump_geometry_completion_control_run_id"
        ],
        "geometry_run_id": geometry["dump_geometry_run_id"],
        "geometry_artifact_digest": geometry[
            "dump_geometry_artifact_digest"
        ],
        "geometry_handoff_sha256": geometry[
            "geometry_handoff_sha256"
        ],
        "candidate_specs": canonical_candidate_specs(),
        "candidate_specs_json": specs_json,
        "candidate_specs_sha256": specs_sha,
        "candidate_count": len(RESEARCH_CANDIDATE_SPECS),
        "inputs": inputs,
        "uses_outcome_labels": False,
        "candidate_selected": False,
        "detector_freeze_ready": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_dump_candidate_research_plan(
    plan: Mapping[str, object],
) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != PHASE2_DUMP_CANDIDATE_PLAN_VERSION:
        raise ValueError("dump-candidate research plan version changed")
    if str(row.get("workflow") or "") != CANDIDATE_RESEARCH_WORKFLOW:
        raise ValueError("dump-candidate research workflow drift")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="dump-candidate plan execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="dump-candidate plan canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("dump-candidate plan branch/HEAD drift")
    geometry_completion = _positive_run_id(
        row.get("geometry_completion_control_run_id"),
        label="dump-candidate geometry completion run ID",
    )
    geometry_run = _positive_run_id(
        row.get("geometry_run_id"),
        label="dump-candidate geometry run ID",
    )
    geometry_digest = _artifact_digest(
        row.get("geometry_artifact_digest"),
        label="dump-candidate geometry artifact",
    )
    geometry_handoff_sha = _sha256(
        row.get("geometry_handoff_sha256"),
        label="dump-candidate geometry handoff",
    )
    expected_specs = canonical_candidate_specs()
    expected_json = candidate_specs_json()
    expected_sha = candidate_specs_sha256()
    if row.get("candidate_specs") != expected_specs:
        raise ValueError("dump-candidate spec grid drift")
    if str(row.get("candidate_specs_json") or "") != expected_json:
        raise ValueError("dump-candidate spec JSON drift")
    if _sha256(
        row.get("candidate_specs_sha256"),
        label="dump-candidate specs",
    ) != expected_sha:
        raise ValueError("dump-candidate spec SHA drift")
    if int(row.get("candidate_count", -1)) != len(expected_specs):
        raise ValueError("dump-candidate count drift")
    expected_inputs = {
        "geometry_run_id": str(geometry_run),
        "expected_geometry_artifact_digest": geometry_digest,
        "expected_geometry_handoff_sha256": geometry_handoff_sha,
        "candidate_specs_json": expected_json,
    }
    if row.get("inputs") != expected_inputs:
        raise ValueError("dump-candidate plan input binding drift")
    for field, expected in (
        ("uses_outcome_labels", False),
        ("candidate_selected", False),
        ("detector_freeze_ready", False),
        ("dump_threshold_frozen", False),
        ("phase2_dump_detector_frozen", False),
        ("outcome_labels_computed", False),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"dump-candidate plan {field} drift")
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "geometry_completion_control_run_id": geometry_completion,
        "geometry_run_id": geometry_run,
        "geometry_artifact_digest": geometry_digest,
        "geometry_handoff_sha256": geometry_handoff_sha,
        "candidate_specs": expected_specs,
        "candidate_specs_json": expected_json,
        "candidate_specs_sha256": expected_sha,
        "candidate_count": len(expected_specs),
        "inputs": expected_inputs,
    }


def validate_phase2_dump_candidate_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_DUMP_CANDIDATE_LAUNCH_VERSION:
        raise ValueError("dump-candidate launch version changed")
    control = _positive_run_id(
        row.get("candidate_control_run_id"),
        label="dump-candidate control run ID",
    )
    plan_run = _positive_run_id(
        row.get("candidate_plan_run_id"),
        label="dump-candidate plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("candidate_plan_artifact_digest"),
        label="dump-candidate plan artifact",
    )
    target = _positive_run_id(
        row.get("candidate_research_run_id"),
        label="dump-candidate target run ID",
    )
    specs_sha = _sha256(
        row.get("candidate_specs_sha256"),
        label="dump-candidate launch specs",
    )
    if specs_sha != candidate_specs_sha256():
        raise ValueError("dump-candidate launch spec SHA drift")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="dump-candidate launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="dump-candidate launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("dump-candidate launch branch/HEAD drift")
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("dump-candidate target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("dump-candidate launcher unexpectedly waited")
    for field, expected in (
        ("uses_outcome_labels", False),
        ("candidate_selected", False),
        ("detector_freeze_ready", False),
        ("phase2_dump_detector_frozen", False),
        ("outcome_labels_computed", False),
        ("workflow_dispatch_performed", True),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"dump-candidate launch {field} drift")
    return {
        **row,
        "candidate_control_run_id": control,
        "candidate_plan_run_id": plan_run,
        "candidate_plan_artifact_digest": plan_digest,
        "candidate_research_run_id": target,
        "candidate_specs_sha256": specs_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_dump_candidate_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_CANDIDATE_COMPLETION_VERSION
    ):
        raise ValueError("dump-candidate completion version changed")
    control = _positive_run_id(
        row.get("candidate_completion_control_run_id"),
        label="dump-candidate completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("candidate_launch_run_id"),
        label="dump-candidate launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("candidate_launch_artifact_digest"),
        label="dump-candidate launch artifact",
    )
    candidate_run = _positive_run_id(
        row.get("candidate_research_run_id"),
        label="completed dump-candidate run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("candidate_artifact_digest"),
        label="dump-candidate artifact",
    )
    handoff_artifact_digest = _artifact_digest(
        row.get("candidate_handoff_artifact_digest"),
        label="dump-candidate handoff artifact",
    )
    handoff_sha = _sha256(
        row.get("candidate_handoff_sha256"),
        label="dump-candidate handoff",
    )
    rows_sha = _sha256(
        row.get("candidate_rows_sha256"),
        label="dump-candidate rows",
    )
    specs_sha = _sha256(
        row.get("candidate_specs_sha256"),
        label="dump-candidate specs",
    )
    summary_sha = _sha256(
        row.get("candidate_summary_sha256"),
        label="dump-candidate summary",
    )
    if specs_sha != candidate_specs_sha256():
        raise ValueError("dump-candidate completion spec SHA drift")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="dump-candidate completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="dump-candidate completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("dump-candidate completion branch/HEAD drift")
    tokens = int(row.get("tokens", -1))
    candidate_rows = int(row.get("candidate_rows", -1))
    candidates = int(row.get("candidates", -1))
    if tokens <= 0 or candidates != len(RESEARCH_CANDIDATE_SPECS):
        raise ValueError("dump-candidate completion dimensions drift")
    if candidate_rows != tokens * candidates:
        raise ValueError("dump-candidate row cardinality drift")
    diagnostics_inputs = {
        "candidate_research_run_id": str(candidate_run),
        "expected_candidate_artifact_digest": artifact_digest,
        "expected_candidate_handoff_sha256": handoff_sha,
    }
    if row.get("diagnostics_inputs") != diagnostics_inputs:
        raise ValueError("candidate-diagnostics input binding drift")
    for field, expected in (
        ("candidate_research_ready", True),
        ("uses_outcome_labels", False),
        ("candidate_selected", False),
        ("detector_freeze_ready", False),
        ("dump_threshold_frozen", False),
        ("phase2_dump_detector_frozen", False),
        ("outcome_labels_computed", False),
        ("target_run_completed", True),
        ("target_run_successful", True),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"dump-candidate completion {field} drift")
    return {
        **row,
        "candidate_completion_control_run_id": control,
        "candidate_launch_run_id": launch_run,
        "candidate_launch_artifact_digest": launch_digest,
        "candidate_research_run_id": candidate_run,
        "candidate_artifact_digest": artifact_digest,
        "candidate_handoff_artifact_digest": handoff_artifact_digest,
        "candidate_handoff_sha256": handoff_sha,
        "candidate_rows_sha256": rows_sha,
        "candidate_specs_sha256": specs_sha,
        "candidate_summary_sha256": summary_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "tokens": tokens,
        "candidate_rows": candidate_rows,
        "candidates": candidates,
        "diagnostics_inputs": diagnostics_inputs,
    }


def validate_phase2_dump_diagnostics_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_DIAGNOSTICS_LAUNCH_VERSION
    ):
        raise ValueError("dump diagnostics launch version changed")
    control = _positive_run_id(
        row.get("diagnostics_control_run_id"),
        label="dump diagnostics control run ID",
    )
    completion_run = _positive_run_id(
        row.get("candidate_completion_run_id"),
        label="candidate completion run ID",
    )
    completion_digest = _artifact_digest(
        row.get("candidate_completion_artifact_digest"),
        label="candidate completion artifact",
    )
    target = _positive_run_id(
        row.get("diagnostics_run_id"),
        label="diagnostics target run ID",
    )
    candidate_run = _positive_run_id(
        row.get("candidate_research_run_id"),
        label="diagnostics candidate-research run ID",
    )
    candidate_digest = _artifact_digest(
        row.get("candidate_artifact_digest"),
        label="diagnostics candidate artifact",
    )
    candidate_handoff_sha = _sha256(
        row.get("candidate_handoff_sha256"),
        label="diagnostics candidate handoff",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="diagnostics launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="diagnostics launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("diagnostics launch branch/HEAD drift")
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("diagnostics target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("diagnostics launcher unexpectedly waited")
    for field, expected in (
        ("uses_outcome_labels", False),
        ("candidate_selected", False),
        ("detector_freeze_ready", False),
        ("phase2_dump_detector_frozen", False),
        ("outcome_labels_computed", False),
        ("workflow_dispatch_performed", True),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"diagnostics launch {field} drift")
    return {
        **row,
        "diagnostics_control_run_id": control,
        "candidate_completion_run_id": completion_run,
        "candidate_completion_artifact_digest": completion_digest,
        "diagnostics_run_id": target,
        "candidate_research_run_id": candidate_run,
        "candidate_artifact_digest": candidate_digest,
        "candidate_handoff_sha256": candidate_handoff_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_dump_diagnostics_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_DIAGNOSTICS_COMPLETION_VERSION
    ):
        raise ValueError("dump diagnostics completion version changed")
    control = _positive_run_id(
        row.get("diagnostics_completion_control_run_id"),
        label="diagnostics completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("diagnostics_launch_run_id"),
        label="diagnostics launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("diagnostics_launch_artifact_digest"),
        label="diagnostics launch artifact",
    )
    diagnostics_run = _positive_run_id(
        row.get("diagnostics_run_id"),
        label="completed diagnostics run ID",
    )
    diagnostics_digest = _artifact_digest(
        row.get("diagnostics_artifact_digest"),
        label="diagnostics artifact",
    )
    diagnostics_handoff_sha = _sha256(
        row.get("diagnostics_handoff_sha256"),
        label="diagnostics handoff",
    )
    diagnostics_sha = _sha256(
        row.get("diagnostics_sha256"),
        label="diagnostics rows",
    )
    diagnostics_summary_sha = _sha256(
        row.get("diagnostics_summary_sha256"),
        label="diagnostics summary",
    )
    candidate_run = _positive_run_id(
        row.get("candidate_research_run_id"),
        label="diagnostics completion candidate run ID",
    )
    candidate_digest = _artifact_digest(
        row.get("candidate_artifact_digest"),
        label="diagnostics completion candidate artifact",
    )
    candidate_handoff_sha = _sha256(
        row.get("candidate_handoff_sha256"),
        label="diagnostics completion candidate handoff",
    )
    specs_sha = _sha256(
        row.get("candidate_specs_sha256"),
        label="diagnostics completion specs",
    )
    if specs_sha != candidate_specs_sha256():
        raise ValueError("diagnostics completion spec SHA drift")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="diagnostics completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="diagnostics completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("diagnostics completion branch/HEAD drift")
    candidates = int(row.get("candidates", -1))
    if candidates != len(RESEARCH_CANDIDATE_SPECS):
        raise ValueError("diagnostics candidate count drift")
    freeze_base_inputs = {
        "candidate_research_run_id": str(candidate_run),
        "expected_candidate_artifact_digest": candidate_digest,
        "expected_candidate_handoff_sha256": candidate_handoff_sha,
        "diagnostics_run_id": str(diagnostics_run),
        "expected_diagnostics_artifact_digest": diagnostics_digest,
        "expected_diagnostics_handoff_sha256": diagnostics_handoff_sha,
    }
    if row.get("detector_freeze_base_inputs") != freeze_base_inputs:
        raise ValueError("detector-freeze base-input binding drift")
    if row.get("selected_candidate_id") is not None:
        raise ValueError("diagnostics completion selected a candidate")
    if row.get("selected_candidate_id_required") is not True:
        raise ValueError("diagnostics completion lost explicit-selection gate")
    for field, expected in (
        ("uses_outcome_labels", False),
        ("candidate_selected", False),
        ("detector_freeze_ready", False),
        ("dump_threshold_frozen", False),
        ("phase2_dump_detector_frozen", False),
        ("outcome_labels_computed", False),
        ("target_run_completed", True),
        ("target_run_successful", True),
        ("workflow_dispatch_performed", False),
    ):
        if row.get(field) is not expected:
            raise ValueError(f"diagnostics completion {field} drift")
    return {
        **row,
        "diagnostics_completion_control_run_id": control,
        "diagnostics_launch_run_id": launch_run,
        "diagnostics_launch_artifact_digest": launch_digest,
        "diagnostics_run_id": diagnostics_run,
        "diagnostics_artifact_digest": diagnostics_digest,
        "diagnostics_handoff_sha256": diagnostics_handoff_sha,
        "diagnostics_sha256": diagnostics_sha,
        "diagnostics_summary_sha256": diagnostics_summary_sha,
        "candidate_research_run_id": candidate_run,
        "candidate_artifact_digest": candidate_digest,
        "candidate_handoff_sha256": candidate_handoff_sha,
        "candidate_specs_sha256": specs_sha,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "candidates": candidates,
        "detector_freeze_base_inputs": freeze_base_inputs,
        "selected_candidate_id": None,
        "selected_candidate_id_required": True,
    }
