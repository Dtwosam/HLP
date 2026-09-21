"""Fail-closed historical coverage contract for Phase-2 sources.

Adapter readiness describes code capability. Coverage readiness describes what
has actually been reconstructed through the frozen snapshot. The two must never
be conflated.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping


COVERAGE_STATUSES = frozenset(
    {"not_started", "partial", "complete", "blocked"}
)


def _nonnegative_int(value: object, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative")
    return result


def _sha256(value: object, *, source_id: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(
            f"{source_id} complete coverage has invalid provenance_sha256"
        )
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(
            f"{source_id} complete coverage has invalid provenance_sha256"
        ) from exc
    return text


def validate_phase2_source_coverage(
    source_inventory: Iterable[Mapping[str, object]],
    coverage_rows: Iterable[Mapping[str, object]],
    *,
    snapshot_head_block: int,
) -> dict:
    """Validate per-source historical coverage and return the completion gate."""
    snapshot = _nonnegative_int(
        snapshot_head_block,
        field="snapshot_head_block",
    )
    inventory: dict[str, dict] = {}
    for raw in source_inventory:
        source_id = str(raw.get("source_id") or "")
        if not source_id:
            raise ValueError("source inventory contains empty source id")
        if source_id in inventory:
            raise ValueError(f"duplicate source inventory id: {source_id}")
        inventory[source_id] = dict(raw)

    coverage: dict[str, dict] = {}
    for raw in coverage_rows:
        source_id = str(raw.get("source_id") or "")
        if source_id not in inventory:
            raise ValueError(
                f"coverage row references unknown source: {source_id!r}"
            )
        if source_id in coverage:
            raise ValueError(f"duplicate source coverage row: {source_id}")

        status = str(raw.get("coverage_status") or "")
        if status not in COVERAGE_STATUSES:
            raise ValueError(
                f"{source_id} has invalid coverage_status: {status!r}"
            )

        required_start = _nonnegative_int(
            raw.get("required_start_block"),
            field=f"{source_id}.required_start_block",
        )
        tokens = _nonnegative_int(
            raw.get("tokens_discovered", 0),
            field=f"{source_id}.tokens_discovered",
        )
        price_points = _nonnegative_int(
            raw.get("price_points", 0),
            field=f"{source_id}.price_points",
        )
        priced_points = _nonnegative_int(
            raw.get("priced_points", 0),
            field=f"{source_id}.priced_points",
        )
        if priced_points > price_points:
            raise ValueError(
                f"{source_id} priced_points exceed price_points"
            )

        volume_raw = raw.get("observed_volume_usd")
        if volume_raw is None:
            volume = None
        else:
            try:
                volume = Decimal(str(volume_raw))
            except Exception as exc:
                raise ValueError(
                    f"{source_id} observed_volume_usd is invalid"
                ) from exc
            if volume < 0:
                raise ValueError(
                    f"{source_id} observed_volume_usd is negative"
                )

        first_raw = raw.get("first_block")
        last_raw = raw.get("last_block")
        first = (
            None
            if first_raw is None
            else _nonnegative_int(
                first_raw,
                field=f"{source_id}.first_block",
            )
        )
        last = (
            None
            if last_raw is None
            else _nonnegative_int(
                last_raw,
                field=f"{source_id}.last_block",
            )
        )
        if (first is None) != (last is None):
            raise ValueError(
                f"{source_id} coverage range must provide both endpoints"
            )
        if first is not None and last < first:
            raise ValueError(f"{source_id} coverage range is reversed")

        continuous = raw.get("continuous")
        if continuous not in {True, False, None}:
            raise ValueError(
                f"{source_id} continuous must be boolean or null"
            )

        missing_ranges = raw.get("missing_ranges", [])
        if not isinstance(missing_ranges, list):
            raise ValueError(
                f"{source_id} missing_ranges must be a list"
            )

        provenance = raw.get("provenance_sha256")
        if status == "complete":
            if first is None or last is None:
                raise ValueError(
                    f"{source_id} complete coverage has no range"
                )
            if first > required_start:
                raise ValueError(
                    f"{source_id} complete coverage starts after required block"
                )
            if last != snapshot:
                raise ValueError(
                    f"{source_id} complete coverage does not reach snapshot"
                )
            if continuous is not True:
                raise ValueError(
                    f"{source_id} complete coverage is not continuous"
                )
            if missing_ranges:
                raise ValueError(
                    f"{source_id} complete coverage has missing ranges"
                )
            provenance = _sha256(provenance, source_id=source_id)
        elif status == "not_started":
            if first is not None or last is not None:
                raise ValueError(
                    f"{source_id} not_started coverage cannot have a range"
                )
            if price_points or priced_points or tokens:
                raise ValueError(
                    f"{source_id} not_started coverage has observed data"
                )

        reason = raw.get("blocking_reason")
        if status == "blocked" and not str(reason or "").strip():
            raise ValueError(
                f"{source_id} blocked coverage needs blocking_reason"
            )

        coverage[source_id] = {
            "source_id": source_id,
            "coverage_status": status,
            "required_start_block": required_start,
            "first_block": first,
            "last_block": last,
            "continuous": continuous,
            "missing_ranges": list(missing_ranges),
            "tokens_discovered": tokens,
            "price_points": price_points,
            "priced_points": priced_points,
            "observed_volume_usd": (
                None if volume is None else str(volume)
            ),
            "provenance_sha256": provenance,
            "blocking_reason": reason,
        }

    missing_sources = sorted(set(inventory) - set(coverage))
    status_counts = {status: 0 for status in sorted(COVERAGE_STATUSES)}
    for row in coverage.values():
        status_counts[row["coverage_status"]] += 1

    complete_sources = sorted(
        source_id
        for source_id, row in coverage.items()
        if row["coverage_status"] == "complete"
    )
    incomplete_sources = sorted(
        source_id
        for source_id in inventory
        if source_id not in complete_sources
    )

    return {
        "snapshot_head_block": snapshot,
        "inventory_sources": len(inventory),
        "reported_sources": len(coverage),
        "missing_source_rows": missing_sources,
        "coverage_status_counts": status_counts,
        "complete_source_ids": complete_sources,
        "incomplete_source_ids": incomplete_sources,
        "all_sources_reported": not missing_sources,
        "phase2_universe_coverage_complete": (
            not missing_sources
            and len(complete_sources) == len(inventory)
        ),
    }
