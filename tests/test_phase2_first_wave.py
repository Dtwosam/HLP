import copy

import pytest

from hlp.data.phase2_first_wave import (
    PHASE2_FIRST_WAVE_LAUNCH_VERSION,
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
    validate_phase2_archive_fanout_launch,
    validate_phase2_first_wave_completion,
    validate_phase2_first_wave_launch,
    validate_phase2_first_wave_launch_receipt,
)


def plans():
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "phase2_universe_coverage_complete": False,
        "completed_node_ids": [],
        "ready_to_dispatch_node_ids": list(PHASE2_FIRST_WAVE_NODE_IDS),
    }
    dispatch = {
        "run_id_inputs_generated_from_verified_receipts": True,
        "non_run_inputs_left_explicit": True,
        "workflow_dispatch_performed": False,
        "nodes": [
            {
                "node_id": "preflight:archive_authenticated",
                "workflow": "phase2-archive-rpc-preflight.yml",
                "status": "ready_to_dispatch",
                "run_id_inputs": {},
                "remaining_manual_inputs": [],
                "all_dispatch_input_names": [],
                "requires_archive_secret": True,
                "requires_explicit_approval": False,
            },
            {
                "node_id": "shared:quote_registry",
                "workflow": "phase2-direct-quote-registry.yml",
                "status": "ready_to_dispatch",
                "run_id_inputs": {},
                "remaining_manual_inputs": [],
                "all_dispatch_input_names": [],
                "requires_archive_secret": False,
                "requires_explicit_approval": False,
            },
        ],
    }
    return execution, dispatch


def test_first_wave_accepts_exact_initial_state():
    execution, dispatch = plans()
    report = validate_phase2_first_wave_launch(execution, dispatch)

    assert report["version"] == PHASE2_FIRST_WAVE_LAUNCH_VERSION
    assert report["first_wave_node_ids"] == list(PHASE2_FIRST_WAVE_NODE_IDS)
    assert report["archive_preflight_required"] is True
    assert report["manual_inputs_required"] is False
    assert report["canonical_ledger_write_authorized"] is False
    assert report["first_wave_launch_authorized"] is True


@pytest.mark.parametrize(
    ("target", "key", "value", "match"),
    [
        ("execution", "complete_sources", 3, "exactly 2"),
        (
            "execution",
            "canonical_complete_source_ids",
            ["pons_v1", "pons_v2", "pools_fun"],
            "Pons-only",
        ),
        (
            "execution",
            "ready_to_dispatch_node_ids",
            ["shared:quote_registry"],
            "not ready",
        ),
        (
            "dispatch",
            "workflow_dispatch_performed",
            True,
            "already claims",
        ),
    ],
)
def test_first_wave_rejects_state_drift(target, key, value, match):
    execution, dispatch = plans()
    selected = execution if target == "execution" else dispatch
    selected[key] = value
    with pytest.raises(ValueError, match=match):
        validate_phase2_first_wave_launch(execution, dispatch)


def test_first_wave_rejects_manual_or_approval_input_drift():
    execution, dispatch = plans()
    manual = copy.deepcopy(dispatch)
    manual["nodes"][0]["remaining_manual_inputs"] = ["unexpected"]
    with pytest.raises(ValueError, match="manual inputs"):
        validate_phase2_first_wave_launch(execution, manual)

    approval = copy.deepcopy(dispatch)
    approval["nodes"][1]["requires_explicit_approval"] = True
    with pytest.raises(ValueError, match="requires approval"):
        validate_phase2_first_wave_launch(execution, approval)


def test_first_wave_rejects_archive_secret_contract_drift():
    execution, dispatch = plans()
    dispatch["nodes"][0]["requires_archive_secret"] = False
    with pytest.raises(ValueError, match="archive-secret contract drift"):
        validate_phase2_first_wave_launch(execution, dispatch)



def completed_plans():
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "completed_node_ids": list(PHASE2_FIRST_WAVE_NODE_IDS),
        "ready_to_dispatch_node_ids": list(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ),
    }
    verified = {
        "all_runs_current_or_ledger_only_ancestors": True,
        "completed_node_ids": list(PHASE2_FIRST_WAVE_NODE_IDS),
        "node_dispatch_run_ids_consumed": [501, 502],
        "node_dispatch_receipts_consumed": [
            {
                "control_run_id": 501,
                "node_id": "preflight:archive_authenticated",
                "target_run_id": 601,
            },
            {
                "control_run_id": 502,
                "node_id": "shared:quote_registry",
                "target_run_id": 602,
            },
        ],
    }
    return execution, verified


def test_first_wave_completion_requires_credited_targets_and_fanout():
    execution, verified = completed_plans()
    report = validate_phase2_first_wave_completion(
        execution,
        verified,
    )

    assert report["first_wave_targets_credited"] is True
    assert report["archive_fanout_unlocked"] is True
    assert report["canonical_coverage_sources_unchanged"] is True
    assert report["canonical_ledger_write_authorized"] is False


def test_first_wave_completion_rejects_missing_archive_fanout():
    execution, verified = completed_plans()
    execution["ready_to_dispatch_node_ids"].remove(
        "shared:v3_initialize"
    )
    with pytest.raises(ValueError, match="archive fan-out"):
        validate_phase2_first_wave_completion(execution, verified)


def test_first_wave_completion_rejects_wrong_dispatch_receipts():
    execution, verified = completed_plans()
    verified["node_dispatch_receipts_consumed"][1]["node_id"] = (
        "registry:pools_fun"
    )
    with pytest.raises(ValueError, match="do not match first-wave"):
        validate_phase2_first_wave_completion(execution, verified)



