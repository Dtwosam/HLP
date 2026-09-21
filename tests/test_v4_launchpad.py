from decimal import Decimal

import pytest

from hlp.data.v4_launchpad import (
    build_v4_launchpad_market_cap_points,
    merge_v4_launchpad_market_cap_summaries,
    summarize_v4_launchpad_market_caps,
)


TOKEN="0x"+"11"*20
QUOTE="0x"+"22"*20
POOL_ID="0x"+"33"*32
REGISTRY=[{
    "venue":"example",
    "token":TOKEN,
    "quote_token":QUOTE,
    "supply_raw":10**18,
    "pool_id":POOL_ID,
    "currency0":TOKEN,
    "currency1":QUOTE,
}]


def point(*, txi=1, logi=0):
    return {
        "pool_id":POOL_ID,
        "sqrt_price_x96":2**96,
        "block_number":10,
        "transaction_hash":"0x"+"aa"*32,
        "transaction_index":txi,
        "log_index":logi,
    }


def test_raw_v4_market_cap_token_decimals_cancel():
    rows=build_v4_launchpad_market_cap_points(
        REGISTRY,[point()],[],[],
        initial_weth_usd=Decimal("2000"),
        quote_decimals={QUOTE:18},
        initial_quote_usd={QUOTE:Decimal("2")},
    )
    assert Decimal(rows[0]["market_cap_quote"]) == Decimal(1)
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal(2)
    assert summarize_v4_launchpad_market_caps(rows)[0]["crossed_100k"] is False


def test_v4_swap_requires_initialize():
    with pytest.raises(ValueError):
        build_v4_launchpad_market_cap_points(
            REGISTRY,[],[point()],[],
            initial_weth_usd=Decimal("2000"),
            quote_decimals={QUOTE:18},
            initial_quote_usd={QUOTE:Decimal("2")},
        )




def test_v4_swap_can_use_recorded_registry_initialize_for_later_shard():
    registry = [{
        **REGISTRY[0],
        "initialize_block": 10,
        "initialize_transaction_index": 1,
        "initialize_log_index": 0,
    }]
    swap = {
        **point(txi=2, logi=0),
        "block_number": 11,
        "liquidity": 1_000 * 10**18,
    }
    rows = build_v4_launchpad_market_cap_points(
        registry,
        [],
        [swap],
        [],
        initial_weth_usd=Decimal("2000"),
        quote_decimals={QUOTE: 18},
        initial_quote_usd={QUOTE: Decimal("2")},
        allow_registry_initialization=True,
    )

    assert len(rows) == 1
    assert rows[0]["event_type"] == "v4_swap"
    assert rows[0]["block_number"] == 11


def test_v4_recorded_registry_initialize_still_rejects_preinitialize_swap():
    registry = [{
        **REGISTRY[0],
        "initialize_block": 10,
        "initialize_transaction_index": 2,
        "initialize_log_index": 0,
    }]
    with pytest.raises(ValueError, match="does not follow recorded Initialize"):
        build_v4_launchpad_market_cap_points(
            registry,
            [],
            [point(txi=1, logi=0)],
            [],
            initial_weth_usd=Decimal("2000"),
            quote_decimals={QUOTE: 18},
            initial_quote_usd={QUOTE: Decimal("2")},
            allow_registry_initialization=True,
        )




def test_v4_market_cap_uses_causal_supply_delta_before_swap():
    registry = [{
        **REGISTRY[0],
        "initialize_block": 10,
        "initialize_transaction_index": 1,
        "initialize_log_index": 0,
    }]
    init = point(txi=1, logi=0)
    swap = {
        **point(txi=2, logi=0),
        "block_number": 11,
        "liquidity": 1_000 * 10**18,
    }
    supply_deltas = [{
        "token": TOKEN,
        "supply_delta_raw": -10**17,
        "block_number": 11,
        "transaction_hash": "0x" + "bb" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }]
    rows = build_v4_launchpad_market_cap_points(
        registry,
        [init],
        [swap],
        [],
        initial_weth_usd=Decimal("2000"),
        quote_decimals={QUOTE: 18},
        initial_quote_usd={QUOTE: Decimal("2")},
        supply_delta_rows=supply_deltas,
    )

    assert rows[0]["supply_raw"] == 10**18
    assert rows[1]["supply_raw"] == 9 * 10**17
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("2")
    assert Decimal(rows[1]["market_cap_proxy_usd"]) == Decimal("1.8")



def test_v4_swap_emits_comparable_active_quote_liquidity():
    init = point(txi=1, logi=0)
    swap = {
        **point(txi=2, logi=0),
        "liquidity": 1_000 * 10**18,
    }
    rows = build_v4_launchpad_market_cap_points(
        REGISTRY,
        [init],
        [swap],
        [],
        initial_weth_usd=Decimal("2000"),
        quote_decimals={QUOTE: 18},
        initial_quote_usd={QUOTE: Decimal("2")},
    )

    assert rows[0]["active_quote_liquidity_usd"] is None
    assert rows[1]["market_id"] == POOL_ID
    assert rows[1]["quote_decimals"] == 18
    assert rows[1]["token_is_currency0"] is True
    assert Decimal(rows[1]["active_quote_liquidity_usd"]) == Decimal("2000")


def test_merge_v4_launchpad_summaries_is_shard_invariant():
    rows = merge_v4_launchpad_market_cap_summaries([
        {
            "token": TOKEN,
            "venue": "example",
            "pool_id": POOL_ID,
            "quote_token": QUOTE,
            "price_points": 2,
            "priced_points": 2,
            "max_market_cap_proxy_usd": "100",
            "max_market_cap_block": 20,
            "crossed_100k": False,
        },
        {
            "token": TOKEN,
            "venue": "example",
            "pool_id": POOL_ID,
            "quote_token": QUOTE,
            "price_points": 3,
            "priced_points": 3,
            "max_market_cap_proxy_usd": "200",
            "max_market_cap_block": 30,
            "crossed_100k": True,
        },
    ])
    assert len(rows) == 1
    assert rows[0]["price_points"] == 5
    assert rows[0]["priced_points"] == 5
    assert rows[0]["max_market_cap_proxy_usd"] == "200"
    assert rows[0]["max_market_cap_block"] == 30
    assert rows[0]["crossed_100k"] is True


def test_merge_v4_launchpad_summaries_uses_earliest_equal_max():
    rows = merge_v4_launchpad_market_cap_summaries([
        {
            "token": TOKEN,
            "venue": "example",
            "pool_id": POOL_ID,
            "quote_token": QUOTE,
            "price_points": 1,
            "priced_points": 1,
            "max_market_cap_proxy_usd": "200",
            "max_market_cap_block": 30,
            "crossed_100k": False,
        },
        {
            "token": TOKEN,
            "venue": "example",
            "pool_id": POOL_ID,
            "quote_token": QUOTE,
            "price_points": 1,
            "priced_points": 1,
            "max_market_cap_proxy_usd": "200",
            "max_market_cap_block": 25,
            "crossed_100k": False,
        },
    ])
    assert rows[0]["max_market_cap_block"] == 25

