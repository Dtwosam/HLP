from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

SOURCE_ELIGIBILITY_RUN_ID = 33_982_556_591

SOURCE_REQUIRED_ARTIFACTS = (
    "phase1-pons-v1-v3-full",
    "phase1-pons-v2-v4-full",
    "phase1-pons-v1-lifecycle-eligibility",
    "phase1-pons-v2-lifecycle-eligibility",
    "phase1-pons-v3-quote-fallback-full",
    "phase1-pons-v4-quote-fallback-full",
    "phase1-pons-quote-fallback-full",
)

EVIDENCE_REQUIRED_ARTIFACTS = (
    "phase1-pons-post-eligibility-evidence-ready",
    "phase1-pons-eligible-universe",
    "phase1-pons-representative-validation",
)

EVIDENCE_ALLOWED_WORKFLOW_PATHS = (
    ".github/workflows/phase1-pons-post-eligibility-evidence-one-shot.yml",
    ".github/workflows/phase1-pons-recovered-completion-one-shot.yml",
)

VIABILITY_ROUTE_WORKFLOW_PATHS = {
    "pons_registry": (
        ".github/workflows/phase1-pons-viability-pons-registry-one-shot.yml"
    ),
    "pons_v1_v3": (
        ".github/workflows/phase1-pons-viability-pons-v1-v3-one-shot.yml"
    ),
    "pons_v2_curve": (
        ".github/workflows/phase1-pons-viability-pons-v2-curve-one-shot.yml"
    ),
    "pons_v2_transition": (
        ".github/workflows/"
        "phase1-pons-viability-pons-v2-transition-one-shot.yml"
    ),
    "pons_v2_v4": (
        ".github/workflows/phase1-pons-viability-pons-v2-v4-one-shot.yml"
    ),
    "weth_usdg_anchor": (
        ".github/workflows/"
        "phase1-pons-viability-weth-usdg-anchor-one-shot.yml"
    ),
    "stock_oracle": (
        ".github/workflows/phase1-pons-viability-stock-oracle-one-shot.yml"
    ),
    "quote_v3_fallback": (
        ".github/workflows/"
        "phase1-pons-viability-quote-v3-fallback-one-shot.yml"
    ),
    "quote_v4_fallback": (
        ".github/workflows/"
        "phase1-pons-viability-quote-v4-fallback-one-shot.yml"
    ),
}

VIABILITY_ROUTE_REQUIRED_ARTIFACTS = {
    route: (
        f"phase1-pons-viability-measurement-{route}-primary",
    )
    for route in VIABILITY_ROUTE_WORKFLOW_PATHS
}
VIABILITY_ROUTE_REQUIRED_ARTIFACTS["pons_registry"] = (
    "phase1-pons-viability-measurement-pons_registry-primary",
    "phase1-pons-viability-measurement-pons_registry-secondary",
)

FINAL_ACCEPTANCE_ARTIFACT = "phase1-pons-acceptance-gate"
FINALIZER_WORKFLOW_PATH = (
    ".github/workflows/phase1-pons-viability-ledger-finalize-one-shot.yml"
)

RECOVERY_VENUE_ARTIFACTS = {
    "v1_v3": "phase1-pons-v1-v3-full",
    "v2_v4": "phase1-pons-v2-v4-full",
}
RECOVERY_VENUE_WORKFLOW_PATHS = {
    "v1_v3": (
        ".github/workflows/phase1-pons-live-venue-rescue-one-shot.yml",
        ".github/workflows/phase1-pons-v1-v3-recover-gaps.yml",
    ),
    "v2_v4": (
        ".github/workflows/phase1-pons-live-venue-rescue-one-shot.yml",
        ".github/workflows/phase1-pons-v2-v4-recover-gaps.yml",
    ),
}


def _artifact_names(run: Mapping[str, Any] | None) -> set[str]:
    if not run:
        return set()
    return {
        str(value)
        for value in run.get("artifacts", ())
        if str(value)
    }


