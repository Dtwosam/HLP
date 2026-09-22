from pathlib import Path

import pytest

from hlp.data.phase2_bootstrap_readiness import (
    PHASE2_BOOTSTRAP_READINESS_VERSION,
    PHASE2_PLANNER_WORKFLOW,
    evaluate_phase2_bootstrap_readiness,
    strip_automatic_workflow_triggers,
)
from hlp.data.phase2_dispatch_readiness import (
    required_phase2_manual_workflows,
)


MANUAL = """name: manual
on:
  workflow_dispatch:

permissions:
  contents: read
"""
PLANNER = """name: planner
on:
  workflow_dispatch:
    inputs:
      completed:
        required: false
        type: string
  push:
    branches:
      - phase1/data-acquisition-spike
  pull_request:
    paths:
      - '.github/workflows/**'

permissions:
  contents: read
"""


def surfaces():
    expected = {
        name: MANUAL
        for name in required_phase2_manual_workflows()
    }
    expected[PHASE2_PLANNER_WORKFLOW] = PLANNER
    bootstrap = dict(expected)
    bootstrap[PHASE2_PLANNER_WORKFLOW] = (
        strip_automatic_workflow_triggers(PLANNER)
    )
    return expected, bootstrap


def test_strip_automatic_triggers_preserves_manual_contract_and_jobs():
    stripped = strip_automatic_workflow_triggers(PLANNER)

    assert "workflow_dispatch:" in stripped
    assert "\n  push:" not in stripped
    assert "\n  pull_request:" not in stripped
    assert "permissions:" in stripped


def test_bootstrap_readiness_accepts_exact_surface_and_planner_variant():
    expected, bootstrap = surfaces()
    assert "phase2-archive-fanout-completion.yml" in expected
    assert "phase2-post-fanout-wave-launch.yml" in expected
    report = evaluate_phase2_bootstrap_readiness(
        expected,
        bootstrap,
    )

    assert report["version"] == PHASE2_BOOTSTRAP_READINESS_VERSION
    assert report["required_workflows"] == len(expected)
    assert report["missing_workflow_names"] == []
    assert report["extra_phase2_workflow_names"] == []
    assert report["dispatch_interface_mismatch_workflow_names"] == []
    assert report["content_mismatch_workflow_names"] == []
    assert report["automatic_trigger_workflows"] == []
    assert report["bootstrap_dispatch_surface_ready"] is True


def test_bootstrap_readiness_rejects_missing_or_extra_workflow():
    expected, bootstrap = surfaces()
    missing = next(
        name for name in bootstrap
        if name != PHASE2_PLANNER_WORKFLOW
    )
    bootstrap.pop(missing)
    bootstrap["phase2-stale-bootstrap-only.yml"] = MANUAL
    report = evaluate_phase2_bootstrap_readiness(
        expected,
        bootstrap,
    )

    assert report["bootstrap_dispatch_surface_ready"] is False
    assert report["missing_workflow_names"] == [missing]
    assert report["extra_phase2_workflow_names"] == [
        "phase2-stale-bootstrap-only.yml"
    ]


def test_bootstrap_readiness_rejects_manual_interface_drift():
    expected, bootstrap = surfaces()
    target = next(
        name for name in bootstrap
        if name != PHASE2_PLANNER_WORKFLOW
    )
    bootstrap[target] = MANUAL.replace(
        "workflow_dispatch:",
        "workflow_dispatch:\n    inputs:\n      drift:\n"
        "        required: false\n        type: string",
    )
    report = evaluate_phase2_bootstrap_readiness(
        expected,
        bootstrap,
    )

    assert report["bootstrap_dispatch_surface_ready"] is False
    assert report["dispatch_interface_mismatch_workflow_names"] == [
        target
    ]


def test_bootstrap_readiness_rejects_non_planner_content_drift():
    expected, bootstrap = surfaces()
    target = next(
        name for name in bootstrap
        if name != PHASE2_PLANNER_WORKFLOW
    )
    bootstrap[target] += "# drift\n"
    report = evaluate_phase2_bootstrap_readiness(
        expected,
        bootstrap,
    )

    assert report["bootstrap_dispatch_surface_ready"] is False
    assert report["content_mismatch_workflow_names"] == [target]


def test_bootstrap_readiness_rejects_automatic_trigger_or_planner_job_drift():
    expected, bootstrap = surfaces()
    target = next(
        name for name in bootstrap
        if name != PHASE2_PLANNER_WORKFLOW
    )
    bootstrap[target] = MANUAL.replace(
        "permissions:",
        "  push:\n\npermissions:",
    )
    bootstrap[PHASE2_PLANNER_WORKFLOW] += "# extra planner drift\n"
    report = evaluate_phase2_bootstrap_readiness(
        expected,
        bootstrap,
    )

    assert report["bootstrap_dispatch_surface_ready"] is False
    assert report["automatic_trigger_workflows"] == [
        {"workflow": target, "triggers": ["push"]}
    ]
    assert PHASE2_PLANNER_WORKFLOW in report[
        "content_mismatch_workflow_names"
    ]



BOOTSTRAP_WORKFLOW = Path(
    ".github/workflows/phase2-bootstrap-workflow-compatibility.yml"
)


def test_bootstrap_compatibility_workflow_binds_exact_inspected_surface():
    text = BOOTSTRAP_WORKFLOW.read_text()

    assert "bootstrap_head_sha" in text
    assert "bootstrap_workflow_surface_sha256" in text
    assert "surface_hasher = hashlib.sha256()" in text
    assert "surface_sha256=" in text
    assert "exact_or_allowed_variant_workflows" in text
    assert "Enforce bootstrap compatibility" in text
