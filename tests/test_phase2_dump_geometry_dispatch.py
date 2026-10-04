import pytest

from hlp.data.phase2_dump_geometry_dispatch import (
    build_dump_geometry_launch_receipt,
    validate_phase2_dump_geometry_completion_receipt,
)


def price_path_completion():
    return {
        "version": "phase2-research-price-path-completion-receipt-v1",
        "price_path_completion_control_run_id": 10001,
        "price_path_launch_run_id": 10002,
        "price_path_launch_artifact_digest": "sha256:" + "11" * 32,
        "price_path_run_id": 10003,
        "price_path_artifact_digest": "sha256:" + "12" * 32,
        "price_path_handoff_sha256": "13" * 32,
        "normalized_price_path_sha256": "14" * 32,
        "price_path_report_sha256": "15" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "16" * 20,
        "canonical_ledger_commit_sha": "16" * 20,
        "universe_run_id": 10004,
        "universe_artifact_digest": "sha256:" + "17" * 32,
        "universe_handoff_sha256": "18" * 32,
        "snapshot_head_block": 54_486_035,
        "eligible_tokens": 500,
        "price_points": 5000,
        "geometry_inputs": {
            "price_path_run_id": "10003",
            "expected_price_path_artifact_digest": "sha256:" + "12" * 32,
            "expected_price_path_handoff_sha256": "13" * 32,
            "universe_run_id": "10004",
            "expected_universe_artifact_digest": "sha256:" + "17" * 32,
            "expected_universe_handoff_sha256": "18" * 32,
        },
        "target_run_completed": True,
        "target_run_successful": True,
        "research_price_path_ready": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def test_geometry_launch_preserves_outcome_blind_state():
    report = build_dump_geometry_launch_receipt(
        price_path_completion(),
        control_run_id=10100,
        completion_run_id=10101,
        completion_artifact_digest="sha256:" + "19" * 32,
        geometry_run_id=10102,
    )
    assert report["geometry_run_id"] == 10102
    assert report["candidate_selected"] is False
    assert report["dump_threshold_frozen"] is False


def geometry_completion():
    return {
        "version": "phase2-dump-geometry-completion-receipt-v1",
        "geometry_completion_control_run_id": 10200,
        "geometry_launch_run_id": 10201,
        "geometry_launch_artifact_digest": "sha256:" + "21" * 32,
        "geometry_run_id": 10202,
        "geometry_artifact_digest": "sha256:" + "22" * 32,
        "geometry_handoff_sha256": "23" * 32,
        "geometry_sha256": "24" * 32,
        "geometry_summary_sha256": "25" * 32,
        "normalized_price_path_sha256": "26" * 32,
        "price_path_handoff_sha256": "27" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "28" * 20,
        "canonical_ledger_commit_sha": "28" * 20,
        "snapshot_head_block": 54_486_035,
        "tokens": 500,
        "price_points": 5000,
        "candidate_research_identity": {
            "geometry_run_id": "10202",
            "expected_geometry_artifact_digest": "sha256:" + "22" * 32,
            "expected_geometry_handoff_sha256": "23" * 32,
        },
        "uses_price_path_only": True,
        "dump_geometry_ready": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "target_run_completed": True,
        "target_run_successful": True,
        "workflow_dispatch_performed": False,
    }


def test_geometry_completion_emits_candidate_research_identity():
    report = validate_phase2_dump_geometry_completion_receipt(
        geometry_completion()
    )
    assert report["candidate_research_identity"]["geometry_run_id"] == (
        "10202"
    )
    assert report["candidate_selected"] is False


def test_geometry_completion_rejects_candidate_selection():
    row = geometry_completion()
    row["candidate_selected"] = True
    with pytest.raises(ValueError, match="selected a candidate"):
        validate_phase2_dump_geometry_completion_receipt(row)
