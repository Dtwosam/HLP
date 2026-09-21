"""Source-agnostic Phase-2 universe assembly.

Venue-specific adapters own price/supply reconstruction. This module normalizes
their per-token threshold summaries, merges the same token across sources, and
applies deterministic address exclusions without erasing threshold evidence.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.exclusions import exclusion_map
from hlp.data.phase2_sources import build_phase2_source_inventory


THRESHOLD_STATUSES = frozenset({"eligible", "unknown", "ineligible"})
PHASE2_UNIVERSE_STATUSES = frozenset(
    {"eligible", "unknown", "ineligible", "excluded"}
)
MARKET_CAP_THRESHOLD_USD = Decimal("100000")


def _source_specs(
    source_inventory: Iterable[Mapping[str, object]] | None,
) -> dict[str, dict]:
    rows = (
        build_phase2_source_inventory()
        if source_inventory is None
        else [dict(row) for row in source_inventory]
    )
    specs: dict[str, dict] = {}
    for raw in rows:
        source_id = str(raw.get("source_id") or "")
        if not source_id:
            raise ValueError("Phase-2 source inventory has an empty source id")
        if source_id in specs:
            raise ValueError(
                f"Phase-2 source inventory repeats source id: {source_id}"
            )
        specs[source_id] = dict(raw)
    return specs


def _count(raw: Mapping[str, object], field: str) -> int:
    try:
        value = int(raw.get(field, 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{field} cannot be negative")
    return value


def normalize_phase2_source_summary(
    source_id: str,
    rows: Iterable[Mapping[str, object]],
    *,
    source_inventory: Iterable[Mapping[str, object]] | None = None,
) -> list[dict]:
    """Normalize one venue/source summary into a common threshold contract.

    Existing Phase-1 summaries may already carry eligibility_status. Generic
    venue summaries expose crossed_100k plus priced/total point counts. Both
    shapes are reduced to the same fail-closed semantics:

    - any observed >=$100k point proves eligible;
    - no crossing plus any unpriced point remains unknown;
    - only complete priced non-crossing history is ineligible.
    """
    specs = _source_specs(source_inventory)
    source_id = str(source_id)
    spec = specs.get(source_id)
    if spec is None:
        raise ValueError(f"unknown Phase-2 source id: {source_id}")

    output: list[dict] = []
    seen_tokens: set[str] = set()
    for raw in rows:
        if "token" not in raw:
            raise ValueError(f"{source_id} summary row has no token")
        token = normalize_address(str(raw["token"]))
        if token in seen_tokens:
            raise ValueError(
                f"duplicate Phase-2 source/token summary: {source_id} {token}"
            )
        seen_tokens.add(token)

        observed_venue = raw.get("venue")
        expected_venue = str(spec.get("venue") or "")
        if observed_venue is not None and str(observed_venue) != expected_venue:
            raise ValueError(
                f"{source_id} venue mismatch: "
                f"{observed_venue!r} != {expected_venue!r}"
            )

        price_points = _count(raw, "price_points")
        priced_points = _count(raw, "priced_points")
        if priced_points > price_points:
            raise ValueError(
                f"{source_id} priced_points exceed price_points for {token}"
            )
        unpriced_points = price_points - priced_points
        if "unpriced_points" in raw:
            explicit_unpriced = _count(raw, "unpriced_points")
            if explicit_unpriced != unpriced_points:
                raise ValueError(
                    f"{source_id} unpriced point count mismatch for {token}"
                )

        crossed_raw = raw.get("crossed_100k", False)
        if not isinstance(crossed_raw, bool):
            raise ValueError(
                f"{source_id} crossed_100k must be boolean for {token}"
            )
        crossed = crossed_raw

        max_value = raw.get("max_market_cap_proxy_usd")
        if max_value is None:
            maximum = None
        else:
            try:
                maximum = Decimal(str(max_value))
            except Exception as exc:
                raise ValueError(
                    f"{source_id} invalid max market cap for {token}"
                ) from exc
            if maximum < 0:
                raise ValueError(
                    f"{source_id} negative max market cap for {token}"
                )
        max_block = raw.get("max_market_cap_block")
        if maximum is not None:
            if max_block is None:
                raise ValueError(
                    f"{source_id} max market cap has no block for {token}"
                )
            max_block = int(max_block)
            if max_block < 0:
                raise ValueError(
                    f"{source_id} max market-cap block is negative for {token}"
                )
        elif priced_points > 0:
            raise ValueError(
                f"{source_id} priced history has no max market cap for {token}"
            )

        if crossed and (
            maximum is None or maximum < MARKET_CAP_THRESHOLD_USD
        ):
            raise ValueError(
                f"{source_id} crossed_100k contradicts max market cap for {token}"
            )
        if (
            not crossed
            and maximum is not None
            and maximum >= MARKET_CAP_THRESHOLD_USD
        ):
            raise ValueError(
                f"{source_id} max market cap contradicts crossed_100k for {token}"
            )

        derived_status = (
            "eligible"
            if crossed
            else "unknown"
            if unpriced_points > 0
            else "ineligible"
        )
        explicit_status = raw.get("eligibility_status")
        if explicit_status is not None:
            explicit_status = str(explicit_status)
            if explicit_status not in THRESHOLD_STATUSES:
                raise ValueError(
                    f"{source_id} invalid eligibility_status for {token}: "
                    f"{explicit_status!r}"
                )
            if explicit_status != derived_status:
                raise ValueError(
                    f"{source_id} eligibility_status contradicts price evidence "
                    f"for {token}: {explicit_status} != {derived_status}"
                )

        output.append(
            {
                "source_id": source_id,
                "venue": expected_venue,
                "source_kind": spec.get("source_kind"),
                "source_readiness": spec.get("readiness"),
                "token": token,
                "eligibility_status": derived_status,
                "crossed_100k": crossed,
                "price_points": price_points,
                "priced_points": priced_points,
                "unpriced_points": unpriced_points,
                "pricing_complete": unpriced_points == 0,
                "max_market_cap_proxy_usd": (
                    None if maximum is None else str(maximum)
                ),
                "max_market_cap_block": max_block,
            }
        )

    output.sort(key=lambda row: row["token"])
    return output


def merge_phase2_universe(
    source_summaries: Mapping[str, Iterable[Mapping[str, object]]],
    exclusion_registry_rows: Iterable[Mapping[str, object]],
    *,
    source_inventory: Iterable[Mapping[str, object]] | None = None,
) -> list[dict]:
    """Merge per-source threshold evidence into one deterministic population."""
    inventory_rows = (
        build_phase2_source_inventory()
        if source_inventory is None
        else [dict(row) for row in source_inventory]
    )
    specs = _source_specs(inventory_rows)
    exclusions = exclusion_map(exclusion_registry_rows)

    grouped: dict[str, list[dict]] = {}
    for source_id in source_summaries:
        if source_id not in specs:
            raise ValueError(f"unknown Phase-2 source id: {source_id}")
        normalized = normalize_phase2_source_summary(
            source_id,
            source_summaries[source_id],
            source_inventory=inventory_rows,
        )
        for row in normalized:
            grouped.setdefault(row["token"], []).append(row)

    output: list[dict] = []
    for token in sorted(grouped):
        evidence = sorted(
            grouped[token],
            key=lambda row: row["source_id"],
        )
        source_ids = [row["source_id"] for row in evidence]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError(
                f"Phase-2 token repeats source evidence: {token}"
            )

        statuses = {row["eligibility_status"] for row in evidence}
        threshold_status = (
            "eligible"
            if "eligible" in statuses
            else "unknown"
            if "unknown" in statuses
            else "ineligible"
        )

        maxima = [
            (
                Decimal(row["max_market_cap_proxy_usd"]),
                row["source_id"],
                row["max_market_cap_block"],
            )
            for row in evidence
            if row["max_market_cap_proxy_usd"] is not None
        ]
        if maxima:
            maximum, maximum_source, maximum_block = max(
                maxima,
                key=lambda item: (item[0], item[1], item[2]),
            )
        else:
            maximum = None
            maximum_source = None
            maximum_block = None

        exclusion = exclusions.get(token)
        universe_status = (
            "excluded" if exclusion is not None else threshold_status
        )
        row = {
            "token": token,
            "source_ids": source_ids,
            "source_count": len(source_ids),
            "source_evidence": evidence,
            "threshold_eligibility_status": threshold_status,
            "eligibility_status": threshold_status,
            "crossed_100k": threshold_status == "eligible",
            "max_market_cap_proxy_usd": (
                None if maximum is None else str(maximum)
            ),
            "max_market_cap_source_id": maximum_source,
            "max_market_cap_block": maximum_block,
            "excluded": exclusion is not None,
            "phase2_universe_status": universe_status,
            "included": universe_status == "eligible",
            "exclusion_category": (
                None if exclusion is None else exclusion["category"]
            ),
            "exclusion_source": (
                None if exclusion is None else exclusion["source"]
            ),
            "exclusion_reason": (
                None if exclusion is None else exclusion["reason"]
            ),
        }
        output.append(row)

    return output


def summarize_phase2_universe(rows: Iterable[Mapping[str, object]]) -> dict:
    """Return compact population counts without changing membership."""
    counts = {status: 0 for status in sorted(PHASE2_UNIVERSE_STATUSES)}
    threshold_counts = {status: 0 for status in sorted(THRESHOLD_STATUSES)}
    source_ids: set[str] = set()
    tokens = 0

    for raw in rows:
        tokens += 1
        status = str(raw.get("phase2_universe_status") or "")
        if status not in counts:
            raise ValueError(f"invalid Phase-2 universe status: {status!r}")
        counts[status] += 1

        threshold_status = str(
            raw.get("threshold_eligibility_status") or ""
        )
        if threshold_status not in threshold_counts:
            raise ValueError(
                f"invalid threshold eligibility status: {threshold_status!r}"
            )
        threshold_counts[threshold_status] += 1

        evidence = raw.get("source_evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(
                f"Phase-2 universe row has no source evidence: {raw.get('token')}"
            )
        source_ids.update(
            str(item["source_id"])
            for item in evidence
            if isinstance(item, Mapping) and item.get("source_id")
        )

    return {
        "tokens": tokens,
        "included_tokens": counts["eligible"],
        "excluded_tokens": counts["excluded"],
        "unknown_tokens": counts["unknown"],
        "ineligible_tokens": counts["ineligible"],
        "threshold_status_counts": threshold_counts,
        "phase2_status_counts": counts,
        "covered_source_ids": sorted(source_ids),
        "covered_sources": len(source_ids),
    }
