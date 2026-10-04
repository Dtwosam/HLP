import pytest

from hlp.data.phase2_research_price_path_dispatch import (
    build_price_path_launch_receipt,
    validate_phase2_research_price_path_completion_receipt,
)


def materialization_completion():
    return {
        "version": "phase2-research-materialization-freeze-completion-receipt-v1",
        "materialization_freeze_completion_control_run_id": 9500,
        "materialization_freeze_launch_run_id": 9501,
        "materialization_freeze_launch_artifact_digest": "sha256:" + "11" * 32,
        "materialization_freeze_run_id": 9502,
        "materialization_freeze_artifact_digest": "sha256:" + "12" * 32,
        "materialization_bundle_sha256": "13" * 32,
        "materialization_handoff_sha256": "14" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "15" * 20,
        "canonical_ledger_commit_sha": "15" * 20,
        "rehydration_plan_run_id": 9503,
        "rehydration_plan_artifact_digest": "sha256:" + "16" * 32,
        "rehydration_plan_sha256": "17" * 32,
        "universe_run_id": 9504,
        "universe_artifact_digest": "sha256:" + "18" * 32,
        "universe_handoff_sha256": "19" * 32,
        "price_path_inputs": {
            "materialization_freeze_run_id": "9502",
            "expected_materialization_artifact_digest": "sha256:" + "12" * 32,
            "expected_bundle_sha256": "13" * 32,
            "expected_materialization_handoff_sha256": "14" * 32,
            "universe_run_id": "9504",
            "expected_universe_artifact_digest": "sha256:" + "18" * 32,
            "expected_universe_handoff_sha256": "19" * 32,
        },
        "target_run_completed": True,
        "target_run_successful": True,
        "research_price_paths_materialized": True,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def test_price_path_launch_binds_materialization_checkpoint():
    report = build_price_path_launch_receipt(
        materialization_completion(),
        control_run_id=9600,
        completion_run_id=9601,
        completion_artifact_digest="sha256:" + "20" * 32,
        price_path_run_id=9602,
    )
    assert report["price_path_run_id"] == 9602
    assert report["materialization_freeze_run_id"] == 9502
    assert report["universe_run_id"] == 9504


def completion_receipt():
    return {
        "version": "phase2-research-price-path-completion-receipt-v1",
        "price_path_completion_control_run_id": 9700,
        "price_path_launch_run_id": 9701,
        "price_path_launch_artifact_digest": "sha256:" + "21" * 32,
        "price_path_run_id": 9702,
        "price_path_artifact_digest": "sha256:" + "22" * 32,
        "price_path_handoff_sha256": "23" * 32,
        "normalized_price_path_sha256": "24" * 32,
        "price_path_report_sha256": "25" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "26" * 20,
        "canonical_ledger_commit_sha": "26" * 20,
        "universe_run_id": 9703,
        "universe_artifact_digest": "sha256:" + "27" * 32,
        "universe_handoff_sha256": "28" * 32,
        "snapshot_head_block": 54_486_035,
        "eligible_tokens": 1234,
        "price_points": 9999,
        "geometry_inputs": {
            "price_path_run_id": "9702",
            "expected_price_path_artifact_digest": "sha256:" + "22" * 32,
            "expected_price_path_handoff_sha256": "23" * 32,
            "universe_run_id": "9703",
            "expected_universe_artifact_digest": "sha256:" + "27" * 32,
            "expected_universe_handoff_sha256": "28" * 32,
        },
        "target_run_completed": True,
        "target_run_successful": True,
        "research_price_path_ready": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def test_price_path_completion_emits_geometry_inputs():
    report = validate_phase2_research_price_path_completion_receipt(
        completion_receipt()
    )
    assert report["geometry_inputs"]["price_path_run_id"] == "9702"
    assert report["research_price_path_ready"] is True


def test_price_path_completion_rejects_geometry_drift():
    row = completion_receipt()
    row["geometry_inputs"]["price_path_run_id"] = "9999"
    with pytest.raises(ValueError, match="dump-geometry input binding drift"):
        validate_phase2_research_price_path_completion_receipt(row)
