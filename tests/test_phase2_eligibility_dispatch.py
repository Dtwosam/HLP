import copy

import pytest

from hlp.data.phase2_eligibility_dispatch import (
    DIRECT_COVERAGE_ARTIFACTS,
    DIRECT_COVERAGE_REPORT_PATH,
    DIRECT_SOURCES,
    LAUNCHPAD_COVERAGE_ARTIFACTS,
    LAUNCHPAD_COVERAGE_REPORT_PATHS,
    LAUNCHPAD_SOURCES,
    LAUNCHPAD_SUMMARY_PATHS,
    PHASE2_ELIGIBILITY_DISPATCH_PLAN_VERSION,
    build_phase2_eligibility_dispatch_plan,
    validate_phase2_eligibility_dispatch_plan,
    validate_phase2_eligibility_wave_launch_receipt,
)


def bindings():
    rows = {}
    for index, source in enumerate(LAUNCHPAD_SOURCES, start=1):
        rows[source] = {
            "run_id": 1000 + index,
            "artifact_name": LAUNCHPAD_COVERAGE_ARTIFACTS[source],
            "artifact_digest": "sha256:" + "11" * 32,
            "report_path": LAUNCHPAD_COVERAGE_REPORT_PATHS[source],
            "report_sha256": "22" * 32,
            "summary_path": LAUNCHPAD_SUMMARY_PATHS[source],
            "summary_sha256": "33" * 32,
        }
    for index, source in enumerate(DIRECT_SOURCES, start=1):
        rows[source] = {
            "run_id": 2000 + index,
            "artifact_name": DIRECT_COVERAGE_ARTIFACTS[source],
            "artifact_digest": "sha256:" + "44" * 32,
            "report_path": DIRECT_COVERAGE_REPORT_PATH,
            "report_sha256": "55" * 32,
        }
    return rows


def selector():
    return {
        "run_id": 3001,
        "artifact_name": "phase2-direct-market-selector-freeze",
        "artifact_digest": "sha256:" + "66" * 32,
        "descriptor_sha256": "77" * 32,
    }


def test_eligibility_dispatch_plan_covers_all_sources():
    report = build_phase2_eligibility_dispatch_plan(
        bindings(),
        selector(),
    )
    assert report["version"] == PHASE2_ELIGIBILITY_DISPATCH_PLAN_VERSION
    assert report["coverage_sources"] == 14
    assert report["dispatch_count"] == 12
    assert len(report["launchpad_dispatches"]) == 11
    assert report["workflow_dispatch_performed"] is False

    pons = report["launchpad_dispatches"][0]
    assert pons["source_id"] == "pons_v1"
    assert pons["inputs"]["coverage_run_id"] == "1001"
    assert pons["inputs"]["eligibility_run_id"] == "1001"
    assert pons["inputs"]["eligibility_summary_path"] == (
        "pons-v1-lifecycle-eligibility.jsonl"
    )

    direct = report["direct_dispatch"]["inputs"]
    assert direct["selector_run_id"] == "3001"
    assert direct["uniswap_v3_coverage_run_id"] == "2001"
    assert direct["sushiswap_v3_coverage_run_id"] == "2002"
    assert direct["uniswap_v4_coverage_run_id"] == "2003"


def test_eligibility_dispatch_plan_rejects_missing_source():
    rows = bindings()
    rows.pop("noxa")
    with pytest.raises(ValueError, match="binding set drift"):
        build_phase2_eligibility_dispatch_plan(rows, selector())


def test_eligibility_dispatch_plan_rejects_summary_path_drift():
    rows = bindings()
    rows["flap"]["summary_path"] = "flap-v3-summary.jsonl"
    with pytest.raises(ValueError, match="summary path drift"):
        build_phase2_eligibility_dispatch_plan(rows, selector())


def test_eligibility_dispatch_plan_rejects_direct_artifact_drift():
    rows = bindings()
    rows["direct_uniswap_v4"]["artifact_name"] = "wrong"
    with pytest.raises(ValueError, match="artifact name drift"):
        build_phase2_eligibility_dispatch_plan(rows, selector())


def test_eligibility_dispatch_plan_rejects_selector_drift():
    row = copy.deepcopy(selector())
    row["artifact_name"] = "wrong"
    with pytest.raises(ValueError, match="selector artifact name drift"):
        build_phase2_eligibility_dispatch_plan(bindings(), row)

def test_dispatch_plan_validator_accepts_execution_metadata():
    report = build_phase2_eligibility_dispatch_plan(bindings(), selector())
    report.update({
        "final_ledger_approval_run_id": 4001,
        "final_ledger_approval_artifact_digest": "sha256:" + "88" * 32,
        "canonical_ledger_commit_sha": "99" * 20,
        "pons_coverage_run_id": 4002,
    })
    validated = validate_phase2_eligibility_dispatch_plan(
        report,
        require_execution_metadata=True,
    )
    assert validated["dispatch_count"] == 12
    assert validated["canonical_ledger_commit_sha"] == "99" * 20


def test_dispatch_plan_validator_rejects_mutating_plan():
    report = build_phase2_eligibility_dispatch_plan(bindings(), selector())
    report["workflow_dispatch_performed"] = True
    with pytest.raises(ValueError, match="not read-only"):
        validate_phase2_eligibility_dispatch_plan(report)


def launch_receipt():
    return {
        "version": "phase2-eligibility-wave-launch-receipt-v1",
        "eligibility_wave_control_run_id": 5001,
        "execution_branch": "phase1/data-acquisition-spike",
        "execution_head_sha": "aa" * 20,
        "plan_run_id": 5002,
        "plan_artifact_digest": "sha256:" + "bb" * 32,
        "canonical_ledger_commit_sha": "aa" * 20,
        "pons_coverage_run_id": 5003,
        "launchpad_run_ids": {
            source: 5100 + index
            for index, source in enumerate(LAUNCHPAD_SOURCES)
        },
        "direct_run_id": 5200,
        "target_runs_created": 12,
        "target_runs_waited_for_completion": False,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_frozen": False,
        "canonical_coverage_ledger_mutated": False,
        "workflow_dispatch_performed": True,
    }


def test_eligibility_wave_launch_receipt_requires_12_unique_runs():
    report = validate_phase2_eligibility_wave_launch_receipt(
        launch_receipt()
    )
    assert report["target_runs_created"] == 12
    assert len(report["launchpad_run_ids"]) == 11

    duplicate = launch_receipt()
    duplicate["direct_run_id"] = next(
        iter(duplicate["launchpad_run_ids"].values())
    )
    with pytest.raises(ValueError, match="not unique"):
        validate_phase2_eligibility_wave_launch_receipt(duplicate)

