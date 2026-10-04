import json
import pytest

from hlp.data.phase2_dump_candidate_dispatch import (
    build_phase2_dump_candidate_dispatch_plan,
    validate_phase2_dump_candidate_dispatch_plan,
    validate_phase2_dump_candidate_launch_receipt,
    validate_phase2_dump_candidate_completion_receipt,
)


def geometry_completion():
    return {
        "version": "phase2-dump-geometry-completion-receipt-v1",
        "dump_geometry_completion_control_run_id": 12001,
        "dump_geometry_launch_run_id": 12002,
        "dump_geometry_launch_artifact_digest": "sha256:" + "11" * 32,
        "dump_geometry_run_id": 12003,
        "dump_geometry_artifact_digest": "sha256:" + "22" * 32,
        "dump_geometry_handoff_artifact_digest": "sha256:" + "23" * 32,
        "geometry_sha256": "24" * 32,
        "geometry_summary_sha256": "25" * 32,
        "geometry_handoff_sha256": "26" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "27" * 20,
        "canonical_ledger_commit_sha": "27" * 20,
        "price_path_run_id": 12004,
        "price_path_artifact_digest": "sha256:" + "28" * 32,
        "price_path_handoff_sha256": "29" * 32,
        "snapshot_head_block": 54_486_035,
        "tokens": 100,
        "price_points": 10000,
        "candidate_research_base_inputs": {
            "geometry_run_id": "12003",
            "expected_geometry_artifact_digest": "sha256:" + "22" * 32,
            "expected_geometry_handoff_sha256": "26" * 32,
        },
        "target_run_completed": True,
        "target_run_successful": True,
        "uses_price_path_only": True,
        "dump_geometry_ready": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def grid():
    return {
        "version": "phase2-dump-candidate-grid-v1",
        "semantics": "research_only_no_selection",
        "candidate_count": 2,
        "candidates": [
            {
                "candidate_id": "a",
                "family": "peak_drawdown_rebound",
                "min_drawdown_fraction": "0.4",
                "confirmation_rebound_fraction": "0.25",
            },
            {
                "candidate_id": "b",
                "family": "peak_drawdown_rebound",
                "min_drawdown_fraction": "0.6",
                "confirmation_rebound_fraction": "0.4",
            },
        ],
    }


def test_candidate_plan_is_research_only():
    plan = build_phase2_dump_candidate_dispatch_plan(
        geometry_completion(), grid()
    )
    assert plan["candidate_count"] == 2
    assert plan["candidate_selected"] is False
    assert json.loads(plan["candidate_specs_json"])[0]["candidate_id"] == "a"
    validated = validate_phase2_dump_candidate_dispatch_plan(plan)
    assert validated["candidate_count"] == 2


def test_candidate_plan_rejects_selection_semantics():
    row = grid()
    row["semantics"] = "pick_best"
    with pytest.raises(ValueError, match="semantics changed"):
        build_phase2_dump_candidate_dispatch_plan(
            geometry_completion(), row
        )


def launch_receipt():
    return {
        "version": "phase2-dump-candidate-launch-receipt-v1",
        "candidate_control_run_id": 12101,
        "candidate_plan_run_id": 12102,
        "candidate_plan_artifact_digest": "sha256:" + "31" * 32,
        "candidate_research_run_id": 12103,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "32" * 20,
        "canonical_ledger_commit_sha": "32" * 20,
        "candidate_specs_sha256": "33" * 32,
        "candidate_count": 24,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def test_candidate_launch_cannot_select_detector():
    report = validate_phase2_dump_candidate_launch_receipt(
        launch_receipt()
    )
    assert report["candidate_count"] == 24
    row = launch_receipt()
    row["candidate_selected"] = True
    with pytest.raises(ValueError, match="selects candidate"):
        validate_phase2_dump_candidate_launch_receipt(row)


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase2-dump-candidate-completion-receipt-v1",
        "candidate_completion_control_run_id": 12201,
        "candidate_launch_run_id": 12202,
        "candidate_launch_artifact_digest": "sha256:" + "41" * 32,
        "candidate_research_run_id": launch["candidate_research_run_id"],
        "candidate_research_artifact_digest": "sha256:" + "42" * 32,
        "candidate_research_handoff_artifact_digest": "sha256:" + "43" * 32,
        "candidate_research_handoff_sha256": "44" * 32,
        "candidate_specs_sha256": "45" * 32,
        "candidate_rows_sha256": "46" * 32,
        "candidate_summary_sha256": "47" * 32,
        "candidate_count": 24,
        "tokens": 100,
        "candidate_rows": 2400,
        "diagnostics_inputs": {
            "candidate_research_run_id": "12103",
            "expected_candidate_artifact_digest": "sha256:" + "42" * 32,
            "expected_candidate_handoff_sha256": "44" * 32,
        },
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


def test_candidate_completion_emits_diagnostics_inputs():
    report = validate_phase2_dump_candidate_completion_receipt(
        completion_receipt()
    )
    assert report["candidate_rows"] == 2400
    assert report["diagnostics_inputs"]["candidate_research_run_id"] == (
        "12103"
    )
