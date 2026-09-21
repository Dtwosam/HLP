"""Deterministic lower-bound planning for Phase-2 source backfills."""

from __future__ import annotations

from math import ceil
from typing import Iterable, Mapping


def estimate_source_discovery_windows(
    boundary_rows: Iterable[Mapping[str, object]],
    *,
    snapshot_head_block: int,
    filtered_log_block_cap: int,
) -> dict:
    """Estimate minimum filtered-log windows for source enumeration.

    This deliberately counts only one address/topic query per block window for
    each source population. It excludes retries, downstream pool/event tapes,
    quote/USD reconstruction, state calls, and any address-filter splitting,
    so the result is a lower bound rather than a full coverage forecast.
    """
    head = int(snapshot_head_block)
    cap = int(filtered_log_block_cap)
    if head < 0:
        raise ValueError("snapshot head block must be non-negative")
    if cap <= 0:
        raise ValueError("filtered log block cap must be positive")

    output = []
    seen = set()
    for raw in boundary_rows:
        row = dict(raw)
        source_id = str(row.get("source_id") or "")
        if not source_id:
            raise ValueError("backfill boundary row has no source_id")
        if source_id in seen:
            raise ValueError(
                f"backfill boundary repeats source: {source_id}"
            )
        seen.add(source_id)

        start = int(row.get("required_start_block", -1))
        if start < 0 or start > head:
            raise ValueError(
                f"invalid backfill start for {source_id}: {start}"
            )
        blocks = head - start + 1
        windows = ceil(blocks / cap)
        output.append({
            "source_id": source_id,
            "source_kind": str(row.get("source_kind") or ""),
            "source_readiness": str(
                row.get("source_readiness") or ""
            ),
            "required_start_block": start,
            "snapshot_head_block": head,
            "required_blocks": blocks,
            "filtered_log_block_cap": cap,
            "minimum_discovery_windows": windows,
        })

    output.sort(
        key=lambda row: (
            row["minimum_discovery_windows"],
            row["source_id"],
        )
    )
    total_blocks = sum(row["required_blocks"] for row in output)
    total_windows = sum(
        row["minimum_discovery_windows"] for row in output
    )
    return {
        "snapshot_head_block": head,
        "filtered_log_block_cap": cap,
        "sources": len(output),
        "total_required_blocks": total_blocks,
        "minimum_discovery_windows": total_windows,
        "rows": output,
        "lower_bound_only": True,
        "excludes": [
            "retries",
            "downstream_pool_event_tapes",
            "quote_usd_reconstruction",
            "state_calls",
            "address_filter_splitting",
        ],
    }
