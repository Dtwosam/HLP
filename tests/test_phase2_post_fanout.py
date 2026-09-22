import pytest

from hlp.data.phase2_first_wave import (
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
)
from hlp.data.phase2_post_fanout import (
    PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS,
    PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS,
    PHASE2_POST_FANOUT_AUTO_NODE_IDS,
    PHASE2_POST_FANOUT_MANUAL_NODE_IDS,
    validate_phase2_post_fanout_stage,
    validate_phase2_post_fanout_wave_completion,
    validate_phase2_post_fanout_wave_launch_receipt,
)


def plans():
    completed = list(PHASE2_FIRST_WAVE_NODE_IDS) + list(
        PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
    )
    ready = list(PHASE2_POST_FANOUT_AUTO_NODE_IDS) + list(
        PHASE2_POST_FANOUT_MANUAL_NODE_IDS
    )
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "completed_node_ids": completed,
        "ready_to_dispatch_node_ids": ready,
    }
    rows = []
    for index, node_id in enumerate(PHASE2_POST_FANOUT_AUTO_NODE_IDS):
        name = f"dependency_{index}_run_id"
        rows.append({
            "node_id": node_id,
            "workflow": f"{node_id.replace(':', '-')}.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {name: str(100 + index)},
            "remaining_manual_inputs": [],
            "all_dispatch_input_names": [name],
            "requires_archive_secret": True,
            "requires_explicit_approval": False,
        })
    rows.append({
        "node_id": "promote:hood_fun_current",
        "workflow": "phase2-source-coverage-promotion.yml",
        "status": "ready_to_dispatch",
        "run_id_inputs": {"coverage_run_id": "999"},
        "remaining_manual_inputs": [
            "coverage_artifact_name",
            "expected_artifact_digest",
            "coverage_report_path",
            "expected_report_sha256",
            "expected_source_id",
        ],
        "all_dispatch_input_names": [
            "coverage_run_id",
            "coverage_artifact_name",
            "expected_artifact_digest",
            "coverage_report_path",
            "expected_report_sha256",
            "expected_source_id",
        ],
        "requires_archive_secret": False,
        "requires_explicit_approval": False,
    })
    dispatch = {
        "run_id_inputs_generated_from_verified_receipts": True,
        "non_run_inputs_left_explicit": True,
        "workflow_dispatch_performed": False,
        "nodes": rows,
    }
    return execution, dispatch


def test_post_fanout_stage_separates_nine_auto_nodes_from_promotion():
    execution, dispatch = plans()
    report = validate_phase2_post_fanout_stage(
        execution,
        dispatch,
    )

    assert report["auto_nodes_count"] == 9
    assert report["manual_promotion_node_ids"] == [
        "promote:hood_fun_current"
    ]
    assert report["hood_fun_current_promotion_held_for_operator"] is True
    assert report["canonical_ledger_write_authorized"] is False


def test_post_fanout_stage_rejects_ready_set_drift():
    execution, dispatch = plans()
    execution["ready_to_dispatch_node_ids"].remove(
        "coverage:noxa"
    )
    with pytest.raises(ValueError, match="ready-node set drift"):
        validate_phase2_post_fanout_stage(execution, dispatch)


def test_post_fanout_stage_rejects_manual_input_on_auto_node():
    execution, dispatch = plans()
    dispatch["nodes"][0]["remaining_manual_inputs"] = ["unexpected"]
    with pytest.raises(ValueError, match="has manual inputs"):
        validate_phase2_post_fanout_stage(execution, dispatch)


def test_post_fanout_stage_rejects_promotion_contract_drift():
    execution, dispatch = plans()
    dispatch["nodes"][-1]["remaining_manual_inputs"].remove(
        "expected_report_sha256"
    )
    with pytest.raises(ValueError, match="manual-input contract drift"):
        validate_phase2_post_fanout_stage(execution, dispatch)



