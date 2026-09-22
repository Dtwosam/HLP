from hlp.data.phase2_dispatch_readiness import (
    PHASE2_DEFAULT_BRANCH_READINESS_VERSION,
    PHASE2_DYNAMIC_WORKFLOWS,
    PHASE2_PLANNER_WORKFLOW,
    evaluate_phase2_default_branch_readiness,
    required_phase2_manual_workflows,
    workflow_dispatch_interface_sha256,
)


DIGEST = "ab" * 32
OTHER_DIGEST = "cd" * 32


def mappings(available):
    required = required_phase2_manual_workflows()
    return (
        {name: DIGEST for name in required},
        {name: DIGEST for name in available},
    )


def evaluate(available, *, available_digests=None):
    expected, default = mappings(available)
    if available_digests is not None:
        default.update(available_digests)
    return evaluate_phase2_default_branch_readiness(
        available,
        default_branch="main",
        expected_dispatch_interface_sha256_by_name=expected,
        available_dispatch_interface_sha256_by_name=default,
    )


def test_required_workflows_cover_planner_and_dynamic_gates():
    required = required_phase2_manual_workflows()

    assert PHASE2_PLANNER_WORKFLOW in required
    for workflow in PHASE2_DYNAMIC_WORKFLOWS:
        assert workflow in required
    assert "phase2-archive-rpc-preflight.yml" in required
    assert "phase2-direct-quote-registry.yml" in required
    assert "phase2-direct-source-coverage.yml" in required
    assert "phase2-execution-node-dispatch.yml" in required
    assert "phase2-first-wave-launch.yml" in required
    assert "phase2-after-post-fanout-wave-launch.yml" in required
    assert "phase2-after-post-fanout-wave-completion.yml" in required
    assert "phase2-pre-selector-wave-launch.yml" in required
    assert "phase2-pre-selector-wave-completion.yml" in required
    assert "phase2-direct-selector-approval-handoff.yml" in required
    assert "phase2-direct-selector-approved-freeze.yml" in required
    assert "phase2-post-selector-wave-launch.yml" in required
    assert "phase2-post-selector-wave-completion.yml" in required
    assert "phase2-direct-coverage-wave-launch.yml" in required
    assert "phase2-direct-coverage-wave-completion.yml" in required
    assert "phase2-archive-fanout-launch.yml" in required
    assert "phase2-archive-fanout-completion.yml" in required
    assert "phase2-post-fanout-wave-launch.yml" in required
    assert "phase2-post-fanout-wave-completion.yml" in required


def test_dispatch_interface_digest_ignores_unrelated_trigger_changes():
    base = """name: x

on:
  workflow_dispatch:
    inputs:
      run_id:
        required: true
        type: string
  push:

jobs:
  x:
    runs-on: ubuntu-latest
"""
    manual_only = """name: x

on:
  workflow_dispatch:
    inputs:
      run_id:
        required: true
        type: string

permissions:
  contents: read
"""
    assert workflow_dispatch_interface_sha256(base) == (
        workflow_dispatch_interface_sha256(manual_only)
    )


def test_dispatch_interface_digest_changes_when_inputs_change():
    before = """on:
  workflow_dispatch:
    inputs:
      run_id:
        required: true
        type: string
"""
    after = """on:
  workflow_dispatch:
    inputs:
      run_id:
        required: false
        type: string
"""
    assert workflow_dispatch_interface_sha256(before) != (
        workflow_dispatch_interface_sha256(after)
    )


def test_default_branch_readiness_fails_closed_when_surface_missing():
    report = evaluate([])

    assert report["version"] == PHASE2_DEFAULT_BRANCH_READINESS_VERSION
    assert report["default_branch"] == "main"
    assert report["present_required_workflows"] == 0
    assert report["compatible_required_workflows"] == 0
    assert report["missing_required_workflows"] == (
        report["required_manual_workflows"]
    )
    assert report["incompatible_required_workflows"] == 0
    assert report["phase2_first_wave_dispatch_ready"] is False
    assert report["phase2_full_coverage_dag_dispatch_ready"] is False
    assert report["dispatch_interface_compatibility_checked"] is True
    assert report["phase2_coverage_state_mutated"] is False


def test_first_wave_can_be_ready_before_full_dag():
    available = [
        "phase2-archive-rpc-preflight.yml",
        "phase2-direct-quote-registry.yml",
    ]
    report = evaluate(available)

    assert report["phase2_first_wave_dispatch_ready"] is True
    assert report["phase2_full_coverage_dag_dispatch_ready"] is False
    assert report["first_wave_missing_workflow_names"] == []
    assert report["first_wave_incompatible_workflow_names"] == []


def test_first_wave_rejects_stale_dispatch_interface():
    available = [
        "phase2-archive-rpc-preflight.yml",
        "phase2-direct-quote-registry.yml",
    ]
    report = evaluate(
        available,
        available_digests={
            "phase2-direct-quote-registry.yml": OTHER_DIGEST,
        },
    )

    assert report["phase2_first_wave_dispatch_ready"] is False
    assert report["first_wave_incompatible_workflow_names"] == [
        "phase2-direct-quote-registry.yml"
    ]


def test_full_surface_requires_compatible_dispatch_interfaces():
    required = required_phase2_manual_workflows()
    report = evaluate(required)

    assert report["phase2_first_wave_dispatch_ready"] is True
    assert report["phase2_full_coverage_dag_dispatch_ready"] is True
    assert report["missing_workflow_names"] == []
    assert report["incompatible_workflow_names"] == []

    stale = evaluate(
        required,
        available_digests={
            PHASE2_PLANNER_WORKFLOW: OTHER_DIGEST,
        },
    )
    assert stale["phase2_full_coverage_dag_dispatch_ready"] is False
    assert stale["incompatible_workflow_names"] == [
        PHASE2_PLANNER_WORKFLOW
    ]
