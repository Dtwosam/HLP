import copy

import pytest

from hlp.data.phase2_first_wave import (
    PHASE2_FIRST_WAVE_LAUNCH_VERSION,
    PHASE2_EXPECTED_ARCHIVE_FANOUT_NODE_IDS,
    PHASE2_FIRST_WAVE_NODE_IDS,
    validate_phase2_first_wave_completion,
    validate_phase2_first_wave_launch,
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
