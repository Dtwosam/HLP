import pytest

from hlp.data.ranges import (
    coalesce_covered_ranges,
    missing_ranges,
    plan_missing_subranges,
    select_contiguous_cover,
    split_range,
)


def test_missing_ranges_preserves_exact_holes():
    assert missing_ranges(
        1,
        30,
        [(1, 10), (21, 30)],
    ) == [(11, 20)]


def test_missing_ranges_accepts_adjacent_complete_coverage():
    assert missing_ranges(
        1,
        30,
        [(1, 10), (11, 20), (21, 30)],
    ) == []


def test_missing_ranges_rejects_overlap():
    with pytest.raises(ValueError, match="overlap"):
        missing_ranges(1, 30, [(1, 10), (10, 20)])


def test_missing_ranges_rejects_out_of_bounds_artifact():
    with pytest.raises(ValueError, match="outside expected bounds"):
        missing_ranges(10, 20, [(9, 12)])


def test_split_range_is_contiguous_and_bounded():
    assert split_range(11, 20, max_blocks=4) == [
        (11, 14),
        (15, 18),
        (19, 20),
    ]


def test_plan_missing_subranges_never_refetches_covered_blocks():
    assert plan_missing_subranges(
        1,
        30,
        [(1, 10), (21, 30)],
        max_blocks=4,
    ) == [
        (11, 14),
        (15, 18),
        (19, 20),
    ]

def test_plan_missing_subranges_reuses_prior_gap_coverage():
    assert plan_missing_subranges(
        1,
        40,
        [
            (31, 40),  # successful partial-recovery suffix
            (1, 10),   # successful partial-recovery prefix
            (16, 20),  # successful earlier gap-recovery artifact
        ],
        max_blocks=4,
    ) == [
        (11, 14),
        (15, 15),
        (21, 24),
        (25, 28),
        (29, 30),
    ]

def test_coalesce_covered_ranges_unions_overlap_and_adjacency():
    assert coalesce_covered_ranges(
        1,
        30,
        [(1, 10), (5, 12), (13, 20), (25, 30)],
    ) == [(1, 20), (25, 30)]


def test_coalesce_covered_ranges_rejects_out_of_bounds():
    with pytest.raises(ValueError, match="outside expected bounds"):
        coalesce_covered_ranges(10, 20, [(9, 12)])


def test_select_contiguous_cover_drops_redundant_overlap():
    candidates = [
        (1, 10),
        (1, 5),
        (6, 10),
        (11, 20),
    ]
    assert select_contiguous_cover(1, 20, candidates) == [0, 3]


def test_select_contiguous_cover_backtracks_to_valid_boundary():
    candidates = [
        (1, 10),
        (1, 5),
        (6, 20),
    ]
    assert select_contiguous_cover(1, 20, candidates) == [1, 2]


def test_select_contiguous_cover_prefers_first_duplicate():
    assert select_contiguous_cover(
        1,
        10,
        [(1, 10), (1, 10)],
    ) == [0]


def test_select_contiguous_cover_rejects_unfillable_overlap():
    with pytest.raises(ValueError, match="cannot form exact cover"):
        select_contiguous_cover(
            1,
            20,
            [(1, 10), (10, 20)],
        )

