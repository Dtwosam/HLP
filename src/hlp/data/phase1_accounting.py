"""Measured GitHub Actions acquisition accounting for Phase 1 evidence."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
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
    json_records = 0
    jobs_with_logs = 0

    for job in job_rows:
        job_id = _nonnegative_int(job.get("id"), field="job.id")
        text = logs_by_job_id.get(job_id)
        if text is None:
            continue
        jobs_with_logs += 1
        records = extract_action_json_records(text)
        json_records += len(records)
        request_totals.update(_request_counters(records))

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
    artifact_bytes = 0
    unsuccessful = []
    incomplete = []

    for row in rows:
        for key, value in dict(row.get("request_counters") or {}).items():
            request_totals[str(key)] += _nonnegative_int(
                value,
                field=f"request_counters.{key}",
            )
        artifact_bytes += _nonnegative_int(
            row.get("artifact_bytes", 0),
            field="artifact_bytes",
        )
        if row.get("status") != "completed":
            incomplete.append(_nonnegative_int(row["run_id"], field="run_id"))
        if row.get("conclusion") != "success":
            unsuccessful.append(
                _nonnegative_int(row["run_id"], field="run_id")
            )

    counted_requests = sum(request_totals.values())
    return {
        "runs": len(rows),
        "run_ids": ids,
        "request_counters": dict(sorted(request_totals.items())),
        "counted_network_requests": counted_requests,
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
            "counted_network_requests sums explicit top-level request counters "
            "printed by HLP jobs; it does not infer unreported requests or "
            "claim that every counter is billable by the same provider"
        ),
    }
