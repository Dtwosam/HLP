"""Default-branch workflow-surface readiness for Phase-2 manual execution."""

from __future__ import annotations

from typing import Iterable

from hlp.data.phase2_coverage_execution import (
    build_phase2_coverage_execution_nodes,
)


PHASE2_DEFAULT_BRANCH_READINESS_VERSION = (
    "phase2-default-branch-dispatch-readiness-v1"
)
PHASE2_PLANNER_WORKFLOW = "phase2-coverage-execution-plan.yml"
PHASE2_DYNAMIC_WORKFLOWS = (
    "phase2-source-coverage-promotion.yml",
    "phase2-source-coverage-ledger-commit.yml",
)
PHASE2_FIRST_WAVE_NODE_IDS = (
    "preflight:archive_authenticated",
    "shared:quote_registry",
)


def required_phase2_manual_workflows() -> list[str]:
    """Return every workflow path needed for coverage execution/planning."""

    names = {
        str(row["workflow"])
        for row in build_phase2_coverage_execution_nodes()
        if row.get("workflow")
    }
    names.update(PHASE2_DYNAMIC_WORKFLOWS)
    names.add(PHASE2_PLANNER_WORKFLOW)
    return sorted(names)


def _first_wave_workflows() -> list[str]:
    by_id = {
        str(row["node_id"]): str(row["workflow"])
        for row in build_phase2_coverage_execution_nodes()
    }
    return sorted(
        {
            by_id[node_id]
            for node_id in PHASE2_FIRST_WAVE_NODE_IDS
        }
    )


def evaluate_phase2_default_branch_readiness(
    available_workflow_names: Iterable[str],
    *,
    default_branch: str,
) -> dict:
    """Compare the default-branch workflow surface with the Phase-2 DAG."""

    branch = str(default_branch or "").strip()
    if not branch:
        raise ValueError("default branch is empty")

    available = {
        str(value).strip()
        for value in available_workflow_names
        if str(value).strip()
    }
    required = required_phase2_manual_workflows()
    first_wave = _first_wave_workflows()

    missing = sorted(set(required) - available)
    first_wave_missing = sorted(set(first_wave) - available)
    present = sorted(set(required) & available)

    return {
        "version": PHASE2_DEFAULT_BRANCH_READINESS_VERSION,
        "default_branch": branch,
        "required_manual_workflows": len(required),
        "present_required_workflows": len(present),
        "missing_required_workflows": len(missing),
        "required_workflow_names": required,
        "present_workflow_names": present,
        "missing_workflow_names": missing,
        "first_wave_workflow_names": first_wave,
        "first_wave_missing_workflow_names": first_wave_missing,
        "phase2_first_wave_dispatch_ready": not first_wave_missing,
        "phase2_full_coverage_dag_dispatch_ready": not missing,
        "default_branch_workflow_surface_checked": True,
        "phase2_coverage_state_mutated": False,
    }
