import pytest

from hlp.data.phase1_acceptance import (
    REQUIRED_PHASE1_ACQUISITION_ROUTES,
    build_phase1_acceptance_report,
)
from hlp.data.phase1_viability import REQUIRED_PHASE1_ROUTE_BLOCKS


def _fixtures():
    eligible_manifest = {
        "sha256": "eligible-sha",
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 54_486_035,
            "eligibility_threshold_usd": "100000",
            "v1_eligibility_run_id": 101,
            "v2_eligibility_run_id": 202,
        },
    }
    eligible_summary = {
        "snapshot_head_block": 54_486_035,
        "all_pons_launches": 494_639,
        "v1_launches": 268_688,
        "v2_launches": 225_951,
        "eligible_tokens": 1234,
        "eligible_v1": 700,
        "eligible_v2": 534,
        "unknown_tokens": 0,
        "universe_sha256": "eligible-sha",
    }
    representative_manifest = {
        "sha256": "representative-sha",
        "provenance": {
            "chain_id": 4663,
            "snapshot_head_block": 54_486_035,
            "v1_eligibility_run_id": 101,
            "v2_eligibility_run_id": 202,
            "source_coverage_sha256": "c" * 64,
        },
    }
    representative_summary = {
        "snapshot_head_block": 54_486_035,
        "tokens": 10,
        "complete_tokens": 10,
        "sample_groups": {"failure": 5, "runner": 5},
        "pons_versions": {"v1": 5, "v2": 5},
        "price_points": 1100,
        "priced_points": 1000,
        "unpriced_points": 100,
        "detailed_price_points": 1100,
        "detailed_priced_points": 1000,
        "detailed_unpriced_points": 100,
        "detailed_price_path_complete_tokens": 7,
        "market_path_rows": 5000,
        "transfers": 2500,
        "dex_targeted": 9,
        "dex_matched": 9,
        "no_registered_v4_pool": 1,
        "dex_price_targeted": 8,
        "dex_price_matched": 8,
        "dex_price_checkpoints_targeted": 20,
        "dex_price_checkpoints_matched": 20,
        "dex_price_multi_checkpoint_tokens": 6,
        "dex_price_no_swap_checkpoint": 1,
        "explorer_verified_transactions": 30,
        "explorer_verified_launch_transactions": 10,
        "explorer_verified_dex_swap_transactions": 20,
        "coverage_sources": 11,
        "continuous_sharded_sources": 7,
        "snapshot_pinned_sources": 4,
        "coverage_sample_start_block": 1000,
        "no_unexplained_block_gaps": True,
        "source_coverage_sha256": "c" * 64,
        "validation_sha256": "representative-sha",
    }
    route_projections = [
        {
            "route": route,
            "all_observed_rpc_routes_free": True,
            "required_blocks": REQUIRED_PHASE1_ROUTE_BLOCKS[route],
            "evidence_processed_blocks": 100_000,
            "evidence_run_ids": [1000 + index],
        }
        for index, route in enumerate(REQUIRED_PHASE1_ACQUISITION_ROUTES)
    ]
    viability = {
        "routes": len(REQUIRED_PHASE1_ACQUISITION_ROUTES),
        "route_names": list(REQUIRED_PHASE1_ACQUISITION_ROUTES),
        "route_projections": route_projections,
        "required_route_blocks": dict(REQUIRED_PHASE1_ROUTE_BLOCKS),
        "required_work_blocks": sum(REQUIRED_PHASE1_ROUTE_BLOCKS.values()),
        "all_routes_instrumented": True,
        "all_observed_rpc_routes_free": True,
        "zero_cost_route_evidence": True,
        "projected_requests": 1_000_000,
        "projected_response_bytes": 5_000_000_000,
        "projected_artifact_bytes": 2_000_000_000,
        "projected_elapsed_seconds": 100_000,
        "projected_job_runtime_seconds": 120_000,
        "free_daily_method_calls": 10_000,
        "projected_free_quota_days": 100,
        "accounting_run_id": 303,
    }
    return (
        eligible_summary,
        eligible_manifest,
        representative_summary,
        representative_manifest,
        viability,
    )


