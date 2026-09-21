from decimal import Decimal

import pytest

from hlp.data.market_quality import (
    active_quote_liquidity_usd,
    rank_market_quality_snapshot,
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
