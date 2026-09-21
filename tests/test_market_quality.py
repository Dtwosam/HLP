from decimal import Decimal

import pytest

from hlp.data.market_quality import (
    active_quote_liquidity_usd,
    build_causal_market_quality_trace,
    rank_market_quality_snapshot,
    summarize_causal_market_quality_trace,
    summarize_market_competition,
)


Q96 = 1 << 96
TOKEN = "0x" + "11" * 20


def test_active_quote_liquidity_token0_uses_y_reserve():
    value = active_quote_liquidity_usd(
        sqrt_price_x96=Q96,
        liquidity_raw=1_000 * 10**18,
        token_is_currency0=True,
        quote_decimals=18,
        quote_usd=Decimal("2"),
    )
    assert value == Decimal("2000")


def test_active_quote_liquidity_token1_uses_x_reserve():
    value = active_quote_liquidity_usd(
        sqrt_price_x96=2 * Q96,
        liquidity_raw=1_000 * 10**18,
        token_is_currency0=False,
        quote_decimals=18,
        quote_usd=Decimal("4"),
    )
    assert value == Decimal("2000")


def test_market_quality_ranking_is_depth_first_then_stable_id():
    rows = rank_market_quality_snapshot(
        [
            {
                "token": TOKEN,
                "market_id": "0xbbb",
                "active_quote_liquidity_usd": "100",
            },
            {
                "token": TOKEN,
                "market_id": "0xaaa",
                "active_quote_liquidity_usd": "100",
            },
            {
                "token": TOKEN,
                "market_id": "0xccc",
                "active_quote_liquidity_usd": "50",
            },
        ]
    )

    assert [row["market_id"] for row in rows] == [
        "0xaaa",
        "0xbbb",
        "0xccc",
    ]
    assert rows[0]["market_quality_candidate"] is True
    assert rows[1]["market_quality_candidate"] is False


def test_market_quality_snapshot_rejects_mixed_tokens():
    with pytest.raises(ValueError, match="exactly one token"):
        rank_market_quality_snapshot(
            [
                {
                    "token": TOKEN,
                    "market_id": "a",
                    "active_quote_liquidity_usd": "1",
                },
                {
                    "token": "0x" + "22" * 20,
                    "market_id": "b",
                    "active_quote_liquidity_usd": "2",
                },
            ]
        )


def test_market_competition_summary_does_not_freeze_selector():
    report = summarize_market_competition(
        [
            {"token": TOKEN, "market_id": "a"},
            {"token": TOKEN, "market_id": "b"},
            {"token": "0x" + "22" * 20, "market_id": "c"},
        ]
    )

    assert report["tokens"] == 2
    assert report["markets"] == 3
    assert report["multi_market_tokens"] == 1
    assert report["max_markets_per_token"] == 2
    assert report["selection_rule_frozen"] is False



def _market_event(
    market_id,
    *,
    block,
    txi,
    depth,
    mcap,
):
    return {
        "token": TOKEN,
        "market_id": market_id,
        "block_number": block,
        "transaction_index": txi,
        "log_index": 0,
        "active_quote_liquidity_usd": str(depth),
        "market_cap_proxy_usd": str(mcap),
    }


def test_causal_trace_does_not_leak_future_market_depth_backward():
    rows = build_causal_market_quality_trace(
        [
            _market_event(
                "0xaaa",
                block=10,
                txi=1,
                depth=100,
                mcap=100_000,
            ),
            _market_event(
                "0xbbb",
                block=20,
                txi=1,
                depth=1_000,
                mcap=120_000,
            ),
        ]
    )

    assert rows[0]["block_number"] == 10
    assert rows[0]["observed_markets"] == 1
    assert rows[0]["candidate_market_id"] == "0xaaa"

    assert rows[1]["block_number"] == 20
    assert rows[1]["observed_markets"] == 2
    assert rows[1]["candidate_market_id"] == "0xbbb"
    assert rows[1]["selection_rule_frozen"] is False