def test_phase1_acceptance_passes_only_complete_consistent_evidence():
    report = build_phase1_acceptance_report(*_fixtures())

    assert report["phase1_acceptance_status"] == "pass"
    assert report["phase1_checkpoint"] == "hlp-v1-phase1-data-viability"
    assert report["snapshot_head_block"] == 54_486_035
    assert report["all_pons_launches"] == 494_639
    assert report["representative_tokens"] == 10
    assert report["representative_price_points"] == 1100
    assert report["representative_detailed_price_points"] == 1100
    assert report[
        "representative_detailed_price_path_complete_tokens"
    ] == 7
    assert report["representative_dex_price_tokens_targeted"] == 8
    assert report["representative_dex_price_checkpoints_targeted"] == 20
    assert report["representative_dex_price_checkpoints_matched"] == 20
    assert report["representative_dex_multi_checkpoint_tokens"] == 6
    assert report["representative_explorer_verified_transactions"] == 30
    assert report[
        "representative_explorer_verified_launch_transactions"
    ] == 10
    assert report[
        "representative_explorer_verified_dex_swap_transactions"
    ] == 20
    assert report["representative_coverage_sources"] == 11
    assert report["representative_no_unexplained_block_gaps"] is True
    assert report["representative_source_coverage_sha256"] == "c" * 64
    assert report["projected_free_quota_days"] == 100
    assert report["required_acquisition_routes"] == list(
        REQUIRED_PHASE1_ACQUISITION_ROUTES
    )


def test_phase1_acceptance_rejects_inconsistent_lifecycle_runs():
    fixtures = list(_fixtures())
    fixtures[3]["provenance"]["v1_eligibility_run_id"] = 999

    with pytest.raises(ValueError, match="V1 lifecycle evidence disagree"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_missing_required_route():
    fixtures = list(_fixtures())
    viability = fixtures[4]
    viability["route_names"] = viability["route_names"][:-1]
    viability["routes"] -= 1
    viability["route_projections"] = viability["route_projections"][:-1]

    with pytest.raises(ValueError, match="route coverage mismatch"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_required_route_block_drift():
    fixtures = list(_fixtures())
    first_route = next(iter(REQUIRED_PHASE1_ROUTE_BLOCKS))
    fixtures[4]["required_route_blocks"][first_route] -= 1
    fixtures[4]["required_work_blocks"] -= 1

    with pytest.raises(ValueError, match="route-block contract changed"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_route_detail_block_drift():
    fixtures = list(_fixtures())
    fixtures[4]["route_projections"][0]["required_blocks"] -= 1

    with pytest.raises(ValueError, match="required-block detail changed"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_non_free_route_evidence():
    fixtures = list(_fixtures())
    fixtures[4]["zero_cost_route_evidence"] = False

    with pytest.raises(ValueError, match="zero-cost route proof"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_detailed_price_path_drift():
    fixtures = list(_fixtures())
    fixtures[2]["detailed_price_points"] -= 1

    with pytest.raises(
        ValueError,
        match="detailed and lifecycle price paths disagree",
    ):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_nested_dex_checkpoint_mismatch():
    fixtures = list(_fixtures())
    fixtures[2]["dex_price_checkpoints_matched"] -= 1

    with pytest.raises(ValueError, match="checkpoint evidence has mismatches"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_incomplete_checkpoint_coverage():
    fixtures = list(_fixtures())
    fixtures[2]["dex_price_checkpoints_targeted"] = 7
    fixtures[2]["dex_price_checkpoints_matched"] = 7

    with pytest.raises(ValueError, match="below targeted token coverage"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_missing_explorer_launch():
    fixtures = list(_fixtures())
    fixtures[2]["explorer_verified_launch_transactions"] = 9
    fixtures[2]["explorer_verified_transactions"] = 29

    with pytest.raises(ValueError, match="all 10 launches"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_explorer_dex_coverage_drift():
    fixtures = list(_fixtures())
    fixtures[2]["explorer_verified_dex_swap_transactions"] = 19
    fixtures[2]["explorer_verified_transactions"] = 29

    with pytest.raises(ValueError, match="explorer/DEX checkpoint coverage"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_unexplained_source_gap():
    fixtures = list(_fixtures())
    fixtures[2]["no_unexplained_block_gaps"] = False

    with pytest.raises(ValueError, match="unexplained source block gaps"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_coverage_sha_drift():
    fixtures = list(_fixtures())
    fixtures[3]["provenance"]["source_coverage_sha256"] = "d" * 64

    with pytest.raises(ValueError, match="coverage SHA disagrees"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_incomplete_dex_price_accounting():
    fixtures = list(_fixtures())
    fixtures[2]["dex_price_no_swap_checkpoint"] = 0

    with pytest.raises(ValueError, match="does not account for all tokens"):
        build_phase1_acceptance_report(*fixtures)


def test_phase1_acceptance_rejects_unknown_eligible_tokens():
    fixtures = list(_fixtures())
    fixtures[0]["unknown_tokens"] = 1

    with pytest.raises(ValueError, match="still contains unknown"):
        build_phase1_acceptance_report(*fixtures)
