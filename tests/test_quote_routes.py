from types import SimpleNamespace

import hlp.data.quote_routes as routes
from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH


TOKEN = "0x" + "11" * 20
POOL = "0x" + "22" * 20


class Rpc:
    def get_code(self, pool, block):
        return "0x6000"


def quote_rows():
    return [
        {
            "quote_token": ROBINHOOD_USDG.lower(),
            "quote_decimals": 6,
            "pricing_status": "priced_usdg_nominal",
        },
        {
            "quote_token": ROBINHOOD_WETH.lower(),
            "quote_decimals": 18,
            "pricing_status": "priced_weth_usdg",
        },
        {
            "quote_token": TOKEN,
            "quote_decimals": 18,
            "pricing_status": "missing_chainlink_feed",
            "symbol": "TEST",
            "first_launch_block": 100,
            "launches": 5,
            "versions": {"v2": 5},
        },
    ]


def test_v3_route_audit_skips_weth_after_causal_usdg_route(monkeypatch):
    calls = []

    def get_pool(rpc, factory, *, token_a, token_b, fee, block):
        calls.append((token_b, fee))
        if token_b == ROBINHOOD_USDG.lower() and fee == 3000:
            return POOL
        return None

    monkeypatch.setattr(routes, "read_v3_factory_pool", get_pool)
    monkeypatch.setattr(
        routes,
        "read_v3_pool_static",
        lambda rpc, pool, block: SimpleNamespace(
            token0=TOKEN,
            token1=ROBINHOOD_USDG.lower(),
        ),
    )
    monkeypatch.setattr(
        routes,
        "read_v3_slot0",
        lambda rpc, pool, block: SimpleNamespace(sqrt_price_x96=2**96),
    )
    monkeypatch.setattr(routes, "read_v3_liquidity", lambda rpc, pool, block: 100)

    rows = routes.audit_unpriced_v3_quote_routes(Rpc(), quote_rows())

    assert rows[0]["v3_causal_ready"] is True
    assert rows[0]["direct_usdg_ready"] is True
    assert rows[0]["searched_anchors"] == [ROBINHOOD_USDG.lower()]
    assert all(anchor != ROBINHOOD_WETH.lower() for anchor, _ in calls)
