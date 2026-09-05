import pytest

from hlp.data.phase1_readiness import (
    EVIDENCE_REQUIRED_ARTIFACTS,
    FINAL_ACCEPTANCE_ARTIFACT,
    SOURCE_ELIGIBILITY_RUN_ID,
    SOURCE_REQUIRED_ARTIFACTS,
    VIABILITY_ROUTE_WORKFLOWS,
    build_phase1_readiness_report,
)


def _run(
    run_id,
    *,
    name="workflow",
    status="completed",
    conclusion="success",
    artifacts=(),
):
    return {
        "id": run_id,
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "artifacts": list(artifacts),
    }


def _source(**overrides):
    values = {
        "run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "artifacts": SOURCE_REQUIRED_ARTIFACTS,
    }
    values.update(overrides)
    return _run(**values)


def _evidence(run_id=400):
    return _run(
        run_id,
        name="phase1-pons-post-eligibility-evidence-one-shot",
        artifacts=EVIDENCE_REQUIRED_ARTIFACTS,
    )


def _route_runs(start=1000):
    return {
        route: _run(start + index, name=workflow)
        for index, (route, workflow) in enumerate(
            VIABILITY_ROUTE_WORKFLOWS.items()
        )
    }


def _ledger_ids(start=1000):
    return {
        route: start + index
        for index, route in enumerate(VIABILITY_ROUTE_WORKFLOWS)
    }


def _report(
    *,
    source_run=None,
    evidence_run=None,
    evidence_run_id=0,
    ledger_generation=0,
    ledger_evidence_run_id=0,
    ledger_route_run_ids=None,
    viability_runs=None,
    finalizer_runs=(),
):
    return build_phase1_readiness_report(
        source_run=source_run or _source(),
        evidence_run=evidence_run,
        viability_runs=viability_runs
        or {route: None for route in VIABILITY_ROUTE_WORKFLOWS},
        finalizer_runs=finalizer_runs,
        configured_source_run_id=SOURCE_ELIGIBILITY_RUN_ID,
        configured_evidence_run_id=evidence_run_id,
        ledger_generation=ledger_generation,
        ledger_evidence_run_id=ledger_evidence_run_id,
        ledger_route_run_ids=ledger_route_run_ids
        or {route: 0 for route in VIABILITY_ROUTE_WORKFLOWS},
    )


def test_readiness_waits_for_full_eligibility_source():
    report = _report(
        source_run=_source(
            status="in_progress",
            conclusion=None,
            artifacts=(),
        )
    )

    assert report["stage"] == "eligibility_acquisition"
    assert (
        report["next_action"]
        == "wait_for_or_recover_full_eligibility_acquisition"
    )
    assert report["phase1_ready"] is False
    assert sorted(report["source_missing_artifacts"]) == sorted(
        SOURCE_REQUIRED_ARTIFACTS
    )


def test_readiness_requires_post_eligibility_evidence_after_source():
    report = _report()

    assert report["stage"] == "post_eligibility_evidence"
    assert report["next_action"] == "launch_post_eligibility_evidence_handoff"
    assert report["evidence_run_id"] == 0


def test_readiness_rejects_incomplete_evidence_bundle():
    evidence = _run(
        400,
        artifacts=EVIDENCE_REQUIRED_ARTIFACTS[:-1],
    )
    report = _report(
        evidence_run=evidence,
        evidence_run_id=400,
    )

    assert report["stage"] == "post_eligibility_evidence"
    assert report["next_action"] == "recover_or_rerun_post_eligibility_evidence"
    assert report["evidence_missing_artifacts"] == [
        "phase1-pons-representative-validation"
    ]


def test_readiness_requires_viability_ledger_to_be_armed():
    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
    )

    assert report["stage"] == "viability_measurements"
    assert report["next_action"] == "arm_viability_run_ledger"
    assert report["pending_viability_routes"] == list(
        VIABILITY_ROUTE_WORKFLOWS
    )


def test_readiness_names_next_missing_viability_route():
    runs = _route_runs()
    ledger = _ledger_ids()
    ledger["pons_v2_curve"] = 0
    runs["pons_v2_curve"] = None

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=ledger,
        viability_runs=runs,
    )

    assert report["stage"] == "viability_measurements"
    assert report["next_action"] == "launch_viability_pons_v2_curve"
    assert report["pending_viability_routes"] == ["pons_v2_curve"]
    assert len(report["completed_viability_routes"]) == 8


def test_readiness_flags_invalid_viability_run_identity():
    runs = _route_runs()
    runs["stock_oracle"]["name"] = "wrong-workflow"

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=runs,
    )

    assert report["stage"] == "viability_measurements"
    assert report["next_action"] == "repair_invalid_viability_routes"
    assert report["invalid_viability_routes"] == [
        {
            "route": "stock_oracle",
            "reason": "workflow_mismatch",
            "expected": VIABILITY_ROUTE_WORKFLOWS["stock_oracle"],
            "observed": "wrong-workflow",
        }
    ]


def test_readiness_advances_to_final_acceptance_after_nine_routes():
    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=_route_runs(),
    )

    assert report["stage"] == "final_acceptance"
    assert report["next_action"] == "launch_phase1_final_acceptance"
    assert report["phase1_ready"] is False


def test_readiness_reports_phase1_complete_only_with_acceptance_artifact():
    finalizer = _run(
        5000,
        name="phase1-pons-viability-ledger-finalize-one-shot",
        artifacts=[FINAL_ACCEPTANCE_ARTIFACT],
    )
    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=_route_runs(),
        finalizer_runs=[finalizer],
    )

    assert report["phase1_ready"] is True
    assert report["stage"] == "complete"
    assert report["next_action"] == "record_phase1_pass_and_merge_pr_3"
    assert report["final_acceptance_run_id"] == 5000


def test_readiness_rejects_reused_viability_run_id():
    ledger = _ledger_ids()
    ledger["pons_v1_v3"] = ledger["pons_registry"]

    with pytest.raises(ValueError, match="reuses a route run ID"):
        _report(
            evidence_run=_evidence(),
            evidence_run_id=400,
            ledger_generation=1,
            ledger_evidence_run_id=400,
            ledger_route_run_ids=ledger,
            viability_runs=_route_runs(),
        )


def test_readiness_rejects_evidence_ledger_drift():
    with pytest.raises(
        ValueError,
        match="ledger evidence run does not match",
    ):
        _report(
            evidence_run=_evidence(),
            evidence_run_id=400,
            ledger_generation=1,
            ledger_evidence_run_id=401,
            ledger_route_run_ids=_ledger_ids(),
            viability_runs=_route_runs(),
        )


def test_readiness_does_not_treat_successful_finalizer_without_pass_artifact_as_complete():
    finalizer = _run(
        5000,
        name="phase1-pons-viability-ledger-finalize-one-shot",
        artifacts=[],
    )
    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=_route_runs(),
        finalizer_runs=[finalizer],
    )

    assert report["phase1_ready"] is False
    assert report["stage"] == "final_acceptance"
    assert report["next_action"] == "launch_phase1_final_acceptance"
    assert report["final_acceptance_run_id"] == 0
