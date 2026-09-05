"""Fail-closed block/snapshot coverage summaries for frozen Phase 1 sources."""

from __future__ import annotations

from typing import Mapping


ROBINHOOD_CHAIN_ID = 4663
PHASE1_SNAPSHOT_HEAD = 54_486_035


def summarize_sharded_manifest_coverage(
    manifest: Mapping[str, object],
    *,
    label: str,
    required_start: int | None = None,
    exact_start: bool = False,
    snapshot_head: int = PHASE1_SNAPSHOT_HEAD,
) -> dict:
    """Prove one merged artifact's shard list has exact continuous coverage."""
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"{label} manifest has no provenance")
    if int(provenance.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError(f"{label} manifest chain changed")
    if int(provenance.get("snapshot_head_block", -1)) != snapshot_head:
        raise ValueError(f"{label} manifest snapshot head changed")

    raw_shards = provenance.get("shards")
    if not isinstance(raw_shards, list) or not raw_shards:
        raise ValueError(f"{label} manifest has no shard coverage")

    shards = []
    for index, source in enumerate(raw_shards):
        if not isinstance(source, Mapping):
            raise ValueError(f"{label} shard {index} is not an object")
        lo = int(source["from_block"])
        hi = int(source["to_block"])
        if lo <= 0 or hi < lo:
            raise ValueError(
                f"{label} shard {index} has invalid range {lo}..{hi}"
            )
        shards.append((lo, hi))

    shards.sort()
    if len(shards) != len(set(shards)):
        raise ValueError(f"{label} shard coverage contains duplicates")
    previous_hi = None
    for lo, hi in shards:
        if previous_hi is not None and lo != previous_hi + 1:
            raise ValueError(
                f"{label} shard coverage gap/overlap: {previous_hi} -> {lo}"
            )
        previous_hi = hi

    first_block = shards[0][0]
    last_block = shards[-1][1]
    if last_block != snapshot_head:
        raise ValueError(
            f"{label} coverage does not close at snapshot head: {last_block}"
        )
    if required_start is not None:
        required = int(required_start)
        if exact_start and first_block != required:
            raise ValueError(
                f"{label} coverage start changed: {first_block} != {required}"
            )
        if not exact_start and first_block > required:
            raise ValueError(
                f"{label} coverage begins after required block: "
                f"{first_block} > {required}"
            )

    return {
        "label": label,
        "source": provenance.get("source"),
        "first_block": first_block,
        "last_block": last_block,
        "shards": len(shards),
        "covered_blocks": last_block - first_block + 1,
        "continuous": True,
        "snapshot_head_block": snapshot_head,
    }


def summarize_snapshot_manifest_coverage(
    manifest: Mapping[str, object],
    *,
    label: str,
    snapshot_head: int = PHASE1_SNAPSHOT_HEAD,
) -> dict:
    """Prove a non-sharded derived state/tape is pinned to the Phase 1 head."""
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"{label} manifest has no provenance")
    if int(provenance.get("chain_id", -1)) != ROBINHOOD_CHAIN_ID:
        raise ValueError(f"{label} manifest chain changed")
    if int(provenance.get("snapshot_head_block", -1)) != snapshot_head:
        raise ValueError(f"{label} manifest snapshot head changed")
    return {
        "label": label,
        "source": provenance.get("source"),
        "snapshot_head_block": snapshot_head,
        "snapshot_pinned": True,
    }


def validate_representative_coverage_report(
    report: Mapping[str, object],
    *,
    sample_start_block: int,
    snapshot_head: int = PHASE1_SNAPSHOT_HEAD,
) -> dict:
    """Validate the compact coverage report consumed by final acceptance."""
    sources = report.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("representative coverage report has no sources")

    rows = [dict(row) for row in sources]
    labels = [str(row.get("label")) for row in rows]
    if len(labels) != len(set(labels)):
        raise ValueError("representative coverage report repeats source labels")

    required = {
        "v1_v3",
        "v2_curve",
        "v2_graduation",
        "v2_registration",
        "v2_v4",
        "weth_usdg_anchor",
        "stock_oracle_initial",
        "stock_oracle_updates",
        "quote_fallback_initial",
        "quote_fallback_updates",
        "representative_transfers",
    }
    if set(labels) != required:
        missing = sorted(required - set(labels))
        extra = sorted(set(labels) - required)
        raise ValueError(
            "representative coverage source contract mismatch: "
            f"missing={missing} extra={extra}"
        )

    sharded = {
        "v1_v3",
        "v2_curve",
        "v2_graduation",
        "v2_registration",
        "v2_v4",
        "weth_usdg_anchor",
        "representative_transfers",
    }
    by_label = {str(row["label"]): row for row in rows}
    for label in sharded:
        row = by_label[label]
        if row.get("continuous") is not True:
            raise ValueError(f"representative source is not continuous: {label}")
        if int(row.get("last_block", -1)) != snapshot_head:
            raise ValueError(
                f"representative source does not reach snapshot head: {label}"
            )
        if int(row.get("first_block", snapshot_head + 1)) > sample_start_block:
            raise ValueError(
                f"representative source starts after sample window: {label}"
            )
        if int(row.get("shards", 0)) <= 0:
            raise ValueError(
                f"representative source has no shard evidence: {label}"
            )

    for label in required - sharded:
        row = by_label[label]
        if row.get("snapshot_pinned") is not True:
            raise ValueError(
                f"representative pricing source is not snapshot-pinned: {label}"
            )
        if int(row.get("snapshot_head_block", -1)) != snapshot_head:
            raise ValueError(
                f"representative pricing source snapshot changed: {label}"
            )

    transfers = by_label["representative_transfers"]
    if int(transfers["first_block"]) != int(sample_start_block):
        raise ValueError(
            "representative transfer coverage does not start at earliest sample"
        )

    return {
        "sources": len(rows),
        "continuous_sharded_sources": len(sharded),
        "snapshot_pinned_sources": len(required - sharded),
        "sample_start_block": int(sample_start_block),
        "snapshot_head_block": snapshot_head,
        "no_unexplained_block_gaps": True,
    }
