"""Frozen storage layouts for Phase-2 research price-path rehydration."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID


PHASE2_RESEARCH_SOURCE_LAYOUT_VERSION = (
    "phase2-research-source-layout-v1"
)

STORAGE_MODES = frozenset({
    "canonical_replay",
    "single_jsonl",
    "sharded_artifacts",
    "shard_report_rebuild",
})


def build_phase2_research_source_layouts() -> dict[str, dict]:
    """Return the exact allowed price-path storage strategy per component."""

    rows = {
        "pons_v1": {
            "strategy": "canonical_replay",
            "segments": [
                {
                    "segment_id": "pons_v1_v3",
                    "storage_mode": "canonical_replay",
                    "replay_version": "phase2-pons-research-replay-v1",
                    "replay_entrypoint": "materialize_v1_research_points",
                },
            ],
        },
        "pons_v2": {
            "strategy": "canonical_replay",
            "segments": [
                {
                    "segment_id": "pons_v2_curve",
                    "storage_mode": "canonical_replay",
                    "replay_version": "phase2-pons-research-replay-v1",
                    "replay_entrypoint": "materialize_v2_curve_research_points",
                },
                {
                    "segment_id": "pons_v2_graduation_seed",
                    "storage_mode": "canonical_replay",
                    "replay_version": "phase2-pons-research-replay-v1",
                    "replay_entrypoint": (
                        "materialize_v2_post_graduation_research_points"
                    ),
                },
                {
                    "segment_id": "pons_v2_v4",
                    "storage_mode": "canonical_replay",
                    "replay_version": "phase2-pons-research-replay-v1",
                    "replay_entrypoint": (
                        "materialize_v2_post_graduation_research_points"
                    ),
                },
            ],
        },
        "pools_fun": {
            "strategy": "coverage_sharded",
            "segments": [
                {
                    "segment_id": "pools_fun_v3",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "coverage_run",
                    "aggregate_manifest_path": (
                        "pools-fun-points-sharded.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-pools-fun-price-*"
                    ],
                    "logical_sha_field": "market_points_sha256",
                },
            ],
        },
        "pools_trade_instant": {
            "strategy": "coverage_sharded",
            "segments": [
                {
                    "segment_id": "pools_trade_instant_v4",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "coverage_run",
                    "aggregate_manifest_path": (
                        "pools-trade-instant-points-sharded.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-pools-trade-instant-price-*"
                    ],
                    "logical_sha_field": "market_points_sha256",
                },
            ],
        },
        "pools_trade_lbp": {
            "strategy": "composite",
            "segments": [
                {
                    "segment_id": "pools_trade_lbp_cca",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "source_provenance_run",
                    "provenance_run_field": "cca_run_id",
                    "artifact_name": (
                        "phase2-pools-trade-lbp-cca-coverage"
                    ),
                    "aggregate_manifest_path": (
                        "lbp-cca-points-sharded.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-pools-trade-lbp-cca-*"
                    ],
                    "logical_sha_field": "cca_market_points_sha256",
                },
                {
                    "segment_id": "pools_trade_lbp_v4",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "coverage_run",
                    "aggregate_manifest_path": (
                        "lbp-v4-points-sharded.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-pools-trade-lbp-v4-price-*"
                    ],
                    "logical_sha_field": "v4_market_points_sha256",
                },
            ],
        },
        "doppler": {
            "strategy": "coverage_sharded",
            "segments": [
                {
                    "segment_id": "doppler_v4",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "coverage_run",
                    "aggregate_manifest_path": (
                        "doppler-points-sharded.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-doppler-price-*"
                    ],
                    "logical_sha_field": "market_points_sha256",
                },
            ],
        },
        "flap": {
            "strategy": "composite",
            "segments": [
                {
                    "segment_id": "flap_curve",
                    "storage_mode": "shard_report_rebuild",
                    "artifact_origin": "source_provenance_run",
                    "provenance_run_field": "curve_run_id",
                    "provenance_artifact_digest_field": (
                        "curve_artifact_digest"
                    ),
                    "artifact_name": "phase2-flap-curve-coverage",
                    "aggregate_manifest_path": (
                        "flap-curve-points.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-flap-curve-price-*"
                    ],
                    "logical_sha_field": "curve_points_sha256",
                },
                {
                    "segment_id": "flap_v3",
                    "storage_mode": "shard_report_rebuild",
                    "artifact_origin": "coverage_run",
                    "shard_artifact_patterns": [
                        "phase2-flap-v3-price-*"
                    ],
                    "logical_sha_field": "v3_points_sha256",
                },
            ],
        },
        "trench_today": {
            "strategy": "composite",
            "segments": [
                {
                    "segment_id": "trench_curve",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "source_provenance_run",
                    "provenance_run_field": "curve_run_id",
                    "provenance_artifact_digest_field": (
                        "curve_artifact_digest"
                    ),
                    "artifact_name": "phase2-trench-curve-coverage",
                    "aggregate_manifest_path": (
                        "trench-curve-points.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-trench-curve-price-*"
                    ],
                    "logical_sha_field": "curve_points_sha256",
                },
                {
                    "segment_id": "trench_post_limit",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "coverage_run",
                    "aggregate_manifest_path": (
                        "trench-post-limit-points.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-trench-v3-price-*",
                        "phase2-trench-v4-price-*",
                    ],
                    "logical_sha_field": "post_limit_points_sha256",
                },
            ],
        },
        "hood_fun_current": {
            "strategy": "coverage_single",
            "segments": [
                {
                    "segment_id": "hood_fun_current_curve",
                    "storage_mode": "single_jsonl",
                    "artifact_origin": "coverage_run",
                    "data_path": (
                        "hood-current-market-cap-points.jsonl"
                    ),
                    "manifest_path": (
                        "hood-current-market-cap-points.jsonl.manifest.json"
                    ),
                    "logical_sha_field": "provenance_sha256",
                },
            ],
        },
        "hood_fun_previous": {
            "strategy": "coverage_single",
            "segments": [
                {
                    "segment_id": "hood_fun_previous_curve",
                    "storage_mode": "single_jsonl",
                    "artifact_origin": "coverage_run",
                    "data_path": (
                        "hood-previous-market-cap-points.jsonl"
                    ),
                    "manifest_path": (
                        "hood-previous-market-cap-points.jsonl.manifest.json"
                    ),
                    "logical_sha_field": "provenance_sha256",
                },
            ],
        },
        "noxa": {
            "strategy": "coverage_sharded",
            "segments": [
                {
                    "segment_id": "noxa_v3",
                    "storage_mode": "sharded_artifacts",
                    "artifact_origin": "coverage_run",
                    "aggregate_manifest_path": (
                        "noxa-points-sharded.manifest.json"
                    ),
                    "shard_artifact_patterns": [
                        "phase2-noxa-price-*"
                    ],
                    "logical_sha_field": "market_points_sha256",
                },
            ],
        },
        DIRECT_RESEARCH_COMPONENT_ID: {
            "strategy": "handoff_single",
            "segments": [
                {
                    "segment_id": DIRECT_RESEARCH_COMPONENT_ID,
                    "storage_mode": "single_jsonl",
                    "artifact_origin": "handoff_run",
                    "data_path": "direct-canonical-market-cap-points.jsonl",
                    "manifest_path": (
                        "direct-canonical-market-cap-points.jsonl.manifest.json"
                    ),
                    "logical_sha_field": "canonical_points_sha256",
                },
            ],
        },
    }
    return {
        component_id: {
            "version": PHASE2_RESEARCH_SOURCE_LAYOUT_VERSION,
            "component_id": component_id,
            **spec,
        }
        for component_id, spec in sorted(rows.items())
    }


def validate_phase2_research_source_layouts(
    layouts: Mapping[str, Mapping[str, object]],
    source_inventory: Iterable[Mapping[str, object]],
) -> dict:
    """Require every frozen source to have one explicit research storage layout."""

    inventory = [dict(row) for row in source_inventory]
    launchpads = {
        str(row["source_id"])
        for row in inventory
        if row.get("source_kind") == "launchpad"
    }
    directs = {
        str(row["source_id"])
        for row in inventory
        if row.get("source_kind") == "direct_dex"
    }
    expected_components = launchpads | {DIRECT_RESEARCH_COMPONENT_ID}
    supplied = {str(value) for value in layouts}
    if supplied != expected_components:
        raise ValueError(
            "research source layout component set mismatch: "
            f"missing={sorted(expected_components - supplied)} "
            f"extra={sorted(supplied - expected_components)}"
        )

    segment_ids: set[str] = set()
    modes: dict[str, int] = {}
    for component_id in sorted(expected_components):
        row = dict(layouts[component_id])
        if (
            str(row.get("version") or "")
            != PHASE2_RESEARCH_SOURCE_LAYOUT_VERSION
        ):
            raise ValueError(
                f"research source layout version changed: {component_id}"
            )
        if str(row.get("component_id") or "") != component_id:
            raise ValueError(
                f"research source layout component drift: {component_id}"
            )
        segments = list(row.get("segments") or [])
        if not segments:
            raise ValueError(
                f"research source layout has no segments: {component_id}"
            )
        for raw_segment in segments:
            segment = dict(raw_segment)
            segment_id = str(segment.get("segment_id") or "")
            if not segment_id or segment_id in segment_ids:
                raise ValueError(
                    f"research source layout segment id is invalid: "
                    f"{segment_id!r}"
                )
            segment_ids.add(segment_id)
            mode = str(segment.get("storage_mode") or "")
            if mode not in STORAGE_MODES:
                raise ValueError(
                    f"research source layout storage mode changed: "
                    f"{component_id} {mode!r}"
                )
            modes[mode] = modes.get(mode, 0) + 1
            if mode == "single_jsonl":
                if not segment.get("data_path") or not segment.get(
                    "manifest_path"
                ):
                    raise ValueError(
                        f"single research tape layout is incomplete: "
                        f"{segment_id}"
                    )
            elif mode == "sharded_artifacts":
                if not segment.get("aggregate_manifest_path"):
                    raise ValueError(
                        f"sharded research tape lacks aggregate manifest: "
                        f"{segment_id}"
                    )
                if not list(segment.get("shard_artifact_patterns") or []):
                    raise ValueError(
                        f"sharded research tape lacks artifact patterns: "
                        f"{segment_id}"
                    )
            elif mode == "shard_report_rebuild":
                if not list(segment.get("shard_artifact_patterns") or []):
                    raise ValueError(
                        f"research shard-report rebuild lacks artifacts: "
                        f"{segment_id}"
                    )
            elif mode == "canonical_replay":
                if not segment.get("replay_entrypoint"):
                    raise ValueError(
                        f"research replay entrypoint is missing: {segment_id}"
                    )
            if not segment.get("logical_sha_field") and mode != (
                "canonical_replay"
            ):
                raise ValueError(
                    f"research segment logical SHA field is missing: "
                    f"{segment_id}"
                )

    if len(launchpads) != 11 or len(directs) != 3:
        raise ValueError("research source layout requires 11+3 source inventory")
    return {
        "version": PHASE2_RESEARCH_SOURCE_LAYOUT_VERSION,
        "components": len(expected_components),
        "launchpad_components": len(launchpads),
        "direct_sources_collapsed": len(directs),
        "segments": len(segment_ids),
        "storage_mode_counts": dict(sorted(modes.items())),
        "all_sources_have_explicit_layout": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }
