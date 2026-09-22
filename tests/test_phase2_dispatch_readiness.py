from hlp.data.phase2_dispatch_readiness import (
    PHASE2_DEFAULT_BRANCH_READINESS_VERSION,
    PHASE2_DYNAMIC_WORKFLOWS,
    PHASE2_PLANNER_WORKFLOW,
    evaluate_phase2_default_branch_readiness,
    required_phase2_manual_workflows,
)


def test_required_workflows_cover_planner_and_dynamic_gates():
    required = required_phase2_manual_workflows()

    assert PHASE2_PLANNER_WORKFLOW in required
    for workflow in PHASE2_DYNAMIC_WORKFLOWS:
        assert workflow in required
    assert "phase2-archive-rpc-preflight.yml" in required
    assert "phase2-direct-quote-registry.yml" in required
    assert "phase2-direct-source-coverage.yml" in required


def test_default_branch_readiness_fails_closed_when_surface_missing():
    report = evaluate_phase2_default_branch_readiness(
        [],
        default_branch="main",
    )

    assert report["version"] == PHASE2_DEFAULT_BRANCH_READINESS_VERSION
    assert report["default_branch"] == "main"
    assert report["present_required_workflows"] == 0
    assert report["missing_required_workflows"] == (
        report["required_manual_workflows"]
    )
    assert report["phase2_first_wave_dispatch_ready"] is False
    assert report["phase2_full_coverage_dag_dispatch_ready"] is False
    assert report["phase2_coverage_state_mutated"] is False


def test_first_wave_can_be_ready_before_full_dag():
    report = evaluate_phase2_default_branch_readiness(
        [
            "phase2-archive-rpc-preflight.yml",
            "phase2-direct-quote-registry.yml",
        ],
        default_branch="main",
    )

    assert report["phase2_first_wave_dispatch_ready"] is True
    assert report["phase2_full_coverage_dag_dispatch_ready"] is False
    assert report["first_wave_missing_workflow_names"] == []


def test_full_surface_is_ready_when_every_required_workflow_exists():
    required = required_phase2_manual_workflows()
    report = evaluate_phase2_default_branch_readiness(
        required,
        default_branch="main",
    )

    assert report["phase2_first_wave_dispatch_ready"] is True
    assert report["phase2_full_coverage_dag_dispatch_ready"] is True
    assert report["missing_workflow_names"] == []
