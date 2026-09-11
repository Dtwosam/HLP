"""Deterministic block-range gap planning for resumable archive backfills."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


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


def validate_gap_plan_jobs(
    plan: Mapping[str, object],
    *,
    expected_start: int,
    expected_end: int,
    max_wave_jobs: int = 240,
    max_waves: int = 4,
) -> dict[str, BlockRange]:
    """Validate bounded serialized gap-plan jobs and return ID-to-range bindings."""
    start = int(expected_start)
    end = int(expected_end)
    wave_size = int(max_wave_jobs)
    wave_count = int(max_waves)
    if start <= 0 or end < start:
        raise ValueError(f"invalid expected range: {start}..{end}")
    if wave_size <= 0 or wave_count <= 0:
        raise ValueError("wave sizing must be positive")

    max_blocks = int(plan.get("max_gap_blocks", 0) or 0)
    if not 1 <= max_blocks <= 100_000:
        raise ValueError("gap plan max_gap_blocks must be between 1 and 100000")

    raw_jobs = plan.get("gap_jobs")
    if not isinstance(raw_jobs, list):
        raise ValueError("gap plan jobs must be a list")
    declared_count = int(plan.get("gap_job_count", -1) or 0)
    if declared_count != len(raw_jobs):
        raise ValueError(
            "gap plan job count mismatch: "
            f"declared={declared_count} observed={len(raw_jobs)}"
        )
    if len(raw_jobs) > wave_size * wave_count:
        raise ValueError(
            "gap plan exceeds serialized wave capacity: "
            f"{len(raw_jobs)} > {wave_size * wave_count}"
        )

    raw_wave_counts = plan.get("gap_wave_job_counts")
    if not isinstance(raw_wave_counts, list) or (
        len(raw_wave_counts) != wave_count
    ):
        raise ValueError("gap plan wave counts changed")
    observed_wave_counts = [int(value) for value in raw_wave_counts]
    expected_wave_counts = [
        min(max(len(raw_jobs) - wave_size * index, 0), wave_size)
        for index in range(wave_count)
    ]
    if observed_wave_counts != expected_wave_counts:
        raise ValueError(
            "gap plan wave counts mismatch: "
            f"observed={observed_wave_counts} "
            f"expected={expected_wave_counts}"
        )

    bindings: dict[str, BlockRange] = {}
    previous_hi: int | None = None
    total_blocks = 0
    for index, raw_job in enumerate(raw_jobs):
        if not isinstance(raw_job, Mapping):
            raise ValueError(f"gap plan job {index} must be an object")
        gap_id = str(raw_job.get("id") or "")
        expected_id = f"{index:03d}"
        if gap_id != expected_id:
            raise ValueError(
                "gap plan job ID changed: "
                f"observed={gap_id!r} expected={expected_id!r}"
            )
        lo = int(raw_job.get("from_block", 0) or 0)
        hi = int(raw_job.get("to_block", -1) or -1)
        if lo < start or hi > end or hi < lo:
            raise ValueError(
                f"gap plan range outside expected bounds: {lo}..{hi}"
            )
        if hi - lo + 1 > max_blocks:
            raise ValueError(
                "gap plan job exceeds max_gap_blocks: "
                f"{gap_id} {lo}..{hi}"
            )
        if previous_hi is not None and lo <= previous_hi:
            raise ValueError(
                "gap plan jobs overlap or are out of order: "
                f"prior_hi={previous_hi} next_lo={lo}"
            )
        bindings[gap_id] = (lo, hi)
        previous_hi = hi
        total_blocks += hi - lo + 1

    declared_blocks = int(plan.get("gap_blocks", -1) or 0)
    if declared_blocks != total_blocks:
        raise ValueError(
            "gap plan block count mismatch: "
            f"declared={declared_blocks} observed={total_blocks}"
        )
    return bindings


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
