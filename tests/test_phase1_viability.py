import pytest

from hlp.data.phase1_viability import (
    REQUIRED_PHASE1_ROUTE_BLOCKS,
    build_phase1_route_plan,
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


def _full_plan(*, missing_run_route=None, reused_run_routes=()):
    plans = []
    run_ids = {}
    next_run_id = 100
    shared_run_id = 999
    reused = set(reused_run_routes)
    for route, required_blocks in REQUIRED_PHASE1_ROUTE_BLOCKS.items():
        if route == missing_run_route:
            run_id = 9999
        elif route in reused:
            run_id = shared_run_id
        else:
            run_id = next_run_id
            next_run_id += 1
        run_ids[route] = run_id
        plans.append(
            {
                "route": route,
                "run_ids": [run_id],
                "required_blocks": required_blocks,
            }
        )
    return plans, run_ids


def _full_runs(run_ids, *, exclude=()):
    excluded = set(exclude)
    rows = []
    seen = set()
    for route, run_id in run_ids.items():
        if route in excluded or run_id in seen:
            continue
        seen.add(run_id)
        rows.append(
            _run(
                run_id,
                blocks=100,
                requests=100,
                response_bytes=1_000,
                artifact_bytes=500,
                elapsed=100,
                job_runtime=200,
            )
        )
    return rows


def test_required_phase1_route_blocks_match_frozen_workflow_geometry():
    head = 54_486_035
    assert REQUIRED_PHASE1_ROUTE_BLOCKS == {
        "pons_registry": (
            head - 8_600_612 + 1
            + head - 26_841_846 + 1
        ),
        "pons_v1_v3": head - 8_621_658 + 1,
        "pons_v2_curve": head - 26_841_846 + 1,
        "pons_v2_transition": head - 26_841_846 + 1,
        "pons_v2_v4": head - 26_841_846 + 1,
        "weth_usdg_anchor": head - 8_621_658 + 1,
        "stock_oracle": head - 8_621_658 + 1,
        "quote_v3_fallback": head - 35_992_329 + 1,
        "quote_v4_fallback": head - 36_023_158 + 1,
    }


def test_build_phase1_route_plan_fills_frozen_work_geometry():
    mapping = {
        route: [100 + index]
        for index, route in enumerate(REQUIRED_PHASE1_ROUTE_BLOCKS)
    }

    plan = build_phase1_route_plan(mapping)

    assert [row["route"] for row in plan] == list(
        REQUIRED_PHASE1_ROUTE_BLOCKS
    )
    assert {
        row["route"]: row["required_blocks"] for row in plan
    } == REQUIRED_PHASE1_ROUTE_BLOCKS
    assert {
        row["route"]: row["run_ids"] for row in plan
    } == mapping


def test_build_phase1_route_plan_rejects_missing_route():
    mapping = {
        route: [100 + index]
        for index, route in enumerate(REQUIRED_PHASE1_ROUTE_BLOCKS)
    }
    mapping.pop(next(iter(REQUIRED_PHASE1_ROUTE_BLOCKS)))

    with pytest.raises(ValueError, match="mapping contract mismatch"):
        build_phase1_route_plan(mapping)


def test_build_phase1_route_plan_rejects_cross_route_run_reuse():
    mapping = {
        route: [100 + index]
        for index, route in enumerate(REQUIRED_PHASE1_ROUTE_BLOCKS)
    }
    routes = list(REQUIRED_PHASE1_ROUTE_BLOCKS)
    mapping[routes[1]] = mapping[routes[0]]

    with pytest.raises(ValueError, match="reused across routes"):
        build_phase1_route_plan(mapping)


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
    plans, run_ids = _full_plan()
    rows = _full_runs(run_ids)
    required_work = sum(REQUIRED_PHASE1_ROUTE_BLOCKS.values())

    result = project_phase1_acquisition_plan(
        plans,
        rows,
        free_daily_method_calls=100,
    )

    assert result["routes"] == len(REQUIRED_PHASE1_ROUTE_BLOCKS)
    assert result["route_names"] == list(REQUIRED_PHASE1_ROUTE_BLOCKS)
    assert result["required_route_blocks"] == REQUIRED_PHASE1_ROUTE_BLOCKS
    assert result["required_work_blocks"] == required_work
    assert result["projected_requests"] == required_work
    assert result["projected_response_bytes"] == required_work * 10
    assert result["projected_artifact_bytes"] == required_work * 5
    assert result["projected_elapsed_seconds"] == required_work
    assert result["projected_job_runtime_seconds"] == required_work * 2
    assert result["projected_free_quota_days"] == (
        required_work + 99
    ) // 100
    assert result["all_routes_instrumented"] is True
    assert result["zero_cost_route_evidence"] is True


def test_phase1_plan_rejects_reused_evidence_run():
    routes = list(REQUIRED_PHASE1_ROUTE_BLOCKS)
    plans, run_ids = _full_plan(
        reused_run_routes=(routes[0], routes[1]),
    )
    rows = _full_runs(run_ids)

    with pytest.raises(ValueError, match="reused across routes"):
        project_phase1_acquisition_plan(plans, rows)


def test_phase1_plan_rejects_missing_accounting_run():
    first_route = next(iter(REQUIRED_PHASE1_ROUTE_BLOCKS))
    plans, run_ids = _full_plan(missing_run_route=first_route)
    rows = _full_runs(run_ids, exclude=(first_route,))

    with pytest.raises(ValueError, match="missing accounting runs"):
        project_phase1_acquisition_plan(plans, rows)

