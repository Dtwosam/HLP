from hlp.data.universe import summarize_v1_market_caps
from hlp.data.v2_curve import (
    merge_v2_lifecycle_market_cap_summaries,
    summarize_v2_curve_market_caps,
)


TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20
POOL = "0x" + "33" * 20
QUOTE = "0x" + "44" * 20


def point(block, mcap):
    return {
        "token": TOKEN,
        "curve": CURVE,
        "pool": POOL,
        "quote_token": QUOTE,
        "launch_block": 10,
        "block_number": block,
        "pricing_status": "unsupported_quote" if mcap is None else "priced",
        "market_cap_proxy_usd": mcap,
    }


def test_v1_summary_marks_partial_non_crossing_history_unknown():
    row = summarize_v1_market_caps([
        point(10, None),
        point(20, "90000"),
    ])[0]
    assert row["unpriced_points"] == 1
    assert row["pricing_complete"] is False
    assert row["eligibility_status"] == "unknown"
    assert row["first_unpriced_block"] == 10
    assert row["first_priced_block"] == 20


def test_v2_summary_marks_crossing_history_eligible_even_if_partial():
    row = summarize_v2_curve_market_caps([
        point(10, None),
        point(20, "120000"),
    ])[0]
    assert row["unpriced_points"] == 1
    assert row["crossed_100k"] is True
    assert row["eligibility_status"] == "eligible"


def test_v2_lifecycle_merge_preserves_unknown_state():
    registry = [{
        "token": TOKEN,
        "curve": CURVE,
        "pair_token": QUOTE,
        "block_number": 10,
    }]
    curve = [{
        "token": TOKEN,
        "pricing_statuses": ["unsupported_quote", "priced"],
        "price_points": 2,
        "priced_points": 1,
        "unpriced_points": 1,
        "first_priced_block": 20,
        "last_priced_block": 20,
        "first_unpriced_block": 10,
        "last_unpriced_block": 10,
        "max_market_cap_proxy_usd": "90000",
        "max_market_cap_block": 20,
        "crossed_100k": False,
    }]
    row = merge_v2_lifecycle_market_cap_summaries(
        registry,
        curve_summary=curve,
    )[0]
    assert row["unpriced_points"] == 1
    assert row["pricing_complete"] is False
    assert row["eligibility_status"] == "unknown"
