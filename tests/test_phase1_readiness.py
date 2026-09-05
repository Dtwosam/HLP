import pytest

from hlp.data.phase1_readiness import (
    EVIDENCE_REQUIRED_ARTIFACTS,
    FINAL_ACCEPTANCE_ARTIFACT,
    FINALIZER_WORKFLOW_PATH,
    SOURCE_ELIGIBILITY_RUN_ID,
    SOURCE_REQUIRED_ARTIFACTS,
    VIABILITY_ROUTE_REQUIRED_ARTIFACTS,
    VIABILITY_ROUTE_WORKFLOW_PATHS,
    build_phase1_readiness_report,
)


def _run(
    run_id,
    *,
    name="workflow",
    status="completed",
    conclusion="success",
    artifacts=(),
    job_counts=None,
    path=None,
    head_branch="phase1/data-acquisition-spike",
):
    return {
        "id": run_id,
        "name": name,
        "path": path,
        "head_branch": head_branch,
        "status": status,
        "conclusion": conclusion,
        "artifacts": list(artifacts),
        "job_counts": dict(job_counts or {}),
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
        path=(
            ".github/workflows/"
            "phase1-pons-post-eligibility-evidence-one-shot.yml"
        ),
        artifacts=EVIDENCE_REQUIRED_ARTIFACTS,
    )


def _route_runs(start=1000, evidence_run_id=400):
    routes = list(VIABILITY_ROUTE_WORKFLOW_PATHS)
    return {
        route: {
            **_run(
                start + index,
                name=f"phase1 viability {route} custom-run-name",
                path=workflow_path,
                artifacts=VIABILITY_ROUTE_REQUIRED_ARTIFACTS[route],
            ),
            "launch_readiness_generation": 1,
            "launch_readiness_source_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "launch_readiness_evidence_run_id": evidence_run_id,
            "launch_ledger_generation": 1,
            "launch_ledger_evidence_run_id": evidence_run_id,
            "launch_route_slot": 0,
            "launch_ledger_routes": routes,
        }
        for index, (route, workflow_path) in enumerate(
            VIABILITY_ROUTE_WORKFLOW_PATHS.items()
        )
    }


def _ledger_ids(start=1000):
    return {
        route: start + index
        for index, route in enumerate(VIABILITY_ROUTE_WORKFLOW_PATHS)
    }


def _finalizer(run_id=5000, *, evidence_run_id=400, route_ids=None):
    return {
        **_run(
            run_id,
            name="phase1-pons-viability-ledger-finalize-one-shot",
            path=FINALIZER_WORKFLOW_PATH,
            artifacts=[FINAL_ACCEPTANCE_ARTIFACT],
        ),
        "launch_readiness_source_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "launch_readiness_evidence_run_id": evidence_run_id,
        "launch_ledger_generation": 1,
        "launch_ledger_evidence_run_id": evidence_run_id,
        "launch_ledger_routes": dict(route_ids or _ledger_ids()),
    }


_AUTO_HANDOFF = object()


