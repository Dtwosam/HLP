import pytest

from hlp.data.phase2_dataset_dispatch import (
    build_phase2_dataset_dispatch_plan,
    validate_phase2_dataset_dispatch_plan,
    validate_phase2_dataset_launch_receipt,
    validate_phase2_dataset_completion_receipt,
)


def universe_completion():
    return {
        "version": "phase2-universe-freeze-completion-receipt-v1",
        "universe_freeze_completion_control_run_id": 14001,
        "universe_freeze_launch_run_id": 14002,
        "universe_freeze_launch_artifact_digest": "sha256:" + "11" * 32,
        "universe_freeze_run_id": 14003,
        "universe_freeze_artifact_digest": "sha256:" + "22" * 32,
        "universe_freeze_handoff_sha256": "33" * 32,
        "eligible_universe_sha256": "44" * 32,
        "universe_summary_sha256": "45" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "55" * 20,
        "canonical_ledger_commit_sha": "55" * 20,
        "snapshot_head_block": 54_486_035,
        "eligible_tokens": 1234,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_frozen": True,
        "target_run_completed": True,
        "target_run_successful": True,
        "canonical_coverage_ledger_mutated": False,
        "workflow_dispatch_performed": False,
    }


def outcome_completion():
    return {
        "version": "phase2-outcome-labels-completion-receipt-v1",
        "outcome_label_completion_control_run_id": 14101,
        "outcome_label_launch_run_id": 14102,
        "outcome_label_launch_artifact_digest": "sha256:" + "66" * 32,
        "outcome_label_run_id": 14103,
        "outcome_artifact_digest": "sha256:" + "77" * 32,
        "outcome_handoff_artifact_digest": "sha256:" + "78" * 32,
        "outcome_rows_sha256": "88" * 32,
        "outcome_summary_sha256": "89" * 32,
        "outcome_handoff_sha256": "99" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "55" * 20,
        "canonical_ledger_commit_sha": "55" * 20,
        "detector_freeze_run_id": 14104,
        "detector_freeze_artifact_digest": "sha256:" + "aa" * 32,
        "detector_freeze_handoff_sha256": "ab" * 32,
        "price_path_run_id": 14105,
        "price_path_artifact_digest": "sha256:" + "ac" * 32,
        "price_path_handoff_sha256": "ad" * 32,
        "tokens": 1234,
        "confirmed_dump_tokens": 456,
        "comeback_5x_tokens": 123,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "max_post_dump_multiple_retained": True,
        "target_run_completed": True,
        "target_run_successful": True,
        "workflow_dispatch_performed": False,
    }


def test_dataset_plan_joins_exact_universe_and_outcomes():
    report = build_phase2_dataset_dispatch_plan(
        universe_completion(),
        outcome_completion(),
    )
    assert report["tokens"] == 1234
    assert report["inputs"]["universe_run_id"] == "14003"
    assert report["inputs"]["outcome_run_id"] == "14103"
    validated = validate_phase2_dataset_dispatch_plan(report)
    assert validated["phase2_dataset_ready"] is False


def test_dataset_plan_rejects_token_count_drift():
    row = outcome_completion()
    row["tokens"] = 1233
    with pytest.raises(ValueError, match="token count drift"):
        build_phase2_dataset_dispatch_plan(universe_completion(), row)


def launch_receipt():
    return {
        "version": "phase2-universe-outcome-dataset-launch-receipt-v1",
        "dataset_control_run_id": 14201,
        "dataset_plan_run_id": 14202,
        "dataset_plan_artifact_digest": "sha256:" + "bb" * 32,
        "dataset_run_id": 14203,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "cc" * 20,
        "canonical_ledger_commit_sha": "cc" * 20,
        "universe_run_id": 14204,
        "universe_artifact_digest": "sha256:" + "bc" * 32,
        "universe_handoff_sha256": "bd" * 32,
        "detector_freeze_run_id": 14205,
        "detector_freeze_artifact_digest": "sha256:" + "be" * 32,
        "detector_freeze_handoff_sha256": "bf" * 32,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "phase2_dataset_ready": False,
        "workflow_dispatch_performed": True,
    }


def test_dataset_launch_has_one_target():
    report = validate_phase2_dataset_launch_receipt(
        launch_receipt()
    )
    assert report["dataset_run_id"] == 14203


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase2-universe-outcome-dataset-completion-receipt-v1",
        "dataset_completion_control_run_id": 14301,
        "dataset_launch_run_id": 14302,
        "dataset_launch_artifact_digest": "sha256:" + "dd" * 32,
        "dataset_run_id": launch["dataset_run_id"],
        "dataset_artifact_digest": "sha256:" + "ee" * 32,
        "dataset_handoff_artifact_digest": "sha256:" + "ef" * 32,
        "dataset_rows_sha256": "f0" * 32,
        "dataset_summary_sha256": "f1" * 32,
        "dataset_handoff_sha256": "f2" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch["canonical_ledger_commit_sha"],
        "universe_run_id": launch["universe_run_id"],
        "universe_artifact_digest": launch["universe_artifact_digest"],
        "universe_handoff_sha256": launch["universe_handoff_sha256"],
        "detector_freeze_run_id": launch["detector_freeze_run_id"],
        "detector_freeze_artifact_digest": launch["detector_freeze_artifact_digest"],
        "detector_freeze_handoff_sha256": launch["detector_freeze_handoff_sha256"],
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


def test_dataset_completion_closes_phase2_checkpoint():
    report = validate_phase2_dataset_completion_receipt(
        completion_receipt()
    )
    assert report["phase2_dataset_ready"] is True
    assert report["phase3_features_attached"] is False
