import pytest

from hlp.data.phase2_outcome_dispatch import (
    validate_phase2_outcome_label_launch_receipt,
    validate_phase2_outcome_label_completion_receipt,
)


def launch_receipt():
    return {
        "version": "phase2-outcome-labels-launch-receipt-v1",
        "outcome_label_control_run_id": 13101,
        "detector_freeze_completion_run_id": 13102,
        "detector_freeze_completion_artifact_digest": "sha256:" + "11" * 32,
        "outcome_label_run_id": 13103,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "22" * 20,
        "canonical_ledger_commit_sha": "22" * 20,
        "detector_freeze_run_id": 13104,
        "detector_freeze_artifact_digest": "sha256:" + "33" * 32,
        "detector_freeze_handoff_sha256": "44" * 32,
        "price_path_run_id": 13105,
        "price_path_artifact_digest": "sha256:" + "55" * 32,
        "price_path_handoff_sha256": "66" * 32,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def test_outcome_launch_requires_frozen_detector():
    report = validate_phase2_outcome_label_launch_receipt(
        launch_receipt()
    )
    assert report["outcome_label_run_id"] == 13103
    row = launch_receipt()
    row["phase2_dump_detector_frozen"] = False
    with pytest.raises(ValueError, match="lacks frozen detector proof"):
        validate_phase2_outcome_label_launch_receipt(row)


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase2-outcome-labels-completion-receipt-v1",
        "outcome_label_completion_control_run_id": 13201,
        "outcome_label_launch_run_id": 13202,
        "outcome_label_launch_artifact_digest": "sha256:" + "77" * 32,
        "outcome_label_run_id": launch["outcome_label_run_id"],
        "outcome_artifact_digest": "sha256:" + "88" * 32,
        "outcome_handoff_artifact_digest": "sha256:" + "99" * 32,
        "outcome_rows_sha256": "aa" * 32,
        "outcome_summary_sha256": "bb" * 32,
        "outcome_handoff_sha256": "cc" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch["canonical_ledger_commit_sha"],
        "detector_freeze_run_id": launch["detector_freeze_run_id"],
        "detector_freeze_artifact_digest": launch[
            "detector_freeze_artifact_digest"
        ],
        "detector_freeze_handoff_sha256": launch[
            "detector_freeze_handoff_sha256"
        ],
        "price_path_run_id": launch["price_path_run_id"],
        "price_path_artifact_digest": launch["price_path_artifact_digest"],
        "price_path_handoff_sha256": launch["price_path_handoff_sha256"],
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


def test_outcome_completion_proves_continuous_labels():
    report = validate_phase2_outcome_label_completion_receipt(
        completion_receipt()
    )
    assert report["outcome_labels_computed"] is True
    assert report["comeback_5x_tokens"] == 123
    row = completion_receipt()
    row["comeback_5x_tokens"] = 500
    with pytest.raises(ValueError, match="count hierarchy drift"):
        validate_phase2_outcome_label_completion_receipt(row)
