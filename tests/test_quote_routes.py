from types import SimpleNamespace

import hlp.data.quote_routes as routes
from hlp.config import (
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    SUSHISWAP_V3_FACTORY,
)


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
        assert block == "latest"
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



def test_delayed_weth_route_discovers_first_known_pool_swap(monkeypatch):
    calls = []

    class DelayedRpc:
        def iter_logs_chunked(
            self,
            start,
            end,
            *,
            address,
            topics,
            chunk_size,
            min_chunk_size,
        ):
            calls.append(
                {
                    "start": start,
                    "end": end,
                    "address": address,
                    "topics": topics,
                    "chunk_size": chunk_size,
                    "min_chunk_size": min_chunk_size,
                }
            )
            return iter([object()])

    audit = [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 100,
        "launches": 5,
        "versions": {"v2": 5},
        "v3_causal_ready": False,
        "v3_candidates": [{
            "anchor_token": ROBINHOOD_WETH.lower(),
            "pool": POOL,
            "fee": 3000,
        }],
    }]
    monkeypatch.setattr(
        routes,
        "decode_v3_swap",
        lambda raw: SimpleNamespace(
            pool=POOL,
            liquidity=123,
            sqrt_price_x96=2**96,
            block_number=150,
            transaction_index=2,
            log_index=3,
        ),
    )
    monkeypatch.setattr(
        routes,
        "read_v3_pool_static",
        lambda rpc, pool, block: SimpleNamespace(
            token0=TOKEN,
            token1=ROBINHOOD_WETH.lower(),
        ),
    )

    rows = routes.discover_delayed_v3_weth_routes(
        DelayedRpc(),
        audit,
        from_block=120,
        to_block=999,
        max_forward_blocks=200,
    )

    assert len(rows) == 1
    assert rows[0]["searched_from_block"] == 120
    assert rows[0]["searched_to_block"] == 319
    assert rows[0]["candidate_pools"] == [POOL]
    assert rows[0]["delayed_route_ready"] is True
    route = rows[0]["route"]
    assert route["activation_block"] == 150
    assert route["activation_transaction_index"] == 2
    assert route["activation_log_index"] == 3
    assert route["anchor_token"] == ROBINHOOD_WETH.lower()
    assert route["route_type"] == "uniswap_v3_direct_weth_delayed"
    assert route["first_observed_quote_per_token"] == "1"
    assert route["first_observed_usd_price"] is None
    assert calls == [{
        "start": 120,
        "end": 319,
        "address": [POOL],
        "topics": [routes.V3_SWAP_TOPIC],
        "chunk_size": 2_000,
        "min_chunk_size": 25,
    }]


def test_delayed_weth_route_skips_assets_without_weth_candidates():
    audit = [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 100,
        "launches": 5,
        "versions": {"v2": 5},
        "v3_causal_ready": False,
        "v3_candidates": [{
            "anchor_token": ROBINHOOD_USDG.lower(),
            "pool": POOL,
            "fee": 3000,
        }],
    }]

    rows = routes.discover_delayed_v3_weth_routes(
        object(),
        audit,
        from_block=100,
        to_block=200,
    )

    assert rows[0]["candidate_pools"] == []
    assert rows[0]["delayed_route_ready"] is False
    assert rows[0]["route"] is None


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



def test_delayed_route_updates_do_not_activate_before_first_swap():
    from decimal import Decimal

    delayed = {
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "activation_block": 100,
        "activation_transaction_index": 3,
        "activation_log_index": 5,
        "pool": POOL,
        "anchor_token": ROBINHOOD_USDG.lower(),
        "anchor_decimals": 6,
        "route_type": "uniswap_v3_direct_usdg_delayed",
    }
    events = [
        {
            "pool": POOL,
            "sqrt_price_x96": 2**96,
            "block_number": 100,
            "transaction_hash": "0x" + "11" * 32,
            "transaction_index": 2,
            "log_index": 7,
        },
        {
            "pool": POOL,
            "sqrt_price_x96": 2**96,
            "block_number": 100,
            "transaction_hash": "0x" + "22" * 32,
            "transaction_index": 3,
            "log_index": 5,
        },
    ]
    rows = list(routes.build_v3_route_usd_updates(
        [delayed],
        events,
        [],
        initial_weth_usd=Decimal("2000"),
    ))
    assert len(rows) == 1
    assert rows[0]["transaction_hash"] == "0x" + "22" * 32


def test_delayed_routes_have_no_pre_activation_state():
    rows = routes.build_v3_route_initial_usd_states([{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "route_type": "uniswap_v3_direct_usdg_delayed",
        "pool": POOL,
        "activation_block": 100,
        "causal_state_block": None,
    }])
    assert rows == []



def test_merge_v3_quote_routes_adds_ready_delayed_routes():
    causal = [{
        "quote_token": "0x" + "01" * 20,
        "activation_block": 10,
    }]
    delayed = [{
        "delayed_route_ready": True,
        "route": {
            "quote_token": "0x" + "02" * 20,
            "activation_block": 20,
        },
    }]
    rows = routes.merge_v3_quote_routes(causal, delayed)
    assert [row["activation_block"] for row in rows] == [10, 20]



def test_v3_route_audit_preserves_non_uniswap_factory(monkeypatch):
    def get_pool(rpc, factory, *, token_a, token_b, fee, block):
        assert factory == SUSHISWAP_V3_FACTORY.lower()
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

    audit = routes.audit_unpriced_v3_quote_routes(
        Rpc(),
        quote_rows(),
        factory=SUSHISWAP_V3_FACTORY,
    )
    selected = routes.select_v3_quote_routes(audit)

    assert audit[0]["factory"] == SUSHISWAP_V3_FACTORY.lower()
    assert audit[0]["venue"] == "sushiswap_v3"
    assert selected[0]["factory"] == SUSHISWAP_V3_FACTORY.lower()
    assert selected[0]["route_type"] == "sushiswap_v3_direct_usdg"



def test_v3_route_audit_does_not_require_anchor_rows(monkeypatch):
    residual = [quote_rows()[-1]]

    def get_pool(rpc, factory, *, token_a, token_b, fee, block):
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

    rows = routes.audit_unpriced_v3_quote_routes(Rpc(), residual)

    assert rows[0]["v3_causal_ready"] is True
    assert rows[0]["direct_usdg_ready"] is True



def test_direct_usdg_route_updates_do_not_require_weth_anchor():
    from decimal import Decimal

    route = {
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "activation_block": 100,
        "pool": POOL,
        "anchor_token": ROBINHOOD_USDG.lower(),
        "anchor_decimals": 6,
        "route_type": "uniswap_v3_direct_usdg",
    }
    rows = list(routes.build_v3_route_usd_updates(
        [route],
        [{
            "pool": POOL,
            "sqrt_price_x96": 2**96,
            "block_number": 100,
            "transaction_hash": "0x" + "77" * 32,
            "transaction_index": 1,
            "log_index": 0,
        }],
    ))
    assert len(rows) == 1
    assert Decimal(rows[0]["anchor_usd"]) == Decimal(1)


def test_delayed_weth_route_composes_with_event_ordered_usd_anchor():
    from decimal import Decimal

    route = {
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "activation_block": 100,
        "activation_transaction_index": 1,
        "activation_log_index": 0,
        "pool": POOL,
        "anchor_token": ROBINHOOD_WETH.lower(),
        "anchor_decimals": 18,
        "route_type": "uniswap_v3_direct_weth_delayed",
    }
    rows = list(
        routes.build_v3_route_usd_updates(
            [route],
            [{
                "pool": POOL,
                "sqrt_price_x96": 2**96,
                "block_number": 100,
                "transaction_hash": "0x" + "88" * 32,
                "transaction_index": 1,
                "log_index": 0,
            }],
            [],
            initial_weth_usd=Decimal("2000"),
        )
    )

    assert len(rows) == 1
    assert rows[0]["pricing_source"] == "uniswap_v3_direct_weth_delayed"
    assert Decimal(rows[0]["quote_per_token"]) == Decimal(1)
    assert Decimal(rows[0]["anchor_usd"]) == Decimal(2000)
    assert Decimal(rows[0]["usd_price"]) == Decimal(2000)


def test_weth_route_still_requires_anchor():
    route = {
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "activation_block": 100,
        "pool": POOL,
        "anchor_token": ROBINHOOD_WETH.lower(),
        "anchor_decimals": 18,
        "route_type": "uniswap_v3_direct_weth",
    }
    try:
        list(routes.build_v3_route_usd_updates([route], []))
    except ValueError as exc:
        assert "initial WETH/USD" in str(exc)
    else:
        raise AssertionError("WETH route without USD anchor must fail closed")
