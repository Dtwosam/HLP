import pytest

from hlp.data.trench_coverage import (
    TRENCH_CURVE_COVERAGE_VERSION,
    validate_trench_curve_coverage_report,
)


SHA = "ab" * 32


def report():
    return {
        "version": TRENCH_CURVE_COVERAGE_VERSION,
        "source_id": "trench_today",
        "coverage_segment": "bonding_curve",
        "required_start_block": 10,
        "snapshot_head_block": 100,
        "continuous_event_scan": True,
        "missing_ranges": [],
        "tokens_discovered": 5,
        "tokens_with_syncs": 4,
        "limit_reach_tokens": 2,
        "curve_price_points": 20,
        "curve_priced_points": 20,
        "curve_tokens_crossed_100k": 1,
        "event_tape_sha256": SHA,
        "registry_sha256": "cd" * 32,
        "quote_decimals_sha256": "ef" * 32,
        "quote_feed_specs_sha256": "12" * 32,
        "curve_points_sha256": "34" * 32,
        "curve_summary_sha256": "56" * 32,
        "blocking_reason": "post_limit_dex_lifecycle_unresolved",
        "source_coverage_complete": False,
    }


def test_validate_trench_curve_coverage_segment():
    row = validate_trench_curve_coverage_report(
        report(),
        required_start_block=10,
        snapshot_head_block=100,
    )
    assert row["curve_priced_points"] == row["curve_price_points"]
    assert row["source_coverage_complete"] is False


def test_trench_curve_coverage_rejects_unpriced_points():
    row = report()
    row["curve_priced_points"] = 19
    with pytest.raises(ValueError, match="unpriced points"):
        validate_trench_curve_coverage_report(
            row,
            required_start_block=10,
            snapshot_head_block=100,
        )


def test_trench_curve_coverage_requires_post_limit_blocker():
    row = report()
    row["blocking_reason"] = None
    with pytest.raises(ValueError, match="DEX-lifecycle blocker"):
        validate_trench_curve_coverage_report(
            row,
            required_start_block=10,
            snapshot_head_block=100,
        )


def test_trench_curve_segment_never_closes_source_coverage():
    row = report()
    row["source_coverage_complete"] = True
    with pytest.raises(ValueError, match="cannot close source coverage"):
        validate_trench_curve_coverage_report(
            row,
            required_start_block=10,
            snapshot_head_block=100,
        )
