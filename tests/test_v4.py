from decimal import Decimal

from hlp.config import ROBINHOOD_WETH
from hlp.data.v4 import (
    build_v2_graduation_seed_points,
    build_v2_v4_market_cap_points,
)


TOKEN = "0x0000000000000000000000000000000000000011"
POOL_ID = "0x" + "aa" * 32


def registry():
    return [
        {
            "token": TOKEN,
            "curve": "0x" + "22" * 20,
            "pair_token": ROBINHOOD_WETH.lower(),
            "block_number": 10,
            "supply_raw": 1_000_000 * 10**18,
            "token_decimals": 18,
            "quote_decimals": 18,
        }
    ]


def test_graduation_seed_price_uses_emitted_amounts():
    graduations = [
        {
            "token": TOKEN,
            "position_id": 1,
            "token_amount": 1000 * 10**18,
            "pair_token_amount": 1000 * 10**18,
            "block_number": 20,
            "transaction_hash": "0x" + "bb" * 32,
            "transaction_index": 1,
            "log_index": 0,
        }
    ]
    rows = list(
        build_v2_graduation_seed_points(
            registry(),
            graduations,
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert Decimal(rows[0]["quote_per_token"]) == Decimal(1)
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("2000000000")
    assert rows[0]["phase"] == "v4_seed"


def test_v4_swap_price_uses_pool_registration():
    registrations = [
        {
            "pool_id": POOL_ID,
            "token": TOKEN,
            "quote_token": ROBINHOOD_WETH.lower(),
            "creator": "0x" + "44" * 20,
            "block_number": 20,
            "transaction_hash": "0x" + "cc" * 32,
            "transaction_index": 2,
            "log_index": 0,
        }
    ]
    swaps = [
        {
            "pool_id": POOL_ID,
            "pool_manager": "0x" + "55" * 20,
            "sender": "0x" + "66" * 20,
            "amount0": 1,
            "amount1": -1,
            "sqrt_price_x96": 2**96,
            "liquidity": 100,
            "tick": 0,
            "fee": 0,
            "block_number": 21,
            "transaction_hash": "0x" + "dd" * 32,
            "transaction_index": 1,
            "log_index": 0,
        }
    ]
    rows = list(
        build_v2_v4_market_cap_points(
            registry(),
            registrations,
            swaps,
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert Decimal(rows[0]["quote_per_token"]) == Decimal(1)
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("2000000000")
    assert rows[0]["phase"] == "v4"
