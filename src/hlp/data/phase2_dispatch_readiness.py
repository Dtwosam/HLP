"""Default-branch workflow-surface readiness for Phase-2 manual execution."""

from __future__ import annotations

import hashlib
from typing import Iterable, Mapping

from hlp.data.phase2_coverage_execution import (
    build_phase2_coverage_execution_nodes,
)


PHASE2_DEFAULT_BRANCH_READINESS_VERSION = (
    "phase2-default-branch-dispatch-readiness-v2"
)
PHASE2_PLANNER_WORKFLOW = "phase2-coverage-execution-plan.yml"
PHASE2_DYNAMIC_WORKFLOWS = (
    "phase2-source-coverage-promotion.yml",
    "phase2-source-coverage-ledger-commit.yml",
    "phase2-execution-node-dispatch.yml",
    "phase2-first-wave-launch.yml",
    "phase2-archive-fanout-launch.yml",
    "phase2-archive-fanout-completion.yml",
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


def workflow_dispatch_interface_text(text: str) -> str:
    """Return a normalized workflow_dispatch block including all inputs."""

    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    start = None
    for index, line in enumerate(lines):
        if line.rstrip() == "  workflow_dispatch:":
            start = index
            break
    if start is None:
        raise ValueError("workflow has no workflow_dispatch event")

    selected = []
    for index in range(start, len(lines)):
        line = lines[index].rstrip()
        if index > start and line:
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)
            if indent <= 2:
                break
        selected.append(line)

    while selected and not selected[-1]:
        selected.pop()
    if not selected:
        raise ValueError("workflow_dispatch block is empty")
    return "\n".join(selected) + "\n"


def workflow_dispatch_interface_sha256(text: str) -> str:
    """Hash only the manual-dispatch contract, not unrelated triggers/jobs."""

    return hashlib.sha256(
        workflow_dispatch_interface_text(text).encode()
    ).hexdigest()


def _digest_map(
    value: Mapping[str, object],
    *,
    label: str,
) -> dict[str, str]:
    output = {}
    for raw_name, raw_digest in value.items():
        name = str(raw_name or "").strip()
        digest = str(raw_digest or "").lower().removeprefix("sha256:")
        if not name:
            raise ValueError(f"{label} contains an empty workflow name")
        if len(digest) != 64:
            raise ValueError(
                f"{label} digest for {name} must be 64 hex chars"
            )
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError(
                f"{label} digest for {name} is not hexadecimal"
            ) from exc
        output[name] = digest
    return output


def evaluate_phase2_default_branch_readiness(
    available_workflow_names: Iterable[str],
    *,
    default_branch: str,
    expected_dispatch_interface_sha256_by_name: Mapping[str, object],
    available_dispatch_interface_sha256_by_name: Mapping[str, object],
) -> dict:
    """Compare default-branch names and manual interfaces with the DAG."""

    branch = str(default_branch or "").strip()
    if not branch:
        raise ValueError("default branch is empty")

    available = {
        str(value).strip()
        for value in available_workflow_names
        if str(value).strip()
    }
    required = required_phase2_manual_workflows()
    required_set = set(required)
    first_wave = _first_wave_workflows()

    expected_digests = _digest_map(
        expected_dispatch_interface_sha256_by_name,
        label="expected dispatch-interface",
    )
    available_digests = _digest_map(
        available_dispatch_interface_sha256_by_name,
        label="default-branch dispatch-interface",
    )
    missing_expected = sorted(required_set - set(expected_digests))
    if missing_expected:
        raise ValueError(
            "expected dispatch-interface digests are missing required "
            f"workflows: {missing_expected}"
        )

    missing = sorted(required_set - available)
    present = sorted(required_set & available)
    missing_available_digest = sorted(
        set(present) - set(available_digests)
    )
    if missing_available_digest:
        raise ValueError(
            "default-branch dispatch-interface digests are missing present "
            f"required workflows: {missing_available_digest}"
        )

    incompatible = sorted(
        name
        for name in present
        if available_digests[name] != expected_digests[name]
    )
    compatible = sorted(set(present) - set(incompatible))
    first_wave_missing = sorted(set(first_wave) - available)
    first_wave_incompatible = sorted(
        set(first_wave) & set(incompatible)
    )

    return {
        "version": PHASE2_DEFAULT_BRANCH_READINESS_VERSION,
        "default_branch": branch,
        "required_manual_workflows": len(required),
        "present_required_workflows": len(present),
        "compatible_required_workflows": len(compatible),
        "missing_required_workflows": len(missing),
        "incompatible_required_workflows": len(incompatible),
        "required_workflow_names": required,
        "present_workflow_names": present,
        "compatible_workflow_names": compatible,
        "missing_workflow_names": missing,
        "incompatible_workflow_names": incompatible,
        "first_wave_workflow_names": first_wave,
        "first_wave_missing_workflow_names": first_wave_missing,
        "first_wave_incompatible_workflow_names": (
            first_wave_incompatible
        ),
        "phase2_first_wave_dispatch_ready": (
            not first_wave_missing
            and not first_wave_incompatible
        ),
        "phase2_full_coverage_dag_dispatch_ready": (
            not missing and not incompatible
        ),
        "default_branch_workflow_surface_checked": True,
        "dispatch_interface_compatibility_checked": True,
        "phase2_coverage_state_mutated": False,
    }