def _successful(run: Mapping[str, Any] | None) -> bool:
    return bool(
        run
        and run.get("status") == "completed"
        and run.get("conclusion") == "success"
    )


def _run_id(run: Mapping[str, Any] | None) -> int:
    if not run:
        return 0
    try:
        return int(run.get("id", 0))
    except (TypeError, ValueError):
        return 0


def _recovered_venue_run_id(
    venue: str,
    run: Mapping[str, Any] | None,
) -> int:
    if venue not in RECOVERY_VENUE_ARTIFACTS:
        raise ValueError(f"unknown recovery venue: {venue}")
    if not _successful(run):
        return 0
    observed_path = str((run or {}).get("path") or "").split("@", 1)[0]
    if observed_path not in RECOVERY_VENUE_WORKFLOW_PATHS[venue]:
        return 0
    if (run or {}).get("head_branch") != "phase1/data-acquisition-spike":
        return 0
    if RECOVERY_VENUE_ARTIFACTS[venue] not in _artifact_names(run):
        return 0
    return _run_id(run)


def _source_recovery_plan(
    source_artifacts: set[str],
    recovery_runs: Mapping[str, Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    recovery_runs = recovery_runs or {}
    if set(recovery_runs) - set(RECOVERY_VENUE_ARTIFACTS):
        raise ValueError("readiness recovery venue set changed")

    has_v1_v3 = "phase1-pons-v1-v3-full" in source_artifacts
    has_v2_v4 = "phase1-pons-v2-v4-full" in source_artifacts
    recovered_v1_v3_id = _recovered_venue_run_id(
        "v1_v3",
        recovery_runs.get("v1_v3"),
    )
    recovered_v2_v4_id = _recovered_venue_run_id(
        "v2_v4",
        recovery_runs.get("v2_v4"),
    )
    recommended_v1_v3_id = (
        SOURCE_ELIGIBILITY_RUN_ID if has_v1_v3 else recovered_v1_v3_id
    )
    recommended_v2_v4_id = (
        SOURCE_ELIGIBILITY_RUN_ID if has_v2_v4 else recovered_v2_v4_id
    )
    pricing_artifacts = {
        "phase1-pons-v1-lifecycle-eligibility",
        "phase1-pons-v2-lifecycle-eligibility",
        "phase1-pons-v3-quote-fallback-full",
        "phase1-pons-v4-quote-fallback-full",
        "phase1-pons-quote-fallback-full",
    }
    has_pricing = pricing_artifacts <= source_artifacts
    reusable_pricing = bool(
        has_pricing
        and recommended_v1_v3_id == SOURCE_ELIGIBILITY_RUN_ID
        and recommended_v2_v4_id == SOURCE_ELIGIBILITY_RUN_ID
    )
    return {
        "source_has_v1_v3_full": has_v1_v3,
        "source_has_v2_v4_full": has_v2_v4,
        "source_has_complete_pricing": has_pricing,
        "recommended_v1_v3_run_id": recommended_v1_v3_id,
        "recommended_v2_v4_run_id": recommended_v2_v4_id,
        "recommended_pricing_run_id": (
            SOURCE_ELIGIBILITY_RUN_ID if reusable_pricing else 0
        ),
        "next_action": (
            "launch_v1_v3_rescue"
            if recommended_v1_v3_id <= 0
            else (
                "launch_v2_v4_rescue"
                if recommended_v2_v4_id <= 0
                else "launch_recovered_phase1_completion"
            )
        ),
    }


def _evidence_handoff_errors(
    handoff: Mapping[str, Any] | None,
    *,
    evidence_run_id: int,
    evidence_path: str,
) -> list[str]:
    if evidence_run_id <= 0:
        return []
    if not isinstance(handoff, Mapping):
        return ["evidence handoff payload is missing"]

    errors: list[str] = []
    if handoff.get("status") != "ready":
        errors.append("evidence handoff status is not ready")
    if int(handoff.get("evidence_run_id", 0)) != evidence_run_id:
        errors.append("evidence handoff run ID mismatch")
    if int(
        handoff.get("source_eligibility_run_id", 0)
    ) != SOURCE_ELIGIBILITY_RUN_ID:
        errors.append("evidence handoff source run mismatch")
    if int(handoff.get("snapshot_head_block", -1)) != 54_486_035:
        errors.append("evidence handoff snapshot head changed")
    if int(handoff.get("all_pons_launches", -1)) != 494_639:
        errors.append("evidence handoff Pons launch count changed")
    if int(handoff.get("eligible_tokens", 0)) <= 0:
        errors.append("evidence handoff eligible universe is empty")
    if int(handoff.get("representative_tokens", -1)) != 10:
        errors.append("evidence handoff representative token count changed")

    for field in (
        "eligible_universe_sha256",
        "representative_validation_sha256",
        "v1_eligibility_sha256",
        "v2_eligibility_sha256",
    ):
        value = str(handoff.get(field) or "").lower()
        if len(value) != 64:
            errors.append(f"evidence handoff hash is invalid: {field}")
            continue
        try:
            int(value, 16)
        except ValueError:
            errors.append(f"evidence handoff hash is invalid: {field}")

    lifecycle_run_id = int(handoff.get("lifecycle_run_id", 0))
    v1_v3_run_id = int(handoff.get("v1_v3_run_id", 0))
    v2_v4_run_id = int(handoff.get("v2_v4_run_id", 0))
    if min(lifecycle_run_id, v1_v3_run_id, v2_v4_run_id) <= 0:
        errors.append("evidence handoff routing run ID is invalid")

    recovery_mode = handoff.get("recovery_mode")
    if not isinstance(recovery_mode, bool):
        errors.append("evidence handoff recovery mode must be boolean")
    elif evidence_path == EVIDENCE_ALLOWED_WORKFLOW_PATHS[0]:
        if recovery_mode:
            errors.append("normal evidence handoff is marked recovered")
        if (
            lifecycle_run_id != SOURCE_ELIGIBILITY_RUN_ID
            or v1_v3_run_id != SOURCE_ELIGIBILITY_RUN_ID
            or v2_v4_run_id != SOURCE_ELIGIBILITY_RUN_ID
        ):
            errors.append("normal evidence handoff routing changed")
    elif evidence_path == EVIDENCE_ALLOWED_WORKFLOW_PATHS[1]:
        if not recovery_mode:
            errors.append("recovered evidence handoff is not marked recovered")

    return errors


def build_phase1_readiness_report(
    *,
    source_run: Mapping[str, Any],
    evidence_run: Mapping[str, Any] | None,
    viability_runs: Mapping[str, Mapping[str, Any] | None],
    finalizer_runs: Sequence[Mapping[str, Any]],
    configured_source_run_id: int,
    configured_evidence_run_id: int,
    ledger_generation: int,
    ledger_evidence_run_id: int,
    ledger_route_run_ids: Mapping[str, int],
    evidence_handoff: Mapping[str, Any] | None = None,
    recovery_runs: Mapping[str, Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    if int(configured_source_run_id) != SOURCE_ELIGIBILITY_RUN_ID:
        raise ValueError("readiness source eligibility run changed")
    if _run_id(source_run) != SOURCE_ELIGIBILITY_RUN_ID:
        raise ValueError("source run payload does not match frozen run ID")

    route_names = list(VIABILITY_ROUTE_WORKFLOW_PATHS)
    if set(viability_runs) != set(route_names):
        raise ValueError("readiness viability route set changed")
    if set(ledger_route_run_ids) != set(route_names):
        raise ValueError("readiness ledger route set changed")

    evidence_id = int(configured_evidence_run_id)
    if evidence_id > 0 and _run_id(evidence_run) != evidence_id:
        raise ValueError("evidence run payload does not match configured run ID")

    evidence_artifacts = _artifact_names(evidence_run)
    evidence_missing = sorted(
        set(EVIDENCE_REQUIRED_ARTIFACTS) - evidence_artifacts
    )
    evidence_path = (
        str((evidence_run or {}).get("path") or "").split("@", 1)[0]
    )
    evidence_path_allowed = evidence_path in EVIDENCE_ALLOWED_WORKFLOW_PATHS
    evidence_handoff_errors = _evidence_handoff_errors(
        evidence_handoff,
        evidence_run_id=evidence_id,
        evidence_path=evidence_path,
    )
    evidence_valid = bool(
        evidence_id > 0
        and _successful(evidence_run)
        and not evidence_missing
        and evidence_path_allowed
        and not evidence_handoff_errors
        and (evidence_run or {}).get("head_branch")
        == "phase1/data-acquisition-spike"
    )

    source_artifacts = _artifact_names(source_run)
    source_missing = sorted(
        set(SOURCE_REQUIRED_ARTIFACTS) - source_artifacts
    )
    source_job_counts = {
        str(key): int(value)
        for key, value in dict(
            source_run.get("job_counts") or {}
        ).items()
    }
    failed_job_states = {
        "failure",
        "cancelled",
        "timed_out",
        "startup_failure",
        "action_required",
        "stale",
    }
    source_failed_jobs = sum(
        count
        for state, count in source_job_counts.items()
        if state in failed_job_states
    )
    source_completed = source_run.get("status") == "completed"
    source_successful = _successful(source_run) and not source_missing
    source_requires_recovery = bool(
        source_completed and not source_successful
    )
    source_recovery_plan = (
        _source_recovery_plan(
            source_artifacts,
            recovery_runs=recovery_runs,
        )
        if source_requires_recovery
        else None
    )

    if not source_successful:
        if source_requires_recovery and evidence_valid:
            pass
        else:
            if not source_completed:
                next_action = "wait_for_full_eligibility_acquisition"
            elif evidence_id > 0:
                next_action = "recover_or_rerun_post_eligibility_evidence"
            else:
                next_action = str(source_recovery_plan["next_action"])
            return {
                "phase1_ready": False,
                "stage": (
                    "post_eligibility_evidence"
                    if source_completed and evidence_id > 0
                    else "eligibility_acquisition"
                ),
                "next_action": next_action,
                "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
                "source_status": source_run.get("status"),
                "source_conclusion": source_run.get("conclusion"),
                "source_job_counts": source_job_counts,
                "source_failed_jobs": source_failed_jobs,
                "source_missing_artifacts": source_missing,
                "source_recovery_plan": source_recovery_plan,
                "evidence_run_id": evidence_id,
                "evidence_status": (
                    evidence_run.get("status") if evidence_run else None
                ),
                "evidence_conclusion": (
                    evidence_run.get("conclusion") if evidence_run else None
                ),
                "evidence_missing_artifacts": evidence_missing,
                "evidence_workflow_path": evidence_path,
                "evidence_handoff_errors": evidence_handoff_errors,
                "completed_viability_routes": [],
                "pending_viability_routes": route_names,
                "final_acceptance_run_id": 0,
            }

    if evidence_id <= 0:
        return {
            "phase1_ready": False,
            "stage": "post_eligibility_evidence",
            "next_action": "launch_post_eligibility_evidence_handoff",
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "source_status": source_run.get("status"),
            "source_conclusion": source_run.get("conclusion"),
            "source_missing_artifacts": source_missing,
            "evidence_run_id": 0,
            "completed_viability_routes": [],
            "pending_viability_routes": route_names,
            "final_acceptance_run_id": 0,
        }

    if not evidence_valid:
        return {
            "phase1_ready": False,
            "stage": "post_eligibility_evidence",
            "next_action": "recover_or_rerun_post_eligibility_evidence",
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "source_status": source_run.get("status"),
            "source_conclusion": source_run.get("conclusion"),
            "source_missing_artifacts": source_missing,
            "evidence_run_id": evidence_id,
            "evidence_status": (
                evidence_run.get("status") if evidence_run else None
            ),
            "evidence_conclusion": (
                evidence_run.get("conclusion") if evidence_run else None
            ),
            "evidence_missing_artifacts": evidence_missing,
            "evidence_workflow_path": evidence_path,
            "evidence_handoff_errors": evidence_handoff_errors,
            "completed_viability_routes": [],
            "pending_viability_routes": route_names,
            "final_acceptance_run_id": 0,
        }

    if int(ledger_generation) <= 0:
        return {
            "phase1_ready": False,
            "stage": "viability_measurements",
            "next_action": "arm_viability_run_ledger",
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "evidence_run_id": evidence_id,
            "completed_viability_routes": [],
            "pending_viability_routes": route_names,
            "final_acceptance_run_id": 0,
        }

    if int(ledger_evidence_run_id) != evidence_id:
        raise ValueError("viability ledger evidence run does not match readiness")

    positive_ids = [
        int(ledger_route_run_ids[route])
        for route in route_names
        if int(ledger_route_run_ids[route]) > 0
    ]
    if len(positive_ids) != len(set(positive_ids)):
        raise ValueError("viability ledger reuses a route run ID")

    completed: list[str] = []
    invalid: list[dict[str, Any]] = []
    for route in route_names:
        ledger_run_id = int(ledger_route_run_ids[route])
        run = viability_runs[route]
        if ledger_run_id <= 0:
            continue
        if _run_id(run) != ledger_run_id:
            invalid.append(
                {
                    "route": route,
                    "reason": "run_id_mismatch",
                    "ledger_run_id": ledger_run_id,
                    "observed_run_id": _run_id(run),
                }
            )
            continue
        observed_path = str(run.get("path") or "").split("@", 1)[0]
        if observed_path != VIABILITY_ROUTE_WORKFLOW_PATHS[route]:
            invalid.append(
                {
                    "route": route,
                    "reason": "workflow_path_mismatch",
                    "expected": VIABILITY_ROUTE_WORKFLOW_PATHS[route],
                    "observed": observed_path,
                }
            )
            continue
        if not _successful(run):
            invalid.append(
                {
                    "route": route,
                    "reason": "run_not_successful",
                    "status": run.get("status"),
                    "conclusion": run.get("conclusion"),
                }
            )
            continue
        missing_artifacts = sorted(
            set(VIABILITY_ROUTE_REQUIRED_ARTIFACTS[route])
            - _artifact_names(run)
        )
        if missing_artifacts:
            invalid.append(
                {
                    "route": route,
                    "reason": "measurement_artifacts_missing",
                    "missing_artifacts": missing_artifacts,
                }
            )
            continue
        launch_routes = set(run.get("launch_ledger_routes") or [])
        if int(run.get("launch_readiness_generation", 0)) <= 0:
            invalid.append(
                {
                    "route": route,
                    "reason": "launch_readiness_unarmed",
                }
            )
            continue
        if int(
            run.get("launch_readiness_source_run_id", 0)
        ) != SOURCE_ELIGIBILITY_RUN_ID:
            invalid.append(
                {
                    "route": route,
                    "reason": "launch_source_run_mismatch",
                    "observed": int(
                        run.get("launch_readiness_source_run_id", 0)
                    ),
                }
            )
            continue
        if int(
            run.get("launch_readiness_evidence_run_id", 0)
        ) != evidence_id:
            invalid.append(
                {
                    "route": route,
                    "reason": "launch_readiness_evidence_mismatch",
                    "expected": evidence_id,
                    "observed": int(
                        run.get("launch_readiness_evidence_run_id", 0)
                    ),
                }
            )
            continue
        if int(run.get("launch_ledger_generation", 0)) <= 0:
            invalid.append(
                {
                    "route": route,
                    "reason": "launch_ledger_unarmed",
                }
            )
            continue
        if int(
            run.get("launch_ledger_evidence_run_id", 0)
        ) != evidence_id:
            invalid.append(
                {
                    "route": route,
                    "reason": "launch_ledger_evidence_mismatch",
                    "expected": evidence_id,
                    "observed": int(
                        run.get("launch_ledger_evidence_run_id", 0)
                    ),
                }
            )
            continue
        if launch_routes != set(route_names):
            invalid.append(
                {
                    "route": route,
                    "reason": "launch_ledger_route_set_mismatch",
                    "observed": sorted(launch_routes),
                }
            )
            continue
        if int(run.get("launch_route_slot", -1)) != 0:
            invalid.append(
                {
                    "route": route,
                    "reason": "launch_route_slot_not_empty",
                    "observed": int(run.get("launch_route_slot", -1)),
                }
            )
            continue
        completed.append(route)

    pending = [route for route in route_names if route not in completed]
    if invalid or pending:
        next_action = (
            "repair_invalid_viability_routes"
            if invalid
            else f"launch_viability_{pending[0]}"
        )
        return {
            "phase1_ready": False,
            "stage": "viability_measurements",
            "next_action": next_action,
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "evidence_run_id": evidence_id,
            "completed_viability_routes": completed,
            "pending_viability_routes": pending,
            "invalid_viability_routes": invalid,
            "final_acceptance_run_id": 0,
        }

    valid_finalizers: list[Mapping[str, Any]] = []
    invalid_finalizers: list[dict[str, Any]] = []
    expected_route_ids = {
        route: int(ledger_route_run_ids[route])
        for route in route_names
    }
    for run in finalizer_runs:
        if not _successful(run):
            continue
        if FINAL_ACCEPTANCE_ARTIFACT not in _artifact_names(run):
            continue

        reason = ""
        observed_path = str(run.get("path") or "").split("@", 1)[0]
        if observed_path != FINALIZER_WORKFLOW_PATH:
            reason = "workflow_path_mismatch"
        elif run.get("head_branch") != "phase1/data-acquisition-spike":
            reason = "branch_mismatch"
        elif int(run.get("launch_readiness_source_run_id", 0)) != (
            SOURCE_ELIGIBILITY_RUN_ID
        ):
            reason = "source_run_mismatch"
        elif int(run.get("launch_readiness_evidence_run_id", 0)) != evidence_id:
            reason = "readiness_evidence_mismatch"
        elif int(run.get("launch_ledger_generation", 0)) != int(
            ledger_generation
        ):
            reason = "ledger_generation_mismatch"
        elif int(run.get("launch_ledger_evidence_run_id", 0)) != evidence_id:
            reason = "ledger_evidence_mismatch"
        else:
            launch_routes = {
                str(route): int(run_id)
                for route, run_id in dict(
                    run.get("launch_ledger_routes") or {}
                ).items()
            }
            if launch_routes != expected_route_ids:
                reason = "ledger_routes_mismatch"

        if reason:
            invalid_finalizers.append(
                {
                    "run_id": _run_id(run),
                    "reason": reason,
                }
            )
            continue
        valid_finalizers.append(run)

    if not valid_finalizers:
        return {
            "phase1_ready": False,
            "stage": "final_acceptance",
            "next_action": "launch_phase1_final_acceptance",
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "evidence_run_id": evidence_id,
            "completed_viability_routes": completed,
            "pending_viability_routes": [],
            "invalid_viability_routes": [],
            "invalid_finalizers": invalid_finalizers,
            "final_acceptance_run_id": 0,
        }

    finalizer = max(
        valid_finalizers,
        key=lambda run: _run_id(run),
    )
    return {
        "phase1_ready": True,
        "stage": "complete",
        "next_action": "record_phase1_pass_and_merge_pr_3",
        "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
        "evidence_run_id": evidence_id,
        "completed_viability_routes": completed,
        "pending_viability_routes": [],
        "invalid_viability_routes": [],
        "invalid_finalizers": invalid_finalizers,
        "final_acceptance_run_id": _run_id(finalizer),
    }
