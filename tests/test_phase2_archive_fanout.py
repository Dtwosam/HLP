import pytest

from hlp.data.phase2_archive_fanout import (
    PHASE2_ARCHIVE_FANOUT_COMPLETION_VERSION,
    PHASE2_ARCHIVE_FANOUT_RECEIPT_VERSION,
    validate_phase2_archive_fanout_completion,
    validate_phase2_archive_fanout_launch_receipt,
)
from hlp.data.phase2_first_wave import (
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
)


def launch_receipt():
    controls = {
        node_id: 1000 + index
        for index, node_id in enumerate(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        )
    }
    targets = {
        node_id: 2000 + index
        for index, node_id in enumerate(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        )
    }
    return {
        "version": PHASE2_ARCHIVE_FANOUT_RECEIPT_VERSION,
        "archive_fanout_control_run_id": 900,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "first_wave_launch_run_id": 901,
        "first_wave_artifact_digest": "sha256:" + "ef" * 32,
        "planner_run_id": 902,
        "planner_artifact_digest": "sha256:" + "12" * 32,
        "node_dispatch_control_run_ids": controls,
        "target_run_ids": targets,
        "archive_fanout_node_ids": list(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ),
        "fanout_contract": {
            "archive_fanout_launch_authorized": True,
        },
        "target_runs_created": 13,
        "target_runs_waited_for_completion": False,
        "coverage_promotion_performed": False,
        "selector_approval_performed": False,
        "canonical_coverage_ledger_mutated": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def test_archive_fanout_launch_receipt_validates_handoff():
    report = validate_phase2_archive_fanout_launch_receipt(
        launch_receipt()
    )

    assert report["archive_fanout_control_run_id"] == 900
    assert report["target_runs_created"] == 13
    assert report["canonical_ledger_write_authorized"] is False


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("version", "other", "version changed"),
        ("target_runs_created", 12, "target count drift"),
        (
            "target_runs_waited_for_completion",
            True,
            "target_runs_waited_for_completion",
        ),
        (
            "canonical_coverage_ledger_mutated",
            True,
            "canonical_coverage_ledger_mutated",
        ),
    ],
)
def test_archive_fanout_launch_receipt_rejects_tampering(
    field,
    value,
    match,
):
    row = launch_receipt()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        validate_phase2_archive_fanout_launch_receipt(row)


def completion_plans():
    expected = list(PHASE2_FIRST_WAVE_NODE_IDS) + list(
        PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
    )
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "completed_node_ids": expected,
        "ready_to_dispatch_node_ids": [
            "shared:direct_market_registry",
            "coverage:pools_fun",
        ],
    }
    verified = {
        "all_runs_current_or_ledger_only_ancestors": True,
        "completed_node_ids": expected,
        "node_dispatch_run_ids_consumed": list(range(3000, 3015)),
        "node_dispatch_receipts_consumed": [
            {
                "control_run_id": 3000 + index,
                "node_id": node_id,
                "target_run_id": 4000 + index,
            }
            for index, node_id in enumerate(expected)
        ],
    }
    return execution, verified


def test_archive_fanout_completion_accepts_exact_15_node_credit():
    execution, verified = completion_plans()
    report = validate_phase2_archive_fanout_completion(
        execution,
        verified,
    )

    assert report["version"] == PHASE2_ARCHIVE_FANOUT_COMPLETION_VERSION
    assert report["completed_execution_nodes"] == 15
    assert report["node_dispatch_control_runs_consumed"] == 15
    assert report["archive_fanout_targets_credited"] is True
    assert report["next_ready_nodes"] == 2


def test_archive_fanout_completion_rejects_missing_target_credit():
    execution, verified = completion_plans()
    execution["completed_node_ids"].remove("shared:v3_initialize")
    with pytest.raises(ValueError, match="node-credit drift"):
        validate_phase2_archive_fanout_completion(execution, verified)


def test_archive_fanout_completion_rejects_completed_node_still_ready():
    execution, verified = completion_plans()
    execution["ready_to_dispatch_node_ids"].append(
        "shared:v3_initialize"
    )
    with pytest.raises(ValueError, match="remain ready"):
        validate_phase2_archive_fanout_completion(execution, verified)
