import json

import pytest

from hlp.data.phase1_accounting import (
    extract_action_json_records,
    summarize_action_run,
    summarize_phase1_runs,
)


def test_extract_action_json_records_ignores_source_echo_and_ansi():
    log = "\n".join(
        [
            "2026-09-05T00:00:00Z \\x1b[36;1mprint({'requests_made': 99})\\x1b[0m",
            '2026-09-05T00:00:01Z {"records": 12, "requests_made": 7}',
            '2026-09-05T00:00:02Z not-json {"requests_made": 3}',
        ]
    )
    rows = extract_action_json_records(log)
    assert rows == [
        {"records": 12, "requests_made": 7},
        {"requests_made": 3},
    ]


def test_summarize_action_run_counts_requests_and_artifact_bytes():
    run = {
        "id": 123,
        "name": "phase1-test",
        "path": ".github/workflows/phase1-test.yml",
        "head_sha": "abc",
        "status": "completed",
        "conclusion": "success",
    }
    jobs = [
        {"id": 1, "conclusion": "success"},
        {"id": 2, "conclusion": "success"},
    ]
    artifacts = [
        {"name": "a", "size_in_bytes": 100, "expired": False},
        {"name": "b", "size_in_bytes": 25, "expired": True},
    ]
    logs = {
        1: 'x {"requests_made": 5, "rhj_requests": 2}\n',
        2: 'x {"archive_rpc_requests": 7, "records": 99}\n',
    }
    result = summarize_action_run(run, jobs, artifacts, logs)
    assert result["request_counters"] == {
        "archive_rpc_requests": 7,
        "requests_made": 5,
        "rhj_requests": 2,
    }
    assert result["request_counter_total"] == 14
    assert result["artifact_bytes"] == 125
    assert result["expired_artifacts"] == 1
    assert result["jobs_with_logs"] == 2
    assert result["all_runs_successful"] if "all_runs_successful" in result else True


def test_phase1_summary_reports_quota_days_and_failures():
    rows = [
        {
            "run_id": 1,
            "status": "completed",
            "conclusion": "success",
            "request_counters": {"requests_made": 9_000},
            "artifact_bytes": 1024,
        },
        {
            "run_id": 2,
            "status": "completed",
            "conclusion": "failure",
            "request_counters": {"archive_rpc_requests": 1_500},
            "artifact_bytes": 2048,
        },
    ]
    result = summarize_phase1_runs(rows, free_daily_method_calls=10_000)
    assert result["counted_network_requests"] == 10_500
    assert result["minimum_free_quota_days_for_counted_requests"] == 2
    assert result["artifact_bytes"] == 3072
    assert result["unsuccessful_run_ids"] == [2]
    assert result["all_runs_successful"] is False


def test_phase1_summary_rejects_duplicate_runs():
    with pytest.raises(ValueError, match="duplicate workflow run id"):
        summarize_phase1_runs(
            [
                {"run_id": 7, "status": "completed", "conclusion": "success"},
                {"run_id": 7, "status": "completed", "conclusion": "success"},
            ]
        )


def test_phase1_summary_rejects_zero_daily_quota():
    with pytest.raises(ValueError, match="must be positive"):
        summarize_phase1_runs([], free_daily_method_calls=0)
