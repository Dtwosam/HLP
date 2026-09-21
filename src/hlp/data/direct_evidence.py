"""Deterministic bounded evidence planning for direct multi-market research."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.reconstruct import event_order


EVIDENCE_SAMPLE_RULE = "chronological_even_spacing_v1"


def build_direct_market_evidence_plan(
    cohort_rows: Iterable[Mapping[str, object]],
    *,
    sample_size: int,
    window_blocks: int,
    snapshot_head_block: int,
) -> list[dict]:
    """Select a chronology-spanning multi-market cohort without ranking pools."""
    size = int(sample_size)
    width = int(window_blocks)
    head = int(snapshot_head_block)
    if size <= 0:
        raise ValueError("direct evidence sample_size must be positive")
    if width <= 0:
        raise ValueError("direct evidence window_blocks must be positive")
    if head < 0:
        raise ValueError("direct evidence snapshot head cannot be negative")

    rows = [dict(row) for row in cohort_rows]
    if not rows:
        return []

    seen_tokens: set[str] = set()
    normalized = []
    for raw in rows:
        token = normalize_address(str(raw["token"]))
        if token in seen_tokens:
            raise ValueError(f"direct evidence cohort repeats token: {token}")
        seen_tokens.add(token)
        markets = [dict(item) for item in raw.get("markets", [])]
        if len(markets) < 2:
            raise ValueError(
                f"direct evidence token lacks competing markets: {token}"
            )
        last_initialize = max(
            int(item["initialize_block"]) for item in markets
        )
        declared_last = int(raw["last_initialize_block"])
        if declared_last != last_initialize:
            raise ValueError(
                f"direct evidence last Initialize drift for {token}"
            )
        if last_initialize > head:
            raise ValueError(
                f"direct evidence token initializes after snapshot: {token}"
            )
        normalized.append({
            **raw,
            "token": token,
            "markets": markets,
            "last_initialize_block": last_initialize,
        })

    normalized.sort(
        key=lambda row: (
            int(row["last_initialize_block"]),
            row["token"],
        )
    )
    count = min(size, len(normalized))
    if count == len(normalized):
        indexes = list(range(len(normalized)))
    elif count == 1:
        indexes = [len(normalized) // 2]
    else:
        indexes = [
            (index * (len(normalized) - 1)) // (count - 1)
            for index in range(count)
        ]
    if len(indexes) != len(set(indexes)):
        raise ValueError("direct evidence sample indexes are not unique")

    output = []
    for rank, index in enumerate(indexes, start=1):
        row = normalized[index]
        start = int(row["last_initialize_block"])
        end = min(head, start + width - 1)
        output.append({
            **row,
            "evidence_sample_rank": rank,
            "evidence_sample_rule": EVIDENCE_SAMPLE_RULE,
            "evidence_window_from_block": start,
            "evidence_window_to_block": end,
            "evidence_window_blocks": end - start + 1,
            "snapshot_head_block": head,
            "selector_freeze_ready": False,
        })
    return output


def summarize_direct_market_evidence_plan(
    rows: Iterable[Mapping[str, object]],
) -> dict:
    data = [dict(row) for row in rows]
    return {
        "tokens": len(data),
        "markets": sum(int(row["market_count"]) for row in data),
        "first_window_block": min(
            (
                int(row["evidence_window_from_block"])
                for row in data
            ),
            default=None,
        ),
        "last_window_block": max(
            (
                int(row["evidence_window_to_block"])
                for row in data
            ),
            default=None,
        ),
        "sampling_rule": EVIDENCE_SAMPLE_RULE,
        "selector_freeze_ready": False,
    }


def _market_windows(
    plan_rows: Iterable[Mapping[str, object]],
    *,
    market_field: str,
) -> dict[str, tuple[str, int, int]]:
    if market_field not in {"pool", "pool_id"}:
        raise ValueError(f"unsupported direct market field: {market_field}")
    expected_kind = "v3_pool" if market_field == "pool" else "v4_pool_id"

    output: dict[str, tuple[str, int, int]] = {}
    for raw in plan_rows:
        token = normalize_address(str(raw["token"]))
        start = int(raw["evidence_window_from_block"])
        end = int(raw["evidence_window_to_block"])
        if end < start:
            raise ValueError(f"invalid direct evidence window for {token}")
        for market in raw.get("markets", []):
            if str(market.get("market_kind")) != expected_kind:
                continue
            market_id = str(market["market_id"]).lower()
            current = output.get(market_id)
            value = (token, start, end)
            if current is not None and current != value:
                raise ValueError(
                    f"direct evidence market maps to multiple windows: {market_id}"
                )
            output[market_id] = value
    return output


def filter_direct_market_events(
    rows: Iterable[Mapping[str, object]],
    plan_rows: Iterable[Mapping[str, object]],
    *,
    market_field: str,
) -> list[dict]:
    """Keep only market events inside each sampled token's overlap window."""
    windows = _market_windows(plan_rows, market_field=market_field)
    output = []
    seen: set[tuple[str, tuple[int, int, int]]] = set()
    for raw in rows:
        row = dict(raw)
        market_id = str(row.get(market_field) or "").lower()
        window = windows.get(market_id)
        if window is None:
            continue
        _, start, end = window
        block = int(row["block_number"])
        if block < start or block > end:
            continue
        key = (market_id, event_order(row))
        if key in seen:
            raise ValueError(
                f"duplicate direct evidence market event: {market_id} {key[1]}"
            )
        seen.add(key)
        output.append(row)
    output.sort(
        key=lambda row: (
            event_order(row),
            str(row[market_field]).lower(),
        )
    )
    return output


