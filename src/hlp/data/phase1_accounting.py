"""Measured GitHub Actions acquisition accounting for Phase 1 evidence."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from typing import Iterable, Mapping


_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

_REQUEST_KEYS = {
    "requests_made",
    "archive_rpc_requests",
    "rpc_requests",
    "rhj_requests",
    "chainlink_directory_requests",
    "robinhood_asset_requests",
}

_RESPONSE_BYTE_KEYS = {
    "response_bytes_received",
    "bytes_received",
    "geckoterminal_bytes",
    "rhj_bytes",
    "chainlink_directory_bytes",
}


def extract_action_json_records(log_text: str) -> list[dict]:
    """Extract machine-readable JSON summaries printed inside Actions logs.

    GitHub prefixes each log line with a timestamp and may include ANSI escape
    sequences. Source-code echo lines are intentionally ignored unless their
    trailing text is itself valid JSON.
    """
    records: list[dict] = []
    for raw_line in log_text.splitlines():
        line = _ANSI_ESCAPE.sub("", raw_line).strip()
        start = line.find("{")
        while start >= 0:
            candidate = line[start:].strip()
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                start = line.find("{", start + 1)
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
            break
    return records


def _nonnegative_int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, not bool")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer: {value!r}") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative: {result}")
    return result


def _request_counters(records: Iterable[dict]) -> Counter[str]:
    counters: Counter[str] = Counter()
    for record in records:
        for key, value in record.items():
            if key not in _REQUEST_KEYS and not key.endswith("_requests"):
                continue
            if value is None:
                continue
            counters[key] += _nonnegative_int(value, field=key)
    return counters


def _response_byte_counters(records: Iterable[dict]) -> Counter[str]:
    counters: Counter[str] = Counter()
    for record in records:
        for key, value in record.items():
            if (
                key not in _RESPONSE_BYTE_KEYS
                and not key.endswith("_bytes_received")
                and not key.endswith("_response_bytes")
            ):
                continue
            if value is None:
                continue
            counters[key] += _nonnegative_int(value, field=key)
    return counters


def _rpc_route_counters(records: Iterable[dict]) -> Counter[str]:
    counters: Counter[str] = Counter()
    for record in records:
        route = record.get("rpc_route")
        if route is None:
            continue
        label = str(route).strip()
        if not label:
            raise ValueError("rpc_route cannot be empty")
        counters[label] += 1
    return counters


def _nonnegative_float(value: object, *, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative: {result}")
    return result


def _reported_block_ranges(records: Iterable[dict]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for record in records:
        candidates = [record]
        provenance = record.get("provenance")
        if isinstance(provenance, Mapping):
            candidates.append(provenance)
        for candidate in candidates:
            if "from_block" not in candidate or "to_block" not in candidate:
                continue
            lo = _nonnegative_int(candidate["from_block"], field="from_block")
            hi = _nonnegative_int(candidate["to_block"], field="to_block")
            if hi < lo:
                raise ValueError(
                    f"reported block range is reversed: {lo}..{hi}"
                )
            ranges.append((lo, hi))

    if not ranges:
        return []
    merged = []
    for lo, hi in sorted(set(ranges)):
        if not merged or lo > merged[-1][1] + 1:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    return [(lo, hi) for lo, hi in merged]


def _job_runtime_seconds(job: Mapping[str, object]) -> float | None:
    start = job.get("started_at")
    end = job.get("completed_at")
    if not start or not end:
        return None
    try:
        started = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        completed = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"invalid GitHub job timestamps: {start!r}, {end!r}"
        ) from exc
    seconds = (completed - started).total_seconds()
    if seconds < 0:
        raise ValueError("GitHub job completed before it started")
    return seconds


def summarize_action_run(
    run: Mapping[str, object],
    jobs: Iterable[Mapping[str, object]],
    artifacts: Iterable[Mapping[str, object]],
    logs_by_job_id: Mapping[int, str],
) -> dict:
    """Summarize one workflow run from GitHub API metadata and decoded logs."""
    run_id = _nonnegative_int(run.get("id"), field="run.id")
    job_rows = list(jobs)
    artifact_rows = list(artifacts)

    conclusions = Counter(
        str(job.get("conclusion") or job.get("status") or "unknown")
        for job in job_rows
    )
    request_totals: Counter[str] = Counter()
    response_byte_totals: Counter[str] = Counter()
    rpc_route_totals: Counter[str] = Counter()
    reported_ranges: list[tuple[int, int]] = []
    reported_elapsed_seconds = 0.0
    job_runtime_values: list[float] = []
    json_records = 0
    jobs_with_logs = 0

    for job in job_rows:
        runtime = _job_runtime_seconds(job)
        if runtime is not None:
            job_runtime_values.append(runtime)
        job_id = _nonnegative_int(job.get("id"), field="job.id")
        text = logs_by_job_id.get(job_id)
        if text is None:
            continue
        jobs_with_logs += 1
        records = extract_action_json_records(text)
        json_records += len(records)
        request_totals.update(_request_counters(records))
        response_byte_totals.update(_response_byte_counters(records))
        rpc_route_totals.update(_rpc_route_counters(records))
        reported_ranges.extend(_reported_block_ranges(records))
        elapsed = [
            _nonnegative_float(
                record["elapsed_seconds"],
                field="elapsed_seconds",
            )
            for record in records
            if record.get("elapsed_seconds") is not None
        ]
        if elapsed:
            # A job may echo multiple nested summaries. The longest reported
            # operation is the least double-counted acquisition-runtime signal.
            reported_elapsed_seconds += max(elapsed)

    merged_ranges = _reported_block_ranges([
        {"from_block": lo, "to_block": hi}
        for lo, hi in reported_ranges
    ])

    artifact_bytes = 0
    expired_artifacts = 0
    artifact_names: list[str] = []
    for artifact in artifact_rows:
        artifact_names.append(str(artifact.get("name") or ""))
        artifact_bytes += _nonnegative_int(
            artifact.get("size_in_bytes", 0),
            field="artifact.size_in_bytes",
        )
        expired_artifacts += int(bool(artifact.get("expired")))

    return {
        "run_id": run_id,
        "workflow_name": run.get("name"),
        "workflow_path": run.get("path"),
        "head_sha": run.get("head_sha"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "jobs": len(job_rows),
        "job_conclusions": dict(sorted(conclusions.items())),
        "jobs_with_logs": jobs_with_logs,
        "log_json_records": json_records,
        "request_counters": dict(sorted(request_totals.items())),
        "request_counter_total": sum(request_totals.values()),
        "response_byte_counters": dict(
            sorted(response_byte_totals.items())
        ),
        "counted_response_bytes": sum(response_byte_totals.values()),
        "rpc_route_counts": dict(sorted(rpc_route_totals.items())),
        "reported_rpc_routes": sorted(rpc_route_totals),
        "reported_block_ranges": [
            [lo, hi] for lo, hi in merged_ranges
        ],
        "reported_processed_blocks": sum(
            hi - lo + 1 for lo, hi in merged_ranges
        ),
        "reported_elapsed_seconds": reported_elapsed_seconds,
        "job_runtime_seconds": sum(job_runtime_values),
        "max_job_runtime_seconds": (
            max(job_runtime_values) if job_runtime_values else None
        ),
        "artifacts": len(artifact_rows),
        "artifact_bytes": artifact_bytes,
        "expired_artifacts": expired_artifacts,
        "artifact_names": sorted(artifact_names),
    }


def summarize_phase1_runs(
    run_summaries: Iterable[Mapping[str, object]],
    *,
    free_daily_method_calls: int = 10_000,
) -> dict:
    """Aggregate measured run evidence without inventing provider semantics."""
    daily = _nonnegative_int(
        free_daily_method_calls,
        field="free_daily_method_calls",
    )
    if daily == 0:
        raise ValueError("free_daily_method_calls must be positive")

    rows = [dict(row) for row in run_summaries]
    ids = [_nonnegative_int(row.get("run_id"), field="run_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate workflow run id in Phase 1 accounting")

    request_totals: Counter[str] = Counter()
    response_byte_totals: Counter[str] = Counter()
    rpc_route_totals: Counter[str] = Counter()
    artifact_bytes = 0
    reported_processed_blocks = 0
    reported_elapsed_seconds = 0.0
    job_runtime_seconds = 0.0
    unsuccessful = []
    incomplete = []

    for row in rows:
        for key, value in dict(row.get("request_counters") or {}).items():
            request_totals[str(key)] += _nonnegative_int(
                value,
                field=f"request_counters.{key}",
            )
        for key, value in dict(
            row.get("response_byte_counters") or {}
        ).items():
            response_byte_totals[str(key)] += _nonnegative_int(
                value,
                field=f"response_byte_counters.{key}",
            )
        for key, value in dict(row.get("rpc_route_counts") or {}).items():
            rpc_route_totals[str(key)] += _nonnegative_int(
                value,
                field=f"rpc_route_counts.{key}",
            )
        artifact_bytes += _nonnegative_int(
            row.get("artifact_bytes", 0),
            field="artifact_bytes",
        )
        reported_processed_blocks += _nonnegative_int(
            row.get("reported_processed_blocks", 0),
            field="reported_processed_blocks",
        )
        reported_elapsed_seconds += _nonnegative_float(
            row.get("reported_elapsed_seconds", 0),
            field="reported_elapsed_seconds",
        )
        job_runtime_seconds += _nonnegative_float(
            row.get("job_runtime_seconds", 0),
            field="job_runtime_seconds",
        )
        if row.get("status") != "completed":
            incomplete.append(_nonnegative_int(row["run_id"], field="run_id"))
        if row.get("conclusion") != "success":
            unsuccessful.append(
                _nonnegative_int(row["run_id"], field="run_id")
            )

    counted_requests = sum(request_totals.values())
    counted_response_bytes = sum(response_byte_totals.values())
    return {
        "runs": len(rows),
        "run_ids": ids,
        "request_counters": dict(sorted(request_totals.items())),
        "counted_network_requests": counted_requests,
        "response_byte_counters": dict(
            sorted(response_byte_totals.items())
        ),
        "counted_response_bytes": counted_response_bytes,
        "counted_response_gib": counted_response_bytes / (1024 ** 3),
        "rpc_route_counts": dict(sorted(rpc_route_totals.items())),
        "reported_rpc_routes": sorted(rpc_route_totals),
        "reported_processed_blocks": reported_processed_blocks,
        "reported_elapsed_seconds": reported_elapsed_seconds,
        "job_runtime_seconds": job_runtime_seconds,
        "artifact_bytes": artifact_bytes,
        "artifact_gib": artifact_bytes / (1024 ** 3),
        "free_daily_method_calls": daily,
        "minimum_free_quota_days_for_counted_requests": (
            0 if counted_requests == 0 else math.ceil(counted_requests / daily)
        ),
        "incomplete_run_ids": incomplete,
        "unsuccessful_run_ids": unsuccessful,
        "all_runs_successful": not incomplete and not unsuccessful,
        "accounting_scope_note": (
            "request and response-byte totals sum explicit top-level counters "
            "printed by HLP jobs; processed blocks use reported from/to ranges "
            "and runtime uses reported acquisition timers plus GitHub job "
            "timestamps. The accounting does not infer unreported traffic or "
            "claim that every counter is billable by the same provider"
        ),
    }
