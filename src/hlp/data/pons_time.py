"""Exact block-time enrichment for Pons research artifacts."""

from __future__ import annotations

from typing import Iterable

from hlp.data.rpc import RpcClient


def fetch_block_timestamp_rows(
    rpc: RpcClient,
    block_numbers: Iterable[int],
    *,
    batch_size: int = 100,
    min_batch_size: int = 1,
) -> list[dict]:
    blocks = sorted({int(block) for block in block_numbers})
    if not blocks:
        return []
    raw = rpc.get_blocks_batched(
        blocks,
        full_transactions=False,
        batch_size=batch_size,
        min_batch_size=min_batch_size,
    )
    if len(raw) != len(blocks):
        raise RuntimeError("batched block response length mismatch")

    output = []
    for expected, row in zip(blocks, raw):
        observed = int(row["number"], 16)
        if observed != expected:
            raise ValueError(
                f"block timestamp response mismatch: {observed} != {expected}"
            )
        output.append(
            {
                "block_number": observed,
                "block_hash": row["hash"],
                "block_timestamp": int(row["timestamp"], 16),
            }
        )
    return output


def enrich_pons_points_with_time(
    points: Iterable[dict],
    timestamp_rows: Iterable[dict],
) -> list[dict]:
    timestamps = {
        int(row["block_number"]): int(row["block_timestamp"])
        for row in timestamp_rows
    }
    grouped: dict[str, list[dict]] = {}
    for source in points:
        row = dict(source)
        block = int(row["block_number"])
        if block not in timestamps:
            raise KeyError(f"missing timestamp for Pons block {block}")
        row["block_timestamp"] = timestamps[block]
        grouped.setdefault(row["token"].lower(), []).append(row)

    output = []
    for token, rows in grouped.items():
        rows.sort(
            key=lambda row: (
                row["block_number"],
                -1
                if row.get("transaction_index") is None
                else row["transaction_index"],
                row["log_index"],
            )
        )
        first = rows[0]["block_timestamp"]
        for row in rows:
            row["seconds_since_first_priced_point"] = (
                row["block_timestamp"] - first
            )
            if row["seconds_since_first_priced_point"] < 0:
                raise ValueError(f"non-monotonic block timestamps for {token}")
            output.append(row)

    output.sort(
        key=lambda row: (
            row["block_number"],
            -1
            if row.get("transaction_index") is None
            else row["transaction_index"],
            row["log_index"],
            row["token"],
        )
    )
    return output


def enrich_pons_episodes_with_time(
    episodes: Iterable[dict],
    timestamp_rows: Iterable[dict],
) -> list[dict]:
    timestamps = {
        int(row["block_number"]): int(row["block_timestamp"])
        for row in timestamp_rows
    }
    output = []
    for source in episodes:
        row = dict(source)
        peak_block = int(row["peak_block"])
        start_block = int(row["drawdown_start_block"])
        trough_block = int(row["trough_block"])
        for block in {peak_block, start_block, trough_block}:
            if block not in timestamps:
                raise KeyError(f"missing timestamp for Pons episode block {block}")

        peak_ts = timestamps[peak_block]
        start_ts = timestamps[start_block]
        trough_ts = timestamps[trough_block]
        row["peak_timestamp"] = peak_ts
        row["drawdown_start_timestamp"] = start_ts
        row["trough_timestamp"] = trough_ts
        row["peak_to_trough_seconds"] = trough_ts - peak_ts
        row["drawdown_start_to_trough_seconds"] = trough_ts - start_ts

        recovery_block = row.get("recovery_block")
        if recovery_block is None:
            row["recovery_timestamp"] = None
            row["trough_to_recovery_seconds"] = None
            row["peak_to_recovery_seconds"] = None
        else:
            recovery_block = int(recovery_block)
            if recovery_block not in timestamps:
                raise KeyError(
                    f"missing timestamp for Pons recovery block {recovery_block}"
                )
            recovery_ts = timestamps[recovery_block]
            row["recovery_timestamp"] = recovery_ts
            row["trough_to_recovery_seconds"] = recovery_ts - trough_ts
            row["peak_to_recovery_seconds"] = recovery_ts - peak_ts

        if row["peak_to_trough_seconds"] < 0:
            raise ValueError("Pons episode trough precedes peak in time")
        output.append(row)

    output.sort(
        key=lambda row: (
            row["peak_timestamp"],
            row["token"],
            row["episode_index"],
        )
    )
    return output