def test_causal_trace_uses_latest_prior_state_of_other_market():
    rows = build_causal_market_quality_trace(
        [
            _market_event(
                "0xaaa",
                block=10,
                txi=1,
                depth=500,
                mcap=100_000,
            ),
            _market_event(
                "0xbbb",
                block=11,
                txi=1,
                depth=400,
                mcap=200_000,
            ),
            _market_event(
                "0xbbb",
                block=12,
                txi=1,
                depth=600,
                mcap=150_000,
            ),
        ]
    )

    final = rows[-1]
    assert final["candidate_market_id"] == "0xbbb"
    assert final["ranked_market_ids"] == ["0xbbb", "0xaaa"]
    assert Decimal(final["min_observed_market_cap_proxy_usd"]) == Decimal(
        "100000"
    )
    assert Decimal(final["max_observed_market_cap_proxy_usd"]) == Decimal(
        "150000"
    )
    assert Decimal(final["market_cap_dispersion_multiple"]) == Decimal(
        "1.5"
    )


def test_causal_trace_skips_unpriced_or_depthless_state_until_usable():
    rows = build_causal_market_quality_trace(
        [
            {
                **_market_event(
                    "0xaaa",
                    block=10,
                    txi=1,
                    depth=100,
                    mcap=100_000,
                ),
                "active_quote_liquidity_usd": None,
            },
            _market_event(
                "0xaaa",
                block=11,
                txi=1,
                depth=100,
                mcap=100_000,
            ),
        ]
    )
    assert len(rows) == 1
    assert rows[0]["block_number"] == 11


def test_causal_trace_rejects_duplicate_event_identity():
    event = _market_event(
        "0xaaa",
        block=10,
        txi=1,
        depth=100,
        mcap=100_000,
    )
    with pytest.raises(ValueError, match="duplicate market-quality event"):
        build_causal_market_quality_trace([event, event])



def test_trace_summary_counts_candidate_switches_and_dispersion():
    trace = [
        {
            "token": TOKEN,
            "event_market_id": "0xaaa",
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 0,
            "observed_markets": 1,
            "candidate_market_id": "0xaaa",
            "market_cap_dispersion_multiple": "1",
            "selection_rule_frozen": False,
        },
        {
            "token": TOKEN,
            "event_market_id": "0xbbb",
            "block_number": 11,
            "transaction_index": 1,
            "log_index": 0,
            "observed_markets": 2,
            "candidate_market_id": "0xaaa",
            "market_cap_dispersion_multiple": "2",
            "selection_rule_frozen": False,
        },
        {
            "token": TOKEN,
            "event_market_id": "0xbbb",
            "block_number": 12,
            "transaction_index": 1,
            "log_index": 0,
            "observed_markets": 2,
            "candidate_market_id": "0xbbb",
            "market_cap_dispersion_multiple": "4",
            "selection_rule_frozen": False,
        },
    ]

    report = summarize_causal_market_quality_trace(trace)

    assert report["snapshots"] == 3
    assert report["tokens"] == 1
    assert report["multi_market_snapshots"] == 2
    assert report["candidate_switches"] == 1
    assert report["tokens_with_candidate_switches"] == 1
    assert report["candidate_switches_by_token"] == {TOKEN: 1}
    assert report["candidate_snapshots_by_market"] == {
        "0xaaa": 2,
        "0xbbb": 1,
    }
    assert Decimal(
        report["median_market_cap_dispersion_multiple"]
    ) == Decimal("3")
    assert Decimal(
        report["max_market_cap_dispersion_multiple"]
    ) == Decimal("4")
    assert report["selection_rule_frozen"] is False


def test_trace_summary_rejects_accidental_selector_freeze():
    with pytest.raises(ValueError, match="unexpectedly freezes"):
        summarize_causal_market_quality_trace(
            [
                {
                    "token": TOKEN,
                    "event_market_id": "0xaaa",
                    "block_number": 10,
                    "transaction_index": 1,
                    "log_index": 0,
                    "observed_markets": 1,
                    "candidate_market_id": "0xaaa",
                    "market_cap_dispersion_multiple": "1",
                    "selection_rule_frozen": True,
                }
            ]
        )