def filter_direct_supply_deltas(
    rows: Iterable[Mapping[str, object]],
    plan_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Keep causal supply deltas from first market seed through evidence end."""
    bounds: dict[str, tuple[int, int]] = {}
    for raw in plan_rows:
        token = normalize_address(str(raw["token"]))
        start = int(raw["first_initialize_block"])
        end = int(raw["evidence_window_to_block"])
        if end < start:
            raise ValueError(f"invalid direct supply evidence bounds: {token}")
        if token in bounds:
            raise ValueError(f"direct supply plan repeats token: {token}")
        bounds[token] = (start, end)

    output = []
    seen: set[tuple[str, tuple[int, int, int]]] = set()
    for raw in rows:
        row = dict(raw)
        token = normalize_address(str(row["token"]))
        bound = bounds.get(token)
        if bound is None:
            continue
        block = int(row["block_number"])
        if block < bound[0] or block > bound[1]:
            continue
        key = (token, event_order(row))
        if key in seen:
            raise ValueError(
                f"duplicate direct evidence supply delta: {token} {key[1]}"
            )
        seen.add(key)
        row["token"] = token
        output.append(row)
    output.sort(key=lambda row: (event_order(row), row["token"]))
    return output


def filter_direct_market_registry(
    rows: Iterable[Mapping[str, object]],
    plan_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Retain exactly the sampled market identities for a registry."""
    planned: set[tuple[str, str]] = set()
    sampled_tokens: set[str] = set()
    for raw in plan_rows:
        token = normalize_address(str(raw["token"]))
        sampled_tokens.add(token)
        for market in raw.get("markets", []):
            planned.add((
                str(market["source_id"]),
                str(market["market_id"]).lower(),
            ))

    output = []
    seen: set[tuple[str, str]] = set()
    for raw in rows:
        row = dict(raw)
        token = normalize_address(str(row["token"]))
        if token not in sampled_tokens:
            continue
        source_id = str(row["source_id"])
        market_id = str(row.get("pool_id") or row.get("pool") or "").lower()
        key = (source_id, market_id)
        if key not in planned:
            continue
        if key in seen:
            raise ValueError(
                f"direct evidence registry repeats market: {source_id} {market_id}"
            )
        seen.add(key)
        output.append(row)

    output.sort(
        key=lambda row: (
            int(row["initialize_block"]),
            str(row["source_id"]),
            str(row.get("pool_id") or row.get("pool")).lower(),
        )
    )
    return output
