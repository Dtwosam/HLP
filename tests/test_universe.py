from decimal import Decimal

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.universe import build_v1_market_cap_points, summarize_v1_market_caps


TOKEN = "0x0000000000000000000000000000000000000011"
POOL = "0x" + "33" * 20


def test_shared_market_cap_join_respects_anchor_order():
    registry = [
        {
            "token": TOKEN,
            "pair_token": ROBINHOOD_WETH.lower(),
            "pool": POOL,
            "block_number": 10,
            "supply_raw": 1_000_000 * 10**18,
            "token_decimals": 18,
        }
    ]
    # TOKEN address < WETH, so sqrt=2**96 means 1 WETH per token.
    swaps = [
        {
            "pool": POOL,
            "block_number": 20,
            "transaction_index": 1,
            "log_index": 0,
            "sqrt_price_x96": 2**96,
        },
        {
            "pool": POOL,
            "block_number": 20,
            "transaction_index": 3,
            "log_index": 0,
            "sqrt_price_x96": 2**96,
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
        build_v1_market_cap_points(
            registry,
            swaps,
            anchors,
            initial_weth_usd=Decimal("2000"),
            weth_decimals=18,
            usdg_decimals=18,
        )
    )
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("2000000000")
    assert Decimal(rows[1]["market_cap_proxy_usd"]) == Decimal("2500000000")


def test_usdg_quote_is_direct_nominal_usd():
    token = "0x0000000000000000000000000000000000000012"
    registry = [
        {
            "token": token,
            "pair_token": ROBINHOOD_USDG.lower(),
            "pool": POOL,
            "block_number": 10,
            "supply_raw": 100_000 * 10**18,
            "token_decimals": 18,
        }
    ]
    swaps = [
        {
            "pool": POOL,
            "block_number": 20,
            "transaction_index": 1,
            "log_index": 0,
            "sqrt_price_x96": 2**96,
        }
    ]
    rows = list(
        build_v1_market_cap_points(
            registry,
            swaps,
            [],
            initial_weth_usd=Decimal("2000"),
            weth_decimals=18,
            usdg_decimals=18,
        )
    )
    assert rows[0]["pricing_status"] == "priced_usdg_nominal"
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("100000")


def test_summary_keeps_threshold_and_full_maximum():
    rows = [
        {
            "token": TOKEN,
            "pool": POOL,
            "quote_token": ROBINHOOD_WETH.lower(),
            "launch_block": 1,
            "block_number": 2,
            "pricing_status": "priced_weth_usdg",
            "market_cap_proxy_usd": "90000",
        },
        {
            "token": TOKEN,
            "pool": POOL,
            "quote_token": ROBINHOOD_WETH.lower(),
            "launch_block": 1,
            "block_number": 3,
            "pricing_status": "priced_weth_usdg",
            "market_cap_proxy_usd": "750000",
        },
    ]
    summary = summarize_v1_market_caps(rows)
    assert summary[0]["crossed_100k"] is True
    assert Decimal(summary[0]["max_market_cap_proxy_usd"]) == Decimal("750000")
    assert summary[0]["max_market_cap_block"] == 3


def test_stock_quote_uses_causal_oracle_timeline():
    stock = "0x" + "44" * 20
    token = "0x0000000000000000000000000000000000000013"
    registry = [{
        "token": token,
        "pair_token": stock,
        "pool": POOL,
        "block_number": 10,
        "supply_raw": 100_000 * 10**18,
        "token_decimals": 18,
    }]
    points = [{
        "pool": POOL,
        "block_number": 20,
        "transaction_index": 1,
        "log_index": 0,
        "sqrt_price_x96": 2**96,
    }, {
        "pool": POOL,
        "block_number": 20,
        "transaction_index": 3,
        "log_index": 0,
        "sqrt_price_x96": 2**96,
    }]
    updates = [{
        "quote_token": stock,
        "block_number": 20,
        "transaction_index": 2,
        "log_index": 0,
        "usd_price": "300",
    }]
    rows = list(build_v1_market_cap_points(
        registry,
        points,
        [],
        initial_weth_usd=Decimal("2000"),
        weth_decimals=18,
        usdg_decimals=6,
        initial_quote_usd={stock: Decimal("250")},
        quote_usd_updates=updates,
        quote_decimals_by_token={stock: 18},
    ))
    assert rows[0]["pricing_status"] == "priced_chainlink_stock_token"
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("25000000")
    assert Decimal(rows[1]["market_cap_proxy_usd"]) == Decimal("30000000")
