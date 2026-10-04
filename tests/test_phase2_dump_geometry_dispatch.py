import pytest

from hlp.data.phase2_dump_geometry_dispatch import (
    validate_phase2_dump_geometry_launch_receipt,
    validate_phase2_dump_geometry_completion_receipt,
)


def launch_receipt():
    return {
        "version": "phase2-dump-geometry-launch-receipt-v1",
        "dump_geometry_control_run_id": 11101,
        "price_path_completion_run_id": 11102,
        "price_path_completion_artifact_digest": "sha256:" + "11" * 32,
        "dump_geometry_run_id": 11103,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "22" * 20,
        "canonical_ledger_commit_sha": "22" * 20,
        "price_path_run_id": 11104,
        "price_path_artifact_digest": "sha256:" + "33" * 32,
        "price_path_handoff_sha256": "44" * 32,
        "universe_run_id": 11105,
        "universe_artifact_digest": "sha256:" + "55" * 32,
        "universe_handoff_sha256": "66" * 32,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def test_dump_geometry_launch_is_outcome_blind():
    report = validate_phase2_dump_geometry_launch_receipt(
        launch_receipt()
    )
    assert report["dump_geometry_run_id"] == 11103
    row = launch_receipt()
    row["candidate_selected"] = True
    with pytest.raises(ValueError, match="selects a candidate"):
        validate_phase2_dump_geometry_launch_receipt(row)


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase2-dump-geometry-completion-receipt-v1",
        "dump_geometry_completion_control_run_id": 11201,
        "dump_geometry_launch_run_id": 11202,
        "dump_geometry_launch_artifact_digest": "sha256:" + "77" * 32,
        "dump_geometry_run_id": launch["dump_geometry_run_id"],
        "dump_geometry_artifact_digest": "sha256:" + "88" * 32,
        "dump_geometry_handoff_artifact_digest": "sha256:" + "99" * 32,
        "geometry_sha256": "aa" * 32,
        "geometry_summary_sha256": "bb" * 32,
        "geometry_handoff_sha256": "cc" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch["canonical_ledger_commit_sha"],
        "price_path_run_id": launch["price_path_run_id"],
        "price_path_artifact_digest": launch["price_path_artifact_digest"],
        "price_path_handoff_sha256": launch["price_path_handoff_sha256"],
        "snapshot_head_block": 54_486_035,
        "tokens": 1234,
        "price_points": 987654,
        "candidate_research_base_inputs": {
            "geometry_run_id": "11103",
            "expected_geometry_artifact_digest": "sha256:" + "88" * 32,
            "expected_geometry_handoff_sha256": "cc" * 32,
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


def test_dump_geometry_completion_stops_before_candidate_choice():
    report = validate_phase2_dump_geometry_completion_receipt(
        completion_receipt()
    )
    assert report["dump_geometry_ready"] is True
    assert report["candidate_research_base_inputs"]["geometry_run_id"] == (
        "11103"
    )
    row = completion_receipt()
    row["candidate_research_base_inputs"]["geometry_run_id"] = "999"
    with pytest.raises(ValueError, match="base-input binding drift"):
        validate_phase2_dump_geometry_completion_receipt(row)
