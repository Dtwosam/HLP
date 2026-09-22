import pytest

from hlp.data.phase2_first_wave import (
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
)
from hlp.data.phase2_post_fanout import (
    PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS,
    PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS,
    PHASE2_AFTER_POST_FANOUT_NEXT_AUTO_NODE_IDS,
    PHASE2_AFTER_POST_FANOUT_NEXT_MANUAL_NODE_IDS,
    PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS,
    PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS,
    PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS,
    PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS,
    PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS,
    PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS,
    PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS,
    PHASE2_PRE_SELECTOR_AUTO_NODE_IDS,
    PHASE2_PRE_SELECTOR_MANUAL_NODE_IDS,
    PHASE2_POST_FANOUT_AUTO_NODE_IDS,
    PHASE2_POST_FANOUT_MANUAL_NODE_IDS,
    validate_phase2_after_post_fanout_wave_completion,
    validate_phase2_after_post_fanout_wave_completion_receipt,
    validate_phase2_after_post_fanout_wave_launch_receipt,
    validate_phase2_pre_selector_wave_completion,
    validate_phase2_selector_freeze_completion,
    validate_phase2_post_selector_wave_completion,
    validate_phase2_post_selector_wave_launch_receipt,
    validate_phase2_post_selector_wave_completion_receipt,
    validate_phase2_pre_selector_wave_completion_receipt,
    validate_phase2_pre_selector_wave_launch_receipt,
    validate_phase2_post_fanout_stage,
    validate_phase2_post_fanout_wave_completion,
    validate_phase2_post_fanout_wave_completion_receipt,
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



def post_fanout_completion_receipt():
    return {
        "version": "phase2-post-fanout-wave-completion-receipt-v1",
        "post_fanout_completion_control_run_id": 10001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "post_fanout_wave_launch_run_id": 10002,
        "post_fanout_wave_artifact_digest": "sha256:" + "ef" * 32,
        "verified_target_run_ids": {
            node_id: 10100 + index
            for index, node_id in enumerate(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        },
        "node_dispatch_control_run_ids_consumed": list(range(10200, 10224)),
        "planner_run_id": 10003,
        "planner_artifact_digest": "sha256:" + "12" * 32,
        "auto_node_ids": list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "post_fanout_targets_completed_successfully": True,
        "planner_refreshed": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def test_post_fanout_completion_receipt_validates_next_wave_handoff():
    report = validate_phase2_post_fanout_wave_completion_receipt(
        post_fanout_completion_receipt()
    )

    assert report["post_fanout_completion_control_run_id"] == 10001
    assert len(report["auto_node_ids"]) == 7
    assert report["manual_promotion_node_ids"] == ["promote:pools_fun"]


def after_post_fanout_wave_completed_plans():
    completed = (
        list(PHASE2_FIRST_WAVE_NODE_IDS)
        + list(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        + list(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
    )
    ready = (
        list(PHASE2_AFTER_POST_FANOUT_NEXT_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_POST_FANOUT_NEXT_MANUAL_NODE_IDS)
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
        "node_dispatch_run_ids_consumed": list(range(11000, 11031)),
    }
    rows = []
    for index, node_id in enumerate(
        PHASE2_AFTER_POST_FANOUT_NEXT_AUTO_NODE_IDS
    ):
        input_name = f"next_dep_{index}_run_id"
        rows.append({
            "node_id": node_id,
            "workflow": f"{node_id.replace(':', '-')}.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {input_name: str(12000 + index)},
            "remaining_manual_inputs": [],
            "all_dispatch_input_names": [input_name],
            "requires_explicit_approval": False,
        })
    rows.append({
        "node_id": "promote:pools_fun",
        "workflow": "phase2-source-coverage-promotion.yml",
        "status": "ready_to_dispatch",
        "run_id_inputs": {"coverage_run_id": "12999"},
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


def test_after_post_fanout_completion_freezes_four_auto_and_promotion():
    execution, verified, dispatch = after_post_fanout_wave_completed_plans()
    report = validate_phase2_after_post_fanout_wave_completion(
        execution,
        verified,
        dispatch,
    )

    assert report["completed_execution_nodes"] == 31
    assert report["node_dispatch_control_runs_consumed"] == 31
    assert len(report["auto_node_ids"]) == 4
    assert report["manual_promotion_node_ids"] == ["promote:pools_fun"]
    assert report["pools_fun_promotion_held_for_operator"] is True


def test_after_post_fanout_completion_rejects_next_ready_drift():
    execution, verified, dispatch = after_post_fanout_wave_completed_plans()
    execution["ready_to_dispatch_node_ids"].remove(
        "shared:direct_quality_evidence"
    )
    with pytest.raises(ValueError, match="next-wave ready-node set drift"):
        validate_phase2_after_post_fanout_wave_completion(
            execution,
            verified,
            dispatch,
        )



def after_post_fanout_launch_receipt():
    return {
        "version": "phase2-after-post-fanout-wave-launch-receipt-v1",
        "after_post_fanout_control_run_id": 13001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "post_fanout_wave_completion_run_id": 13002,
        "post_fanout_wave_completion_artifact_digest": (
            "sha256:" + "ef" * 32
        ),
        "planner_run_id": 13003,
        "planner_artifact_digest": "sha256:" + "12" * 32,
        "node_dispatch_control_run_ids": {
            node_id: 13100 + index
            for index, node_id in enumerate(
                PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS
            )
        },
        "target_run_ids": {
            node_id: 13200 + index
            for index, node_id in enumerate(
                PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS
            )
        },
        "auto_node_ids": list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_FANOUT_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "target_runs_created": 7,
        "target_runs_waited_for_completion": False,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def test_after_post_fanout_launch_receipt_validates_seven_node_handoff():
    report = validate_phase2_after_post_fanout_wave_launch_receipt(
        after_post_fanout_launch_receipt()
    )

    assert report["after_post_fanout_control_run_id"] == 13001
    assert report["target_runs_created"] == 7
    assert report["pools_fun_promotion_held_for_operator"] is True



def seven_node_completion_receipt():
    return {
        "version": "phase2-after-post-fanout-wave-completion-receipt-v1",
        "after_post_fanout_completion_control_run_id": 14001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "after_post_fanout_wave_launch_run_id": 14002,
        "after_post_fanout_wave_artifact_digest": "sha256:" + "ef" * 32,
        "verified_target_run_ids": {
            node_id: 14100 + index
            for index, node_id in enumerate(
                PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS
            )
        },
        "node_dispatch_control_run_ids_consumed": list(range(14200, 14231)),
        "planner_run_id": 14003,
        "planner_artifact_digest": "sha256:" + "12" * 32,
        "auto_node_ids": list(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": ["promote:pools_fun"],
        "pools_fun_promotion_held_for_operator": True,
        "after_post_fanout_targets_completed_successfully": True,
        "planner_refreshed": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def test_seven_node_completion_receipt_validates_pre_selector_handoff():
    report = validate_phase2_after_post_fanout_wave_completion_receipt(
        seven_node_completion_receipt()
    )
    assert report["after_post_fanout_completion_control_run_id"] == 14001
    assert len(report["auto_node_ids"]) == 4
    assert report["manual_promotion_node_ids"] == ["promote:pools_fun"]


def pre_selector_completed_plans():
    completed = (
        list(PHASE2_FIRST_WAVE_NODE_IDS)
        + list(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        + list(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
    )
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "completed_node_ids": completed,
        "ready_to_dispatch_node_ids": (
            list(PHASE2_AFTER_PRE_SELECTOR_AUTO_NODE_IDS)
            + list(PHASE2_AFTER_PRE_SELECTOR_MANUAL_NODE_IDS)
        ),
        "awaiting_explicit_approval_node_ids": list(
            PHASE2_AFTER_PRE_SELECTOR_APPROVAL_NODE_IDS
        ),
    }
    verified = {
        "all_runs_current_or_ledger_only_ancestors": True,
        "completed_node_ids": completed,
        "node_dispatch_run_ids_consumed": list(range(15000, 15035)),
    }
    rows = [
        {
            "node_id": "coverage:trench_today",
            "workflow": "phase2-trench-source-coverage.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {"registry_run_id": "15100"},
            "remaining_manual_inputs": [],
            "all_dispatch_input_names": ["registry_run_id"],
            "requires_explicit_approval": False,
        },
        {
            "node_id": "promote:pools_fun",
            "workflow": "phase2-source-coverage-promotion.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {"coverage_run_id": "15101"},
            "remaining_manual_inputs": [
                "coverage_artifact_name",
                "coverage_report_path",
                "expected_artifact_digest",
                "expected_report_sha256",
                "expected_source_id",
            ],
            "all_dispatch_input_names": [
                "coverage_run_id",
                "coverage_artifact_name",
                "coverage_report_path",
                "expected_artifact_digest",
                "expected_report_sha256",
                "expected_source_id",
            ],
            "requires_explicit_approval": False,
        },
        {
            "node_id": "shared:direct_selector_freeze",
            "workflow": "phase2-direct-market-selector-freeze.yml",
            "status": "awaiting_explicit_approval",
            "run_id_inputs": {"evidence_run_id": "15102"},
            "remaining_manual_inputs": [
                "expected_artifact_digest",
                "expected_handoff_sha256",
                "freeze_active_quote_liquidity_causal_v1",
            ],
            "all_dispatch_input_names": [
                "evidence_run_id",
                "expected_artifact_digest",
                "expected_handoff_sha256",
                "freeze_active_quote_liquidity_causal_v1",
            ],
            "requires_explicit_approval": True,
        },
    ]
    dispatch = {
        "run_id_inputs_generated_from_verified_receipts": True,
        "nodes": rows,
    }
    return execution, verified, dispatch


def test_pre_selector_completion_freezes_auto_promotion_and_approval():
    execution, verified, dispatch = pre_selector_completed_plans()
    report = validate_phase2_pre_selector_wave_completion(
        execution,
        verified,
        dispatch,
    )
    assert report["completed_execution_nodes"] == 35
    assert report["auto_node_ids"] == ["coverage:trench_today"]
    assert report["manual_promotion_node_ids"] == ["promote:pools_fun"]
    assert report["approval_node_ids"] == [
        "shared:direct_selector_freeze"
    ]
    assert report["selector_approval_performed"] is False


def test_pre_selector_completion_rejects_missing_selector_approval_gate():
    execution, verified, dispatch = pre_selector_completed_plans()
    execution["awaiting_explicit_approval_node_ids"] = []
    with pytest.raises(ValueError, match="approval-node set drift"):
        validate_phase2_pre_selector_wave_completion(
            execution,
            verified,
            dispatch,
        )



def pre_selector_launch_receipt():
    return {
        "version": "phase2-pre-selector-wave-launch-receipt-v1",
        "pre_selector_control_run_id": 16001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "after_post_fanout_wave_completion_run_id": 16002,
        "after_post_fanout_wave_completion_artifact_digest": (
            "sha256:" + "ef" * 32
        ),
        "planner_run_id": 16003,
        "planner_artifact_digest": "sha256:" + "12" * 32,
        "node_dispatch_control_run_ids": {
            node_id: 16100 + index
            for index, node_id in enumerate(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        },
        "target_run_ids": {
            node_id: 16200 + index
            for index, node_id in enumerate(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        },
        "auto_node_ids": list(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_PRE_SELECTOR_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "target_runs_created": 4,
        "target_runs_waited_for_completion": False,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def test_pre_selector_launch_receipt_validates_four_node_handoff():
    report = validate_phase2_pre_selector_wave_launch_receipt(
        pre_selector_launch_receipt()
    )
    assert report["pre_selector_control_run_id"] == 16001
    assert report["target_runs_created"] == 4
    assert report["pools_fun_promotion_held_for_operator"] is True



def pre_selector_completion_receipt():
    return {
        "version": "phase2-pre-selector-wave-completion-receipt-v1",
        "pre_selector_completion_control_run_id": 17001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "pre_selector_wave_launch_run_id": 17002,
        "pre_selector_wave_artifact_digest": "sha256:" + "ef" * 32,
        "verified_target_run_ids": {
            node_id: 17100 + index
            for index, node_id in enumerate(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        },
        "node_dispatch_control_run_ids_consumed": list(range(17200, 17235)),
        "planner_run_id": 17003,
        "planner_artifact_digest": "sha256:" + "12" * 32,
        "auto_node_ids": ["coverage:trench_today"],
        "manual_promotion_node_ids": ["promote:pools_fun"],
        "approval_node_ids": ["shared:direct_selector_freeze"],
        "selector_manual_inputs": [
            "expected_artifact_digest",
            "expected_handoff_sha256",
            "freeze_active_quote_liquidity_causal_v1",
        ],
        "pools_fun_promotion_held_for_operator": True,
        "pre_selector_targets_completed_successfully": True,
        "planner_refreshed": True,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def test_pre_selector_completion_receipt_validates_approval_handoff():
    report = validate_phase2_pre_selector_wave_completion_receipt(
        pre_selector_completion_receipt()
    )
    assert report["pre_selector_completion_control_run_id"] == 17001
    assert report["auto_node_ids"] == ["coverage:trench_today"]
    assert report["approval_node_ids"] == [
        "shared:direct_selector_freeze"
    ]
    assert report["selector_approval_performed"] is False



def selector_freeze_completed_plans():
    completed = (
        list(PHASE2_FIRST_WAVE_NODE_IDS)
        + list(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        + list(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        + ["shared:direct_selector_freeze"]
    )
    ready = (
        list(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS)
    )
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "completed_node_ids": completed,
        "ready_to_dispatch_node_ids": ready,
        "awaiting_explicit_approval_node_ids": [],
    }
    verified = {
        "all_runs_current_or_ledger_only_ancestors": True,
        "completed_node_ids": completed,
        "node_dispatch_run_ids_consumed": list(range(15000, 15035)),
    }
    rows = []
    for index, node_id in enumerate(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS):
        input_name = f"selector_dep_{index}_run_id"
        rows.append({
            "node_id": node_id,
            "workflow": f"{node_id.replace(':', '-')}.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {input_name: str(16000 + index)},
            "remaining_manual_inputs": [],
            "all_dispatch_input_names": [input_name],
            "requires_explicit_approval": False,
        })
    rows.append({
        "node_id": "promote:pools_fun",
        "workflow": "phase2-source-coverage-promotion.yml",
        "status": "ready_to_dispatch",
        "run_id_inputs": {"coverage_run_id": "16999"},
        "remaining_manual_inputs": [
            "coverage_artifact_name",
            "coverage_report_path",
            "expected_artifact_digest",
            "expected_report_sha256",
            "expected_source_id",
        ],
        "all_dispatch_input_names": [
            "coverage_run_id",
            "coverage_artifact_name",
            "coverage_report_path",
            "expected_artifact_digest",
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


def test_selector_freeze_completion_unlocks_two_auto_nodes():
    execution, verified, dispatch = selector_freeze_completed_plans()
    report = validate_phase2_selector_freeze_completion(
        execution,
        verified,
        dispatch,
    )

    assert report["completed_execution_nodes"] == 36
    assert report["node_dispatch_control_runs_consumed"] == 35
    assert report["auto_node_ids"] == [
        "shared:direct_source_population",
        "coverage:trench_today",
    ]
    assert report["manual_promotion_node_ids"] == ["promote:pools_fun"]
    assert report["selector_approval_performed"] is True
    assert report["selector_freeze_completed"] is True


def test_selector_freeze_completion_rejects_remaining_approval():
    execution, verified, dispatch = selector_freeze_completed_plans()
    execution["awaiting_explicit_approval_node_ids"] = [
        "shared:direct_selector_freeze"
    ]
    with pytest.raises(ValueError, match="remains after approved freeze"):
        validate_phase2_selector_freeze_completion(
            execution,
            verified,
            dispatch,
        )



def post_selector_completed_plans():
    completed = (
        list(PHASE2_FIRST_WAVE_NODE_IDS)
        + list(PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS)
        + list(PHASE2_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_POST_FANOUT_AUTO_NODE_IDS)
        + list(PHASE2_PRE_SELECTOR_AUTO_NODE_IDS)
        + ["shared:direct_selector_freeze"]
        + list(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS)
    )
    ready = (
        list(PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS)
        + list(PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS)
    )
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "completed_node_ids": completed,
        "ready_to_dispatch_node_ids": ready,
        "awaiting_explicit_approval_node_ids": [],
    }
    verified = {
        "all_runs_current_or_ledger_only_ancestors": True,
        "completed_node_ids": completed,
        "node_dispatch_run_ids_consumed": list(range(17000, 17037)),
    }
    rows = []
    for index, node_id in enumerate(
        PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS
    ):
        input_name = f"direct_dep_{index}_run_id"
        rows.append({
            "node_id": node_id,
            "workflow": "phase2-direct-source-coverage.yml",
            "status": "ready_to_dispatch",
            "run_id_inputs": {input_name: str(18000 + index)},
            "remaining_manual_inputs": [],
            "all_dispatch_input_names": [input_name],
            "requires_explicit_approval": False,
        })
    rows.append({
        "node_id": "promote:pools_fun",
        "workflow": "phase2-source-coverage-promotion.yml",
        "status": "ready_to_dispatch",
        "run_id_inputs": {"coverage_run_id": "18999"},
        "remaining_manual_inputs": [
            "coverage_artifact_name",
            "coverage_report_path",
            "expected_artifact_digest",
            "expected_report_sha256",
            "expected_source_id",
        ],
        "all_dispatch_input_names": [
            "coverage_run_id",
            "coverage_artifact_name",
            "coverage_report_path",
            "expected_artifact_digest",
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


def test_post_selector_completion_unlocks_three_direct_coverages():
    execution, verified, dispatch = post_selector_completed_plans()
    report = validate_phase2_post_selector_wave_completion(
        execution,
        verified,
        dispatch,
    )

    assert report["completed_execution_nodes"] == 38
    assert report["node_dispatch_control_runs_consumed"] == 37
    assert report["auto_node_ids"] == [
        "coverage:direct_uniswap_v3",
        "coverage:direct_sushiswap_v3",
        "coverage:direct_uniswap_v4",
    ]
    assert report["manual_promotion_node_ids"] == ["promote:pools_fun"]


def test_post_selector_completion_rejects_direct_ready_drift():
    execution, verified, dispatch = post_selector_completed_plans()
    execution["ready_to_dispatch_node_ids"].remove(
        "coverage:direct_uniswap_v4"
    )
    with pytest.raises(ValueError, match="direct-coverage ready-node set drift"):
        validate_phase2_post_selector_wave_completion(
            execution,
            verified,
            dispatch,
        )



def post_selector_launch_receipt():
    return {
        "version": "phase2-post-selector-wave-launch-receipt-v1",
        "post_selector_control_run_id": 19001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "aa" * 20,
        "canonical_coverage_ledger_sha256": "bb" * 32,
        "approved_freeze_run_id": 19002,
        "approved_freeze_artifact_digest": "sha256:" + "cc" * 32,
        "selector_run_id": 19003,
        "planner_run_id": 19004,
        "planner_artifact_digest": "sha256:" + "dd" * 32,
        "node_dispatch_control_run_ids": {
            node_id: 19100 + index
            for index, node_id in enumerate(
                PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS
            )
        },
        "target_run_ids": {
            node_id: 19200 + index
            for index, node_id in enumerate(
                PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS
            )
        },
        "auto_node_ids": list(PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_SELECTOR_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "target_runs_created": 2,
        "target_runs_waited_for_completion": False,
        "selector_approval_performed": True,
        "selector_freeze_completed": True,
        "coverage_promotion_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def test_post_selector_launch_receipt_validates_two_node_handoff():
    report = validate_phase2_post_selector_wave_launch_receipt(
        post_selector_launch_receipt()
    )

    assert report["post_selector_control_run_id"] == 19001
    assert report["target_runs_created"] == 2
    assert report["selector_approval_performed"] is True
    assert report["pools_fun_promotion_held_for_operator"] is True



def post_selector_completion_receipt():
    return {
        "version": "phase2-post-selector-wave-completion-receipt-v1",
        "post_selector_completion_control_run_id": 20001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "aa" * 20,
        "canonical_coverage_ledger_sha256": "bb" * 32,
        "post_selector_wave_launch_run_id": 20002,
        "post_selector_wave_artifact_digest": "sha256:" + "cc" * 32,
        "approved_freeze_run_id": 20003,
        "selector_run_id": 20004,
        "verified_target_run_ids": {
            node_id: 20100 + index
            for index, node_id in enumerate(
                PHASE2_AFTER_SELECTOR_AUTO_NODE_IDS
            )
        },
        "node_dispatch_control_run_ids_consumed": list(range(20200, 20237)),
        "planner_run_id": 20005,
        "planner_artifact_digest": "sha256:" + "dd" * 32,
        "auto_node_ids": list(PHASE2_AFTER_POST_SELECTOR_AUTO_NODE_IDS),
        "manual_promotion_node_ids": list(
            PHASE2_AFTER_POST_SELECTOR_MANUAL_NODE_IDS
        ),
        "pools_fun_promotion_held_for_operator": True,
        "post_selector_targets_completed_successfully": True,
        "planner_refreshed": True,
        "selector_approval_performed": True,
        "selector_freeze_completed": True,
        "coverage_promotion_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
    }


def test_post_selector_completion_receipt_validates_direct_boundary():
    report = validate_phase2_post_selector_wave_completion_receipt(
        post_selector_completion_receipt()
    )

    assert report["post_selector_completion_control_run_id"] == 20001
    assert len(report["auto_node_ids"]) == 3
    assert report["selector_freeze_completed"] is True
    assert report["pools_fun_promotion_held_for_operator"] is True
