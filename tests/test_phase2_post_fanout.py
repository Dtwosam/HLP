import pytest

from hlp.data.phase2_first_wave import (
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
)
from hlp.data.phase2_post_fanout import (
    PHASE2_POST_FANOUT_AUTO_NODE_IDS,
    PHASE2_POST_FANOUT_MANUAL_NODE_IDS,
    validate_phase2_post_fanout_stage,
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
