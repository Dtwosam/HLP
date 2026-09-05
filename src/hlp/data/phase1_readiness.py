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
    evidence_valid = bool(
        evidence_id > 0
        and _successful(evidence_run)
        and not evidence_missing
        and evidence_path_allowed
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
    source_terminal_failure = bool(
        source_completed and source_run.get("conclusion") != "success"
    )

    if not source_successful:
        if source_terminal_failure and evidence_valid:
            pass
        else:
            if not source_completed:
                next_action = "wait_for_full_eligibility_acquisition"
            else:
                next_action = "recover_full_eligibility_acquisition"
                if evidence_id > 0:
                    next_action = "recover_or_rerun_post_eligibility_evidence"
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
                "evidence_run_id": evidence_id,
                "evidence_status": (
                    evidence_run.get("status") if evidence_run else None
                ),
                "evidence_conclusion": (
                    evidence_run.get("conclusion") if evidence_run else None
                ),
                "evidence_missing_artifacts": evidence_missing,
                "evidence_workflow_path": evidence_path,
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

    successful_finalizers = [
        run
        for run in finalizer_runs
        if _successful(run)
        and FINAL_ACCEPTANCE_ARTIFACT in _artifact_names(run)
    ]
    if not successful_finalizers:
        return {
            "phase1_ready": False,
            "stage": "final_acceptance",
            "next_action": "launch_phase1_final_acceptance",
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "evidence_run_id": evidence_id,
            "completed_viability_routes": completed,
            "pending_viability_routes": [],
            "invalid_viability_routes": [],
            "final_acceptance_run_id": 0,
        }

    finalizer = max(
        successful_finalizers,
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
        "final_acceptance_run_id": _run_id(finalizer),
    }
