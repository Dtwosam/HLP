"""Fail-closed launch-origin attribution for direct DEX market registries."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.direct_markets import attribute_direct_market_origins
from hlp.data.phase2_coverage import validate_phase2_coverage_ledger


DIRECT_ORIGIN_ATTRIBUTION_VERSION = "phase2-direct-origin-attribution-v1"


def build_direct_origin_attribution(
    market_rows: Iterable[Mapping[str, object]],
    launch_registries: Mapping[str, Iterable[Mapping[str, object]]],
    *,
    source_inventory: Iterable[Mapping[str, object]],
    coverage_ledger: Mapping[str, object],
) -> tuple[list[dict], dict]:
    """Attribute exact token matches without turning missing matches into facts."""
    inventory = [dict(row) for row in source_inventory]
    coverage = validate_phase2_coverage_ledger(
        coverage_ledger,
        inventory,
    )
    inventory_by_id = {
        str(row["source_id"]): row
        for row in inventory
    }
    launch_source_ids = sorted(
        source_id
        for source_id, row in inventory_by_id.items()
        if row.get("source_kind") == "launchpad"
    )
    if not launch_source_ids:
        raise ValueError("Phase-2 source inventory has no launchpad sources")

    supplied: dict[str, list[dict]] = {}
    for source_id, rows in launch_registries.items():
        source_id = str(source_id)
        spec = inventory_by_id.get(source_id)
        if spec is None:
            raise ValueError(
                f"launch-origin registry references unknown source: {source_id}"
            )
        if spec.get("source_kind") != "launchpad":
            raise ValueError(
                f"launch-origin registry is not a launchpad source: {source_id}"
            )
        if source_id in supplied:
            raise ValueError(
                f"launch-origin registry repeats source: {source_id}"
            )
        supplied[source_id] = [dict(row) for row in rows]

    markets = [dict(row) for row in market_rows]
    direct_source_ids = {
        str(row.get("source_id") or "")
        for row in markets
    }
    if "" in direct_source_ids:
        raise ValueError("direct market row has no source_id")
    for source_id in direct_source_ids:
        spec = inventory_by_id.get(source_id)
        if spec is None:
            raise ValueError(
                f"direct market references unknown source: {source_id}"
            )
        if spec.get("source_kind") != "direct_dex":
            raise ValueError(
                f"market registry source is not direct DEX: {source_id}"
            )

    attributed = attribute_direct_market_origins(
        markets,
        supplied,
    )

    coverage_rows = {
        str(row["source_id"]): row
        for row in coverage_ledger["sources"]
    }
    complete_launch_sources = sorted(
        source_id
        for source_id in launch_source_ids
        if coverage_rows[source_id].get("coverage_status") == "complete"
    )
    provided_source_ids = sorted(supplied)
    missing_registry_sources = sorted(
        set(launch_source_ids) - set(provided_source_ids)
    )
    incomplete_coverage_sources = sorted(
        set(launch_source_ids) - set(complete_launch_sources)
    )
    fully_covered_and_supplied = (
        not missing_registry_sources
        and not incomplete_coverage_sources
    )

    known = sum(
        row["origin_classification"] == "known_launch_source"
        for row in attributed
    )
    unattributed = sum(
        row["origin_classification"] == "unattributed"
        for row in attributed
    )
    multi_source = sum(
        int(row["launch_source_count"]) > 1
        for row in attributed
    )
    matched_sources = sorted({
        source_id
        for row in attributed
        for source_id in row["launch_source_ids"]
    })

    report = {
        "version": DIRECT_ORIGIN_ATTRIBUTION_VERSION,
        "snapshot_head_block": int(coverage["snapshot_head_block"]),
        "direct_source_ids": sorted(direct_source_ids),
        "markets": len(attributed),
        "tokens": len({
            str(row["token"]).lower()
            for row in attributed
        }),
        "known_launch_source_markets": known,
        "unattributed_markets": unattributed,
        "multi_launch_source_markets": multi_source,
        "matched_launch_source_ids": matched_sources,
        "launch_source_ids": launch_source_ids,
        "provided_launch_source_ids": provided_source_ids,
        "complete_launch_source_ids": complete_launch_sources,
        "missing_launch_registry_source_ids": missing_registry_sources,
        "incomplete_launch_coverage_source_ids": incomplete_coverage_sources,
        "launch_source_coverage_complete": fully_covered_and_supplied,
        "absence_from_launch_registries_is_conclusive": (
            fully_covered_and_supplied
        ),
        "unattributed_markets_remain_direct_launch_unknown": (
            unattributed > 0 and not fully_covered_and_supplied
        ),
        "phase2_universe_coverage_complete": bool(
            coverage["phase2_universe_coverage_complete"]
        ),
    }
    return attributed, report
