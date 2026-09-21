import pytest

from hlp.data.pools_trade_coverage import (
    POOLS_TRADE_INSTANT_COVERAGE_VERSION,
    POOLS_TRADE_LBP_COVERAGE_VERSION,
    validate_pools_trade_instant_coverage_report,
    validate_pools_trade_lbp_coverage_report,
)


SHA = "ab" * 32


def report():
    return {
        "version": POOLS_TRADE_INSTANT_COVERAGE_VERSION,
        "source_id": "pools_trade_instant",
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
        "swap_points": 5,
        "tokens_with_price_points": 3,
        "price_points": 8,
        "priced_points": 8,
        "tokens_crossed_100k": 1,
        "observed_volume_usd": None,
        "blocking_reason": None,
        "all_pools_initialized": True,
        "initialized_registry_sha256": SHA,
        "v4_initialize_sha256": "cd" * 32,
        "shared_v4_swap_sha256": "ef" * 32,
        "shared_supply_delta_sha256": "12" * 32,
        "filtered_supply_sha256": "34" * 32,
        "quote_decimals_sha256": "56" * 32,
        "quote_feed_specs_sha256": "78" * 32,
        "market_points_sha256": "9a" * 32,
        "token_summary_sha256": "bc" * 32,
        "provenance_sha256": "de" * 32,
    }


def validate(row):
    return validate_pools_trade_instant_coverage_report(
        row,
        required_start_block=10,
        snapshot_head_block=100,
    )


def test_validate_complete_pools_trade_instant_coverage():
    row = validate(report())
    assert row["tokens_discovered"] == 3
    assert row["initialize_points"] == 3
    assert row["priced_points"] == row["price_points"] == 8


def test_pools_trade_instant_requires_one_initialize_per_token():
    row = report()
    row["initialize_points"] = 2
    with pytest.raises(ValueError, match="one Initialize"):
        validate(row)


def test_pools_trade_instant_rejects_unpriced_points():
    row = report()
    row["priced_points"] = 7
    with pytest.raises(ValueError, match="unpriced points"):
        validate(row)


def test_pools_trade_instant_requires_every_token_priced():
    row = report()
    row["tokens_with_price_points"] = 2
    with pytest.raises(ValueError, match="every token"):
        validate(row)


def test_pools_trade_instant_requires_initialized_registry():
    row = report()
    row["all_pools_initialized"] = False
    with pytest.raises(ValueError, match="Initialize population"):
        validate(row)


def lbp_report():
    return {
        "version": POOLS_TRADE_LBP_COVERAGE_VERSION,
        "source_id": "pools_trade_lbp",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 10,
        "first_block": 10,
        "last_block": 100,
        "snapshot_head_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 4,
        "cca_phase_coverage_complete": True,
        "cca_tokens_with_price_points": 4,
        "migrated_tokens": 2,
        "non_migrated_tokens": 2,
        "migration_absence_conclusive": True,
        "v4_tokens_with_price_points": 2,
        "v4_initialize_points": 2,
        "tokens_with_price_points": 4,
        "cca_price_points": 20,
        "v4_price_points": 8,
        "price_points": 28,
        "priced_points": 28,
        "tokens_crossed_100k": 1,
        "observed_volume_usd": None,
        "blocking_reason": None,
        "registry_sha256": SHA,
        "cca_events_sha256": "12" * 32,
        "cca_market_points_sha256": "23" * 32,
        "cca_token_summary_sha256": "34" * 32,
        "v4_initialize_sha256": "45" * 32,
        "migrated_registry_sha256": "56" * 32,
        "shared_v4_swap_sha256": "67" * 32,
        "shared_supply_delta_sha256": "78" * 32,
        "filtered_supply_sha256": "89" * 32,
        "quote_decimals_sha256": "9a" * 32,
        "quote_feed_specs_sha256": "ab" * 32,
        "v4_market_points_sha256": "bc" * 32,
        "v4_token_summary_sha256": "cd" * 32,
        "lifecycle_summary_sha256": "de" * 32,
        "provenance_sha256": "ef" * 32,
    }


def validate_lbp(row):
    return validate_pools_trade_lbp_coverage_report(
        row,
        required_start_block=10,
        snapshot_head_block=100,
    )


def test_validate_complete_pools_trade_lbp_coverage():
    row = validate_lbp(lbp_report())
    assert row["tokens_discovered"] == 4
    assert row["migrated_tokens"] == 2
    assert row["non_migrated_tokens"] == 2
    assert row["priced_points"] == row["price_points"] == 28


def test_pools_trade_lbp_requires_complete_cca_population():
    row = lbp_report()
    row["cca_tokens_with_price_points"] = 3
    with pytest.raises(ValueError, match="CCA history"):
        validate_lbp(row)


def test_pools_trade_lbp_requires_conclusive_migration_absence():
    row = lbp_report()
    row["migration_absence_conclusive"] = False
    with pytest.raises(ValueError, match="absence is not conclusive"):
        validate_lbp(row)


def test_pools_trade_lbp_requires_every_migrated_v4_token():
    row = lbp_report()
    row["v4_tokens_with_price_points"] = 1
    with pytest.raises(ValueError, match="every migrated token"):
        validate_lbp(row)


def test_pools_trade_lbp_rejects_unpriced_points():
    row = lbp_report()
    row["priced_points"] = 27
    with pytest.raises(ValueError, match="unpriced points"):
        validate_lbp(row)


def test_pools_trade_lbp_reconciles_phase_point_counts():
    row = lbp_report()
    row["v4_price_points"] = 7
    with pytest.raises(ValueError, match="point accounting"):
        validate_lbp(row)

