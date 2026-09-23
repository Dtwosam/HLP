import pytest

from hlp.data.doppler_coverage import (
    DOPPLER_COVERAGE_VERSION,
    validate_doppler_coverage_report,
)


SHA = "ab" * 32


def report():
    return {
        "version": DOPPLER_COVERAGE_VERSION,
        "source_id": "doppler",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 10,
        "first_block": 10,
        "last_block": 100,
        "snapshot_head_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 3,
        "initialize_points": 3,
        "tokens_with_price_points": 3,
        "price_points": 9,
        "priced_points": 9,
        "tokens_crossed_100k": 1,
        "observed_volume_usd": None,
        "blocking_reason": None,
        "same_transaction_initialize_complete": True,
        "registry_sha256": SHA,
        "launch_state_sha256": "cd" * 32,
        "v4_initialize_sha256": "ef" * 32,
        "shared_v4_swap_sha256": "12" * 32,
        "shared_supply_delta_sha256": "34" * 32,
        "filtered_supply_sha256": "56" * 32,
        "quote_decimals_sha256": "78" * 32,
        "quote_feed_specs_sha256": "90" * 32,
        "market_points_sha256": "11" * 32,
        "token_summary_sha256": "22" * 32,
        "provenance_sha256": "33" * 32,
    }


def validate(row):
    return validate_doppler_coverage_report(
        row,
        required_start_block=10,
        snapshot_head_block=100,
    )


def test_validate_complete_doppler_coverage():
    row = validate(report())
    assert row["priced_points"] == row["price_points"] == 9
    assert row["initialize_points"] == row["tokens_discovered"] == 3


def test_doppler_coverage_requires_one_initialize_per_token():
    row = report()
    row["initialize_points"] = 2
    with pytest.raises(ValueError, match="exactly one Initialize"):
        validate(row)


def test_doppler_coverage_requires_every_token_priceable():
    row = report()
    row["tokens_with_price_points"] = 2
    with pytest.raises(ValueError, match="every token"):
        validate(row)


def test_doppler_coverage_rejects_unpriced_points():
    row = report()
    row["priced_points"] = 8
    with pytest.raises(ValueError, match="unpriced points"):
        validate(row)


def test_doppler_complete_report_cannot_remain_blocked():
    row = report()
    row["blocking_reason"] = "blocked"
    with pytest.raises(ValueError, match="blocking_reason"):
        validate(row)
