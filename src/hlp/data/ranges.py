"""Deterministic block-range gap planning for resumable archive backfills."""

from __future__ import annotations

from collections.abc import Iterable


BlockRange = tuple[int, int]


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
