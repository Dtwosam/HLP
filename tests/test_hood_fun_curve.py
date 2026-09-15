from decimal import Decimal

from hlp.data.hood_fun_curve import (
    build_hood_fun_curve_market_cap_points,
    summarize_hood_fun_curve_market_caps,
)
from hlp.data.types import HoodFunEvent


TOKEN = "0x" + "11" * 20


def event(kind, *, vq, vt, logi=0):
    return HoodFunEvent(
        event_type=kind,
        token=TOKEN,
        actor="0x" + "22" * 20,
        is_buy=True if kind == "trade" else None,
        quote_amount_raw=10**16 if kind == "trade" else None,
        token_amount_raw=10**18 if kind == "trade" else None,
        fee_raw=10**14 if kind == "trade" else None,
        virtual_quote_raw=vq,
        virtual_token_raw=vt,
        curve_inventory_raw=800_000_000 * 10**18 if kind == "token_created" else None,
        name="Cat" if kind == "token_created" else None,
        symbol="CAT" if kind == "token_created" else None,
        metadata_uri=None,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=logi,
    )


REGISTRY = [{
    "token": TOKEN,
    "supply_raw": 1_000_000_000 * 10**18,
}]


def test_hood_fun_market_cap_uses_virtual_reserve_ratio():
    rows = build_hood_fun_curve_market_cap_points(
        [
            event(
                "token_created",
                vq=2_810_000_000_000_000_000,
                vt=1_145_000_000 * 10**18,
            )
        ],
        REGISTRY,
        [],
        initial_weth_usd=Decimal("2000"),
    )
    expected_eth = (
        Decimal("2.81")
        / Decimal("1145000000")
        * Decimal("1000000000")
    )
    assert Decimal(rows[0]["market_cap_quote"]) == expected_eth
    assert Decimal(rows[0]["market_cap_proxy_usd"]) == expected_eth * Decimal("2000")


def test_hood_fun_summary_flags_100k():
    rows = build_hood_fun_curve_market_cap_points(
        [
            event(
                "token_created",
                vq=100 * 10**18,
                vt=1_000_000_000 * 10**18,
            )
        ],
        REGISTRY,
        [],
        initial_weth_usd=Decimal("2000"),
    )
    assert summarize_hood_fun_curve_market_caps(rows)[0]["crossed_100k"] is True
