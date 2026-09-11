from decimal import Decimal

import pytest

from hlp.data.v3_launchpad import (
    build_v3_launchpad_market_cap_points,
    summarize_v3_launchpad_market_caps,
)


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20


REGISTRY = [{
    "venue": "example",
    "token": TOKEN,
    "quote_token": QUOTE,
    "pool": POOL,
    "supply_raw": 10**18,
}]


def point(kind="init", *, txi=1, logi=0):
    return {
        "pool": POOL,
        "sqrt_price_x96": 2**96,
        "block_number": 10,
        "transaction_hash": "0x" + "aa" * 32,
        "transaction_index": txi,
        "log_index": logi,
    }


def test_raw_v3_market_cap_token_decimals_cancel():
    rows = build_v3_launchpad_market_cap_points(
        REGISTRY,
        [point()],
        [],
        [],
        initial_weth_usd=Decimal("2000"),
        quote_decimals={QUOTE: 18},
        initial_quote_usd={QUOTE: Decimal("2")},
    )
    assert len(rows) == 1
    assert Decimal(rows[0]["market_cap_quote"]) == Decimal(1)
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal(2)
    assert summarize_v3_launchpad_market_caps(rows)[0]["crossed_100k"] is False


def test_v3_swap_requires_initialize():
    with pytest.raises(ValueError):
        build_v3_launchpad_market_cap_points(
            REGISTRY,
            [],
            [point("swap")],
            [],
            initial_weth_usd=Decimal("2000"),
            quote_decimals={QUOTE: 18},
            initial_quote_usd={QUOTE: Decimal("2")},
        )
