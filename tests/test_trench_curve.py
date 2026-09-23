from decimal import Decimal

import pytest

from hlp.data.trench_curve import (
    build_trench_curve_market_cap_points,
    summarize_trench_curve_market_caps,
)
from hlp.data.types import TrenchEvent


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20


def sync(token=TOKEN, vq=10**18, vt=10**27):
    return TrenchEvent(
        event_type="sync",
        token=token,
        actor=None,
        curve=None,
        quote_token=None,
        amount_raw=None,
        quote_amount_raw=None,
        protocol_fee_raw=None,
        extra_fee_raw=None,
        extra_fee_receiver=None,
        extra_fee_rate=None,
        real_quote_reserves_raw=1,
        real_token_reserves_raw=2,
        virtual_quote_raw=vq,
        virtual_token_raw=vt,
        name=None,
        symbol=None,
        token_uri=None,
        timestamp=None,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=0,
    )


REGISTRY = [
    {
        "token": TOKEN,
        "curve": "0x" + "22" * 20,
        "quote_token": ZERO,
        "launch_block": 9,
        "launch_transaction_index": 1,
        "launch_log_index": 0,
        "supply_raw": 1_000_000_000 * 10**18,
        "token_decimals": 18,
        "quote_decimals": 18,
    }
]


def test_trench_sync_market_cap_uses_virtual_reserve_ratio():
    # 1 ETH / 1B tokens = 1e-9 ETH/token. At $2k ETH => $2k mcap.
    rows = list(
        build_trench_curve_market_cap_points(
            [sync()],
            REGISTRY,
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert len(rows) == 1
    assert Decimal(rows[0]["quote_per_token"]) == Decimal("1e-9")
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("2000")
    assert summarize_trench_curve_market_caps(rows)[0]["crossed_100k"] is False


def test_trench_sync_fails_for_unregistered_carry_in():
    with pytest.raises(ValueError):
        list(
            build_trench_curve_market_cap_points(
                [sync(token="0x" + "44" * 20)],
                REGISTRY,
                [],
                initial_weth_usd=Decimal("2000"),
            )
        )


def test_trench_sync_rejects_snapshot_before_recorded_launch():
    future_registry = [{
        **REGISTRY[0],
        "launch_block": 10,
        "launch_transaction_index": 2,
        "launch_log_index": 1,
    }]
    with pytest.raises(ValueError, match="precedes recorded launch"):
        list(
            build_trench_curve_market_cap_points(
                [sync()],
                future_registry,
                [],
                initial_weth_usd=Decimal("2000"),
            )
        )




def test_trench_market_cap_uses_registry_supply_not_fixed_constant():
    registry = [{
        **REGISTRY[0],
        "supply_raw": 500_000_000 * 10**18,
    }]
    rows = list(
        build_trench_curve_market_cap_points(
            [sync()],
            registry,
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == Decimal("1000")


def test_trench_market_cap_respects_non18_decimals():
    registry = [{
        **REGISTRY[0],
        "supply_raw": 2_000_000 * 10**9,
        "token_decimals": 9,
        "quote_decimals": 6,
    }]
    event = sync(vq=2_000_000, vt=1_000_000_000)
    rows = list(
        build_trench_curve_market_cap_points(
            [event],
            registry,
            [],
            initial_weth_usd=Decimal("2000"),
            initial_quote_usd={ZERO: Decimal("1")},
        )
    )
    assert Decimal(rows[0]["quote_per_token"]) == Decimal("2")
    assert Decimal(rows[0]["market_cap_quote"]) == Decimal("4000000")


def test_trench_sync_rejects_snapshot_after_recorded_limit_reach():
    limited_registry = [{
        **REGISTRY[0],
        "limit_reach_block": 10,
        "limit_reach_transaction_index": 1,
        "limit_reach_log_index": 9,
    }]
    with pytest.raises(ValueError, match="follows recorded LimitReach"):
        list(
            build_trench_curve_market_cap_points(
                [sync()],
                limited_registry,
                [],
                initial_weth_usd=Decimal("2000"),
            )
        )


def test_trench_sync_allows_snapshot_before_recorded_limit_reach():
    limited_registry = [{
        **REGISTRY[0],
        "limit_reach_block": 10,
        "limit_reach_transaction_index": 3,
        "limit_reach_log_index": 0,
    }]
    rows = list(
        build_trench_curve_market_cap_points(
            [sync()],
            limited_registry,
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )
    assert len(rows) == 1

