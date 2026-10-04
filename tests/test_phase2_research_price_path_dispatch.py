import pytest

from hlp.data.phase2_research_price_path_dispatch import (
    validate_phase2_research_price_path_launch_receipt,
    validate_phase2_research_price_path_completion_receipt,
)


def launch_receipt():
    return {
        "version": "phase2-research-price-path-launch-receipt-v1",
        "price_path_control_run_id": 10101,
        "materialization_freeze_completion_run_id": 10102,
        "materialization_freeze_completion_artifact_digest": "sha256:" + "11" * 32,
        "price_path_run_id": 10103,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "22" * 20,
        "canonical_ledger_commit_sha": "22" * 20,
        "materialization_freeze_run_id": 10104,
        "materialization_freeze_artifact_digest": "sha256:" + "33" * 32,
        "materialization_bundle_sha256": "44" * 32,
        "materialization_handoff_sha256": "55" * 32,
        "universe_run_id": 10105,
        "universe_artifact_digest": "sha256:" + "66" * 32,
        "universe_handoff_sha256": "77" * 32,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def test_price_path_launch_requires_one_readonly_target():
    report = validate_phase2_research_price_path_launch_receipt(
        launch_receipt()
    )
    assert report["price_path_run_id"] == 10103
    row = launch_receipt()
    row["dump_threshold_frozen"] = True
    with pytest.raises(ValueError, match="prematurely freezes threshold"):
        validate_phase2_research_price_path_launch_receipt(row)


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase2-research-price-path-completion-receipt-v1",
        "price_path_completion_control_run_id": 10201,
        "price_path_launch_run_id": 10202,
        "price_path_launch_artifact_digest": "sha256:" + "88" * 32,
        "price_path_run_id": launch["price_path_run_id"],
        "price_path_artifact_digest": "sha256:" + "99" * 32,
        "price_path_handoff_artifact_digest": "sha256:" + "aa" * 32,
        "price_path_sha256": "bb" * 32,
        "price_path_report_sha256": "cc" * 32,
        "price_path_handoff_sha256": "dd" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch["canonical_ledger_commit_sha"],
        "materialization_freeze_run_id": launch["materialization_freeze_run_id"],
        "materialization_freeze_artifact_digest": launch[
            "materialization_freeze_artifact_digest"
        ],
        "materialization_bundle_sha256": launch[
            "materialization_bundle_sha256"
        ],
        "materialization_handoff_sha256": launch[
            "materialization_handoff_sha256"
        ],
        "universe_run_id": launch["universe_run_id"],
        "universe_artifact_digest": launch["universe_artifact_digest"],
        "universe_handoff_sha256": launch["universe_handoff_sha256"],
        "snapshot_head_block": 54_486_035,
        "eligible_tokens": 1234,
        "price_points": 987654,
        "components": 12,
        "geometry_inputs": {
            "price_path_run_id": "10103",
            "expected_price_path_artifact_digest": "sha256:" + "99" * 32,
            "expected_price_path_handoff_sha256": "dd" * 32,
            "universe_run_id": "10105",
            "expected_universe_artifact_digest": "sha256:" + "66" * 32,
            "expected_universe_handoff_sha256": "77" * 32,
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
    assert report["research_price_path_ready"] is True
    assert report["geometry_inputs"]["price_path_run_id"] == "10103"

    row = completion_receipt()
    row["geometry_inputs"]["price_path_run_id"] = "999"
    with pytest.raises(ValueError, match="dump-geometry input binding drift"):
        validate_phase2_research_price_path_completion_receipt(row)