def test_first_wave_rejects_existing_execution_credit_or_extra_dispatch_node():
    execution, dispatch = plans()
    execution["completed_node_ids"] = ["shared:quote_registry"]
    with pytest.raises(ValueError, match="zero credited"):
        validate_phase2_first_wave_launch(execution, dispatch)

    execution, dispatch = plans()
    dispatch["nodes"].append({
        "node_id": "registry:pools_fun",
        "workflow": "phase2-pools-fun-registry-backfill.yml",
        "status": "ready_to_dispatch",
        "run_id_inputs": {},
        "remaining_manual_inputs": [],
        "all_dispatch_input_names": [],
        "requires_archive_secret": True,
        "requires_explicit_approval": False,
    })
    with pytest.raises(ValueError, match="exactly the two"):
        validate_phase2_first_wave_launch(execution, dispatch)



def fanout_plans():
    execution = {
        "canonical_complete_source_ids": ["pons_v1", "pons_v2"],
        "complete_sources": 2,
        "incomplete_sources": 12,
        "phase2_universe_coverage_complete": False,
        "completed_node_ids": list(PHASE2_FIRST_WAVE_NODE_IDS),
        "ready_to_dispatch_node_ids": list(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ),
    }
    dispatch = {
        "run_id_inputs_generated_from_verified_receipts": True,
        "non_run_inputs_left_explicit": True,
        "workflow_dispatch_performed": False,
        "nodes": [
            {
                "node_id": node_id,
                "workflow": f"{node_id.replace(':', '-')}.yml",
                "status": "ready_to_dispatch",
                "run_id_inputs": {},
                "remaining_manual_inputs": [],
                "all_dispatch_input_names": [],
                "requires_archive_secret": True,
                "requires_explicit_approval": False,
            }
            for node_id in PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ],
    }
    return execution, dispatch


def test_archive_fanout_accepts_exact_zero_input_post_first_wave_state():
    execution, dispatch = fanout_plans()
    report = validate_phase2_archive_fanout_launch(
        execution,
        dispatch,
    )

    assert report["fanout_nodes"] == 13
    assert report["manual_inputs_required"] is False
    assert report["approval_gated_nodes_present"] is False
    assert report["canonical_ledger_write_authorized"] is False
    assert report["archive_fanout_launch_authorized"] is True


def test_archive_fanout_rejects_ready_set_drift():
    execution, dispatch = fanout_plans()
    execution["ready_to_dispatch_node_ids"].remove(
        "shared:v3_initialize"
    )
    with pytest.raises(ValueError, match="ready-node set drift"):
        validate_phase2_archive_fanout_launch(execution, dispatch)


def test_archive_fanout_rejects_manual_input_or_secret_drift():
    execution, dispatch = fanout_plans()
    dispatch["nodes"][0]["remaining_manual_inputs"] = ["unexpected"]
    with pytest.raises(ValueError, match="manual inputs"):
        validate_phase2_archive_fanout_launch(execution, dispatch)

    execution, dispatch = fanout_plans()
    dispatch["nodes"][0]["requires_archive_secret"] = False
    with pytest.raises(ValueError, match="lost archive-secret gate"):
        validate_phase2_archive_fanout_launch(execution, dispatch)



def first_wave_receipt():
    return {
        "version": "phase2-first-wave-launch-receipt-v1",
        "first_wave_control_run_id": 500,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "ab" * 20,
        "canonical_coverage_ledger_sha256": "cd" * 32,
        "initial_planner_run_id": 501,
        "initial_planner_artifact_digest": "sha256:" + "ef" * 32,
        "node_dispatch_control_run_ids": {
            "preflight:archive_authenticated": 502,
            "shared:quote_registry": 503,
        },
        "target_run_ids": {
            "preflight:archive_authenticated": 504,
            "shared:quote_registry": 505,
        },
        "refreshed_planner_run_id": 506,
        "refreshed_planner_artifact_digest": "sha256:" + "12" * 32,
        "ready_after_first_wave": list(
            PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS
        ),
        "launch_contract": {
            "first_wave_launch_authorized": True,
        },
        "completion_contract": {
            "first_wave_targets_credited": True,
            "archive_fanout_unlocked": True,
        },
        "first_wave_targets_completed_successfully": True,
        "archive_fanout_unlocked": True,
        "canonical_coverage_ledger_mutated": False,
        "selector_approval_performed": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def test_first_wave_receipt_validates_archive_fanout_handoff():
    row = validate_phase2_first_wave_launch_receipt(
        first_wave_receipt()
    )

    assert row["first_wave_control_run_id"] == 500
    assert row["refreshed_planner_run_id"] == 506
    assert row["archive_fanout_unlocked"] is True
    assert row["canonical_ledger_write_authorized"] is False


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("version", "other", "version changed"),
        (
            "archive_fanout_unlocked",
            False,
            "archive_fanout_unlocked",
        ),
        (
            "canonical_coverage_ledger_mutated",
            True,
            "canonical_coverage_ledger_mutated",
        ),
        (
            "canonical_ledger_write_authorized",
            True,
            "canonical_ledger_write_authorized",
        ),
    ],
)
def test_first_wave_receipt_rejects_tampering(field, value, match):
    row = first_wave_receipt()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        validate_phase2_first_wave_launch_receipt(row)


def test_first_wave_receipt_rejects_fanout_or_run_mapping_drift():
    row = first_wave_receipt()
    row["ready_after_first_wave"] = ["shared:v3_initialize"]
    with pytest.raises(ValueError, match="archive-fanout set drift"):
        validate_phase2_first_wave_launch_receipt(row)

    row = first_wave_receipt()
    row["target_run_ids"]["shared:quote_registry"] = 504
    with pytest.raises(ValueError, match="reuses a target run"):
        validate_phase2_first_wave_launch_receipt(row)
