import pytest

from hlp.data.phase1_viability import (
    project_phase1_acquisition_plan,
    project_route_requirements,
)


def _run(
    run_id,
    *,
    blocks,
    requests,
    response_bytes,
    artifact_bytes,
    elapsed,
    job_runtime,
    route="solidrpc_keyless_public",
):
    return {
        "run_id": run_id,
        "status": "completed",
        "conclusion": "success",
        "request_counter_total": requests,
        "counted_response_bytes": response_bytes,
        "artifact_bytes": artifact_bytes,
        "reported_processed_blocks": blocks,
        "reported_elapsed_seconds": elapsed,
        "job_runtime_seconds": job_runtime,
        "rpc_route_counts": {route: 1},
    }


def test_route_projection_uses_worst_observed_per_block_rates():
    rows = [
        _run(
            1,
            blocks=100,
            requests=20,
            response_bytes=1_000,
            artifact_bytes=500,
            elapsed=10,
            job_runtime=12,
        ),
        _run(
            2,
            blocks=200,
            requests=60,
            response_bytes=3_000,
            artifact_bytes=1_600,
            elapsed=30,
            job_runtime=50,
            route="solidrpc_authenticated_free",
        ),
    ]
    result = project_route_requirements(
        "v2_curve",
        rows,
        required_blocks=1_000,
        free_daily_method_calls=100,
    )

    assert result["projection_basis"] == (
        "worst_observed_per_processed_block"
    )
    assert result["observed_rpc_routes"] == [
        "solidrpc_authenticated_free",
        "solidrpc_keyless_public",
    ]
    assert result["projected_requests"] == 300
    assert result["projected_response_bytes"] == 15_000
    assert result["projected_artifact_bytes"] == 8_000
    assert result["projected_elapsed_seconds"] == 150
    assert result["projected_job_runtime_seconds"] == 250
    assert result["projected_free_quota_days"] == 3
    assert result["all_observed_rpc_routes_free"] is True


def test_route_projection_rejects_custom_rpc_route():
    with pytest.raises(ValueError, match="unproven free RPC routes"):
        project_route_requirements(
            "v1_v3",
            [
                _run(
                    1,
                    blocks=100,
                    requests=20,
                    response_bytes=1_000,
                    artifact_bytes=500,
                    elapsed=10,
                    job_runtime=12,
                    route="custom_archive_rpc",
                )
            ],
            required_blocks=1_000,
        )


def test_route_projection_requires_response_egress_measurement():
    row = _run(
        1,
        blocks=100,
        requests=20,
        response_bytes=1_000,
        artifact_bytes=500,
        elapsed=10,
        job_runtime=12,
    )
    row["counted_response_bytes"] = 0

    with pytest.raises(ValueError, match="counted_response_bytes"):
        project_route_requirements(
            "anchor",
            [row],
            required_blocks=1_000,
        )


def test_phase1_plan_aggregates_routes_and_free_quota_days():
    rows = [
        _run(
            11,
            blocks=100,
            requests=10,
            response_bytes=1_000,
            artifact_bytes=500,
            elapsed=10,
            job_runtime=20,
        ),
        _run(
            12,
            blocks=50,
            requests=20,
            response_bytes=2_000,
            artifact_bytes=1_000,
            elapsed=20,
            job_runtime=30,
            route="robinhood_public",
        ),
    ]
    result = project_phase1_acquisition_plan(
        [
            {
                "route": "registry",
                "run_ids": [11],
                "required_blocks": 1_000,
            },
            {
                "route": "anchor",
                "run_ids": [12],
                "required_blocks": 500,
            },
        ],
        rows,
        free_daily_method_calls=100,
    )

    assert result["routes"] == 2
    assert result["route_names"] == ["registry", "anchor"]
    assert result["projected_requests"] == 300
    assert result["projected_response_bytes"] == 30_000
    assert result["projected_artifact_bytes"] == 15_000
    assert result["projected_elapsed_seconds"] == 300
    assert result["projected_job_runtime_seconds"] == 500
    assert result["projected_free_quota_days"] == 3
    assert result["all_routes_instrumented"] is True
    assert result["zero_cost_route_evidence"] is True


def test_phase1_plan_rejects_reused_evidence_run():
    rows = [
        _run(
            11,
            blocks=100,
            requests=10,
            response_bytes=1_000,
            artifact_bytes=500,
            elapsed=10,
            job_runtime=20,
        )
    ]
    with pytest.raises(ValueError, match="reused across routes"):
        project_phase1_acquisition_plan(
            [
                {
                    "route": "registry",
                    "run_ids": [11],
                    "required_blocks": 1_000,
                },
                {
                    "route": "v1_v3",
                    "run_ids": [11],
                    "required_blocks": 1_000,
                },
            ],
            rows,
        )


def test_phase1_plan_rejects_missing_accounting_run():
    with pytest.raises(ValueError, match="missing accounting runs"):
        project_phase1_acquisition_plan(
            [
                {
                    "route": "registry",
                    "run_ids": [99],
                    "required_blocks": 1_000,
                }
            ],
            [
                _run(
                    11,
                    blocks=100,
                    requests=10,
                    response_bytes=1_000,
                    artifact_bytes=500,
                    elapsed=10,
                    job_runtime=20,
                )
            ],
        )
