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

VIABILITY_ROUTE_WORKFLOWS = {
    "pons_registry": "phase1-pons-viability-pons-registry-one-shot",
    "pons_v1_v3": "phase1-pons-viability-pons-v1-v3-one-shot",
    "pons_v2_curve": "phase1-pons-viability-pons-v2-curve-one-shot",
    "pons_v2_transition": (
        "phase1-pons-viability-pons-v2-transition-one-shot"
    ),
    "pons_v2_v4": "phase1-pons-viability-pons-v2-v4-one-shot",
    "weth_usdg_anchor": (
        "phase1-pons-viability-weth-usdg-anchor-one-shot"
    ),
    "stock_oracle": "phase1-pons-viability-stock-oracle-one-shot",
    "quote_v3_fallback": (
        "phase1-pons-viability-quote-v3-fallback-one-shot"
    ),
    "quote_v4_fallback": (
        "phase1-pons-viability-quote-v4-fallback-one-shot"
    ),
}

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

    route_names = list(VIABILITY_ROUTE_WORKFLOWS)
    if set(viability_runs) != set(route_names):
        raise ValueError("readiness viability route set changed")
    if set(ledger_route_run_ids) != set(route_names):
        raise ValueError("readiness ledger route set changed")

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
    if not _successful(source_run) or source_missing:
        source_terminal_failure = bool(
            source_run.get("status") == "completed"
            and source_run.get("conclusion") != "success"
        )
        next_action = (
            "recover_full_eligibility_acquisition"
            if source_failed_jobs > 0 or source_terminal_failure
            else "wait_for_full_eligibility_acquisition"
        )
        return {
            "phase1_ready": False,
            "stage": "eligibility_acquisition",
            "next_action": next_action,
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "source_status": source_run.get("status"),
            "source_conclusion": source_run.get("conclusion"),
            "source_job_counts": source_job_counts,
            "source_failed_jobs": source_failed_jobs,
            "source_missing_artifacts": source_missing,
            "evidence_run_id": 0,
            "completed_viability_routes": [],
            "pending_viability_routes": route_names,
            "final_acceptance_run_id": 0,
        }

    evidence_id = int(configured_evidence_run_id)
    if evidence_id <= 0:
        return {
            "phase1_ready": False,
            "stage": "post_eligibility_evidence",
            "next_action": "launch_post_eligibility_evidence_handoff",
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "source_status": source_run.get("status"),
            "source_conclusion": source_run.get("conclusion"),
            "source_missing_artifacts": [],
            "evidence_run_id": 0,
            "completed_viability_routes": [],
            "pending_viability_routes": route_names,
            "final_acceptance_run_id": 0,
        }

    if _run_id(evidence_run) != evidence_id:
        raise ValueError("evidence run payload does not match configured run ID")
    evidence_artifacts = _artifact_names(evidence_run)
    evidence_missing = sorted(
        set(EVIDENCE_REQUIRED_ARTIFACTS) - evidence_artifacts
    )
    if not _successful(evidence_run) or evidence_missing:
        return {
            "phase1_ready": False,
            "stage": "post_eligibility_evidence",
            "next_action": "recover_or_rerun_post_eligibility_evidence",
            "source_eligibility_run_id": SOURCE_ELIGIBILITY_RUN_ID,
            "source_status": source_run.get("status"),
            "source_conclusion": source_run.get("conclusion"),
            "source_missing_artifacts": [],
            "evidence_run_id": evidence_id,
            "evidence_status": (
                evidence_run.get("status") if evidence_run else None
            ),
            "evidence_conclusion": (
                evidence_run.get("conclusion") if evidence_run else None
            ),
            "evidence_missing_artifacts": evidence_missing,
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
        if run.get("name") != VIABILITY_ROUTE_WORKFLOWS[route]:
            invalid.append(
                {
                    "route": route,
                    "reason": "workflow_mismatch",
                    "expected": VIABILITY_ROUTE_WORKFLOWS[route],
                    "observed": run.get("name"),
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
