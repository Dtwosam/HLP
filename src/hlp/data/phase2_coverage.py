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
PHASE2_COVERAGE_LEDGER_VERSION = "phase2-source-coverage-v1"


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

        required_start_raw = raw.get("required_start_block")
        required_start = (
            None
            if required_start_raw is None
            else _nonnegative_int(
                required_start_raw,
                field=f"{source_id}.required_start_block",
            )
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
            if required_start is None:
                raise ValueError(
                    f"{source_id} complete coverage has no required start"
                )
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
            if priced_points != price_points:
                raise ValueError(
                    f"{source_id} complete coverage has unpriced points"
                )
            provenance = _sha256(provenance, source_id=source_id)
        elif status == "partial":
            if required_start is None:
                raise ValueError(
                    f"{source_id} partial coverage has no required start"
                )
            if first is None or last is None:
                raise ValueError(
                    f"{source_id} partial coverage has no range"
                )
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



def validate_phase2_coverage_ledger(
    ledger: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
) -> dict:
    """Validate the versioned repository coverage ledger.

    The ledger must contain one row for every source, even if that source has
    not started. This makes omissions explicit rather than silently dropping a
    material venue from the Phase-2 completion gate.
    """
    version = str(ledger.get("version") or "")
    if version != PHASE2_COVERAGE_LEDGER_VERSION:
        raise ValueError(
            "Phase-2 coverage ledger version changed: "
            f"{version!r}"
        )
    snapshot = _nonnegative_int(
        ledger.get("snapshot_head_block"),
        field="snapshot_head_block",
    )
    raw_sources = ledger.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError("Phase-2 coverage ledger sources must be a list")

    inventory_rows = [dict(row) for row in source_inventory]
    inventory_ids = {
        str(row.get("source_id") or "")
        for row in inventory_rows
    }
    if "" in inventory_ids:
        raise ValueError("source inventory contains empty source id")

    ledger_ids = [
        str(row.get("source_id") or "")
        for row in raw_sources
        if isinstance(row, Mapping)
    ]
    if len(ledger_ids) != len(raw_sources):
        raise ValueError("Phase-2 coverage ledger contains a non-object row")
    if len(ledger_ids) != len(set(ledger_ids)):
        raise ValueError("Phase-2 coverage ledger repeats a source id")
    if set(ledger_ids) != inventory_ids:
        missing = sorted(inventory_ids - set(ledger_ids))
        extra = sorted(set(ledger_ids) - inventory_ids)
        raise ValueError(
            "Phase-2 coverage ledger source contract mismatch: "
            f"missing={missing} extra={extra}"
        )

    readiness_by_source = {
        str(row["source_id"]): str(row.get("readiness") or "")
        for row in inventory_rows
    }
    for raw in raw_sources:
        source_id = str(raw["source_id"])
        reported = str(raw.get("source_readiness") or "")
        expected = readiness_by_source[source_id]
        if reported != expected:
            raise ValueError(
                "Phase-2 coverage ledger readiness drift: "
                f"{source_id} {reported!r} != {expected!r}"
            )

    report = validate_phase2_source_coverage(
        inventory_rows,
        raw_sources,
        snapshot_head_block=snapshot,
    )
    report["version"] = version
    return report



_COVERAGE_LEDGER_ROW_FIELDS = (
    "source_id",
    "source_readiness",
    "coverage_status",
    "required_start_block",
    "first_block",
    "last_block",
    "continuous",
    "missing_ranges",
    "tokens_discovered",
    "price_points",
    "priced_points",
    "observed_volume_usd",
    "provenance_sha256",
    "blocking_reason",
)


def apply_phase2_source_coverage_report(
    ledger: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    report: Mapping[str, object],
) -> tuple[dict, dict]:
    """Apply one immutable source report to the canonical coverage ledger.

    The report may contain extra source-specific audit fields, but only the
    canonical ledger fields are promoted. Snapshot/readiness drift fails before
    the replacement is accepted, then the complete ledger is revalidated.
    """
    inventory_rows = [dict(row) for row in source_inventory]
    current = validate_phase2_coverage_ledger(ledger, inventory_rows)
    snapshot = int(current["snapshot_head_block"])

    source_id = str(report.get("source_id") or "")
    inventory_by_id = {
        str(row["source_id"]): row
        for row in inventory_rows
    }
    if source_id not in inventory_by_id:
        raise ValueError(
            f"coverage report references unknown source: {source_id!r}"
        )
    report_snapshot = int(report.get("snapshot_head_block", -1))
    if report_snapshot != snapshot:
        raise ValueError(
            "coverage report snapshot drift: "
            f"{report_snapshot} != {snapshot}"
        )

    expected_readiness = str(
        inventory_by_id[source_id].get("readiness") or ""
    )
    reported_readiness = str(
        report.get("source_readiness") or ""
    )
    if reported_readiness != expected_readiness:
        raise ValueError(
            "coverage report readiness drift: "
            f"{source_id} {reported_readiness!r} "
            f"!= {expected_readiness!r}"
        )

    replacement = {}
    for field in _COVERAGE_LEDGER_ROW_FIELDS:
        if field not in report:
            raise ValueError(
                f"coverage report missing canonical field: {field}"
            )
        replacement[field] = report[field]

    current_row = next(
        dict(row)
        for row in ledger["sources"]
        if str(row.get("source_id") or "") == source_id
    )
    if (
        replacement["required_start_block"]
        != current_row.get("required_start_block")
    ):
        raise ValueError(
            "coverage report required start drift: "
            f"{source_id} {replacement['required_start_block']!r} "
            f"!= {current_row.get('required_start_block')!r}"
        )

    if str(current_row.get("coverage_status") or "") == "complete":
        current_canonical = {
            field: current_row.get(field)
            for field in _COVERAGE_LEDGER_ROW_FIELDS
        }
        if replacement != current_canonical:
            raise ValueError(
                "coverage report cannot rewrite completed source: "
                f"{source_id}"
            )

    updated = {
        **dict(ledger),
        "sources": [
            replacement
            if str(row.get("source_id") or "") == source_id
            else dict(row)
            for row in ledger["sources"]
        ],
    }
    validation = validate_phase2_coverage_ledger(
        updated,
        inventory_rows,
    )
    return updated, validation



PHASE2_BOUNDARY_REPORT_VERSION = (
    "phase2-source-deployment-boundaries-v1"
)


def apply_phase2_source_boundaries(
    ledger: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    boundary_report: Mapping[str, object],
) -> tuple[dict, dict]:
    """Apply conservative source start boundaries without claiming coverage."""
    inventory_rows = [dict(row) for row in source_inventory]
    current = validate_phase2_coverage_ledger(
        ledger,
        inventory_rows,
    )
    snapshot = int(current["snapshot_head_block"])

    version = str(boundary_report.get("version") or "")
    if version != PHASE2_BOUNDARY_REPORT_VERSION:
        raise ValueError(
            "Phase-2 boundary report version changed: "
            f"{version!r}"
        )
    report_snapshot = int(
        boundary_report.get("snapshot_head_block", -1)
    )
    if report_snapshot != snapshot:
        raise ValueError(
            "Phase-2 boundary report snapshot drift: "
            f"{report_snapshot} != {snapshot}"
        )
    raw_sources = boundary_report.get("sources")
    if not isinstance(raw_sources, list):
        raise ValueError(
            "Phase-2 boundary report sources must be a list"
        )

    inventory_by_id = {
        str(row["source_id"]): row
        for row in inventory_rows
    }
    boundaries: dict[str, int] = {}
    for raw in raw_sources:
        if not isinstance(raw, Mapping):
            raise ValueError(
                "Phase-2 boundary report contains non-object row"
            )
        source_id = str(raw.get("source_id") or "")
        if source_id not in inventory_by_id:
            raise ValueError(
                f"boundary report references unknown source: {source_id!r}"
            )
        if source_id in boundaries:
            raise ValueError(
                f"boundary report repeats source: {source_id}"
            )
        # Deployment boundaries are immutable chain evidence. Adapter
        # readiness is intentionally not part of the boundary identity because
        # it may advance after the first-code proof was frozen.
        start = int(raw.get("required_start_block", -1))
        if start < 0 or start > snapshot:
            raise ValueError(
                f"invalid boundary for {source_id}: {start}"
            )
        boundaries[source_id] = start

    updated_rows = []
    for raw in ledger["sources"]:
        row = dict(raw)
        source_id = str(row["source_id"])
        if source_id not in boundaries:
            updated_rows.append(row)
            continue

        start = boundaries[source_id]
        current_start = row.get("required_start_block")
        status = str(row.get("coverage_status") or "")
        if current_start is not None:
            current_start = int(current_start)
            if current_start != start:
                raise ValueError(
                    "boundary report disagrees with existing start: "
                    f"{source_id} {start} != {current_start}"
                )
        elif status == "complete":
            raise ValueError(
                f"cannot backfill boundary onto complete source: {source_id}"
            )
        row["required_start_block"] = start
        updated_rows.append(row)

    updated = {
        **dict(ledger),
        "sources": updated_rows,
    }
    validation = validate_phase2_coverage_ledger(
        updated,
        inventory_rows,
    )
    return updated, validation
