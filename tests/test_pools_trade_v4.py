from decimal import Decimal

from hlp.data.pools_trade_v4 import (
    build_pools_trade_v4_market_cap_points,
    summarize_pools_trade_market_caps,
)


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20
POOL_ID = "0x" + "33" * 32


def test_raw_v4_market_cap_does_not_need_token_decimals():
    registry = [{
        "token": TOKEN,
        "quote_token": ZERO,
        "supply_raw": 10**18,
        "pool_id": POOL_ID,
        "currency0": TOKEN,
        "currency1": ZERO,
    }]
    init = [{
        "pool_id": POOL_ID,
        "sqrt_price_x96": 2**96,
        "block_number": 10,
        "transaction_hash": "0x" + "aa" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }]
    rows = build_pools_trade_v4_market_cap_points(
        registry,
        init,
        [],
        [],
        initial_weth_usd=Decimal("2000"),
        quote_decimals={ZERO: 18},
    )
    assert len(rows) == 1
    # raw quote/token ratio = 1; supply_raw=1e18; quote decimals=18 => 1 ETH FDV.
    assert Decimal(rows[0]["market_cap_quote"]) == Decimal(1)
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal(2000)
    assert summarize_pools_trade_market_caps(rows)[0]["crossed_100k"] is False


def test_v4_swap_requires_initialize_first():
    registry = [{
        "token": TOKEN,
        "quote_token": ZERO,
        "supply_raw": 10**18,
        "pool_id": POOL_ID,
        "currency0": TOKEN,
        "currency1": ZERO,
    }]
    swap = [{
        "pool_id": POOL_ID,
        "sqrt_price_x96": 2**96,
        "block_number": 10,
        "transaction_hash": "0x" + "bb" * 32,
        "transaction_index": 2,
        "log_index": 0,
    }]
    import pytest
    with pytest.raises(ValueError):
        build_pools_trade_v4_market_cap_points(
            registry,
            [],
            swap,
            [],
            initial_weth_usd=Decimal("2000"),
            quote_decimals={ZERO: 18},
        )
