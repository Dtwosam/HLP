import pytest

from hlp.data.flap_coverage import (
    FLAP_CURVE_COVERAGE_VERSION,
    FLAP_SOURCE_COVERAGE_VERSION,
    validate_flap_curve_coverage_report,
    validate_flap_source_coverage_report,
)


SHA = "ab" * 32


def report():
    return {
        "version": FLAP_CURVE_COVERAGE_VERSION,
        "source_id": "flap",
        "coverage_segment": "bonding_curve",
        "required_start_block": 10,
        "snapshot_head_block": 100,
        "continuous_event_scan": True,
        "missing_ranges": [],
        "tokens_discovered": 5,
        "tokens_with_curve_trades": 4,
        "graduated_tokens": 2,
        "curve_price_points": 20,
        "curve_priced_points": 20,
        "curve_tokens_crossed_100k": 1,
        "event_tape_sha256": SHA,
        "registry_sha256": "cd" * 32,
        "quote_feed_specs_sha256": "ef" * 32,
        "curve_points_sha256": "12" * 32,
        "curve_summary_sha256": "34" * 32,
        "blocking_reason": "post_graduation_dex_lifecycle_not_yet_merged",
        "source_coverage_complete": False,
    }


def validate(row):
    return validate_flap_curve_coverage_report(
        row,
        required_start_block=10,
        snapshot_head_block=100,
    )


def test_validate_flap_curve_coverage_segment():
    row = validate(report())
    assert row["curve_priced_points"] == row["curve_price_points"] == 20
    assert row["graduated_tokens"] == 2
    assert row["source_coverage_complete"] is False


def test_flap_curve_coverage_rejects_unpriced_points():
    row = report()
    row["curve_priced_points"] = 19
    with pytest.raises(ValueError, match="unpriced points"):
        validate(row)


def test_flap_curve_coverage_cannot_close_full_source():
    row = report()
    row["source_coverage_complete"] = True
    with pytest.raises(ValueError, match="cannot close"):
        validate(row)


def test_flap_curve_coverage_requires_graduation_blocker():
    row = report()
    row["blocking_reason"] = None
    with pytest.raises(ValueError, match="DEX-lifecycle blocker"):
        validate(row)


def full_report():
    return {
        "version": FLAP_SOURCE_COVERAGE_VERSION,
        "source_id": "flap",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 10,
        "first_block": 10,
        "last_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 5,
        "lifecycle_tokens_with_points": 5,
        "graduated_tokens": 2,
        "graduation_snapshots": 2,
        "curve_price_points": 20,
        "v3_price_points": 7,
        "price_points": 27,
        "priced_points": 27,
        "observed_volume_usd": None,
        "provenance_sha256": SHA,
        "event_tape_sha256": "cd" * 32,
        "registry_sha256": "ef" * 32,
        "curve_report_sha256": "12" * 32,
        "curve_points_sha256": "34" * 32,
        "graduation_registry_sha256": "56" * 32,
        "v3_points_sha256": "78" * 32,
        "final_summary_sha256": "90" * 32,
        "blocking_reason": None,
        "snapshot_head_block": 100,
    }


def validate_full(row):
    return validate_flap_source_coverage_report(
        row,
        required_start_block=10,
        snapshot_head_block=100,
    )


def test_validate_full_flap_source_coverage():
    row = validate_full(full_report())
    assert row["coverage_status"] == "complete"
    assert row["lifecycle_tokens_with_points"] == 5
    assert row["graduation_snapshots"] == 2


def test_full_flap_source_coverage_requires_every_launch_priced():
    row = full_report()
    row["lifecycle_tokens_with_points"] = 4
    with pytest.raises(ValueError, match="every launch"):
        validate_full(row)


def test_full_flap_source_coverage_requires_every_graduation_snapshot():
    row = full_report()
    row["graduation_snapshots"] = 1
    with pytest.raises(ValueError, match="snapshot count"):
        validate_full(row)

