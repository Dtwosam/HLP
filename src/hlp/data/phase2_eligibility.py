"""Canonical eligibility handoff for complete launchpad sources."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.phase2_universe import (
    normalize_phase2_source_eligibility_rows,
)


PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION = (
    "phase2-launchpad-eligibility-handoff-v1"
)


def build_launchpad_eligibility_handoff(
    source_id: str,
    raw_summary_rows: Iterable[Mapping[str, object]],
    coverage_report: Mapping[str, object],
    *,
    source_inventory: Iterable[Mapping[str, object]],
    provenance_sha256: str,
) -> tuple[list[dict], dict]:
    """Normalize one complete launchpad's full token summary for the universe."""
    source_id = str(source_id)
    inventory = {
        str(row["source_id"]): dict(row)
        for row in source_inventory
    }
    spec = inventory.get(source_id)
    if spec is None:
        raise ValueError(
            f"unknown Phase-2 eligibility source: {source_id!r}"
        )
    if spec.get("source_kind") != "launchpad":
        raise ValueError(
            f"Phase-2 launchpad eligibility rejects direct source: {source_id}"
        )

    if str(coverage_report.get("source_id") or "") != source_id:
        raise ValueError("launchpad eligibility coverage source drift")
    if str(coverage_report.get("coverage_status") or "") != "complete":
        raise ValueError("launchpad eligibility requires complete coverage")
    expected_readiness = str(spec.get("readiness") or "")
    if str(coverage_report.get("source_readiness") or "") != (
        expected_readiness
    ):
        raise ValueError(
            "launchpad eligibility coverage readiness drift"
        )
    snapshot = int(coverage_report.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError(
            "launchpad eligibility coverage snapshot is invalid"
        )
    if int(coverage_report.get("last_block", -1)) != snapshot:
        raise ValueError(
            "launchpad eligibility coverage does not reach snapshot"
        )
    if coverage_report.get("continuous") is not True:
        raise ValueError(
            "launchpad eligibility coverage is not continuous"
        )
    missing = coverage_report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError(
            "launchpad eligibility coverage has missing ranges"
        )

    normalized = normalize_phase2_source_eligibility_rows(
        source_id,
        raw_summary_rows,
        provenance_sha256=provenance_sha256,
        canonical_price_series=True,
    )
    token_count = len(normalized)
    price_points = sum(
        int(row["price_points"]) for row in normalized
    )
    priced_points = sum(
        int(row["priced_points"]) for row in normalized
    )

    if token_count != int(
        coverage_report.get("tokens_discovered", -1)
    ):
        raise ValueError(
            "launchpad eligibility token count disagrees with coverage"
        )
    if price_points != int(
        coverage_report.get("price_points", -1)
    ):
        raise ValueError(
            "launchpad eligibility price-point count disagrees with coverage"
        )
    if priced_points != int(
        coverage_report.get("priced_points", -1)
    ):
        raise ValueError(
            "launchpad eligibility priced-point count disagrees with coverage"
        )
    if priced_points != price_points:
        raise ValueError(
            "launchpad eligibility contains unpriced points"
        )

    eligible = sum(
        bool(row["crossed_100k"])
        for row in normalized
    )
    summary = {
        "version": PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION,
        "source_id": source_id,
        "source_readiness": expected_readiness,
        "snapshot_head_block": snapshot,
        "tokens": token_count,
        "price_points": price_points,
        "priced_points": priced_points,
        "eligible_tokens": eligible,
        "below_threshold_tokens": token_count - eligible,
        "canonical_price_series": True,
        "source_coverage_complete": True,
        "phase2_universe_source_ready": True,
        "phase2_universe_frozen": False,
    }
    return normalized, summary