def post_fanout_launch_receipt():
    controls = {
        node_id: 6000 + index
        for index, node_id in enumerate(
            PHASE2_POST_FANOUT_AUTO_NODE_IDS
        )
    }
    targets = {
        node_id: 7000 + index
        for index, node_id in enumerate(
            PHASE2_POST_FANOUT_AUTO_NODE_IDS
        )
    }
    return {
        "version": "phase2-post-fanout-wave-launch-receipt-v1",
        "post_fanout_control_run_id": 5900,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "archive_fanout_completion_run_id": 5901,
        "archive_fanout_completion_artifact_digest": (
            "sha256:" + "ef" * 32
        ),
        "planner_run_id": 5902,
        "planner_artifact_digest": "sha256:" + "12" * 32,
        "node_dispatch_control_run_ids": controls,
        "target_run_ids": targets,
        "auto_node_ids": list(PHASE2_POST_FANOUT_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "hood_fun_current_promotion_held_for_operator": True,
        "target_runs_created": 9,
        "target_runs_waited_for_completion": False,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def test_post_fanout_launch_receipt_validates_completion_handoff():
    report = validate_phase2_post_fanout_wave_launch_receipt(
        post_fanout_launch_receipt()
    )

    assert report["post_fanout_control_run_id"] == 5900
    assert report["target_runs_created"] == 9
    assert report["hood_fun_current_promotion_held_for_operator"] is True


def after_post_fanout_plans():
    completed = (
        list(PHASE2_FIRST_WAVE_NODE_IDS)
        + list(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        + list(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
    )
    ready = (
        list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS)
    )
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "completed_node_ids": completed,
        "ready_to_dispatch_node_ids": ready,
    }
    verified = {
        "all_runs_current_or_ledger_only_ancestors": True,
        "completed_node_ids": completed,
        "node_dispatch_run_ids_consumed": list(range(8000, 8024)),
    }
    rows = []
    for index, node_id in enumerate(
        PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS
    ):
        input_name = f"dep_{index}_run_id"
        rows.append({
            "node_id": node_id,
            "workflow": f"{node_id.replace(':', '-')}.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {input_name: str(9000 + index)},
            "remaining_manual_inputs": [],
            "all_dispatch_input_names": [input_name],
            "requires_explicit_approval": False,
        })
    rows.append({
        "node_id": "promote:pools_fun",
        "workflow": "phase2-source-coverage-promotion.yml",
        "status": "ready_to_dispatch",
        "run_id_inputs": {"coverage_run_id": "9999"},
        "remaining_manual_inputs": [
            "coverage_artifact_name",
            "expected_artifact_digest",
            "coverage_report_path",
            "expected_report_sha256",
            "expected_source_id",
        ],
        "all_dispatch_input_names": [
            "coverage_run_id",
            "coverage_artifact_name",
            "expected_artifact_digest",
            "coverage_report_path",
            "expected_report_sha256",
            "expected_source_id",
        ],
        "requires_explicit_approval": False,
    })
    dispatch = {
        "run_id_inputs_generated_from_verified_receipts": True,
        "non_run_inputs_left_explicit": True,
        "workflow_dispatch_performed": False,
        "nodes": rows,
    }
    return execution, verified, dispatch


def test_post_fanout_completion_freezes_seven_auto_and_one_promotion():
    execution, verified, dispatch = after_post_fanout_plans()
    report = validate_phase2_post_fanout_wave_completion(
        execution,
        verified,
        dispatch,
    )

    assert report["completed_execution_nodes"] == 24
    assert report["node_dispatch_control_runs_consumed"] == 24
    assert len(report["auto_node_ids"]) == 7
    assert report["manual_promotion_node_ids"] == ["promote:pools_fun"]
    assert report["pools_fun_promotion_held_for_operator"] is True


def test_post_fanout_completion_rejects_ready_set_drift():
    execution, verified, dispatch = after_post_fanout_plans()
    execution["ready_to_dispatch_node_ids"].remove(
        "coverage:doppler"
    )
    with pytest.raises(ValueError, match="ready-node set drift"):
        validate_phase2_post_fanout_wave_completion(
            execution,
            verified,
            dispatch,
        )
