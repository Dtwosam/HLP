import pytest

from hlp.data.phase2_research_materialization_dispatch import (
    COMPOSITE_WORKFLOW,
    PONS_WORKFLOW,
    SIMPLE_WORKFLOW,
    build_phase2_research_materialization_dispatch_plan,
    validate_phase2_research_materialization_dispatch_plan,
    validate_phase2_research_materialization_wave_launch_receipt,
    validate_phase2_research_materialization_wave_completion_receipt,
)
from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID
from hlp.data.phase2_research_source_layouts import (
    build_phase2_research_source_layouts,
)


def rehydration_plan():
    launchpads = {
        component: {"component_id": component}
        for component in build_phase2_research_source_layouts()
        if component != DIRECT_RESEARCH_COMPONENT_ID
    }
    return {
        "version": "phase2-research-rehydration-plan-v1",
        "snapshot_head_block": 54_486_035,
        "eligible_universe_sha256": "11" * 32,
        "launchpad_bindings": launchpads,
        "direct_binding": {
            "component_id": DIRECT_RESEARCH_COMPONENT_ID,
        },
        "component_count": 12,
        "source_count": 14,
        "research_price_paths_materialized": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }


def universe_completion():
    return {
        "version": "phase2-universe-freeze-completion-receipt-v1",
        "universe_freeze_completion_control_run_id": 8001,
        "universe_freeze_launch_run_id": 8002,
        "universe_freeze_launch_artifact_digest": "sha256:" + "22" * 32,
        "universe_freeze_run_id": 8003,
        "universe_freeze_artifact_digest": "sha256:" + "33" * 32,
        "universe_freeze_handoff_sha256": "44" * 32,
        "eligible_universe_sha256": "11" * 32,
        "universe_summary_sha256": "55" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "66" * 20,
        "canonical_ledger_commit_sha": "66" * 20,
        "snapshot_head_block": 54_486_035,
        "eligible_tokens": 1234,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_frozen": True,
        "target_run_completed": True,
        "target_run_successful": True,
        "canonical_coverage_ledger_mutated": False,
        "workflow_dispatch_performed": False,
    }


def test_materialization_dispatch_plan_uses_frozen_layout_split():
    report = build_phase2_research_materialization_dispatch_plan(
        rehydration_plan(),
        rehydration_plan_run_id=9001,
        rehydration_plan_artifact_digest="sha256:" + "77" * 32,
        rehydration_plan_sha256="88" * 32,
        universe_completion=universe_completion(),
    )
    assert report["component_count"] == 12
    assert report["workflow_counts"] == {
        PONS_WORKFLOW: 2,
        SIMPLE_WORKFLOW: 7,
        COMPOSITE_WORKFLOW: 3,
    }
    assert {
        row["component_id"] for row in report["component_dispatches"]
    } == set(build_phase2_research_source_layouts())
    validated = validate_phase2_research_materialization_dispatch_plan(
        report
    )
    assert validated["component_count"] == 12


def test_materialization_dispatch_plan_rejects_universe_drift():
    row = rehydration_plan()
    row["eligible_universe_sha256"] = "99" * 32
    with pytest.raises(ValueError, match="universe SHA drift"):
        build_phase2_research_materialization_dispatch_plan(
            row,
            rehydration_plan_run_id=9001,
            rehydration_plan_artifact_digest="sha256:" + "77" * 32,
            rehydration_plan_sha256="88" * 32,
            universe_completion=universe_completion(),
        )


def launch_receipt():
    components = sorted(build_phase2_research_source_layouts())
    return {
        "version": "phase2-research-materialization-wave-launch-receipt-v1",
        "materialization_wave_control_run_id": 9100,
        "dispatch_plan_run_id": 9101,
        "dispatch_plan_artifact_digest": "sha256:" + "aa" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "bb" * 20,
        "canonical_ledger_commit_sha": "bb" * 20,
        "component_run_ids": {
            component: 9200 + index
            for index, component in enumerate(components)
        },
        "target_runs_created": 12,
        "target_runs_waited_for_completion": False,
        "workflow_dispatch_performed": True,
    }


def test_materialization_launch_requires_unique_component_runs():
    report = validate_phase2_research_materialization_wave_launch_receipt(
        launch_receipt()
    )
    assert len(report["component_run_ids"]) == 12
    row = launch_receipt()
    values = list(row["component_run_ids"].values())
    first = next(iter(row["component_run_ids"]))
    row["component_run_ids"][first] = values[-1]
    with pytest.raises(ValueError, match="not unique"):
        validate_phase2_research_materialization_wave_launch_receipt(row)


def completion_receipt():
    launch = launch_receipt()
    runs = launch["component_run_ids"]
    return {
        "version": "phase2-research-materialization-wave-completion-receipt-v1",
        "materialization_completion_control_run_id": 9300,
        "materialization_wave_launch_run_id": 9301,
        "materialization_wave_launch_artifact_digest": "sha256:" + "cc" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "dd" * 20,
        "canonical_ledger_commit_sha": "dd" * 20,
        "component_run_ids": runs,
        "component_runs_json": __import__("json").dumps(
            runs,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "component_runs_completed": 12,
        "all_component_runs_successful": True,
        "research_components_ready": True,
        "research_price_paths_materialized": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def test_materialization_completion_emits_freeze_input_json():
    report = (
        validate_phase2_research_materialization_wave_completion_receipt(
            completion_receipt()
        )
    )
    assert report["component_runs_completed"] == 12
    assert report["component_runs_json"].startswith("{")
