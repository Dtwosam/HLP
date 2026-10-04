import pytest

from hlp.data.phase2_dump_detector_dispatch import (
    SELECTED_CANDIDATE_ID,
    SELECTION_POLICY,
    build_phase2_dump_detector_selection_plan,
    validate_phase2_dump_detector_selection_plan,
    validate_phase2_dump_detector_freeze_launch_receipt,
    validate_phase2_dump_detector_freeze_completion_receipt,
)
from hlp.data.phase2_dump_candidate_dispatch import candidate_specs_sha256


def diagnostics_completion():
    return {
        "version": "phase2-dump-candidate-diagnostics-completion-receipt-v1",
        "diagnostics_completion_control_run_id": 12101,
        "diagnostics_launch_run_id": 12102,
        "diagnostics_launch_artifact_digest": "sha256:" + "11" * 32,
        "diagnostics_run_id": 12103,
        "diagnostics_artifact_digest": "sha256:" + "22" * 32,
        "diagnostics_handoff_sha256": "33" * 32,
        "diagnostics_sha256": "34" * 32,
        "diagnostics_summary_sha256": "35" * 32,
        "candidate_research_run_id": 12104,
        "candidate_artifact_digest": "sha256:" + "44" * 32,
        "candidate_handoff_sha256": "55" * 32,
        "candidate_specs_sha256": candidate_specs_sha256(),
        "price_path_run_id": 12105,
        "price_path_artifact_digest": "sha256:" + "66" * 32,
        "price_path_handoff_sha256": "77" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "88" * 20,
        "canonical_ledger_commit_sha": "88" * 20,
        "candidates": 9,
        "equivalent_candidate_pairs": [],
        "detector_freeze_base_inputs": {
            "candidate_research_run_id": "12104",
            "expected_candidate_artifact_digest": "sha256:" + "44" * 32,
            "expected_candidate_handoff_sha256": "55" * 32,
            "diagnostics_run_id": "12103",
            "expected_diagnostics_artifact_digest": "sha256:" + "22" * 32,
            "expected_diagnostics_handoff_sha256": "33" * 32,
        },
        "selected_candidate_id": None,
        "selected_candidate_id_required": True,
        "uses_outcome_labels": False,
        "candidate_selected": False,
        "detector_freeze_ready": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "target_run_completed": True,
        "target_run_successful": True,
        "workflow_dispatch_performed": False,
    }


def test_detector_selection_plan_is_explicit_and_outcome_blind():
    report = build_phase2_dump_detector_selection_plan(
        diagnostics_completion()
    )
    assert report["selected_candidate_id"] == "dd40-rb25"
    assert report["selection_policy"] == SELECTION_POLICY
    assert report["uses_outcome_labels"] is False
    assert report["inputs"]["selected_candidate_id"] == "dd40-rb25"
    validated = validate_phase2_dump_detector_selection_plan(report)
    assert validated["selected_candidate_id"] == SELECTED_CANDIDATE_ID


def test_detector_selection_plan_rejects_candidate_drift():
    report = build_phase2_dump_detector_selection_plan(
        diagnostics_completion()
    )
    report["selected_candidate_id"] = "dd30-rb15"
    with pytest.raises(ValueError, match="candidate ID drift"):
        validate_phase2_dump_detector_selection_plan(report)


def launch_receipt():
    return {
        "version": "phase2-dump-detector-freeze-launch-receipt-v1",
        "detector_freeze_control_run_id": 12201,
        "selection_plan_run_id": 12202,
        "selection_plan_artifact_digest": "sha256:" + "99" * 32,
        "detector_freeze_run_id": 12203,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "aa" * 20,
        "canonical_ledger_commit_sha": "aa" * 20,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selection_policy": SELECTION_POLICY,
        "price_path_run_id": 12204,
        "price_path_artifact_digest": "sha256:" + "ab" * 32,
        "price_path_handoff_sha256": "ac" * 32,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "uses_outcome_labels": False,
        "phase2_dump_detector_frozen": False,
        "workflow_dispatch_performed": True,
    }


def test_detector_freeze_launch_keeps_outcomes_hidden():
    report = validate_phase2_dump_detector_freeze_launch_receipt(
        launch_receipt()
    )
    assert report["selected_candidate_id"] == SELECTED_CANDIDATE_ID
    row = launch_receipt()
    row["uses_outcome_labels"] = True
    with pytest.raises(ValueError, match="uses outcomes"):
        validate_phase2_dump_detector_freeze_launch_receipt(row)


def completion_receipt():
    launch = launch_receipt()
    return {
        "version": "phase2-dump-detector-freeze-completion-receipt-v1",
        "detector_freeze_completion_control_run_id": 12301,
        "detector_freeze_launch_run_id": 12302,
        "detector_freeze_launch_artifact_digest": "sha256:" + "bb" * 32,
        "detector_freeze_run_id": launch["detector_freeze_run_id"],
        "detector_freeze_artifact_digest": "sha256:" + "cc" * 32,
        "detector_freeze_handoff_artifact_digest": "sha256:" + "dd" * 32,
        "detector_rows_sha256": "ee" * 32,
        "freeze_summary_sha256": "ef" * 32,
        "detector_freeze_handoff_sha256": "f0" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch["canonical_ledger_commit_sha"],
        "price_path_run_id": 12303,
        "price_path_artifact_digest": "sha256:" + "f1" * 32,
        "price_path_handoff_sha256": "f2" * 32,
        "tokens": 1234,
        "confirmed_tokens": 456,
        "selected_candidate_id": SELECTED_CANDIDATE_ID,
        "selection_policy": SELECTION_POLICY,
        "outcome_label_inputs": {
            "detector_freeze_run_id": "12203",
            "expected_detector_artifact_digest": "sha256:" + "cc" * 32,
            "expected_detector_handoff_sha256": "f0" * 32,
            "price_path_run_id": "12303",
            "expected_price_path_artifact_digest": "sha256:" + "f1" * 32,
            "expected_price_path_handoff_sha256": "f2" * 32,
        },
        "target_run_completed": True,
        "target_run_successful": True,
        "uses_outcome_labels": False,
        "candidate_selected": True,
        "detector_freeze_ready": True,
        "dump_threshold_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def test_detector_freeze_completion_opens_outcome_stage_only_after_freeze():
    report = validate_phase2_dump_detector_freeze_completion_receipt(
        completion_receipt()
    )
    assert report["phase2_dump_detector_frozen"] is True
    assert report["outcome_label_inputs"]["detector_freeze_run_id"] == (
        "12203"
    )
    row = completion_receipt()
    row["outcome_labels_computed"] = True
    with pytest.raises(ValueError, match="outcome_labels_computed drift"):
        validate_phase2_dump_detector_freeze_completion_receipt(row)
