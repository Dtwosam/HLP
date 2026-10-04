"""Orchestration contracts for the Phase-2 research materialization wave."""

from __future__ import annotations

import json
from typing import Mapping

from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID
from hlp.data.phase2_research_rehydration import (
    PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION,
)
from hlp.data.phase2_research_source_layouts import (
    build_phase2_research_source_layouts,
    validate_phase2_research_source_layouts,
)
from hlp.data.phase2_sources import build_phase2_source_inventory
from hlp.data.phase2_universe_freeze_dispatch import (
    validate_phase2_universe_freeze_completion_receipt,
)


PHASE2_RESEARCH_MATERIALIZATION_DISPATCH_PLAN_VERSION = (
    "phase2-research-materialization-dispatch-plan-v1"
)
PHASE2_RESEARCH_MATERIALIZATION_WAVE_LAUNCH_VERSION = (
    "phase2-research-materialization-wave-launch-receipt-v1"
)
PHASE2_RESEARCH_MATERIALIZATION_WAVE_COMPLETION_VERSION = (
    "phase2-research-materialization-wave-completion-receipt-v1"
)

PONS_WORKFLOW = "phase2-research-materialize-pons.yml"
SIMPLE_WORKFLOW = "phase2-research-materialize-component.yml"
COMPOSITE_WORKFLOW = "phase2-research-materialize-composite.yml"

