import pytest

from hlp.data.phase3_feature_entry_dispatch import (
    build_phase3_feature_entry_plan,
    validate_phase3_feature_entry_plan,
    validate_phase3_feature_entry_launch_receipt,
    validate_phase3_feature_entry_completion_receipt,
)


def phase2_completion():
    return {
        "version": "phase2-universe-outcome-dataset-completion-receipt-v1",
        "dataset_completion_control_run_id": 15001,
        "dataset_launch_run_id": 15002,
        "dataset_launch_artifact_digest": "sha256:" + "11" * 32,
        "dataset_run_id": 15003,
        "dataset_artifact_digest": "sha256:" + "12" * 32,
        "dataset_handoff_artifact_digest": "sha256:" + "13" * 32,
        "dataset_rows_sha256": "14" * 32,
        "dataset_summary_sha256": "15" * 32,
        "dataset_handoff_sha256": "16" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "17" * 20,
        "canonical_ledger_commit_sha": "17" * 20,
        "universe_run_id": 15004,
        "universe_artifact_digest": "sha256:" + "18" * 32,
        "universe_handoff_sha256": "19" * 32,
        "detector_freeze_run_id": 15005,
        "detector_freeze_artifact_digest": "sha256:" + "1a" * 32,
        "detector_freeze_handoff_sha256": "1b" * 32,
        "price_path_run_id": 15006,
        "price_path_artifact_digest": "sha256:" + "1c" * 32,
        "price_path_handoff_sha256": "1d" * 32,
        "checkpoint_name": "hlp-v1-phase2-universe-labels",
        "tokens": 1234,
        "confirmed_dump_tokens": 456,
        "comeback_5x_tokens": 123,
        "target_run_completed": True,
        "target_run_successful": True,
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
        "phase2_dataset_ready": True,
        "workflow_dispatch_performed": False,
    }


def test_feature_entry_plan_maps_checkpoint_lineage():
    report = build_phase3_feature_entry_plan(phase2_completion())
    assert report["inputs"]["phase2_dataset_run_id"] == "15003"
    assert report["inputs"]["universe_run_id"] == "15004"
    assert report["inputs"]["detector_freeze_run_id"] == "15005"
    assert report["price_path_run_id"] == 15006
    validated = validate_phase3_feature_entry_plan(report)
    assert validated["phase3_feature_entry_ready"] is False


def launch_receipt():
    return {
        "version": "phase3-feature-entry-launch-receipt-v1",
        "feature_entry_control_run_id": 15101,
        "feature_entry_plan_run_id": 15102,
        "feature_entry_plan_artifact_digest": "sha256:" + "21" * 32,
        "feature_entry_run_id": 15103,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "22" * 20,
        "canonical_ledger_commit_sha": "22" * 20,
        "universe_run_id": 15104,
        "universe_artifact_digest": "sha256:" + "23" * 32,
        "universe_handoff_sha256": "24" * 32,
        "price_path_run_id": 15105,
        "price_path_artifact_digest": "sha256:" + "25" * 32,
        "price_path_handoff_sha256": "26" * 32,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "outcome_rows_consumed": False,
        "phase3_feature_entry_ready": False,
        "workflow_dispatch_performed": True,
    }


def test_feature_entry_launch_is_leakage_safe():
    report = validate_phase3_feature_entry_launch_receipt(
        launch_receipt()
    )
    assert report["feature_entry_run_id"] == 15103
    row = launch_receipt()
    row["outcome_rows_consumed"] = True
    with pytest.raises(ValueError, match="consumed outcomes"):
        validate_phase3_feature_entry_launch_receipt(row)


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase3-feature-entry-completion-receipt-v1",
        "feature_entry_completion_control_run_id": 15201,
        "feature_entry_launch_run_id": 15202,
        "feature_entry_launch_artifact_digest": "sha256:" + "31" * 32,
        "feature_entry_run_id": launch["feature_entry_run_id"],
        "feature_entry_artifact_digest": "sha256:" + "32" * 32,
        "feature_entry_handoff_artifact_digest": "sha256:" + "33" * 32,
        "feature_subjects_sha256": "34" * 32,
        "entry_summary_sha256": "35" * 32,
        "entry_handoff_sha256": "36" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch["canonical_ledger_commit_sha"],
        "universe_run_id": launch["universe_run_id"],
        "universe_artifact_digest": launch["universe_artifact_digest"],
        "universe_handoff_sha256": launch["universe_handoff_sha256"],
        "price_path_run_id": launch["price_path_run_id"],
        "price_path_artifact_digest": launch["price_path_artifact_digest"],
        "price_path_handoff_sha256": launch["price_path_handoff_sha256"],
        "feature_subjects": 456,
        "snapshot_kind": "first_major_dump_confirmation",
        "target_run_completed": True,
        "target_run_successful": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": True,
        "workflow_dispatch_performed": False,
    }


def test_feature_entry_completion_freezes_subjects_only():
    report = validate_phase3_feature_entry_completion_receipt(
        completion_receipt()
    )
    assert report["feature_subjects"] == 456
    assert report["phase3_feature_values_computed"] is False
