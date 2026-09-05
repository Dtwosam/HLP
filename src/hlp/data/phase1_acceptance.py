"""Fail-closed Phase 1 acceptance gate for frozen evidence artifacts."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase1_viability import REQUIRED_PHASE1_ROUTE_BLOCKS


SNAPSHOT_HEAD_BLOCK = 54_486_035
EXPECTED_PONS_LAUNCHES = 494_639
EXPECTED_V1_LAUNCHES = 268_688
EXPECTED_V2_LAUNCHES = 225_951
FREE_DAILY_METHOD_CALLS = 10_000

REQUIRED_PHASE1_ACQUISITION_ROUTES = tuple(
    REQUIRED_PHASE1_ROUTE_BLOCKS
)


def _int(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer, not bool")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer: {value!r}") from exc


def _positive(value: object, *, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if result <= 0:
        raise ValueError(f"{field} must be positive: {result}")
    return result


def _manifest_provenance(
    manifest: Mapping[str, object],
    *,
    label: str,
) -> Mapping[str, object]:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"{label} manifest has no provenance")
    if _int(provenance.get("chain_id"), field=f"{label}.chain_id") != 4663:
        raise ValueError(f"{label} manifest chain is not Robinhood Chain")
    if _int(
        provenance.get("snapshot_head_block"),
        field=f"{label}.snapshot_head_block",
    ) != SNAPSHOT_HEAD_BLOCK:
        raise ValueError(f"{label} manifest snapshot head changed")
    return provenance


def build_phase1_acceptance_report(
    eligible_summary: Mapping[str, object],
    eligible_manifest: Mapping[str, object],
    representative_summary: Mapping[str, object],
    representative_manifest: Mapping[str, object],
    viability_projection: Mapping[str, object],
) -> dict:
    """Return PASS only when every frozen Phase 1 evidence pillar agrees."""
    eligible = dict(eligible_summary)
    representative = dict(representative_summary)
    viability = dict(viability_projection)

    if _int(
        eligible.get("snapshot_head_block"),
        field="eligible.snapshot_head_block",
    ) != SNAPSHOT_HEAD_BLOCK:
        raise ValueError("eligible universe snapshot head changed")
    if _int(
        eligible.get("all_pons_launches"),
        field="eligible.all_pons_launches",
    ) != EXPECTED_PONS_LAUNCHES:
        raise ValueError("eligible universe Pons launch count changed")
    if _int(
        eligible.get("v1_launches"),
        field="eligible.v1_launches",
    ) != EXPECTED_V1_LAUNCHES:
        raise ValueError("eligible universe V1 launch count changed")
    if _int(
        eligible.get("v2_launches"),
        field="eligible.v2_launches",
    ) != EXPECTED_V2_LAUNCHES:
        raise ValueError("eligible universe V2 launch count changed")
    if _int(
        eligible.get("unknown_tokens"),
        field="eligible.unknown_tokens",
    ) != 0:
        raise ValueError("eligible universe still contains unknown tokens")

    eligible_tokens = _int(
        eligible.get("eligible_tokens"),
        field="eligible.eligible_tokens",
    )
    eligible_v1 = _int(
        eligible.get("eligible_v1"),
        field="eligible.eligible_v1",
    )
    eligible_v2 = _int(
        eligible.get("eligible_v2"),
        field="eligible.eligible_v2",
    )
    if eligible_tokens <= 0 or eligible_v1 + eligible_v2 != eligible_tokens:
        raise ValueError("eligible universe generation accounting is invalid")

    eligible_provenance = _manifest_provenance(
        eligible_manifest,
        label="eligible universe",
    )
    if str(eligible_provenance.get("eligibility_threshold_usd")) != "100000":
        raise ValueError("eligible universe threshold changed")
    if eligible.get("universe_sha256") != eligible_manifest.get("sha256"):
        raise ValueError("eligible universe summary SHA disagrees with manifest")

    v1_eligibility_run_id = _int(
        eligible_provenance.get("v1_eligibility_run_id"),
        field="eligible.v1_eligibility_run_id",
    )
    v2_eligibility_run_id = _int(
        eligible_provenance.get("v2_eligibility_run_id"),
        field="eligible.v2_eligibility_run_id",
    )
    if v1_eligibility_run_id <= 0 or v2_eligibility_run_id <= 0:
        raise ValueError("eligible universe lifecycle run provenance is invalid")

    if _int(
        representative.get("snapshot_head_block"),
        field="representative.snapshot_head_block",
    ) != SNAPSHOT_HEAD_BLOCK:
        raise ValueError("representative validation snapshot head changed")
    if _int(representative.get("tokens"), field="representative.tokens") != 10:
        raise ValueError("representative validation must contain 10 tokens")
    if _int(
        representative.get("complete_tokens"),
        field="representative.complete_tokens",
    ) != 10:
        raise ValueError("representative validation is incomplete")

    if dict(representative.get("sample_groups") or {}) != {
        "failure": 5,
        "runner": 5,
    }:
        raise ValueError("representative validation sample groups changed")
    versions = {
        str(key): _int(value, field=f"representative.pons_versions.{key}")
        for key, value in dict(
            representative.get("pons_versions") or {}
        ).items()
    }
    if set(versions) != {"v1", "v2"} or sum(versions.values()) != 10:
        raise ValueError(
            "representative validation must cover both Pons generations"
        )
    if min(versions.values()) <= 0:
        raise ValueError(
            "representative validation has empty Pons generation coverage"
        )

    price_points = _int(
        representative.get("price_points"),
        field="representative.price_points",
    )
    priced_points = _int(
        representative.get("priced_points"),
        field="representative.priced_points",
    )
    unpriced_points = _int(
        representative.get("unpriced_points"),
        field="representative.unpriced_points",
    )
    if (
        price_points <= 0
        or priced_points <= 0
        or unpriced_points < 0
        or price_points != priced_points + unpriced_points
    ):
        raise ValueError(
            "representative lifecycle price-point accounting is invalid"
        )

    detailed_price_points = _int(
        representative.get("detailed_price_points"),
        field="representative.detailed_price_points",
    )
    detailed_priced_points = _int(
        representative.get("detailed_priced_points"),
        field="representative.detailed_priced_points",
    )
    detailed_unpriced_points = _int(
        representative.get("detailed_unpriced_points"),
        field="representative.detailed_unpriced_points",
    )
    if (
        detailed_price_points != price_points
        or detailed_priced_points != priced_points
        or detailed_unpriced_points != unpriced_points
    ):
        raise ValueError(
            "representative detailed and lifecycle price paths disagree"
        )
    detailed_complete_tokens = _int(
        representative.get("detailed_price_path_complete_tokens"),
        field="representative.detailed_price_path_complete_tokens",
    )
    if not 0 <= detailed_complete_tokens <= 10:
        raise ValueError(
            "representative detailed price-path completeness is invalid"
        )

    _positive(
        representative.get("market_path_rows"),
        field="representative.market_path_rows",
    )
    _positive(
        representative.get("transfers"),
        field="representative.transfers",
    )

    dex_targeted = _int(
        representative.get("dex_targeted"),
        field="representative.dex_targeted",
    )
    dex_matched = _int(
        representative.get("dex_matched"),
        field="representative.dex_matched",
    )
    no_pool = _int(
        representative.get("no_registered_v4_pool"),
        field="representative.no_registered_v4_pool",
    )
    if dex_targeted + no_pool != 10 or dex_matched != dex_targeted:
        raise ValueError("representative DEX pool evidence is incomplete")

    price_targeted = _int(
        representative.get("dex_price_targeted"),
        field="representative.dex_price_targeted",
    )
    price_matched = _int(
        representative.get("dex_price_matched"),
        field="representative.dex_price_matched",
    )
    no_swap = _int(
        representative.get("dex_price_no_swap_checkpoint"),
        field="representative.dex_price_no_swap_checkpoint",
    )
    if price_matched != price_targeted:
        raise ValueError("representative DEX price evidence has mismatches")
    if price_matched + no_swap + no_pool != 10:
        raise ValueError(
            "representative DEX price evidence does not account for all tokens"
        )

    checkpoint_targeted = _int(
        representative.get("dex_price_checkpoints_targeted"),
        field="representative.dex_price_checkpoints_targeted",
    )
    checkpoint_matched = _int(
        representative.get("dex_price_checkpoints_matched"),
        field="representative.dex_price_checkpoints_matched",
    )
    multi_checkpoint_tokens = _int(
        representative.get("dex_price_multi_checkpoint_tokens"),
        field="representative.dex_price_multi_checkpoint_tokens",
    )
    if price_targeted > 0:
        if checkpoint_targeted < price_targeted:
            raise ValueError(
                "representative DEX checkpoint coverage is below targeted "
                "token coverage"
            )
        if checkpoint_targeted > 3 * price_targeted:
            raise ValueError(
                "representative DEX checkpoint coverage exceeds first/max/last "
                "contract"
            )
    elif checkpoint_targeted != 0:
        raise ValueError(
            "representative DEX checkpoints exist without targeted tokens"
        )
    if checkpoint_matched != checkpoint_targeted:
        raise ValueError(
            "representative DEX checkpoint evidence has mismatches"
        )
    if not 0 <= multi_checkpoint_tokens <= price_targeted:
        raise ValueError(
            "representative multi-checkpoint token count is invalid"
        )

    explorer_verified_tokens = _int(
        representative.get("explorer_verified_tokens", 0),
        field="representative.explorer_verified_tokens",
    )
    explorer_launches = _int(
        representative.get("explorer_verified_launch_transactions", 0),
        field="representative.explorer_verified_launch_transactions",
    )
    explorer_dex_transactions = _int(
        representative.get("explorer_verified_dex_swap_transactions", 0),
        field="representative.explorer_verified_dex_swap_transactions",
    )
    explorer_transactions = _int(
        representative.get("explorer_verified_transactions", 0),
        field="representative.explorer_verified_transactions",
    )
    explorer_supplied = any(
        value > 0
        for value in (
            explorer_verified_tokens,
            explorer_launches,
            explorer_dex_transactions,
            explorer_transactions,
        )
    )
    if explorer_supplied:
        if explorer_verified_tokens != 10 or explorer_launches != 10:
            raise ValueError(
                "supplementary explorer evidence does not verify all 10 "
                "representative launches"
            )
        if explorer_dex_transactions != checkpoint_targeted:
            raise ValueError(
                "supplementary explorer/DEX checkpoint coverage mismatch"
            )
        if (
            explorer_transactions
            != explorer_launches + explorer_dex_transactions
        ):
            raise ValueError(
                "supplementary explorer transaction accounting is invalid"
            )

    coverage_sources = _int(
        representative.get("coverage_sources"),
        field="representative.coverage_sources",
    )
    continuous_sources = _int(
        representative.get("continuous_sharded_sources"),
        field="representative.continuous_sharded_sources",
    )
    snapshot_sources = _int(
        representative.get("snapshot_pinned_sources"),
        field="representative.snapshot_pinned_sources",
    )
    if coverage_sources != 11 or continuous_sources != 7 or snapshot_sources != 4:
        raise ValueError(
            "representative source coverage contract is incomplete"
        )
    if representative.get("no_unexplained_block_gaps") is not True:
        raise ValueError(
            "representative validation has unexplained source block gaps"
        )
    coverage_start = _int(
        representative.get("coverage_sample_start_block"),
        field="representative.coverage_sample_start_block",
    )
    if coverage_start <= 0:
        raise ValueError("representative coverage sample start is invalid")
    coverage_sha = str(
        representative.get("source_coverage_sha256") or ""
    )
    if len(coverage_sha) != 64:
        raise ValueError("representative source coverage SHA is invalid")

    representative_provenance = _manifest_provenance(
        representative_manifest,
        label="representative validation",
    )
    if representative.get("validation_sha256") != representative_manifest.get(
        "sha256"
    ):
        raise ValueError(
            "representative validation summary SHA disagrees with manifest"
        )
    if representative_provenance.get("source_coverage_sha256") != coverage_sha:
        raise ValueError(
            "representative source coverage SHA disagrees with validation "
            "provenance"
        )
    if _int(
        representative_provenance.get("v1_eligibility_run_id"),
        field="representative.v1_eligibility_run_id",
    ) != v1_eligibility_run_id:
        raise ValueError(
            "representative and universe V1 lifecycle evidence disagree"
        )
    if _int(
        representative_provenance.get("v2_eligibility_run_id"),
        field="representative.v2_eligibility_run_id",
    ) != v2_eligibility_run_id:
        raise ValueError(
            "representative and universe V2 lifecycle evidence disagree"
        )

    route_names = [str(value) for value in viability.get("route_names") or []]
    required_routes = list(REQUIRED_PHASE1_ACQUISITION_ROUTES)
    if len(route_names) != len(set(route_names)):
        raise ValueError("viability projection contains duplicate routes")
    if set(route_names) != set(required_routes):
        missing = sorted(set(required_routes) - set(route_names))
        extra = sorted(set(route_names) - set(required_routes))
        raise ValueError(
            "viability projection route coverage mismatch: "
            f"missing={missing} extra={extra}"
        )
    if _int(viability.get("routes"), field="viability.routes") != len(
        required_routes
    ):
        raise ValueError("viability projection route count changed")
    observed_route_blocks = dict(
        viability.get("required_route_blocks") or {}
    )
    expected_route_blocks = dict(REQUIRED_PHASE1_ROUTE_BLOCKS)
    if observed_route_blocks != expected_route_blocks:
        raise ValueError(
            "viability projection required route-block contract changed"
        )
    if _int(
        viability.get("required_work_blocks"),
        field="viability.required_work_blocks",
    ) != sum(expected_route_blocks.values()):
        raise ValueError(
            "viability projection required work-block total changed"
        )
    if viability.get("all_routes_instrumented") is not True:
        raise ValueError("viability projection contains uninstrumented routes")
    if viability.get("all_observed_rpc_routes_free") is not True:
        raise ValueError("viability projection contains non-free RPC routes")
    if viability.get("zero_cost_route_evidence") is not True:
        raise ValueError("viability projection has no zero-cost route proof")
    if _int(
        viability.get("free_daily_method_calls"),
        field="viability.free_daily_method_calls",
    ) != FREE_DAILY_METHOD_CALLS:
        raise ValueError("viability projection free quota assumption changed")

    projected_requests = _positive(
        viability.get("projected_requests"),
        field="viability.projected_requests",
    )
    projected_response_bytes = _positive(
        viability.get("projected_response_bytes"),
        field="viability.projected_response_bytes",
    )
    projected_artifact_bytes = _positive(
        viability.get("projected_artifact_bytes"),
        field="viability.projected_artifact_bytes",
    )
    projected_elapsed_seconds = _positive(
        viability.get("projected_elapsed_seconds"),
        field="viability.projected_elapsed_seconds",
    )
    projected_job_runtime_seconds = _positive(
        viability.get("projected_job_runtime_seconds"),
        field="viability.projected_job_runtime_seconds",
    )
    projected_free_quota_days = _int(
        viability.get("projected_free_quota_days"),
        field="viability.projected_free_quota_days",
    )
    if projected_free_quota_days <= 0:
        raise ValueError("viability projection free quota days are invalid")

    route_projections = list(viability.get("route_projections") or [])
    if len(route_projections) != len(required_routes):
        raise ValueError("viability projection route detail coverage changed")
    detail_names = [str(row.get("route")) for row in route_projections]
    if len(detail_names) != len(set(detail_names)):
        raise ValueError("viability projection repeats route details")
    if set(detail_names) != set(required_routes):
        raise ValueError(
            "viability projection route details do not match required routes"
        )
    used_evidence_run_ids: set[int] = set()
    route_evidence_run_ids: dict[str, list[int]] = {}
    for row in route_projections:
        name = str(row.get("route"))
        if name not in REQUIRED_PHASE1_ACQUISITION_ROUTES:
            raise ValueError(f"unexpected viability route detail: {name}")
        if row.get("all_observed_rpc_routes_free") is not True:
            raise ValueError(f"viability route is not proven free: {name}")
        detail_required_blocks = _int(
            row.get("required_blocks"),
            field=f"{name}.required_blocks",
        )
        if detail_required_blocks != expected_route_blocks[name]:
            raise ValueError(
                f"viability route required-block detail changed: {name}"
            )
        _positive(
            row.get("evidence_processed_blocks"),
            field=f"{name}.evidence_processed_blocks",
        )
        evidence_run_ids = [
            _int(value, field=f"{name}.evidence_run_ids")
            for value in list(row.get("evidence_run_ids") or [])
        ]
        if not evidence_run_ids or min(evidence_run_ids) <= 0:
            raise ValueError(f"viability route has no valid run evidence: {name}")
        if len(evidence_run_ids) != len(set(evidence_run_ids)):
            raise ValueError(
                f"viability route repeats an evidence run id: {name}"
            )
        evidence_runs = _int(
            row.get("evidence_runs"),
            field=f"{name}.evidence_runs",
        )
        if evidence_runs != len(evidence_run_ids):
            raise ValueError(
                f"viability route evidence-run count disagrees: {name}"
            )
        overlap = used_evidence_run_ids & set(evidence_run_ids)
        if overlap:
            raise ValueError(
                "viability evidence run reused across routes: "
                f"{sorted(overlap)}"
            )
        used_evidence_run_ids.update(evidence_run_ids)
        route_evidence_run_ids[name] = evidence_run_ids

    accounting_run_id = _int(
        viability.get("accounting_run_id"),
        field="viability.accounting_run_id",
    )
    if accounting_run_id <= 0:
        raise ValueError("viability projection accounting run id is invalid")

    return {
        "phase1_acceptance_status": "pass",
        "phase1_checkpoint": "hlp-v1-phase1-data-viability",
        "chain_id": 4663,
        "snapshot_head_block": SNAPSHOT_HEAD_BLOCK,
        "all_pons_launches": EXPECTED_PONS_LAUNCHES,
        "eligible_tokens": eligible_tokens,
        "eligible_v1": eligible_v1,
        "eligible_v2": eligible_v2,
        "v1_eligibility_run_id": v1_eligibility_run_id,
        "v2_eligibility_run_id": v2_eligibility_run_id,
        "representative_tokens": 10,
        "representative_price_points": price_points,
        "representative_detailed_price_points": detailed_price_points,
        "representative_detailed_price_path_complete_tokens": (
            detailed_complete_tokens
        ),
        "representative_dex_targeted": dex_targeted,
        "representative_dex_matched": dex_matched,
        "representative_dex_price_tokens_targeted": price_targeted,
        "representative_dex_price_checkpoints_targeted": checkpoint_targeted,
        "representative_dex_price_checkpoints_matched": checkpoint_matched,
        "representative_dex_multi_checkpoint_tokens": (
            multi_checkpoint_tokens
        ),
        "representative_explorer_evidence_status": (
            "verified" if explorer_supplied else "not_required"
        ),
        "representative_explorer_verified_tokens": explorer_verified_tokens,
        "representative_explorer_verified_transactions": (
            explorer_transactions
        ),
        "representative_explorer_verified_launch_transactions": (
            explorer_launches
        ),
        "representative_explorer_verified_dex_swap_transactions": (
            explorer_dex_transactions
        ),
        "representative_coverage_sources": coverage_sources,
        "representative_no_unexplained_block_gaps": True,
        "representative_source_coverage_sha256": coverage_sha,
        "required_acquisition_routes": required_routes,
        "required_route_blocks": expected_route_blocks,
        "route_evidence_run_ids": route_evidence_run_ids,
        "required_work_blocks": sum(expected_route_blocks.values()),
        "projected_requests": int(projected_requests),
        "projected_response_bytes": int(projected_response_bytes),
        "projected_artifact_bytes": int(projected_artifact_bytes),
        "projected_elapsed_seconds": projected_elapsed_seconds,
        "projected_job_runtime_seconds": projected_job_runtime_seconds,
        "projected_free_quota_days": projected_free_quota_days,
        "free_daily_method_calls": FREE_DAILY_METHOD_CALLS,
        "eligible_universe_sha256": eligible_manifest.get("sha256"),
        "representative_validation_sha256": representative_manifest.get(
            "sha256"
        ),
        "accounting_run_id": accounting_run_id,
        "acceptance_note": (
            "PASS means the frozen eligible universe, 10-token end-to-end "
            "validation and complete required acquisition projection agree at "
            "the same Phase 1 snapshot, with measured instrumented evidence "
            "using only approved free/public RPC routes."
        ),
    }
