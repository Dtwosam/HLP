"""Fail-closed Phase 1 full-history acquisition viability projections."""

from __future__ import annotations

import math
from typing import Iterable, Mapping


FREE_RPC_ROUTES = frozenset({
    "robinhood_public",
    "solidrpc_keyless_public",
    "solidrpc_authenticated_free",
})


def _positive_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, not bool")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer: {value!r}") from exc
    if result <= 0:
        raise ValueError(f"{field} must be positive: {result}")
    return result


def _positive_float(value: object, *, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if result <= 0:
        raise ValueError(f"{field} must be positive: {result}")
    return result


def _request_total(row: Mapping[str, object]) -> int:
    if row.get("request_counter_total") is not None:
        return _positive_int(
            row["request_counter_total"],
            field="request_counter_total",
        )
    total = sum(
        int(value)
        for value in dict(row.get("request_counters") or {}).values()
    )
    return _positive_int(total, field="request_counters total")


def project_route_requirements(
    route: str,
    run_summaries: Iterable[Mapping[str, object]],
    *,
    required_blocks: int,
    free_daily_method_calls: int = 10_000,
) -> dict:
    """Project one full-history route from successful instrumented evidence.

    The projection uses the worst observed per-processed-block rate across the
    supplied runs. That deliberately favors a conservative capacity estimate
    over a mean that could hide one dense or slow shard.
    """
    name = str(route).strip()
    if not name:
        raise ValueError("route cannot be empty")
    required = _positive_int(required_blocks, field="required_blocks")
    daily = _positive_int(
        free_daily_method_calls,
        field="free_daily_method_calls",
    )

    rows = [dict(row) for row in run_summaries]
    if not rows:
        raise ValueError(f"route {name} has no measured evidence")

    run_ids = []
    observed_routes: set[str] = set()
    request_rates = []
    response_byte_rates = []
    artifact_byte_rates = []
    elapsed_rates = []
    job_runtime_rates = []
    evidence_blocks = 0

    for row in rows:
        run_id = _positive_int(row.get("run_id"), field="run_id")
        if run_id in run_ids:
            raise ValueError(f"route {name} repeats run id {run_id}")
        run_ids.append(run_id)

        if row.get("status") != "completed" or row.get("conclusion") != "success":
            raise ValueError(
                f"route {name} evidence run {run_id} is not successful"
            )

        blocks = _positive_int(
            row.get("reported_processed_blocks"),
            field=f"run {run_id} reported_processed_blocks",
        )
        requests = _request_total(row)
        response_bytes = _positive_int(
            row.get("counted_response_bytes"),
            field=f"run {run_id} counted_response_bytes",
        )
        artifact_bytes = _positive_int(
            row.get("artifact_bytes"),
            field=f"run {run_id} artifact_bytes",
        )
        elapsed = _positive_float(
            row.get("reported_elapsed_seconds"),
            field=f"run {run_id} reported_elapsed_seconds",
        )
        job_runtime = _positive_float(
            row.get("job_runtime_seconds"),
            field=f"run {run_id} job_runtime_seconds",
        )

        route_counts = dict(row.get("rpc_route_counts") or {})
        if not route_counts:
            raise ValueError(
                f"route {name} evidence run {run_id} has no RPC route provenance"
            )
        for route_label, count in route_counts.items():
            _positive_int(
                count,
                field=f"run {run_id} rpc_route_counts.{route_label}",
            )
            observed_routes.add(str(route_label))

        unsupported = sorted(observed_routes - FREE_RPC_ROUTES)
        if unsupported:
            raise ValueError(
                f"route {name} uses unproven free RPC routes: {unsupported}"
            )

        evidence_blocks += blocks
        request_rates.append(requests / blocks)
        response_byte_rates.append(response_bytes / blocks)
        artifact_byte_rates.append(artifact_bytes / blocks)
        elapsed_rates.append(elapsed / blocks)
        job_runtime_rates.append(job_runtime / blocks)

    worst_request_rate = max(request_rates)
    worst_response_byte_rate = max(response_byte_rates)
    worst_artifact_byte_rate = max(artifact_byte_rates)
    worst_elapsed_rate = max(elapsed_rates)
    worst_job_runtime_rate = max(job_runtime_rates)

    projected_requests = math.ceil(worst_request_rate * required)
    projected_response_bytes = math.ceil(
        worst_response_byte_rate * required
    )
    projected_artifact_bytes = math.ceil(
        worst_artifact_byte_rate * required
    )
    projected_elapsed_seconds = worst_elapsed_rate * required
    projected_job_runtime_seconds = worst_job_runtime_rate * required

    return {
        "route": name,
        "required_blocks": required,
        "evidence_run_ids": run_ids,
        "evidence_runs": len(rows),
        "evidence_processed_blocks": evidence_blocks,
        "observed_rpc_routes": sorted(observed_routes),
        "all_observed_rpc_routes_free": True,
        "projection_basis": "worst_observed_per_processed_block",
        "worst_requests_per_block": worst_request_rate,
        "worst_response_bytes_per_block": worst_response_byte_rate,
        "worst_artifact_bytes_per_block": worst_artifact_byte_rate,
        "worst_elapsed_seconds_per_block": worst_elapsed_rate,
        "worst_job_runtime_seconds_per_block": worst_job_runtime_rate,
        "projected_requests": projected_requests,
        "projected_response_bytes": projected_response_bytes,
        "projected_response_gib": projected_response_bytes / (1024 ** 3),
        "projected_artifact_bytes": projected_artifact_bytes,
        "projected_artifact_gib": projected_artifact_bytes / (1024 ** 3),
        "projected_elapsed_seconds": projected_elapsed_seconds,
        "projected_job_runtime_seconds": projected_job_runtime_seconds,
        "free_daily_method_calls": daily,
        "projected_free_quota_days": (
            0
            if projected_requests == 0
            else math.ceil(projected_requests / daily)
        ),
    }


def project_phase1_acquisition_plan(
    route_plan: Iterable[Mapping[str, object]],
    run_summaries: Iterable[Mapping[str, object]],
    *,
    free_daily_method_calls: int = 10_000,
) -> dict:
    """Project all required acquisition routes from measured run summaries."""
    plans = [dict(row) for row in route_plan]
    if not plans:
        raise ValueError("Phase 1 acquisition plan cannot be empty")

    summaries = {
        _positive_int(row.get("run_id"), field="run_id"): dict(row)
        for row in run_summaries
    }
    if not summaries:
        raise ValueError("Phase 1 acquisition projection has no run evidence")

    names: set[str] = set()
    used_run_ids: set[int] = set()
    projected = []

    for plan in plans:
        name = str(plan.get("route") or "").strip()
        if not name:
            raise ValueError("Phase 1 route plan has empty route name")
        if name in names:
            raise ValueError(f"duplicate Phase 1 route plan: {name}")
        names.add(name)

        run_ids = [
            _positive_int(value, field=f"{name}.run_ids")
            for value in list(plan.get("run_ids") or [])
        ]
        if not run_ids:
            raise ValueError(f"route {name} has no evidence run ids")
        overlap = used_run_ids & set(run_ids)
        if overlap:
            raise ValueError(
                f"Phase 1 evidence run reused across routes: {sorted(overlap)}"
            )
        used_run_ids.update(run_ids)

        missing = sorted(set(run_ids) - set(summaries))
        if missing:
            raise ValueError(
                f"route {name} references missing accounting runs: {missing}"
            )

        projected.append(
            project_route_requirements(
                name,
                [summaries[run_id] for run_id in run_ids],
                required_blocks=_positive_int(
                    plan.get("required_blocks"),
                    field=f"{name}.required_blocks",
                ),
                free_daily_method_calls=free_daily_method_calls,
            )
        )

    total_requests = sum(row["projected_requests"] for row in projected)
    total_response_bytes = sum(
        row["projected_response_bytes"] for row in projected
    )
    total_artifact_bytes = sum(
        row["projected_artifact_bytes"] for row in projected
    )
    total_elapsed_seconds = sum(
        row["projected_elapsed_seconds"] for row in projected
    )
    total_job_runtime_seconds = sum(
        row["projected_job_runtime_seconds"] for row in projected
    )
    daily = _positive_int(
        free_daily_method_calls,
        field="free_daily_method_calls",
    )

    return {
        "routes": len(projected),
        "route_names": [row["route"] for row in projected],
        "route_projections": projected,
        "all_routes_instrumented": True,
        "all_observed_rpc_routes_free": all(
            row["all_observed_rpc_routes_free"] for row in projected
        ),
        "projected_requests": total_requests,
        "projected_response_bytes": total_response_bytes,
        "projected_response_gib": total_response_bytes / (1024 ** 3),
        "projected_artifact_bytes": total_artifact_bytes,
        "projected_artifact_gib": total_artifact_bytes / (1024 ** 3),
        "projected_elapsed_seconds": total_elapsed_seconds,
        "projected_job_runtime_seconds": total_job_runtime_seconds,
        "free_daily_method_calls": daily,
        "projected_free_quota_days": (
            0
            if total_requests == 0
            else math.ceil(total_requests / daily)
        ),
        "zero_cost_route_evidence": all(
            row["all_observed_rpc_routes_free"] for row in projected
        ),
        "projection_scope_note": (
            "capacity projection uses the worst observed per-processed-block "
            "request, response-byte, artifact-byte and runtime rates from "
            "successful instrumented evidence runs. It is a conservative "
            "planning estimate, not a provider billing claim."
        ),
    }
