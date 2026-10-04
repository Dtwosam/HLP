import json

import pytest

from hlp.data.phase2_dump_candidate_dispatch import (
    RESEARCH_CANDIDATE_SPECS,
    build_phase2_dump_candidate_research_plan,
    candidate_specs_sha256,
    validate_phase2_dump_candidate_research_plan,
    validate_phase2_dump_candidate_completion_receipt,
    validate_phase2_dump_diagnostics_completion_receipt,
)


def geometry_completion():
    return {
        "version": "phase2-dump-geometry-completion-receipt-v1",
        "dump_geometry_completion_control_run_id": 11001,
        "dump_geometry_launch_run_id": 11002,
        "dump_geometry_launch_artifact_digest": "sha256:" + "11" * 32,
        "dump_geometry_run_id": 11003,
        "dump_geometry_artifact_digest": "sha256:" + "12" * 32,
        "dump_geometry_handoff_artifact_digest": "sha256:" + "13" * 32,
        "geometry_sha256": "14" * 32,
        "geometry_summary_sha256": "15" * 32,
        "geometry_handoff_sha256": "16" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "17" * 20,
        "canonical_ledger_commit_sha": "17" * 20,
        "price_path_run_id": 11004,
        "price_path_artifact_digest": "sha256:" + "18" * 32,
        "price_path_handoff_sha256": "19" * 32,
        "snapshot_head_block": 54_486_035,
        "tokens": 500,
        "price_points": 5000,
        "candidate_research_base_inputs": {
            "geometry_run_id": "11003",
            "expected_geometry_artifact_digest": "sha256:" + "12" * 32,
            "expected_geometry_handoff_sha256": "16" * 32,
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


def test_candidate_plan_freezes_explicit_grid_without_selection():
    report = build_phase2_dump_candidate_research_plan(
        geometry_completion()
    )
    assert report["candidate_count"] == 9
    assert len(report["candidate_specs"]) == 9
    assert report["candidate_selected"] is False
    assert report["uses_outcome_labels"] is False
    assert report["candidate_specs_sha256"] == candidate_specs_sha256()
    assert json.loads(report["candidate_specs_json"]) == list(
        RESEARCH_CANDIDATE_SPECS
    )
    validate_phase2_dump_candidate_research_plan(report)


def candidate_completion():
    return {
        "version": "phase2-dump-candidate-research-completion-receipt-v1",
        "candidate_completion_control_run_id": 11100,
        "candidate_launch_run_id": 11101,
        "candidate_launch_artifact_digest": "sha256:" + "21" * 32,
        "candidate_research_run_id": 11102,
        "candidate_artifact_digest": "sha256:" + "22" * 32,
        "candidate_handoff_artifact_digest": "sha256:" + "23" * 32,
        "candidate_handoff_sha256": "24" * 32,
        "candidate_rows_sha256": "25" * 32,
        "candidate_specs_sha256": candidate_specs_sha256(),
        "candidate_summary_sha256": "26" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "27" * 20,
        "canonical_ledger_commit_sha": "27" * 20,
        "tokens": 500,
        "candidate_rows": 4500,
        "candidates": 9,
        "diagnostics_inputs": {
            "candidate_research_run_id": "11102",
            "expected_candidate_artifact_digest": "sha256:" + "22" * 32,
            "expected_candidate_handoff_sha256": "24" * 32,
        },
        "candidate_research_ready": True,
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


def test_candidate_completion_emits_diagnostics_inputs():
    report = validate_phase2_dump_candidate_completion_receipt(
        candidate_completion()
    )
    assert report["diagnostics_inputs"]["candidate_research_run_id"] == (
        "11102"
    )


def diagnostics_completion():
    return {
        "version": "phase2-dump-diagnostics-completion-receipt-v1",
        "diagnostics_completion_control_run_id": 11200,
        "diagnostics_launch_run_id": 11201,
        "diagnostics_launch_artifact_digest": "sha256:" + "31" * 32,
        "diagnostics_run_id": 11202,
        "diagnostics_artifact_digest": "sha256:" + "32" * 32,
        "diagnostics_handoff_sha256": "33" * 32,
        "diagnostics_sha256": "34" * 32,
        "diagnostics_summary_sha256": "35" * 32,
        "candidate_research_run_id": 11102,
        "candidate_artifact_digest": "sha256:" + "22" * 32,
        "candidate_handoff_sha256": "24" * 32,
        "candidate_specs_sha256": candidate_specs_sha256(),
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "36" * 20,
        "canonical_ledger_commit_sha": "36" * 20,
        "candidates": 9,
        "detector_freeze_base_inputs": {
            "candidate_research_run_id": "11102",
            "expected_candidate_artifact_digest": "sha256:" + "22" * 32,
            "expected_candidate_handoff_sha256": "24" * 32,
            "diagnostics_run_id": "11202",
            "expected_diagnostics_artifact_digest": "sha256:" + "32" * 32,
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


def test_diagnostics_completion_stops_at_explicit_selection_gate():
    report = validate_phase2_dump_diagnostics_completion_receipt(
        diagnostics_completion()
    )
    assert report["selected_candidate_id"] is None
    assert report["selected_candidate_id_required"] is True
    assert report["detector_freeze_ready"] is False


def test_diagnostics_completion_rejects_hidden_selection():
    row = diagnostics_completion()
    row["selected_candidate_id"] = "dd40-rb25"
    with pytest.raises(ValueError, match="selected a candidate"):
        validate_phase2_dump_diagnostics_completion_receipt(row)

def diagnostics_launch_receipt():
    return {
        "version": "phase2-dump-diagnostics-launch-receipt-v1",
        "diagnostics_control_run_id": 12301,
        "candidate_completion_run_id": 12302,
        "candidate_completion_artifact_digest": "sha256:" + "51" * 32,
        "candidate_research_run_id": 12303,
        "candidate_research_artifact_digest": "sha256:" + "52" * 32,
        "candidate_research_handoff_sha256": "53" * 32,
        "diagnostics_run_id": 12304,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "54" * 20,
        "canonical_ledger_commit_sha": "54" * 20,
        "candidate_specs_sha256": "55" * 32,
        "candidate_count": 24,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "uses_outcome_labels": False,
        "candidate_selected": False,
        "detector_freeze_ready": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": True,
    }


def test_diagnostics_launch_remains_outcome_blind():
    report = validate_phase2_dump_diagnostics_launch_receipt(
        diagnostics_launch_receipt()
    )
    assert report["candidate_count"] == 24
    row = diagnostics_launch_receipt()
    row["detector_freeze_ready"] = True
    with pytest.raises(ValueError, match="self-approves freeze"):
        validate_phase2_dump_diagnostics_launch_receipt(row)


def diagnostics_completion_receipt():
    launch = diagnostics_launch_receipt()
    ids = [f"candidate-{index:02d}" for index in range(24)]
    return {
        "version": "phase2-dump-diagnostics-completion-receipt-v1",
        "diagnostics_completion_control_run_id": 12401,
        "diagnostics_launch_run_id": 12402,
        "diagnostics_launch_artifact_digest": "sha256:" + "61" * 32,
        "candidate_research_run_id": launch["candidate_research_run_id"],
        "candidate_research_artifact_digest": launch[
            "candidate_research_artifact_digest"
        ],
        "candidate_research_handoff_sha256": launch[
            "candidate_research_handoff_sha256"
        ],
        "diagnostics_run_id": launch["diagnostics_run_id"],
        "diagnostics_artifact_digest": "sha256:" + "62" * 32,
        "diagnostics_sha256": "63" * 32,
        "diagnostics_summary_sha256": "64" * 32,
        "diagnostics_handoff_sha256": "65" * 32,
        "execution_branch": launch["execution_branch"],
        "execution_head_sha": launch["execution_head_sha"],
        "canonical_ledger_commit_sha": launch["canonical_ledger_commit_sha"],
        "candidate_specs_sha256": launch["candidate_specs_sha256"],
        "candidate_count": 24,
        "candidate_ids": ids,
        "detector_freeze_base_inputs": {
            "candidate_research_run_id": "12303",
            "expected_candidate_artifact_digest": "sha256:" + "52" * 32,
            "expected_candidate_handoff_sha256": "53" * 32,
            "diagnostics_run_id": "12304",
            "expected_diagnostics_artifact_digest": "sha256:" + "62" * 32,
            "expected_diagnostics_handoff_sha256": "65" * 32,
        },
        "target_run_completed": True,
        "target_run_successful": True,
        "uses_outcome_labels": False,
        "candidate_selected": False,
        "detector_freeze_ready": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
        "workflow_dispatch_performed": False,
    }


def test_diagnostics_completion_requires_explicit_selected_id_later():
    report = validate_phase2_dump_diagnostics_completion_receipt(
        diagnostics_completion_receipt()
    )
    assert report["selected_candidate_id_required"] is True
    assert len(report["candidate_ids"]) == 24
    assert "selected_candidate_id" not in report["detector_freeze_base_inputs"]

