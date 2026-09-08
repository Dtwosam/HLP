"""Deterministic block-range gap planning for resumable archive backfills."""

from __future__ import annotations

from collections.abc import Iterable


BlockRange = tuple[int, int]


def coalesce_covered_ranges(
    expected_start: int,
    expected_end: int,
    covered: Iterable[BlockRange],
) -> list[BlockRange]:
    """Return the union of valid covered intervals, tolerating overlap."""
    start = int(expected_start)
    end = int(expected_end)
    if start <= 0 or end < start:
        raise ValueError(f"invalid expected range: {start}..{end}")

    rows = sorted((int(lo), int(hi)) for lo, hi in covered)
    merged: list[list[int]] = []
    for lo, hi in rows:
        if lo <= 0 or hi < lo:
            raise ValueError(f"invalid covered range: {lo}..{hi}")
        if lo < start or hi > end:
            raise ValueError(
                f"covered range outside expected bounds: {lo}..{hi} "
                f"not within {start}..{end}"
            )
        if not merged or lo > merged[-1][1] + 1:
            merged.append([lo, hi])
            continue
        merged[-1][1] = max(merged[-1][1], hi)
    return [(lo, hi) for lo, hi in merged]


def select_contiguous_cover(
    expected_start: int,
    expected_end: int,
    candidates: Iterable[BlockRange],
) -> list[int]:
    """Select whole candidate intervals forming one exact non-overlapping cover."""
    start = int(expected_start)
    end = int(expected_end)
    if start <= 0 or end < start:
        raise ValueError(f"invalid expected range: {start}..{end}")

    rows = [(int(lo), int(hi)) for lo, hi in candidates]
    by_start: dict[int, list[int]] = {}
    for index, (lo, hi) in enumerate(rows):
        if lo <= 0 or hi < lo:
            raise ValueError(f"invalid candidate range: {lo}..{hi}")
        if lo < start or hi > end:
            raise ValueError(
                f"candidate range outside expected bounds: {lo}..{hi} "
                f"not within {start}..{end}"
            )
        by_start.setdefault(lo, []).append(index)

    reachable = {end + 1}
    choice: dict[int, int] = {}
    for cursor in sorted(by_start, reverse=True):
        indexes = sorted(
            by_start[cursor],
            key=lambda index: (-rows[index][1], index),
        )
        for index in indexes:
            if rows[index][1] + 1 in reachable:
                choice[cursor] = index
                reachable.add(cursor)
                break

    if start not in reachable:
        raise ValueError(
            f"candidate ranges cannot form exact cover: {start}..{end}"
        )

    selected: list[int] = []
    cursor = start
    while cursor <= end:
        index = choice[cursor]
        selected.append(index)
        cursor = rows[index][1] + 1
    return selected


def missing_ranges(
    expected_start: int,
    expected_end: int,
    covered: Iterable[BlockRange],
) -> list[BlockRange]:
    """Return exact uncovered intervals, failing closed on bad coverage."""
    start = int(expected_start)
    end = int(expected_end)
    if start <= 0 or end < start:
        raise ValueError(f"invalid expected range: {start}..{end}")

    rows = sorted((int(lo), int(hi)) for lo, hi in covered)
    prior_hi = None
    for lo, hi in rows:
        if lo <= 0 or hi < lo:
            raise ValueError(f"invalid covered range: {lo}..{hi}")
        if lo < start or hi > end:
            raise ValueError(
                f"covered range outside expected bounds: {lo}..{hi} "
                f"not within {start}..{end}"
            )
        if prior_hi is not None and lo <= prior_hi:
            raise ValueError(
                f"covered ranges overlap: prior_hi={prior_hi} next_lo={lo}"
            )
        prior_hi = hi

    gaps: list[BlockRange] = []
    cursor = start
    for lo, hi in rows:
        if lo > cursor:
            gaps.append((cursor, lo - 1))
        cursor = hi + 1
    if cursor <= end:
        gaps.append((cursor, end))
    return gaps


def indexed_shard_bounds(
    expected_start: int,
    expected_end: int,
    shard_index: int,
    shard_count: int,
) -> BlockRange:
    """Return deterministic inclusive bounds for one indexed equal-span shard."""
    start = int(expected_start)
    end = int(expected_end)
    index = int(shard_index)
    count = int(shard_count)
    if start <= 0 or end < start:
        raise ValueError(f"invalid expected range: {start}..{end}")
    if count <= 0:
        raise ValueError("shard_count must be positive")
    if index < 0 or index >= count:
        raise ValueError(
            f"shard_index outside 0..{count - 1}: {index}"
        )
    span = end - start + 1
    lo = start + (span * index) // count
    hi = start + (span * (index + 1)) // count - 1
    if hi < lo:
        raise ValueError(
            "shard_count exceeds inclusive block span: "
            f"{count} > {span}"
        )
    return lo, hi


def split_range(
    start: int,
    end: int,
    *,
    max_blocks: int,
) -> list[BlockRange]:
    """Split one inclusive range into contiguous chunks of at most max_blocks."""
    lo = int(start)
    hi = int(end)
    size = int(max_blocks)
    if lo <= 0 or hi < lo:
        raise ValueError(f"invalid range: {lo}..{hi}")
    if size <= 0:
        raise ValueError("max_blocks must be positive")

    output: list[BlockRange] = []
    cursor = lo
    while cursor <= hi:
        chunk_hi = min(hi, cursor + size - 1)
        output.append((cursor, chunk_hi))
        cursor = chunk_hi + 1
    return output


def plan_missing_subranges(
    expected_start: int,
    expected_end: int,
    covered: Iterable[BlockRange],
    *,
    max_blocks: int,
) -> list[BlockRange]:
    """Plan bounded, non-overlapping retries for exactly the missing coverage."""
    output: list[BlockRange] = []
    for lo, hi in missing_ranges(expected_start, expected_end, covered):
        output.extend(split_range(lo, hi, max_blocks=max_blocks))
    return output