def _handoff(run_id, *, recovered=False):
    routing_run_id = run_id if recovered else SOURCE_ELIGIBILITY_RUN_ID
    return {
        "status": "ready",
        "recovery_mode": recovered,
        "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "lifecycle_run_id": routing_run_id,
        "v1_v3_run_id": routing_run_id,
        "v2_v4_run_id": routing_run_id,
        "evidence_run_id": run_id,
        "snapshot_head_block": 54_486_035,
        "all_pons_launches": 494_639,
        "eligible_tokens": 1,
        "representative_tokens": 10,
        "eligible_universe_sha256": "a" * 64,
        "representative_validation_sha256": "b" * 64,
        "v1_eligibility_sha256": "c" * 64,
        "v2_eligibility_sha256": "d" * 64,
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
    evidence_handoff=_AUTO_HANDOFF,
):
    if evidence_handoff is _AUTO_HANDOFF:
        recovered = bool(
            evidence_run
            and str(evidence_run.get("path") or "").endswith(
                "phase1-pons-recovered-completion-one-shot.yml"
            )
        )
        evidence_handoff = (
            _handoff(evidence_run_id, recovered=recovered)
            if evidence_run_id > 0
            else None
        )
    return build_phase1_readiness_report(
        source_run=source_run or _source(),
        evidence_run=evidence_run,
        viability_runs=viability_runs
        or {route: None for route in VIABILITY_ROUTE_WORKFLOW_PATHS},
        finalizer_runs=finalizer_runs,
        configured_source_run_id=SOURCE_ELIGIBILITY_RUN_ID,
        configured_evidence_run_id=evidence_run_id,
        ledger_generation=ledger_generation,
        ledger_evidence_run_id=ledger_evidence_run_id,
        ledger_route_run_ids=ledger_route_run_ids
        or {route: 0 for route in VIABILITY_ROUTE_WORKFLOW_PATHS},
        evidence_handoff=evidence_handoff,
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
        == "wait_for_full_eligibility_acquisition"
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
        VIABILITY_ROUTE_WORKFLOW_PATHS
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
    runs["stock_oracle"]["path"] = ".github/workflows/wrong-workflow.yml"

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
            "reason": "workflow_path_mismatch",
            "expected": VIABILITY_ROUTE_WORKFLOW_PATHS["stock_oracle"],
            "observed": ".github/workflows/wrong-workflow.yml",
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
    finalizer = _finalizer()
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
    finalizer = _finalizer()
    finalizer["artifacts"] = []
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


def test_readiness_waits_for_parent_recovery_while_source_is_active():
    report = _report(
        source_run=_source(
            status="queued",
            conclusion=None,
            artifacts=(),
            job_counts={
                "success": 10,
                "in_progress": 2,
                "queued": 228,
                "failure": 1,
            },
        )
    )

    assert report["stage"] == "eligibility_acquisition"
    assert report["next_action"] == "wait_for_full_eligibility_acquisition"
    assert report["source_failed_jobs"] == 1
    assert report["source_job_counts"]["in_progress"] == 2


def test_readiness_rejects_missing_viability_measurement_artifact():
    runs = _route_runs()
    runs["pons_v2_v4"]["artifacts"] = []

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=runs,
    )

    assert report["next_action"] == "repair_invalid_viability_routes"
    assert report["invalid_viability_routes"] == [
        {
            "route": "pons_v2_v4",
            "reason": "measurement_artifacts_missing",
            "missing_artifacts": [
                "phase1-pons-viability-measurement-pons_v2_v4-primary"
            ],
        }
    ]


def test_readiness_requires_registry_primary_and_secondary_artifacts():
    runs = _route_runs()
    runs["pons_registry"]["artifacts"] = [
        "phase1-pons-viability-measurement-pons_registry-primary"
    ]

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=runs,
    )

    assert report["next_action"] == "repair_invalid_viability_routes"
    assert report["invalid_viability_routes"] == [
        {
            "route": "pons_registry",
            "reason": "measurement_artifacts_missing",
            "missing_artifacts": [
                "phase1-pons-viability-measurement-pons_registry-secondary"
            ],
        }
    ]


def test_readiness_advances_from_terminal_source_failure_with_recovered_evidence():
    source = _source(
        status="completed",
        conclusion="failure",
        artifacts=(),
        job_counts={"success": 16, "cancelled": 1},
    )
    evidence = _run(
        500,
        name="phase1-pons-recovered-completion-one-shot",
        path=(
            ".github/workflows/"
            "phase1-pons-recovered-completion-one-shot.yml"
        ),
        artifacts=EVIDENCE_REQUIRED_ARTIFACTS,
    )

    report = _report(
        source_run=source,
        evidence_run=evidence,
        evidence_run_id=500,
    )

    assert report["stage"] == "viability_measurements"
    assert report["next_action"] == "arm_viability_run_ledger"
    assert report["evidence_run_id"] == 500


def test_readiness_rejects_unapproved_recovery_evidence_workflow():
    source = _source(
        status="completed",
        conclusion="failure",
        artifacts=(),
    )
    evidence = _run(
        500,
        path=".github/workflows/unapproved.yml",
        artifacts=EVIDENCE_REQUIRED_ARTIFACTS,
    )

    report = _report(
        source_run=source,
        evidence_run=evidence,
        evidence_run_id=500,
    )

    assert report["stage"] == "post_eligibility_evidence"
    assert (
        report["next_action"]
        == "recover_or_rerun_post_eligibility_evidence"
    )
    assert report["evidence_workflow_path"] == (
        ".github/workflows/unapproved.yml"
    )


def test_readiness_rejects_route_launched_for_stale_evidence():
    runs = _route_runs()
    runs["pons_v1_v3"]["launch_readiness_evidence_run_id"] = 399

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=runs,
    )

    assert report["next_action"] == "repair_invalid_viability_routes"
    assert report["invalid_viability_routes"] == [
        {
            "route": "pons_v1_v3",
            "reason": "launch_readiness_evidence_mismatch",
            "expected": 400,
            "observed": 399,
        }
    ]


