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
