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


def test_summarize_action_run_measures_requests_egress_blocks_and_runtime():
    run = {
        "id": 123,
        "name": "phase1-test",
        "path": ".github/workflows/phase1-test.yml",
        "head_sha": "abc",
        "status": "completed",
        "conclusion": "success",
    }
    jobs = [
        {
            "id": 1,
            "conclusion": "success",
            "started_at": "2026-09-05T00:00:00Z",
            "completed_at": "2026-09-05T00:01:30Z",
        },
        {
            "id": 2,
            "conclusion": "success",
            "started_at": "2026-09-05T00:02:00Z",
            "completed_at": "2026-09-05T00:04:00Z",
        },
    ]
    artifacts = [
        {"name": "a", "size_in_bytes": 100, "expired": False},
        {"name": "b", "size_in_bytes": 25, "expired": True},
    ]
    logs = {
        1: (
            'x {"requests_made": 5, "rhj_requests": 2, '
            '"rhj_bytes": 200, "chainlink_directory_requests": 1, '
            '"chainlink_directory_bytes": 300, '
            '"response_bytes_received": 1000, "rpc_route": '
            '"solidrpc_keyless_public", "elapsed_seconds": 12.5, '
            '"provenance": {"from_block": 10, "to_block": 19}}\n'
        ),
        2: (
            'x {"archive_rpc_requests": 7, "records": 99, '
            '"response_bytes_received": 2500, "rpc_route": '
            '"solidrpc_keyless_public", "elapsed_seconds": 8, '
            '"provenance": {"from_block": 20, "to_block": 29}}\n'
        ),
    }
    result = summarize_action_run(run, jobs, artifacts, logs)
    assert result["request_counters"] == {
        "archive_rpc_requests": 7,
        "chainlink_directory_requests": 1,
        "requests_made": 5,
        "rhj_requests": 2,
    }
    assert result["request_counter_total"] == 15
    assert result["response_byte_counters"] == {
        "chainlink_directory_bytes": 300,
        "response_bytes_received": 3500,
        "rhj_bytes": 200,
    }
    assert result["counted_response_bytes"] == 4000
    assert result["rpc_route_counts"] == {"solidrpc_keyless_public": 2}
    assert result["reported_rpc_routes"] == ["solidrpc_keyless_public"]
    assert result["reported_block_ranges"] == [[10, 29]]
    assert result["reported_processed_blocks"] == 20
    assert result["reported_elapsed_seconds"] == 20.5
    assert result["job_runtime_seconds"] == 210
    assert result["max_job_runtime_seconds"] == 120
    assert result["artifact_bytes"] == 125
    assert result["expired_artifacts"] == 1
    assert result["jobs_with_logs"] == 2


def test_summarize_action_run_deduplicates_repeated_reported_ranges():
    run = {
        "id": 124,
        "status": "completed",
        "conclusion": "success",
    }
    jobs = [{"id": 1, "conclusion": "success"}]
    logs = {
        1: "\n".join(
            [
                'x {"from_block": 10, "to_block": 20}',
                (
                    'x {"elapsed_seconds": 4, "provenance": '
                    '{"from_block": 10, "to_block": 20}}'
                ),
                'x {"from_block": 18, "to_block": 25}',
            ]
        )
    }
    result = summarize_action_run(run, jobs, [], logs)
    assert result["reported_block_ranges"] == [[10, 25]]
    assert result["reported_processed_blocks"] == 16
    assert result["reported_elapsed_seconds"] == 4


def test_phase1_summary_reports_quota_egress_runtime_and_failures():
    rows = [
        {
            "run_id": 1,
            "status": "completed",
            "conclusion": "success",
            "request_counters": {"requests_made": 9_000},
            "response_byte_counters": {"response_bytes_received": 10_000},
            "rpc_route_counts": {"solidrpc_keyless_public": 3},
            "reported_processed_blocks": 500_000,
            "reported_elapsed_seconds": 100,
            "job_runtime_seconds": 120,
            "artifact_bytes": 1024,
        },
        {
            "run_id": 2,
            "status": "completed",
            "conclusion": "failure",
            "request_counters": {"archive_rpc_requests": 1_500},
            "response_byte_counters": {
                "response_bytes_received": 20_000,
                "geckoterminal_bytes": 500,
            },
            "rpc_route_counts": {
                "solidrpc_authenticated_free": 1,
                "custom_archive_rpc": 1,
            },
            "reported_processed_blocks": 250_000,
            "reported_elapsed_seconds": 50,
            "job_runtime_seconds": 60,
            "artifact_bytes": 2048,
        },
    ]
    result = summarize_phase1_runs(rows, free_daily_method_calls=10_000)
    assert result["counted_network_requests"] == 10_500
    assert result["minimum_free_quota_days_for_counted_requests"] == 2
    assert result["counted_response_bytes"] == 30_500
    assert result["rpc_route_counts"] == {
        "custom_archive_rpc": 1,
        "solidrpc_authenticated_free": 1,
        "solidrpc_keyless_public": 3,
    }
    assert result["reported_rpc_routes"] == [
        "custom_archive_rpc",
        "solidrpc_authenticated_free",
        "solidrpc_keyless_public",
    ]
    assert result["reported_processed_blocks"] == 750_000
    assert result["reported_elapsed_seconds"] == 150
    assert result["job_runtime_seconds"] == 180
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