def test_readiness_rejects_route_launched_with_nonempty_ledger_slot():
    runs = _route_runs()
    runs["quote_v4_fallback"]["launch_route_slot"] = 1234

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        ledger_generation=1,
        ledger_evidence_run_id=400,
        ledger_route_run_ids=_ledger_ids(),
        viability_runs=runs,
    )

    assert report["next_action"] == "repair_invalid_viability_routes"
    assert report["invalid_viability_routes"] == [
        {
            "route": "quote_v4_fallback",
            "reason": "launch_route_slot_not_empty",
            "observed": 1234,
        }
    ]


def test_readiness_rejects_malformed_evidence_handoff_fingerprint():
    handoff = _handoff(400)
    handoff["representative_validation_sha256"] = "bad"

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        evidence_handoff=handoff,
    )

    assert report["stage"] == "post_eligibility_evidence"
    assert report["next_action"] == "recover_or_rerun_post_eligibility_evidence"
    assert report["evidence_handoff_errors"] == [
        "evidence handoff hash is invalid: "
        "representative_validation_sha256"
    ]


def test_readiness_rejects_normal_handoff_marked_recovered():
    handoff = _handoff(400)
    handoff["recovery_mode"] = True

    report = _report(
        evidence_run=_evidence(),
        evidence_run_id=400,
        evidence_handoff=handoff,
    )

    assert report["stage"] == "post_eligibility_evidence"
    assert "normal evidence handoff is marked recovered" in (
        report["evidence_handoff_errors"]
    )


def test_readiness_terminal_failure_requires_v1_rescue_when_tape_missing():
    artifacts = [
        name
        for name in SOURCE_REQUIRED_ARTIFACTS
        if name != "phase1-pons-v1-v3-full"
    ]
    report = _report(
        source_run=_source(
            status="completed",
            conclusion="failure",
            artifacts=artifacts,
        )
    )

    assert report["stage"] == "eligibility_acquisition"
    assert report["next_action"] == "launch_v1_v3_rescue"
    assert report["source_recovery_plan"] == {
        "source_has_v1_v3_full": False,
        "source_has_v2_v4_full": True,
        "source_has_complete_pricing": True,
        "recommended_v1_v3_run_id": 0,
        "recommended_v2_v4_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "recommended_pricing_run_id": 0,
        "next_action": "launch_v1_v3_rescue",
    }


def test_readiness_terminal_failure_reuses_complete_source_pricing():
    report = _report(
        source_run=_source(
            status="completed",
            conclusion="failure",
            artifacts=SOURCE_REQUIRED_ARTIFACTS,
        )
    )

    assert report["stage"] == "eligibility_acquisition"
    assert report["next_action"] == "launch_recovered_phase1_completion"
    assert report["source_recovery_plan"] == {
        "source_has_v1_v3_full": True,
        "source_has_v2_v4_full": True,
        "source_has_complete_pricing": True,
        "recommended_v1_v3_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "recommended_v2_v4_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "recommended_pricing_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "next_action": "launch_recovered_phase1_completion",
    }

def test_readiness_successful_source_missing_artifact_requires_recovery():
    artifacts = [
        name
        for name in SOURCE_REQUIRED_ARTIFACTS
        if name != "phase1-pons-v1-lifecycle-eligibility"
    ]
    report = _report(
        source_run=_source(
            status="completed",
            conclusion="success",
            artifacts=artifacts,
        )
    )

    assert report["stage"] == "eligibility_acquisition"
    assert report["next_action"] == "launch_recovered_phase1_completion"
    assert report["source_recovery_plan"] == {
        "source_has_v1_v3_full": True,
        "source_has_v2_v4_full": True,
        "source_has_complete_pricing": False,
        "recommended_v1_v3_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "recommended_v2_v4_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "recommended_pricing_run_id": 0,
        "next_action": "launch_recovered_phase1_completion",
    }

def test_readiness_rejects_finalizer_from_stale_route_ledger():
    stale_routes = _ledger_ids()
    stale_routes["pons_v1_v3"] = 9999
    finalizer = _finalizer(route_ids=stale_routes)

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
    assert report["invalid_finalizers"] == [
        {"run_id": 5000, "reason": "ledger_routes_mismatch"}
    ]

