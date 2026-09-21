"""Fail-closed launch-origin attribution for direct DEX market registries."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.direct_markets import attribute_direct_market_origins
from hlp.data.phase2_coverage import validate_phase2_coverage_ledger


DIRECT_ORIGIN_ATTRIBUTION_VERSION = "phase2-direct-origin-attribution-v1"
DIRECT_LAUNCH_POPULATION_VERSION = "phase2-direct-launch-population-v1"


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


def build_conclusive_direct_launch_population(
    attributed_rows: Iterable[Mapping[str, object]],
    attribution_report: Mapping[str, object],
) -> tuple[list[dict], dict]:
    """Freeze launchpad-excluded direct markets after conclusive attribution.

    This does not select a canonical market per token. Every surviving market
    remains available for later empirical multi-pool selector research.
    """
    version = str(attribution_report.get("version") or "")
    if version != DIRECT_ORIGIN_ATTRIBUTION_VERSION:
        raise ValueError(
            f"direct origin attribution version changed: {version!r}"
        )
    if attribution_report.get("launch_source_coverage_complete") is not True:
        raise ValueError(
            "direct launch population requires complete launch-source coverage"
        )
    if attribution_report.get(
        "absence_from_launch_registries_is_conclusive"
    ) is not True:
        raise ValueError(
            "direct launch population requires conclusive launch-registry absence"
        )
    if attribution_report.get(
        "unattributed_markets_remain_direct_launch_unknown"
    ) not in {False, None}:
        raise ValueError(
            "direct launch population still marks unmatched markets unknown"
        )

    missing = attribution_report.get(
        "missing_launch_registry_source_ids", []
    )
    incomplete = attribution_report.get(
        "incomplete_launch_coverage_source_ids", []
    )
    if not isinstance(missing, list) or missing:
        raise ValueError(
            "direct launch population has missing launch registries"
        )
    if not isinstance(incomplete, list) or incomplete:
        raise ValueError(
            "direct launch population has incomplete launch coverage"
        )

    launch_ids = sorted(
        str(value)
        for value in attribution_report.get("launch_source_ids", [])
    )
    provided_ids = sorted(
        str(value)
        for value in attribution_report.get(
            "provided_launch_source_ids", []
        )
    )
    complete_ids = sorted(
        str(value)
        for value in attribution_report.get(
            "complete_launch_source_ids", []
        )
    )
    if (
        not launch_ids
        or provided_ids != launch_ids
        or complete_ids != launch_ids
    ):
        raise ValueError(
            "direct launch population launch-source set is not fully "
            "supplied and complete"
        )

    direct_source_ids = sorted(
        str(value)
        for value in attribution_report.get("direct_source_ids", [])
    )
    if not direct_source_ids:
        raise ValueError(
            "direct launch population attribution has no direct sources"
        )
    direct_source_set = set(direct_source_ids)

    rows = [dict(row) for row in attributed_rows]
    if len(rows) != int(attribution_report.get("markets", -1)):
        raise ValueError(
            "direct launch population market count disagrees with attribution"
        )
    input_tokens = {
        normalize_address(str(row["token"]))
        for row in rows
    }
    if len(input_tokens) != int(attribution_report.get("tokens", -1)):
        raise ValueError(
            "direct launch population token count disagrees with attribution"
        )

    output: list[dict] = []
    seen_markets: set[tuple[str, str]] = set()
    known_count = 0
    unattributed_count = 0
    multi_source_count = 0
    for raw in rows:
        row = dict(raw)
        source_id = str(row.get("source_id") or "")
        if source_id not in direct_source_set:
            raise ValueError(
                f"direct launch population has unexpected source: {source_id!r}"
            )
        token = normalize_address(str(row["token"]))
        raw_source_ids = row.get("launch_source_ids")
        if not isinstance(raw_source_ids, list):
            raise ValueError(
                f"direct launch market has invalid launch_source_ids: {token}"
            )
        matched_source_ids = sorted(str(value) for value in raw_source_ids)
        if any(not value for value in matched_source_ids):
            raise ValueError(
                f"direct launch market has empty launch source id: {token}"
            )
        if len(matched_source_ids) != len(set(matched_source_ids)):
            raise ValueError(
                f"direct launch market repeats launch source id: {token}"
            )
        source_count = int(row.get("launch_source_count", -1))
        if source_count != len(matched_source_ids):
            raise ValueError(
                f"direct launch market launch-source count drift: {token}"
            )
        if source_count > 1:
            multi_source_count += 1

        market_id = str(
            row.get("pool_id") or row.get("pool") or ""
        ).lower()
        if not market_id:
            raise ValueError(
                f"direct launch market has no market identity: {token}"
            )
        market_key = (source_id, market_id)
        if market_key in seen_markets:
            raise ValueError(
                "direct launch population repeats market: "
                f"{source_id} {market_id}"
            )
        seen_markets.add(market_key)

        classification = str(
            row.get("origin_classification") or ""
        )
        if classification == "known_launch_source":
            if (
                source_count <= 0
                or row.get("origin_attribution_complete") is not True
            ):
                raise ValueError(
                    "known launch-source market attribution is inconsistent: "
                    f"{token}"
                )
            known_count += 1
            continue
        if classification != "unattributed":
            raise ValueError(
                "direct launch market has invalid origin classification: "
                f"{classification!r}"
            )
        if source_count != 0 or matched_source_ids:
            raise ValueError(
                f"unattributed direct market has launch-source matches: {token}"
            )
        if row.get("origin_attribution_complete") is not False:
            raise ValueError(
                f"unattributed direct market attribution state changed: {token}"
            )

        initialize_block = int(row.get("initialize_block", -1))
        if initialize_block < 0:
            raise ValueError(
                f"direct launch market has invalid initialize block: {token}"
            )
        unattributed_count += 1
        output.append({
            **row,
            "token": token,
            "direct_launch_classification": "conclusive_direct_launch",
            "direct_launch_attribution_complete": True,
            "selector_freeze_ready": False,
            "source_coverage_complete": False,
        })

    if known_count != int(
        attribution_report.get("known_launch_source_markets", -1)
    ):
        raise ValueError(
            "direct launch population known-launch count drift"
        )
    if unattributed_count != int(
        attribution_report.get("unattributed_markets", -1)
    ):
        raise ValueError(
            "direct launch population unattributed count drift"
        )
    if multi_source_count != int(
        attribution_report.get("multi_launch_source_markets", -1)
    ):
        raise ValueError(
            "direct launch population multi-source count drift"
        )
    if known_count + unattributed_count != len(rows):
        raise ValueError(
            "direct launch population attribution classes do not reconcile"
        )

    output.sort(
        key=lambda row: (
            int(row["initialize_block"]),
            str(row["source_id"]),
            str(row.get("pool_id") or row.get("pool")).lower(),
        )
    )
    summary = {
        "version": DIRECT_LAUNCH_POPULATION_VERSION,
        "snapshot_head_block": int(
            attribution_report["snapshot_head_block"]
        ),
        "input_markets": len(rows),
        "input_tokens": len(input_tokens),
        "excluded_known_launch_source_markets": known_count,
        "direct_launch_candidate_markets": len(output),
        "direct_launch_candidate_tokens": len({
            row["token"] for row in output
        }),
        "direct_source_ids": direct_source_ids,
        "launch_source_ids": launch_ids,
        "launch_source_coverage_complete": True,
        "absence_from_launch_registries_is_conclusive": True,
        "direct_launch_population_conclusive": True,
        "selector_freeze_ready": False,
        "source_coverage_complete": False,
    }
    return output, summary
