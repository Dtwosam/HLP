import pytest

from hlp.data.trench_coverage import (
    TRENCH_CURVE_COVERAGE_VERSION,
    TRENCH_SOURCE_COVERAGE_VERSION,
    merge_trench_lifecycle_market_cap_summaries,
    summarize_trench_post_limit_market_caps,
    validate_trench_curve_coverage_report,
    validate_trench_source_coverage_report,
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


def handoff():
    return {
        "token": "0x" + "11" * 20,
        "market_id": "0x" + "22" * 20,
        "market_source_id": "direct_uniswap_v3",
        "market_venue": "uniswap_v3",
        "limit_reach_block": 20,
        "limit_reach_transaction_index": 1,
        "limit_reach_log_index": 2,
        "handoff_rule_frozen": True,
    }


def test_summarize_trench_post_limit_requires_frozen_selected_market():
    rows = summarize_trench_post_limit_market_caps(
        [{
            "source_id": "trench_today",
            "token": handoff()["token"],
            "market_id": handoff()["market_id"],
            "block_number": 20,
            "transaction_hash": "0x" + "aa" * 32,
            "transaction_index": 1,
            "log_index": 3,
            "market_cap_proxy_usd": "125000",
        }],
        [handoff()],
    )
    assert rows[0]["post_limit_price_points"] == 1
    assert rows[0]["post_limit_priced_points"] == 1
    assert rows[0]["crossed_100k"] is True


def test_summarize_trench_post_limit_rejects_missing_handoff_history():
    with pytest.raises(ValueError, match="lack post-limit price points"):
        summarize_trench_post_limit_market_caps([], [handoff()])


def test_merge_trench_lifecycle_requires_curve_point_for_every_launch():
    registry = [
        {
            "token": handoff()["token"],
            "limit_reach_block": 20,
        },
        {
            "token": "0x" + "33" * 20,
            "limit_reach_block": None,
        },
    ]
    curve = [{
        "token": handoff()["token"],
        "price_points": 2,
        "priced_points": 2,
        "max_market_cap_proxy_usd": "90000",
        "max_market_cap_block": 19,
        "crossed_100k": False,
    }]
    post = [{
        "token": handoff()["token"],
        "post_limit_price_points": 1,
        "post_limit_priced_points": 1,
        "max_market_cap_proxy_usd": "125000",
        "max_market_cap_block": 20,
        "crossed_100k": True,
    }]
    with pytest.raises(ValueError, match="every launch"):
        merge_trench_lifecycle_market_cap_summaries(
            registry,
            curve,
            post,
        )


def test_merge_trench_lifecycle_combines_curve_and_post_limit():
    token = handoff()["token"]
    registry = [{
        "token": token,
        "limit_reach_block": 20,
    }]
    curve = [{
        "token": token,
        "price_points": 2,
        "priced_points": 2,
        "max_market_cap_proxy_usd": "90000",
        "max_market_cap_block": 19,
        "crossed_100k": False,
    }]
    post = [{
        "token": token,
        "post_limit_price_points": 3,
        "post_limit_priced_points": 3,
        "max_market_cap_proxy_usd": "125000",
        "max_market_cap_block": 21,
        "crossed_100k": True,
    }]
    rows = merge_trench_lifecycle_market_cap_summaries(
        registry,
        curve,
        post,
    )
    assert rows[0]["price_points"] == 5
    assert rows[0]["priced_points"] == 5
    assert rows[0]["max_market_cap_proxy_usd"] == "125000"
    assert rows[0]["crossed_100k"] is True


def full_report():
    return {
        "version": TRENCH_SOURCE_COVERAGE_VERSION,
        "source_id": "trench_today",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": 10,
        "first_block": 10,
        "last_block": 100,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": 5,
        "curve_tokens_with_points": 5,
        "limit_reach_tokens": 2,
        "post_limit_tokens_with_points": 2,
        "lifecycle_tokens_with_points": 5,
        "curve_price_points": 20,
        "post_limit_price_points": 8,
        "price_points": 28,
        "priced_points": 28,
        "observed_volume_usd": None,
        "handoff_rule_version": "trench-limit-same-transaction-after-v1",
        "handoff_rule_frozen": True,
        "provenance_sha256": SHA,
        "event_tape_sha256": "cd" * 32,
        "registry_sha256": "ef" * 32,
        "curve_report_sha256": "12" * 32,
        "curve_points_sha256": "34" * 32,
        "handoff_report_sha256": "56" * 32,
        "handoff_manifest_sha256": "78" * 32,
        "post_limit_points_sha256": "90" * 32,
        "final_summary_sha256": "ab" * 32,
        "blocking_reason": None,
        "snapshot_head_block": 100,
    }


def validate_full(row):
    return validate_trench_source_coverage_report(
        row,
        required_start_block=10,
        snapshot_head_block=100,
    )


def test_validate_full_trench_source_coverage():
    row = validate_full(full_report())
    assert row["coverage_status"] == "complete"
    assert row["curve_tokens_with_points"] == 5
    assert row["post_limit_tokens_with_points"] == 2


def test_full_trench_coverage_requires_curve_points_for_every_launch():
    row = full_report()
    row["curve_tokens_with_points"] = 4
    with pytest.raises(ValueError, match="every launch"):
        validate_full(row)


def test_full_trench_coverage_requires_every_limit_token_post_history():
    row = full_report()
    row["post_limit_tokens_with_points"] = 1
    with pytest.raises(ValueError, match="every LimitReach"):
        validate_full(row)


def test_full_trench_coverage_rejects_unfrozen_handoff():
    row = full_report()
    row["handoff_rule_frozen"] = False
    with pytest.raises(ValueError, match="not frozen"):
        validate_full(row)

