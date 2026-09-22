"""Compatibility checks for the narrow Phase-2 default-branch bootstrap."""

from __future__ import annotations

import hashlib
from typing import Mapping

from hlp.data.phase2_dispatch_readiness import (
    PHASE2_PLANNER_WORKFLOW,
    required_phase2_manual_workflows,
    workflow_dispatch_interface_sha256,
)


PHASE2_BOOTSTRAP_READINESS_VERSION = (
    "phase2-bootstrap-workflow-compatibility-v1"
)
PHASE2_BOOTSTRAP_BRANCH = "phase2/workflow-dispatch-bootstrap"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text).encode()).hexdigest()


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def strip_automatic_workflow_triggers(text: str) -> str:
    """Remove top-level push/pull_request event blocks and nothing else."""

    lines = str(text).splitlines()
    output = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line in {"  push:", "  pull_request:"}:
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate and _indent(candidate) <= 2:
                    break
                index += 1
            continue
        output.append(line)
        index += 1
    result = "\n".join(output)
    if str(text).endswith("\n"):
        result += "\n"
    return result


def _automatic_triggers(text: str) -> list[str]:
    triggers = []
    for line in str(text).splitlines():
        if line == "  push:":
            triggers.append("push")
        elif line == "  pull_request:":
            triggers.append("pull_request")
    return triggers


def evaluate_phase2_bootstrap_readiness(
    expected_workflow_text_by_name: Mapping[str, str],
    bootstrap_workflow_text_by_name: Mapping[str, str],
) -> dict:
    """Prove the bootstrap surface is exact and manual-interface compatible."""

    required = required_phase2_manual_workflows()
    required_set = set(required)
    expected_names = set(expected_workflow_text_by_name)
    bootstrap_names = set(bootstrap_workflow_text_by_name)

    missing_expected = sorted(required_set - expected_names)
    if missing_expected:
        raise ValueError(
            "working branch lacks required Phase-2 workflow text: "
            f"{missing_expected}"
        )

    missing = sorted(required_set - bootstrap_names)
    extra = sorted(bootstrap_names - required_set)
    present = sorted(required_set & bootstrap_names)

    interface_mismatches = []
    exact_content_mismatches = []
    automatic_trigger_workflows = []

    for name in present:
        expected = str(expected_workflow_text_by_name[name])
        actual = str(bootstrap_workflow_text_by_name[name])

        if workflow_dispatch_interface_sha256(
            expected
        ) != workflow_dispatch_interface_sha256(actual):
            interface_mismatches.append(name)

        triggers = _automatic_triggers(actual)
        if triggers:
            automatic_trigger_workflows.append({
                "workflow": name,
                "triggers": triggers,
            })

        if name == PHASE2_PLANNER_WORKFLOW:
            expected_manual = strip_automatic_workflow_triggers(expected)
            if actual != expected_manual:
                exact_content_mismatches.append(name)
        elif actual != expected:
            exact_content_mismatches.append(name)

    exact_matches = len(
        [
            name
            for name in present
            if name not in exact_content_mismatches
        ]
    )

    ready = not (
        missing
        or extra
        or interface_mismatches
        or exact_content_mismatches
        or automatic_trigger_workflows
    )
    return {
        "version": PHASE2_BOOTSTRAP_READINESS_VERSION,
        "bootstrap_branch": PHASE2_BOOTSTRAP_BRANCH,
        "required_workflows": len(required),
        "present_required_workflows": len(present),
        "exact_or_allowed_variant_workflows": exact_matches,
        "missing_workflow_names": missing,
        "extra_phase2_workflow_names": extra,
        "dispatch_interface_mismatch_workflow_names": sorted(
            interface_mismatches
        ),
        "content_mismatch_workflow_names": sorted(
            exact_content_mismatches
        ),
        "automatic_trigger_workflows": automatic_trigger_workflows,
        "planner_trigger_removal_is_only_allowed_content_variant": True,
        "all_bootstrap_workflows_manual_only": (
            not automatic_trigger_workflows
        ),
        "bootstrap_dispatch_surface_ready": ready,
    }
