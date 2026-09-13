import pytest

from hlp.data.quote_v4_routes import build_v4_route_usd_updates


TOKEN = "0x" + "11" * 20
POOL_ID = "0x" + "aa" * 32
POOL_MANAGER = "0x" + "55" * 20


def _route():
    return {
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "route_type": "uniswap_v4_direct_usdg",
        "pool_manager": POOL_MANAGER,
        "pool_id": POOL_ID,
        "token_is_token0": True,
        "activation_block": 100,
    }


def _swap(*, liquidity, log_index):
    return {
        "pool_manager": POOL_MANAGER,
        "pool_id": POOL_ID,
        "sqrt_price_x96": 2**96,
        "liquidity": liquidity,
        "block_number": 101,
        "transaction_hash": "0x" + f"{log_index + 1:02x}" * 32,
        "transaction_index": 1,
        "log_index": log_index,
    }


def test_zero_post_swap_liquidity_still_emits_observed_close():
    updates = list(
        build_v4_route_usd_updates(
            [_route()],
            [
                _swap(liquidity=100, log_index=0),
                _swap(liquidity=0, log_index=1),
            ],
        )
    )

    assert len(updates) == 2
    assert updates[-1]["transaction_hash"] == "0x" + "02" * 32
    assert updates[-1]["usd_price"] == "1000000000000"


def test_negative_v4_liquidity_is_rejected_as_malformed_input():
    with pytest.raises(ValueError, match="cannot be negative"):
        list(
            build_v4_route_usd_updates(
                [_route()],
                [_swap(liquidity=-1, log_index=0)],
            )
        )
