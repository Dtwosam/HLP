"""Validate source eligibility handoffs before final Phase-2 universe freeze."""

from __future__ import annotations

from typing import Mapping, Iterable

from hlp.data.phase2_coverage import validate_phase2_coverage_ledger


PHASE2_UNIVERSE_SOURCE_BUNDLE_VERSION = (
    "phase2-universe-source-bundle-v1"
)


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def validate_phase2_universe_source_bundle(
    source_summaries: Mapping[str, Mapping[str, object]],
    *,
    coverage_ledger: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
) -> dict:
    """Require every universe-source handoff to match promoted coverage."""
    inventory = [dict(row) for row in source_inventory]
    coverage = validate_phase2_coverage_ledger(
        coverage_ledger,
        inventory,
    )
    if coverage["phase2_universe_coverage_complete"] is not True:
        raise ValueError(
            "Phase-2 universe source bundle requires 14/14 complete coverage"
        )

    inventory_by_id = {
        str(row["source_id"]): row
        for row in inventory
    }
    expected_ids = set(inventory_by_id)
    supplied_ids = {str(value) for value in source_summaries}
    if supplied_ids != expected_ids:
        raise ValueError(
            "Phase-2 universe source bundle set mismatch: "
            f"missing={sorted(expected_ids - supplied_ids)} "
            f"extra={sorted(supplied_ids - expected_ids)}"
        )

    ledger_by_id = {
        str(row["source_id"]): dict(row)
        for row in coverage_ledger["sources"]
    }
    snapshot = int(coverage["snapshot_head_block"])
    source_token_counts = {}
    source_point_counts = {}
    source_eligible_counts = {}

    for source_id in sorted(expected_ids):
        summary = dict(source_summaries[source_id])
        ledger_row = ledger_by_id[source_id]
        spec = inventory_by_id[source_id]

        if str(summary.get("source_id") or "") != source_id:
            raise ValueError(
                f"Phase-2 universe source summary identity drift: {source_id}"
            )
        if str(summary.get("source_readiness") or "") != str(
            spec.get("readiness") or ""
        ):
            raise ValueError(
                f"Phase-2 universe source readiness drift: {source_id}"
            )
        if int(summary.get("snapshot_head_block", -1)) != snapshot:
            raise ValueError(
                f"Phase-2 universe source snapshot drift: {source_id}"
            )
        if summary.get("canonical_price_series") is not True:
            raise ValueError(
                f"Phase-2 universe source is not canonical: {source_id}"
            )
        if summary.get("source_coverage_complete") is not True:
            raise ValueError(
                f"Phase-2 universe source coverage is incomplete: {source_id}"
            )
        if summary.get("phase2_universe_source_ready") is not True:
            raise ValueError(
                f"Phase-2 universe source is not ready: {source_id}"
            )
        if summary.get("phase2_universe_frozen") is not False:
            raise ValueError(
                f"Phase-2 universe source prematurely freezes universe: "
                f"{source_id}"
            )

        summary_provenance = _sha256(
            summary.get("coverage_provenance_sha256"),
            label=f"{source_id} eligibility coverage provenance",
        )
        ledger_provenance = _sha256(
            ledger_row.get("provenance_sha256"),
            label=f"{source_id} ledger coverage provenance",
        )
        if summary_provenance != ledger_provenance:
            raise ValueError(
                f"Phase-2 universe coverage provenance drift: {source_id}"
            )

        tokens = int(summary.get("tokens", -1))
        if tokens != int(ledger_row.get("tokens_discovered", -1)):
            raise ValueError(
                f"Phase-2 universe source token count drift: {source_id}"
            )

        if spec.get("source_kind") == "direct_dex":
            points = int(summary.get("coverage_price_points", -1))
            priced = int(summary.get("coverage_priced_points", -1))
        else:
            points = int(summary.get("price_points", -1))
            priced = int(summary.get("priced_points", -1))
        if (
            points != int(ledger_row.get("price_points", -1))
            or priced != int(ledger_row.get("priced_points", -1))
            or priced != points
        ):
            raise ValueError(
                f"Phase-2 universe source point count drift: {source_id}"
            )

        eligible = int(summary.get("eligible_tokens", -1))
        if eligible < 0 or eligible > tokens:
            raise ValueError(
                f"Phase-2 universe eligible count is invalid: {source_id}"
            )
        source_token_counts[source_id] = tokens
        source_point_counts[source_id] = points
        source_eligible_counts[source_id] = eligible

    return {
        "version": PHASE2_UNIVERSE_SOURCE_BUNDLE_VERSION,
        "snapshot_head_block": snapshot,
        "sources": len(expected_ids),
        "source_token_counts": dict(sorted(source_token_counts.items())),
        "source_coverage_point_counts": dict(
            sorted(source_point_counts.items())
        ),
        "source_eligible_counts": dict(
            sorted(source_eligible_counts.items())
        ),
        "coverage_provenance_matches_ledger": True,
        "all_sources_canonical": True,
        "all_sources_coverage_complete": True,
        "phase2_universe_source_bundle_ready": True,
        "phase2_universe_frozen": False,
    }