COMMON_INPUT_NAMES = frozenset({
    "rehydration_plan_run_id",
    "expected_plan_artifact_digest",
    "expected_plan_sha256",
    "universe_run_id",
    "expected_universe_artifact_digest",
    "expected_universe_handoff_sha256",
    "component_id",
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


def _validated_rehydration_plan(plan: Mapping[str, object]) -> dict:
    row = dict(plan)
    if str(row.get("version") or "") != (
        PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION
    ):
        raise ValueError("research rehydration plan version changed")
    snapshot = int(row.get("snapshot_head_block", 0))
    if snapshot <= 0:
        raise ValueError("research rehydration snapshot is invalid")
    universe_sha = _sha256(
        row.get("eligible_universe_sha256"),
        label="research rehydration universe",
    )
    if int(row.get("component_count", -1)) != 12:
        raise ValueError("research rehydration component count drift")
    if int(row.get("source_count", -1)) != 14:
        raise ValueError("research rehydration source count drift")
    launchpads = row.get("launchpad_bindings")
    if not isinstance(launchpads, Mapping) or len(launchpads) != 11:
        raise ValueError("research rehydration launchpad binding set drift")
    direct = row.get("direct_binding")
    if not isinstance(direct, Mapping):
        raise ValueError("research rehydration direct binding is missing")
    if str(direct.get("component_id") or "") != DIRECT_RESEARCH_COMPONENT_ID:
        raise ValueError("research rehydration direct component drift")
    if row.get("research_price_paths_materialized") is not False:
        raise ValueError("rehydration plan already materialized price paths")
    if row.get("dump_threshold_frozen") is not False:
        raise ValueError("rehydration plan freezes dump threshold")
    if row.get("outcome_labels_computed") is not False:
        raise ValueError("rehydration plan contains outcome labels")
    return {
        **row,
        "snapshot_head_block": snapshot,
        "eligible_universe_sha256": universe_sha,
    }


def _workflow_for_component(component_id: str, strategy: str) -> str:
    if strategy == "canonical_replay":
        if component_id not in {"pons_v1", "pons_v2"}:
            raise ValueError(
                f"unexpected canonical-replay component: {component_id}"
            )
        return PONS_WORKFLOW
    if strategy == "composite":
        return COMPOSITE_WORKFLOW
    if strategy in {
        "coverage_single",
        "coverage_sharded",
        "handoff_single",
    }:
        return SIMPLE_WORKFLOW
    raise ValueError(
        f"unsupported research materialization strategy: {strategy}"
    )


def build_phase2_research_materialization_dispatch_plan(
    rehydration_plan: Mapping[str, object],
    *,
    rehydration_plan_run_id: int,
    rehydration_plan_artifact_digest: str,
    rehydration_plan_sha256: str,
    universe_completion: Mapping[str, object],
) -> dict:
    """Build exact 12-component materializer dispatches."""

    plan = _validated_rehydration_plan(rehydration_plan)
    universe = validate_phase2_universe_freeze_completion_receipt(
        universe_completion
    )
    plan_run_id = _positive_run_id(
        rehydration_plan_run_id,
        label="rehydration plan run ID",
    )
    plan_digest = _artifact_digest(
        rehydration_plan_artifact_digest,
        label="rehydration plan artifact",
    )
    plan_sha = _sha256(
        rehydration_plan_sha256,
        label="rehydration plan file",
    )
    if plan["eligible_universe_sha256"] != universe[
        "eligible_universe_sha256"
    ]:
        raise ValueError("materialization plan universe SHA drift")
    if int(plan["snapshot_head_block"]) != int(
        universe["snapshot_head_block"]
    ):
        raise ValueError("materialization plan snapshot drift")

    layouts = build_phase2_research_source_layouts()
    validation = validate_phase2_research_source_layouts(
        layouts,
        build_phase2_source_inventory(),
    )
    if int(validation["components"]) != 12:
        raise ValueError("research source-layout component count drift")

    expected_components = (
        set(plan["launchpad_bindings"]) | {DIRECT_RESEARCH_COMPONENT_ID}
    )
    if set(layouts) != expected_components:
        raise ValueError("materialization plan/layout component set drift")

    common = {
        "rehydration_plan_run_id": str(plan_run_id),
        "expected_plan_artifact_digest": plan_digest,
        "expected_plan_sha256": plan_sha,
        "universe_run_id": str(universe["universe_freeze_run_id"]),
        "expected_universe_artifact_digest": universe[
            "universe_freeze_artifact_digest"
        ],
        "expected_universe_handoff_sha256": universe[
            "universe_freeze_handoff_sha256"
        ],
    }
    dispatches = []
    workflow_counts = {
        PONS_WORKFLOW: 0,
        SIMPLE_WORKFLOW: 0,
        COMPOSITE_WORKFLOW: 0,
    }
    for component_id in sorted(expected_components):
        layout = dict(layouts[component_id])
        workflow = _workflow_for_component(
            component_id,
            str(layout.get("strategy") or ""),
        )
        workflow_counts[workflow] += 1
        dispatches.append({
            "component_id": component_id,
            "workflow": workflow,
            "inputs": {
                **common,
                "component_id": component_id,
            },
        })

    if workflow_counts != {
        PONS_WORKFLOW: 2,
        SIMPLE_WORKFLOW: 7,
        COMPOSITE_WORKFLOW: 3,
    }:
        raise ValueError("research materialization workflow split drift")

    return {
        "version": PHASE2_RESEARCH_MATERIALIZATION_DISPATCH_PLAN_VERSION,
        "execution_branch": universe["execution_branch"],
        "execution_head_sha": universe["execution_head_sha"],
        "canonical_ledger_commit_sha": universe[
            "canonical_ledger_commit_sha"
        ],
        "rehydration_plan_run_id": plan_run_id,
        "rehydration_plan_artifact_digest": plan_digest,
        "rehydration_plan_sha256": plan_sha,
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
        "snapshot_head_block": universe["snapshot_head_block"],
        "component_dispatches": dispatches,
        "component_count": 12,
        "workflow_counts": workflow_counts,
        "research_price_paths_materialized": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_research_materialization_dispatch_plan(
    plan: Mapping[str, object],
) -> dict:
    """Validate the immutable 12-component materialization dispatch plan."""

    row = dict(plan)
    if str(row.get("version") or "") != (
        PHASE2_RESEARCH_MATERIALIZATION_DISPATCH_PLAN_VERSION
    ):
        raise ValueError("research materialization dispatch-plan version changed")
    branch = str(row.get("execution_branch") or "")
    if not branch:
        raise ValueError("research materialization branch is empty")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="research materialization execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="research materialization canonical commit",
    )
    if head != canonical:
        raise ValueError(
            "research materialization canonical commit is not execution HEAD"
        )
    plan_run_id = _positive_run_id(
        row.get("rehydration_plan_run_id"),
        label="research materialization plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("rehydration_plan_artifact_digest"),
        label="research materialization plan artifact",
    )
    plan_sha = _sha256(
        row.get("rehydration_plan_sha256"),
        label="research materialization plan file",
    )
    universe_run_id = _positive_run_id(
        row.get("universe_run_id"),
        label="research materialization universe run ID",
    )
    universe_digest = _artifact_digest(
        row.get("universe_artifact_digest"),
        label="research materialization universe artifact",
    )
    universe_handoff_sha = _sha256(
        row.get("universe_handoff_sha256"),
        label="research materialization universe handoff",
    )
    universe_sha = _sha256(
        row.get("eligible_universe_sha256"),
        label="research materialization universe",
    )
    if int(row.get("snapshot_head_block", 0)) <= 0:
        raise ValueError("research materialization snapshot is invalid")

    layouts = build_phase2_research_source_layouts()
    expected_components = set(layouts)
    raw_dispatches = row.get("component_dispatches")
    if not isinstance(raw_dispatches, list) or len(raw_dispatches) != 12:
        raise ValueError("research materialization dispatch count drift")
    normalized = []
    seen = set()
    counts = {PONS_WORKFLOW: 0, SIMPLE_WORKFLOW: 0, COMPOSITE_WORKFLOW: 0}
    for raw in raw_dispatches:
        if not isinstance(raw, Mapping):
            raise ValueError("research materialization dispatch is invalid")
        item = dict(raw)
        component_id = str(item.get("component_id") or "")
        if component_id not in expected_components or component_id in seen:
            raise ValueError(
                f"research materialization component drift: {component_id}"
            )
        seen.add(component_id)
        expected_workflow = _workflow_for_component(
            component_id,
            str(layouts[component_id]["strategy"]),
        )
        if str(item.get("workflow") or "") != expected_workflow:
            raise ValueError(
                f"{component_id} materializer workflow drift"
            )
        inputs_raw = item.get("inputs")
        if not isinstance(inputs_raw, Mapping):
            raise ValueError(f"{component_id} materializer inputs missing")
        inputs = dict(inputs_raw)
        if set(inputs) != COMMON_INPUT_NAMES:
            raise ValueError(
                f"{component_id} materializer input set drift"
            )
        expected_inputs = {
            "rehydration_plan_run_id": str(plan_run_id),
            "expected_plan_artifact_digest": plan_digest,
            "expected_plan_sha256": plan_sha,
            "universe_run_id": str(universe_run_id),
            "expected_universe_artifact_digest": universe_digest,
            "expected_universe_handoff_sha256": universe_handoff_sha,
            "component_id": component_id,
        }
        if inputs != expected_inputs:
            raise ValueError(
                f"{component_id} materializer input binding drift"
            )
        counts[expected_workflow] += 1
        normalized.append({
            "component_id": component_id,
            "workflow": expected_workflow,
            "inputs": expected_inputs,
        })
    if seen != expected_components:
        raise ValueError("research materialization component set drift")
    if counts != {
        PONS_WORKFLOW: 2,
        SIMPLE_WORKFLOW: 7,
        COMPOSITE_WORKFLOW: 3,
    }:
        raise ValueError("research materialization workflow split drift")
    if int(row.get("component_count", -1)) != 12:
        raise ValueError("research materialization component count drift")
    if row.get("workflow_counts") != counts:
        raise ValueError("research materialization workflow-count drift")
    if row.get("research_price_paths_materialized") is not False:
        raise ValueError("research materialization plan already materialized")
    if row.get("dump_threshold_frozen") is not False:
        raise ValueError("research materialization plan freezes threshold")
    if row.get("outcome_labels_computed") is not False:
        raise ValueError("research materialization plan contains outcomes")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("research materialization plan is not read-only")
    return {
        **row,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "rehydration_plan_run_id": plan_run_id,
        "rehydration_plan_artifact_digest": plan_digest,
        "rehydration_plan_sha256": plan_sha,
        "universe_run_id": universe_run_id,
        "universe_artifact_digest": universe_digest,
        "universe_handoff_sha256": universe_handoff_sha,
        "eligible_universe_sha256": universe_sha,
        "component_dispatches": sorted(
            normalized,
            key=lambda item: item["component_id"],
        ),
        "component_count": 12,
        "workflow_counts": counts,
        "research_price_paths_materialized": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def validate_phase2_research_materialization_wave_launch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_RESEARCH_MATERIALIZATION_WAVE_LAUNCH_VERSION
    ):
        raise ValueError("research materialization launch version changed")
    control = _positive_run_id(
        row.get("materialization_wave_control_run_id"),
        label="materialization-wave control run ID",
    )
    plan_run = _positive_run_id(
        row.get("dispatch_plan_run_id"),
        label="materialization dispatch-plan run ID",
    )
    plan_digest = _artifact_digest(
        row.get("dispatch_plan_artifact_digest"),
        label="materialization dispatch-plan artifact",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="materialization launch execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="materialization launch canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("materialization launch branch/HEAD drift")
    raw_runs = row.get("component_run_ids")
    if not isinstance(raw_runs, Mapping):
        raise ValueError("materialization launch component runs missing")
    expected = set(build_phase2_research_source_layouts())
    if set(raw_runs) != expected:
        raise ValueError("materialization launch component run set drift")
    runs = {
        component: _positive_run_id(
            raw_runs[component],
            label=f"{component} materialization target run ID",
        )
        for component in sorted(expected)
    }
    if len(set(runs.values())) != 12:
        raise ValueError("materialization target run IDs are not unique")
    if int(row.get("target_runs_created", -1)) != 12:
        raise ValueError("materialization launch target-run count drift")
    if row.get("target_runs_waited_for_completion") is not False:
        raise ValueError("materialization launcher unexpectedly waited")
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError("materialization launch lacks dispatch proof")
    return {
        **row,
        "materialization_wave_control_run_id": control,
        "dispatch_plan_run_id": plan_run,
        "dispatch_plan_artifact_digest": plan_digest,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "component_run_ids": runs,
        "target_runs_created": 12,
        "target_runs_waited_for_completion": False,
        "workflow_dispatch_performed": True,
    }


def validate_phase2_research_materialization_wave_completion_receipt(
    receipt: Mapping[str, object],
) -> dict:
    row = dict(receipt)
    if str(row.get("version") or "") != (
        PHASE2_RESEARCH_MATERIALIZATION_WAVE_COMPLETION_VERSION
    ):
        raise ValueError("research materialization completion version changed")
    control = _positive_run_id(
        row.get("materialization_completion_control_run_id"),
        label="materialization completion control run ID",
    )
    launch_run = _positive_run_id(
        row.get("materialization_wave_launch_run_id"),
        label="materialization launch run ID",
    )
    launch_digest = _artifact_digest(
        row.get("materialization_wave_launch_artifact_digest"),
        label="materialization launch artifact",
    )
    branch = str(row.get("execution_branch") or "")
    head = _commit_sha(
        row.get("execution_head_sha"),
        label="materialization completion execution head",
    )
    canonical = _commit_sha(
        row.get("canonical_ledger_commit_sha"),
        label="materialization completion canonical commit",
    )
    if not branch or head != canonical:
        raise ValueError("materialization completion branch/HEAD drift")
    raw_runs = row.get("component_run_ids")
    if not isinstance(raw_runs, Mapping):
        raise ValueError("materialization completion component runs missing")
    expected = set(build_phase2_research_source_layouts())
    if set(raw_runs) != expected:
        raise ValueError("materialization completion component set drift")
    runs = {
        component: _positive_run_id(
            raw_runs[component],
            label=f"{component} completed materializer run ID",
        )
        for component in sorted(expected)
    }
    if len(set(runs.values())) != 12:
        raise ValueError("materialization completion run IDs are not unique")
    expected_json = json.dumps(
        runs,
        sort_keys=True,
        separators=(",", ":"),
    )
    if str(row.get("component_runs_json") or "") != expected_json:
        raise ValueError("materialization component-runs JSON drift")
    if int(row.get("component_runs_completed", -1)) != 12:
        raise ValueError("materialization completion count drift")
    if row.get("all_component_runs_successful") is not True:
        raise ValueError("materialization completion lacks success proof")
    if row.get("research_components_ready") is not True:
        raise ValueError("materialization completion components not ready")
    if row.get("research_price_paths_materialized") is not False:
        raise ValueError("materialization completion prematurely joins paths")
    if row.get("dump_threshold_frozen") is not False:
        raise ValueError("materialization completion freezes threshold")
    if row.get("outcome_labels_computed") is not False:
        raise ValueError("materialization completion contains outcomes")
    if row.get("workflow_dispatch_performed") is not False:
        raise ValueError("materialization completion unexpectedly dispatches")
    return {
        **row,
        "materialization_completion_control_run_id": control,
        "materialization_wave_launch_run_id": launch_run,
        "materialization_wave_launch_artifact_digest": launch_digest,
        "execution_branch": branch,
        "execution_head_sha": head,
        "canonical_ledger_commit_sha": canonical,
        "component_run_ids": runs,
        "component_runs_json": expected_json,
        "component_runs_completed": 12,
        "all_component_runs_successful": True,
        "research_components_ready": True,
        "research_price_paths_materialized": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }
