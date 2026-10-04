import pytest

from hlp.data.phase2_eligibility_dispatch import LAUNCHPAD_SOURCES
from hlp.data.phase2_universe_freeze_dispatch import (
    PHASE2_UNIVERSE_FREEZE_DISPATCH_PLAN_VERSION,
    build_phase2_universe_freeze_dispatch_plan,
    validate_phase2_universe_freeze_dispatch_plan,
    validate_phase2_universe_freeze_launch_receipt,
)


def completion():
    return {
        "version": "phase2-eligibility-wave-completion-receipt-v1",
        "eligibility_completion_control_run_id": 6001,
        "eligibility_wave_launch_run_id": 6002,
        "eligibility_wave_launch_artifact_digest": "sha256:" + "aa" * 32,
        "plan_run_id": 6003,
        "plan_artifact_digest": "sha256:" + "bb" * 32,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "cc" * 20,
        "canonical_ledger_commit_sha": "cc" * 20,
        "launchpad_handoffs": {
            source: {
                "run_id": 6100 + index,
                "artifact_digest": "sha256:" + "11" * 32,
                "summary_sha256": "22" * 32,
            }
            for index, source in enumerate(LAUNCHPAD_SOURCES)
        },
        "direct_handoff": {
            "run_id": 6200,
            "artifact_digest": "sha256:" + "33" * 32,
            "handoff_sha256": "44" * 32,
        },
        "eligibility_runs_completed": 12,
        "all_eligibility_runs_successful": True,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_sources_ready": True,
        "phase2_universe_frozen": False,
        "canonical_coverage_ledger_mutated": False,
        "workflow_dispatch_performed": False,
    }


def exclusion():
    return {
        "run_id": 6300,
        "artifact_name": "phase2-exclusion-registry",
        "artifact_digest": "sha256:" + "55" * 32,
        "summary_sha256": "66" * 32,
        "registry_acceptance_ready": True,
        "phase2_universe_frozen": False,
    }


def test_freeze_dispatch_plan_binds_exact_universe_inputs():
    report = build_phase2_universe_freeze_dispatch_plan(
        completion(),
        exclusion(),
    )
    assert report["version"] == PHASE2_UNIVERSE_FREEZE_DISPATCH_PLAN_VERSION
    assert report["workflow"] == "phase2-universe-freeze.yml"
    assert report["inputs"]["direct_run_id"] == "6200"
    assert report["inputs"]["exclusion_run_id"] == "6300"
    assert report["phase2_universe_frozen"] is False

    validated = validate_phase2_universe_freeze_dispatch_plan(report)
    assert len(validated["launchpad_handoffs"]) == 11
    assert validated["inputs"] == report["inputs"]


def test_freeze_dispatch_plan_rejects_unready_exclusions():
    row = exclusion()
    row["registry_acceptance_ready"] = False
    with pytest.raises(ValueError, match="not acceptance-ready"):
        build_phase2_universe_freeze_dispatch_plan(completion(), row)


def test_freeze_dispatch_plan_rejects_input_drift():
    report = build_phase2_universe_freeze_dispatch_plan(
        completion(),
        exclusion(),
    )
    report["inputs"]["direct_run_id"] = "9999"
    with pytest.raises(ValueError, match="input binding drift"):
        validate_phase2_universe_freeze_dispatch_plan(report)


def launch_receipt():
    return {
        "version": "phase2-universe-freeze-launch-receipt-v1",
        "universe_freeze_control_run_id": 7001,
        "plan_run_id": 7002,
        "plan_artifact_digest": "sha256:" + "77" * 32,
        "universe_freeze_run_id": 7003,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "88" * 20,
        "canonical_ledger_commit_sha": "88" * 20,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_sources_ready": True,
        "phase2_universe_frozen": False,
        "target_runs_created": 1,
        "target_run_waited_for_completion": False,
        "canonical_coverage_ledger_mutated": False,
        "workflow_dispatch_performed": True,
    }


def test_freeze_launch_receipt_requires_one_target():
    report = validate_phase2_universe_freeze_launch_receipt(
        launch_receipt()
    )
    assert report["universe_freeze_run_id"] == 7003
    assert report["target_runs_created"] == 1

    row = launch_receipt()
    row["target_runs_created"] = 2
    with pytest.raises(ValueError, match="target-run count drift"):
        validate_phase2_universe_freeze_launch_receipt(row)
