"""Dispatch contracts for outcome-blind Phase-2 dump candidate research."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping

from hlp.data.phase2_dump_geometry_dispatch import (
    validate_phase2_dump_geometry_completion_receipt,
)
from hlp.data.phase2_dump_research import (
    normalize_phase2_dump_candidate_specs,
)


PHASE2_DUMP_CANDIDATE_PLAN_VERSION = "phase2-dump-candidate-plan-v1"
PHASE2_DUMP_CANDIDATE_LAUNCH_VERSION = (
    "phase2-dump-candidate-launch-receipt-v1"
)
PHASE2_DUMP_CANDIDATE_COMPLETION_VERSION = (
    "phase2-dump-candidate-completion-receipt-v1"
)
CANDIDATE_WORKFLOW = "phase2-dump-candidate-research.yml"
DIAGNOSTICS_WORKFLOW = "phase2-dump-candidate-diagnostics.yml"


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


def build_phase2_dump_candidate_dispatch_plan(
    geometry_completion: Mapping[str, object],
    candidate_grid: Mapping[str, object],
) -> dict:
    geometry = validate_phase2_dump_geometry_completion_receipt(
        geometry_completion
    )
    grid = dict(candidate_grid)
    if str(grid.get("version") or "") != "phase2-dump-candidate-grid-v1":
        raise ValueError("dump candidate grid version changed")
    if str(grid.get("semantics") or "") != "research_only_no_selection":
        raise ValueError("dump candidate grid semantics changed")
    raw_candidates = grid.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("dump candidate grid lacks candidates")
    normalized = normalize_phase2_dump_candidate_specs(raw_candidates)
    if len(normalized) != int(grid.get("candidate_count", -1)):
        raise ValueError("dump candidate grid count drift")
    normalized_json = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    )
    specs_sha = hashlib.sha256(
        (normalized_json + "\n").encode()
    ).hexdigest()
    inputs = {
        **geometry["candidate_research_base_inputs"],
        "candidate_specs_json": normalized_json,
    }
    return {
        "version": PHASE2_DUMP_CANDIDATE_PLAN_VERSION,
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
        "candidate_specs": normalized,
        "candidate_specs_json": normalized_json,
        "candidate_specs_sha256": specs_sha,
        "candidate_count": len(normalized),
        "workflow": CANDIDATE_WORKFLOW,
        "inputs": inputs,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_dump_candidate_dispatch_plan(
    plan: Mapping[str, object],
) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != PHASE2_DUMP_CANDIDATE_PLAN_VERSION:
        raise ValueError("dump candidate plan version changed")
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="dump candidate plan execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="dump candidate plan canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("dump candidate plan branch/HEAD drift")
    completion_run = _positive_run_id(
        row.get("geometry_completion_control_run_id"),
        label="dump candidate geometry completion run ID",
    )
    geometry_run = _positive_run_id(
        row.get("geometry_run_id"),
        label="dump candidate geometry run ID",
    )
    geometry_digest = _artifact_digest(
        row.get("geometry_artifact_digest"),
        label="dump candidate geometry artifact",
    )
    geometry_handoff_sha = _sha256(
        row.get("geometry_handoff_sha256"),
        label="dump candidate geometry handoff",
    )
    raw_specs = row.get("candidate_specs")
    if not isinstance(raw_specs, list):
        raise ValueError("dump candidate plan specs are missing")
    specs = normalize_phase2_dump_candidate_specs(raw_specs)
    if len(specs) != int(row.get("candidate_count", -1)):
        raise ValueError("dump candidate plan count drift")
    specs_json = json.dumps(
        specs,
        sort_keys=True,
        separators=(",", ":"),
    )
    specs_sha = hashlib.sha256(
        (specs_json + "\n").encode()
    ).hexdigest()
    if str(row.get("candidate_specs_json") or "") != specs_json:
        raise ValueError("dump candidate JSON drift")
    if _sha256(
        row.get("candidate_specs_sha256"),
        label="dump candidate specs",
    ) != specs_sha:
        raise ValueError("dump candidate specs SHA drift")
    if str(row.get("workflow") or "") != CANDIDATE_WORKFLOW:
        raise ValueError("dump candidate workflow drift")
    expected_inputs = {
        "geometry_run_id": str(geometry_run),
        "expected_geometry_artifact_digest": geometry_digest,
        "expected_geometry_handoff_sha256": geometry_handoff_sha,
        "candidate_specs_json": specs_json,
    }
    if row.get("inputs") != expected_inputs:
        raise ValueError("dump candidate input binding drift")
    for key, message in (
        ("candidate_selected", "candidate plan selects candidate"),
        ("dump_threshold_frozen", "candidate plan freezes threshold"),
        ("phase2_dump_detector_frozen", "candidate plan freezes detector"),
        ("outcome_labels_computed", "candidate plan contains outcomes"),
        ("workflow_dispatch_performed", "candidate plan dispatches workflow"),
    ):
        if row.get(key) is not False:
            raise ValueError(message)
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "geometry_completion_control_run_id": completion_run,
        "geometry_run_id": geometry_run,
        "geometry_artifact_digest": geometry_digest,
        "geometry_handoff_sha256": geometry_handoff_sha,
        "candidate_specs": specs,
        "candidate_specs_json": specs_json,
        "candidate_specs_sha256": specs_sha,
        "candidate_count": len(specs),
        "workflow": CANDIDATE_WORKFLOW,
        "inputs": expected_inputs,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_dump_candidate_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_DUMP_CANDIDATE_LAUNCH_VERSION:
        raise ValueError("dump candidate launch version changed")
    control = _positive_run_id(
        row.get("candidate_control_run_id"),
        label="dump candidate control run ID",
    )
    plan_run = _positive_run_id(
        row.get("candidate_plan_run_id"),
        label="dump candidate plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("candidate_plan_artifact_digest"),
        label="dump candidate plan artifact",
    )
    target = _positive_run_id(
        row.get("candidate_research_run_id"),
        label="dump candidate target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="dump candidate launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="dump candidate launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("dump candidate launch branch/HEAD drift")
    specs_sha = _sha256(
        row.get("candidate_specs_sha256"),
        label="dump candidate launch specs",
    )
    if int(row.get("candidate_count", -1)) <= 0:
        raise ValueError("dump candidate launch count is invalid")
    if int(row.get("target_runs_created", -1)) != 1:
        raise ValueError("dump candidate target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("dump candidate launcher unexpectedly waited")
    for key, message in (
        ("candidate_selected", "dump candidate launcher selects candidate"),
        ("dump_threshold_frozen", "dump candidate launcher freezes threshold"),
        ("phase2_dump_detector_frozen", "dump candidate launcher freezes detector"),
        ("outcome_labels_computed", "dump candidate launcher contains outcomes"),
    ):
        if row.get(key) is not False:
            raise ValueError(message)
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("dump candidate launch lacks dispatch proof")
    return {
        **row,
        "candidate_control_run_id": control,
        "candidate_plan_run_id": plan_run,
        "candidate_plan_artifact_digest": plan_digest,
        "candidate_research_run_id": target,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "candidate_specs_sha256": specs_sha,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_dump_candidate_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_DUMP_CANDIDATE_COMPLETION_VERSION
    ):
        raise ValueError("dump candidate completion version changed")
    control = _positive_run_id(
        row.get("candidate_completion_control_run_id"),
        label="dump candidate completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("candidate_launch_run_id"),
        label="dump candidate launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("candidate_launch_artifact_digest"),
        label="dump candidate launch artifact",
    )
    target = _positive_run_id(
        row.get("candidate_research_run_id"),
        label="completed dump candidate run ID",
    )
    artifact_digest = _artifact_digest(
        row.get("candidate_research_artifact_digest"),
        label="dump candidate research artifact",
    )
    handoff_artifact_digest = _artifact_digest(
        row.get("candidate_research_handoff_artifact_digest"),
        label="dump candidate handoff artifact",
    )
    handoff_sha = _sha256(
        row.get("candidate_research_handoff_sha256"),
        label="dump candidate handoff",
    )
    specs_sha = _sha256(
        row.get("candidate_specs_sha256"),
        label="dump candidate completion specs",
    )
    rows_sha = _sha256(
        row.get("candidate_rows_sha256"),
        label="dump candidate rows",
    )
    summary_sha = _sha256(
        row.get("candidate_summary_sha256"),
        label="dump candidate summary",
    )
    candidate_count = int(row.get("candidate_count", -1))
    tokens = int(row.get("tokens", -1))
    candidate_rows = int(row.get("candidate_rows", -1))
    if candidate_count <= 0 or tokens <= 0:
        raise ValueError("dump candidate completion dimensions are invalid")
    if candidate_rows != candidate_count * tokens:
        raise ValueError("dump candidate completion row count drift")
    diagnostics_inputs = {
        "candidate_research_run_id": str(target),
        "expected_candidate_artifact_digest": artifact_digest,
        "expected_candidate_handoff_sha256": handoff_sha,
    }
    if row.get("diagnostics_inputs") != diagnostics_inputs:
        raise ValueError("dump diagnostics input binding drift")
    if row.get("target_run_completed") is not True:
        raise ValueError("dump candidate target is not completed")
    if row.get("target_run_successful") is not True:
        raise ValueError("dump candidate target is not successful")
    if row.get("uses_price_path_only") is not True:
        raise ValueError("dump candidate research is not price-path only")
    if row.get("point_in_time_confirmation") is not True:
        raise ValueError("dump candidate research is not point-in-time")
    for key, message in (
        ("candidate_selected", "dump candidate completion selects candidate"),
        ("dump_threshold_frozen", "dump candidate completion freezes threshold"),
        ("phase2_dump_detector_frozen", "dump candidate completion freezes detector"),
        ("outcome_labels_computed", "dump candidate completion contains outcomes"),
        ("workflow_dispatch_performed", "dump candidate completion dispatches workflow"),
    ):
        if row.get(key) is not False:
            raise ValueError(message)
    return {
        **row,
        "candidate_completion_control_run_id": control,
        "candidate_launch_run_id": launch_run,
        "candidate_launch_artifact_digest": launch_digest,
        "candidate_research_run_id": target,
        "candidate_research_artifact_digest": artifact_digest,
        "candidate_research_handoff_artifact_digest": handoff_artifact_digest,
        "candidate_research_handoff_sha256": handoff_sha,
        "candidate_specs_sha256": specs_sha,
        "candidate_rows_sha256": rows_sha,
        "candidate_summary_sha256": summary_sha,
        "candidate_count": candidate_count,
        "tokens": tokens,
        "candidate_rows": candidate_rows,
        "diagnostics_inputs": diagnostics_inputs,
        "target_run_completed": True,
        "target_run_successful": True,
        "uses_price_path_only": True,
        "point_in_time_confirmation": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }
