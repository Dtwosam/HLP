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



def test_select_v3_route_prefers_usdg_then_highest_liquidity():
    audit = [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 100,
        "causal_state_block": 99,
        "launches": 5,
        "versions": {"v2": 5},
        "v3_candidates": [
            {
                "anchor_token": ROBINHOOD_WETH.lower(),
                "fee": 500,
                "pool": "0x" + "30" * 20,
                "active_liquidity": 999999,
                "quote_per_token": "0.1",
                "quote_usd": "2000",
                "token_price_usd": "200",
                "causal_ready": True,
            },
            {
                "anchor_token": ROBINHOOD_USDG.lower(),
                "fee": 3000,
                "pool": "0x" + "31" * 20,
                "active_liquidity": 100,
                "quote_per_token": "201",
                "quote_usd": "1",
                "token_price_usd": "201",
                "causal_ready": True,
            },
            {
                "anchor_token": ROBINHOOD_USDG.lower(),
                "fee": 500,
                "pool": "0x" + "32" * 20,
                "active_liquidity": 200,
                "quote_per_token": "200",
                "quote_usd": "1",
                "token_price_usd": "200",
                "causal_ready": True,
            },
        ],
    }]

    selected = routes.select_v3_quote_routes(audit)

    assert len(selected) == 1
    assert selected[0]["pool"] == "0x" + "32" * 20
    assert selected[0]["route_type"] == "uniswap_v3_direct_usdg"
    assert selected[0]["initial_usd_price"] == "200"


def test_v3_route_initial_state_matches_quote_timeline_shape():
    states = routes.build_v3_route_initial_usd_states([{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "route_type": "uniswap_v3_direct_usdg",
        "pool": POOL,
        "causal_state_block": 99,
        "activation_block": 100,
        "initial_usd_price": "200",
    }])

    assert states == [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "pricing_source": "uniswap_v3_direct_usdg",
        "source_pool": POOL,
        "block_number": 99,
        "activation_block": 100,
        "usd_price": "200",
    }]
