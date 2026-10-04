"""Immutable Phase-2 universe-freeze dispatch planning and launch receipts."""

from __future__ import annotations

import json
from typing import Mapping

from hlp.data.phase2_eligibility_dispatch import (
    LAUNCHPAD_SOURCES,
    validate_phase2_eligibility_wave_completion_receipt,
)


PHASE2_UNIVERSE_FREEZE_DISPATCH_PLAN_VERSION = (
    "phase2-universe-freeze-dispatch-plan-v1"
)
PHASE2_UNIVERSE_FREEZE_LAUNCH_RECEIPT_VERSION = (
    "phase2-universe-freeze-launch-receipt-v1"
)
UNIVERSE_FREEZE_WORKFLOW = "phase2-universe-freeze.yml"
UNIVERSE_FREEZE_INPUT_NAMES = frozenset({
    "launchpad_handoffs_json",
    "direct_run_id",
    "expected_direct_artifact_digest",
    "expected_direct_handoff_sha256",
    "exclusion_run_id",
    "expected_exclusion_artifact_digest",
    "expected_exclusion_summary_sha256",
})


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


def build_phase2_universe_freeze_dispatch_plan(
    eligibility_completion: Mapping[str, object],
    exclusion_binding: Mapping[str, object],
) -> dict:
    """Bind all verified universe inputs without dispatching the freeze."""

    completion = validate_phase2_eligibility_wave_completion_receipt(
        eligibility_completion
    )
    exclusion = dict(exclusion_binding)
    exclusion_run_id = _positive_run_id(
        exclusion.get("run_id"),
        label="exclusion registry run ID",
    )
    exclusion_digest = _artifact_digest(
        exclusion.get("artifact_digest"),
        label="exclusion registry artifact digest",
    )
    exclusion_summary_sha = _sha256(
        exclusion.get("summary_sha256"),
        label="exclusion registry summary",
    )
    if str(exclusion.get("artifact_name") or "") != (
        "phase2-exclusion-registry"
    ):
        raise ValueError("exclusion registry artifact name drift")
    if exclusion.get("registry_acceptance_ready") is not True:
        raise ValueError("exclusion registry is not acceptance-ready")
    if exclusion.get("phase2_universe_frozen") is not False:
        raise ValueError("exclusion registry prematurely freezes universe")

    launchpads = completion["launchpad_handoffs"]
    launchpad_json = json.dumps(
        launchpads,
        sort_keys=True,
        separators=(",", ":"),
    )
    direct = completion["direct_handoff"]
    inputs = {
        "launchpad_handoffs_json": launchpad_json,
        "direct_run_id": str(direct["run_id"]),
        "expected_direct_artifact_digest": direct["artifact_digest"],
        "expected_direct_handoff_sha256": direct["handoff_sha256"],
        "exclusion_run_id": str(exclusion_run_id),
        "expected_exclusion_artifact_digest": exclusion_digest,
        "expected_exclusion_summary_sha256": exclusion_summary_sha,
    }
    return {
        "version": PHASE2_UNIVERSE_FREEZE_DISPATCH_PLAN_VERSION,
        "workflow": UNIVERSE_FREEZE_WORKFLOW,
        "inputs": inputs,
        "eligibility_completion_control_run_id": completion[
            "eligibility_completion_control_run_id"
        ],
        "execution_branch": completion["execution_branch"],
        "execution_head_sha": completion["execution_head_sha"],
        "canonical_ledger_commit_sha": completion[
            "canonical_ledger_commit_sha"
        ],
        "launchpad_handoffs": launchpads,
        "direct_handoff": direct,
        "exclusion_binding": {
            "run_id": exclusion_run_id,
            "artifact_name": "phase2-exclusion-registry",
            "artifact_digest": exclusion_digest,
            "summary_sha256": exclusion_summary_sha,
        },
        "phase2_universe_coverage_complete": True,
        "phase2_universe_sources_ready": True,
        "phase2_universe_frozen": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_universe_freeze_dispatch_plan(
    plan: Mapping[str, object],
) -> dict:
    """Validate exact freeze inputs and immutable source identities."""

    row = dict(plan)
    if str(row.get("version") or "") != (
        PHASE2_UNIVERSE_FREEZE_DISPATCH_PLAN_VERSION
    ):
        raise ValueError("Phase-2 universe-freeze plan version changed")
    if str(row.get("workflow") or "") != UNIVERSE_FREEZE_WORKFLOW:
        raise ValueError("Phase-2 universe-freeze workflow drift")
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("Phase-2 universe-freeze plan branch is empty")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="universe-freeze plan execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="universe-freeze plan canonical ledger commit",
    )
    if head != canonical:
        raise ValueError(
            "universe-freeze plan canonical commit is not execution HEAD"
        )
    completion_run_id = _positive_run_id(
        row.get("eligibility_completion_control_run_id"),
        label="universe-freeze eligibility completion run ID",
    )

    raw_launchpads = row.get("launchpad_handoffs")
    if not isinstance(raw_launchpads, Mapping):
        raise ValueError("universe-freeze launchpad handoffs are missing")
    if set(raw_launchpads) != set(LAUNCHPAD_SOURCES):
        raise ValueError("universe-freeze launchpad handoff set drift")
    launchpads = {}
    for source in LAUNCHPAD_SOURCES:
        raw = raw_launchpads[source]
        if not isinstance(raw, Mapping):
            raise ValueError(f"{source} universe-freeze handoff is invalid")
        item = dict(raw)
        launchpads[source] = {
            "run_id": _positive_run_id(
                item.get("run_id"),
                label=f"{source} universe-freeze run ID",
            ),
            "artifact_digest": _artifact_digest(
                item.get("artifact_digest"),
                label=f"{source} universe-freeze artifact",
            ),
            "summary_sha256": _sha256(
                item.get("summary_sha256"),
                label=f"{source} universe-freeze summary",
            ),
        }

    raw_direct = row.get("direct_handoff")
    if not isinstance(raw_direct, Mapping):
        raise ValueError("universe-freeze direct handoff is missing")
    direct = dict(raw_direct)
    direct_handoff = {
        "run_id": _positive_run_id(
            direct.get("run_id"),
            label="universe-freeze direct run ID",
        ),
        "artifact_digest": _artifact_digest(
            direct.get("artifact_digest"),
            label="universe-freeze direct artifact",
        ),
        "handoff_sha256": _sha256(
            direct.get("handoff_sha256"),
            label="universe-freeze direct handoff",
        ),
    }

    raw_exclusion = row.get("exclusion_binding")
    if not isinstance(raw_exclusion, Mapping):
        raise ValueError("universe-freeze exclusion binding is missing")
    exclusion = dict(raw_exclusion)
    if str(exclusion.get("artifact_name") or "") != (
        "phase2-exclusion-registry"
    ):
        raise ValueError("universe-freeze exclusion artifact name drift")
    exclusion_binding = {
        "run_id": _positive_run_id(
            exclusion.get("run_id"),
            label="universe-freeze exclusion run ID",
        ),
        "artifact_name": "phase2-exclusion-registry",
        "artifact_digest": _artifact_digest(
            exclusion.get("artifact_digest"),
            label="universe-freeze exclusion artifact",
        ),
        "summary_sha256": _sha256(
            exclusion.get("summary_sha256"),
            label="universe-freeze exclusion summary",
        ),
    }

    raw_inputs = row.get("inputs")
    if not isinstance(raw_inputs, Mapping):
        raise ValueError("universe-freeze dispatch inputs are missing")
    inputs = dict(raw_inputs)
    if set(inputs) != UNIVERSE_FREEZE_INPUT_NAMES:
        raise ValueError("universe-freeze dispatch-input set drift")
    expected_launchpads_json = json.dumps(
        launchpads,
        sort_keys=True,
        separators=(",", ":"),
    )
    if str(inputs["launchpad_handoffs_json"]) != expected_launchpads_json:
        raise ValueError("universe-freeze launchpad JSON drift")
    expected_inputs = {
        "launchpad_handoffs_json": expected_launchpads_json,
        "direct_run_id": str(direct_handoff["run_id"]),
        "expected_direct_artifact_digest": direct_handoff[
            "artifact_digest"
        ],
        "expected_direct_handoff_sha256": direct_handoff[
            "handoff_sha256"
        ],
        "exclusion_run_id": str(exclusion_binding["run_id"]),
        "expected_exclusion_artifact_digest": exclusion_binding[
            "artifact_digest"
        ],
        "expected_exclusion_summary_sha256": exclusion_binding[
            "summary_sha256"
        ],
    }
    if inputs != expected_inputs:
        raise ValueError("universe-freeze dispatch input binding drift")
    if row.get("phase2_universe_coverage_complete") is not True:
        raise ValueError("universe-freeze plan lost 14/14 coverage proof")
    if row.get("phase2_universe_sources_ready") is not True:
        raise ValueError("universe-freeze plan sources are not ready")
    if row.get("phase2_universe_frozen") is not False:
        raise ValueError("universe-freeze plan prematurely freezes universe")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("universe-freeze plan is not read-only")

    return {
        **row,
        "workflow": UNIVERSE_FREEZE_WORKFLOW,
        "inputs": expected_inputs,
        "eligibility_completion_control_run_id": completion_run_id,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "launchpad_handoffs": launchpads,
        "direct_handoff": direct_handoff,
        "exclusion_binding": exclusion_binding,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_sources_ready": True,
        "phase2_universe_frozen": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_universe_freeze_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate the single-run dispatch receipt for universe freeze."""

    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_UNIVERSE_FREEZE_LAUNCH_RECEIPT_VERSION
    ):
        raise ValueError("Phase-2 universe-freeze launch version changed")
    control_run_id = _positive_run_id(
        row.get("universe_freeze_control_run_id"),
        label="universe-freeze control run ID",
    )
    plan_run_id = _positive_run_id(
        row.get("plan_run_id"),
        label="universe-freeze plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("plan_artifact_digest"),
        label="universe-freeze plan artifact digest",
    )
    target_run_id = _positive_run_id(
        row.get("universe_freeze_run_id"),
        label="universe-freeze target run ID",
    )
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("universe-freeze launch branch is empty")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="universe-freeze launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="universe-freeze launch canonical commit",
    )
    if head != canonical:
        raise ValueError(
            "universe-freeze launch canonical commit is not execution HEAD"
        )
    if row.get("phase2_universe_coverage_complete") is not True:
        raise ValueError("universe-freeze launch lost 14/14 coverage proof")
    if row.get("phase2_universe_sources_ready") is not True:
        raise ValueError("universe-freeze launch sources are not ready")
    if row.get("phase2_universe_frozen") is not False:
        raise ValueError("universe-freeze launcher claims freeze prematurely")
    if row.get("target_runs_created") != 1:
        raise ValueError("universe-freeze target-run count drift")
    if row.get("target_run_waited_for_completion") is not False:
        raise ValueError("universe-freeze launcher unexpectedly waited")
    if row.get("canonical_coverage_ledger_mutated") is not False:
        raise ValueError("universe-freeze launcher mutated coverage ledger")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("universe-freeze launch lacks dispatch proof")
    return {
        **row,
        "universe_freeze_control_run_id": control_run_id,
        "plan_run_id": plan_run_id,
        "plan_artifact_digest": plan_digest,
        "universe_freeze_run_id": target_run_id,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_sources_ready": True,
        "phase2_universe_frozen": False,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "canonical_coverage_ledger_mutated": False,
        "workflow_dispatch_performed": True,
    }
