from decimal import Decimal

from hlp.config import ROBINHOOD_WETH
from hlp.data.v2_curve import build_v2_curve_market_cap_points


TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20


def registry():
    return [
        {
            "version": "v2",
            "token": TOKEN,
            "curve": CURVE,
            "deployer": "0x" + "33" * 20,
            "pair_token": ROBINHOOD_WETH.lower(),
            "launch_config_id": 0,
            "graduation_threshold": 1000,
            "block_number": 10,
            "transaction_hash": "0x" + "aa" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "supply_raw": 1000 * 10**18,
            "token_decimals": 18,
            "quote_decimals": 18,
            "phantom_quote": 10 * 10**18,
        }
    ]


def test_curve_replay_buy_sell_buyback_and_full_market_cap():
    events = [
        {
            "event_type": "curve_buy",
            "curve": CURVE,
            "block_number": 11,
            "transaction_hash": "0x" + "bb" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "quote_amount": 2 * 10**18,
            "token_amount": 100 * 10**18,
            "fee": 10**17,
            "tax": 10**17,
        },
        {
            "event_type": "curve_sell",
            "curve": CURVE,
            "block_number": 12,
            "transaction_hash": "0x" + "cc" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "quote_amount": 9 * 10**17,
            "token_amount": 50 * 10**18,
            "fee": 5 * 10**16,
            "tax": 5 * 10**16,
        },
        {
            "event_type": "curve_buyback",
            "curve": CURVE,
            "block_number": 13,
            "transaction_hash": "0x" + "dd" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "quote_spent": 2 * 10**17,
            "tokens_locked": 10 * 10**18,
        },
    ]
    rows = list(
        build_v2_curve_market_cap_points(
            registry(),
            events,
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert [row["event_type"] for row in rows] == [
        "curve_initialized",
        "curve_buy",
        "curve_sell",
        "curve_buyback",
    ]

    # Initial 10 WETH / 1000 tokens = 0.01 WETH/token.
    assert Decimal(rows[0]["quote_per_token"]) == Decimal("0.01")
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("20000")

    # Buy: quote reserve +1.8 WETH, token reserve -100.
    assert rows[1]["quote_reserve_raw"] == 118 * 10**17
    assert rows[1]["token_reserve_raw"] == 900 * 10**18

    # Sell: reserve loses quoteOut+fee+tax = 1.0 WETH, gets 50 tokens.
    assert rows[2]["quote_reserve_raw"] == 108 * 10**17
    assert rows[2]["token_reserve_raw"] == 950 * 10**18

    # Buyback behaves like an internal quote->token buy.
    assert rows[3]["quote_reserve_raw"] == 110 * 10**17
    assert rows[3]["token_reserve_raw"] == 940 * 10**18


def test_same_block_anchor_updates_only_after_its_event():
    events = [
        {
            "event_type": "curve_buy",
            "curve": CURVE,
            "block_number": 20,
            "transaction_hash": "0x" + "bb" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "quote_amount": 10**18,
            "token_amount": 10 * 10**18,
            "fee": 0,
            "tax": 0,
        },
        {
            "event_type": "curve_buy",
            "curve": CURVE,
            "block_number": 20,
            "transaction_hash": "0x" + "cc" * 32,
            "transaction_index": 3,
            "log_index": 0,
            "quote_amount": 10**18,
            "token_amount": 10 * 10**18,
            "fee": 0,
            "tax": 0,
        },
    ]
    anchors = [
        {
            "block_number": 20,
            "transaction_index": 2,
            "log_index": 0,
            "quote_per_token": "2500",
        }
    ]
    rows = list(
        build_v2_curve_market_cap_points(
            registry(),
            events,
            anchors,
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert Decimal(rows[1]["quote_usd"]) == Decimal("2000")
    assert Decimal(rows[2]["quote_usd"]) == Decimal("2500")
