from types import SimpleNamespace

import pytest

from hlp.config import ROBINHOOD_USDG
from hlp.data.quote_v4_routes import (
    _address_topic,
    build_v4_route_initial_usd_states,
    build_v4_route_usd_updates,
    extend_v4_usdg_routes,
    probe_v4_usdg_routes,
    select_v4_quote_routes,
    validate_v4_usdg_pool_candidate,
)
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC


TOKEN = "0x" + "11" * 20
POOL_ID = "0x" + "aa" * 32


def test_address_topic_pads_to_bytes32():
    topic = _address_topic(TOKEN)
    assert len(topic) == 66
    assert topic.endswith(TOKEN[2:])


def test_probe_with_no_initialize_is_explicitly_unresolved():
    calls = []

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            calls.append((start, end, kwargs))
            return iter(())

    rows = probe_v4_usdg_routes(
        Rpc(),
        [{
            "pricing_status": "missing_chainlink_feed",
            "quote_token": TOKEN,
            "symbol": "TEST",
            "quote_decimals": 18,
            "first_launch_block": 1000,
            "launches": 3,
            "versions": {"v2": 3},
        }],
        snapshot_head=2000,
        lookaround_blocks=100,
    )

    assert len(rows) == 1
    assert rows[0]["search_from_block"] == 900
    assert rows[0]["search_to_block"] == 1100
    assert rows[0]["initialize_events"] == 0
    assert rows[0]["causal_route_ready"] is False
    assert rows[0]["delayed_route_ready"] is False
    topics = calls[0][2]["topics"]
    assert topics[0] == V4_INITIALIZE_TOPIC
    assert topics[1] is None
    assert topics[2] in {_address_topic(TOKEN), _address_topic(ROBINHOOD_USDG)}
    assert topics[3] in {_address_topic(TOKEN), _address_topic(ROBINHOOD_USDG)}



def test_select_v4_causal_route_prefers_latest_swap_over_liquidity():
    older = {
        "pool_id": "0x" + "01" * 32,
        "initialize": {
            "pool_manager": "0x" + "55" * 20,
            "pool_id": "0x" + "01" * 32,
            "currency0": TOKEN,
            "currency1": ROBINHOOD_USDG.lower(),
            "fee": 3000,
            "tick_spacing": 60,
            "hooks": "0x" + "00" * 20,
        },
        "latest_pre_use_swap": {
            "pool_id": "0x" + "01" * 32,
            "block_number": 90,
            "transaction_hash": "0x" + "10" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "liquidity": 1_000_000,
            "quote_per_token": "200",
            "usd_price": "200",
        },
        "first_post_use_swap": None,
    }
    newer = {
        "pool_id": "0x" + "02" * 32,
        "initialize": {
            "pool_manager": "0x" + "55" * 20,
            "pool_id": "0x" + "02" * 32,
            "currency0": TOKEN,
            "currency1": ROBINHOOD_USDG.lower(),
            "fee": 500,
            "tick_spacing": 10,
            "hooks": "0x" + "00" * 20,
        },
        "latest_pre_use_swap": {
            "pool_id": "0x" + "02" * 32,
            "block_number": 99,
            "transaction_hash": "0x" + "20" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "liquidity": 100,
            "quote_per_token": "201",
            "usd_price": "201",
        },
        "first_post_use_swap": None,
    }
    probe = [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 100,
        "launches": 5,
        "versions": {"v2": 5},
        "causal_route_ready": True,
        "delayed_route_ready": False,
        "selected_causal_candidate": newer,
        "selected_delayed_candidate": None,
    }]
    route = select_v4_quote_routes(probe)[0]
    assert route["pool_id"] == newer["pool_id"]
    assert route["causal_state_block"] == 99
    assert route["activation_block"] == 100
    assert route["initial_usd_price"] == "201"


def test_delayed_v4_route_has_no_initial_state_and_activates_on_swap():
    pool_manager = "0x" + "55" * 20
    candidate = {
        "pool_id": POOL_ID,
        "initialize": {
            "pool_manager": pool_manager,
            "pool_id": POOL_ID,
            "currency0": TOKEN,
            "currency1": ROBINHOOD_USDG.lower(),
            "fee": 500,
            "tick_spacing": 10,
            "hooks": "0x" + "00" * 20,
        },
        "latest_pre_use_swap": None,
        "first_post_use_swap": {
            "pool_id": POOL_ID,
            "block_number": 101,
            "transaction_hash": "0x" + "30" * 32,
            "transaction_index": 2,
            "log_index": 4,
            "liquidity": 100,
            "quote_per_token": "1",
            "usd_price": "1",
        },
    }
    route = select_v4_quote_routes([{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 100,
        "launches": 5,
        "versions": {"v2": 5},
        "causal_route_ready": False,
        "delayed_route_ready": True,
        "selected_causal_candidate": None,
        "selected_delayed_candidate": candidate,
    }])[0]
    assert build_v4_route_initial_usd_states([route]) == []

    events = [
        {
            "pool_manager": pool_manager,
            "pool_id": POOL_ID,
            "sqrt_price_x96": 2**96,
            "liquidity": 100,
            "block_number": 101,
            "transaction_hash": "0x" + "31" * 32,
            "transaction_index": 1,
            "log_index": 9,
        },
        {
            "pool_manager": pool_manager,
            "pool_id": POOL_ID,
            "sqrt_price_x96": 2**96,
            "liquidity": 100,
            "block_number": 101,
            "transaction_hash": "0x" + "32" * 32,
            "transaction_index": 2,
            "log_index": 4,
        },
    ]
    updates = list(build_v4_route_usd_updates([route], events))
    assert len(updates) == 1
    assert updates[0]["transaction_hash"] == "0x" + "32" * 32



def test_extend_v4_routes_starts_after_prior_search_end():
    calls = []

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            calls.append((start, end, kwargs["topics"]))
            return iter(())

    prior = [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 1000,
        "launches": 3,
        "versions": {"v2": 3},
        "search_from_block": 900,
        "search_to_block": 1100,
        "initialize_events": 0,
        "v4_candidates": [],
        "causal_route_ready": False,
        "delayed_route_ready": False,
        "selected_causal_candidate": None,
        "selected_delayed_candidate": None,
    }]
    rows = extend_v4_usdg_routes(
        Rpc(),
        prior,
        snapshot_head=2000,
        forward_blocks=500,
    )
    assert rows[0]["continuation_from_block"] == 1101
    assert rows[0]["continuation_to_block"] == 1600
    assert calls[0][0:2] == (1101, 1600)


def test_extend_v4_known_pool_can_find_first_later_swap(monkeypatch):
    pool_manager = "0x" + "55" * 20
    initialized = {
        "pool_manager": pool_manager,
        "pool_id": POOL_ID,
        "currency0": TOKEN,
        "currency1": ROBINHOOD_USDG.lower(),
        "fee": 500,
        "tick_spacing": 10,
        "hooks": "0x" + "00" * 20,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 1050,
        "transaction_hash": "0x" + "10" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }
    swap = SimpleNamespace(
        pool_manager=pool_manager,
        pool_id=POOL_ID,
        sender="0x" + "66" * 20,
        amount0=1,
        amount1=-1,
        sqrt_price_x96=2**96,
        liquidity=100,
        tick=0,
        fee=500,
        block_number=1200,
        transaction_hash="0x" + "20" * 32,
        transaction_index=1,
        log_index=0,
    )
    monkeypatch.setattr(
        "hlp.data.quote_v4_routes.decode_v4_swap",
        lambda raw: swap,
    )

    calls = []

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            calls.append((start, end, kwargs["topics"]))
            if kwargs["topics"][0] == V4_INITIALIZE_TOPIC:
                return iter(())
            return iter([object()])

    prior = [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 1000,
        "launches": 3,
        "versions": {"v2": 3},
        "search_from_block": 900,
        "search_to_block": 1100,
        "initialize_events": 1,
        "v4_candidates": [{
            "pool_id": POOL_ID,
            "initialize": initialized,
            "latest_pre_use_swap": None,
            "first_post_use_swap": None,
            "swap_count_in_window": 0,
        }],
        "causal_route_ready": False,
        "delayed_route_ready": False,
        "selected_causal_candidate": None,
        "selected_delayed_candidate": None,
    }]
    row = extend_v4_usdg_routes(
        Rpc(),
        prior,
        snapshot_head=2000,
        forward_blocks=500,
        known_pool_only=True,
    )[0]
    assert len(calls) == 1
    assert calls[0][2] == [V4_SWAP_TOPIC, POOL_ID]
    assert row["continuation_mode"] == "known_pool_only"
    assert row["delayed_route_ready"] is True
    assert row["selected_delayed_candidate"]["first_post_use_swap"][
        "block_number"
    ] == 1200


def test_extend_v4_known_pool_only_requires_candidate():
    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            raise AssertionError("known-pool-only must fail before RPC")

    prior = [{
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 1000,
        "launches": 3,
        "versions": {"v2": 3},
        "search_from_block": 900,
        "search_to_block": 1100,
        "initialize_events": 0,
        "v4_candidates": [],
        "causal_route_ready": False,
        "delayed_route_ready": False,
        "selected_causal_candidate": None,
        "selected_delayed_candidate": None,
    }]
    with pytest.raises(ValueError, match="requires an existing V4 candidate"):
        extend_v4_usdg_routes(
            Rpc(),
            prior,
            snapshot_head=2000,
            forward_blocks=500,
            known_pool_only=True,
        )


def test_validate_known_v4_usdg_pool_candidate(monkeypatch):
    manager = "0x" + "55" * 20
    observed = SimpleNamespace(
        pool_manager=manager,
        pool_id=POOL_ID,
        currency0=TOKEN,
        currency1=ROBINHOOD_USDG.lower(),
        fee=500,
        tick_spacing=10,
        hooks="0x" + "00" * 20,
        sqrt_price_x96=2**96,
        tick=0,
        block_number=100,
        transaction_hash="0x" + "22" * 32,
        transaction_index=1,
        log_index=2,
    )
    monkeypatch.setattr(
        "hlp.data.quote_v4_routes.decode_v4_pool_initialized",
        lambda raw: observed,
    )
    calls = []

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            calls.append((start, end, kwargs))
            return iter([object()])

    row = validate_v4_usdg_pool_candidate(
        Rpc(),
        {
            "quote_token": TOKEN,
            "symbol": "TEST",
            "quote_decimals": 18,
            "first_launch_block": 1000,
            "launches": 3,
            "versions": {"v2": 3},
        },
        pool_id=POOL_ID,
        from_block=90,
        to_block=110,
        pool_manager=manager,
    )

    assert row["pool_id"] == POOL_ID
    assert row["token_is_token0"] is True
    assert row["initialize"]["block_number"] == 100
    assert calls[0][0:2] == (90, 110)
    assert calls[0][2]["topics"] == [V4_INITIALIZE_TOPIC, POOL_ID]


def test_validate_known_v4_candidate_rejects_wrong_currencies(monkeypatch):
    observed = SimpleNamespace(
        pool_id=POOL_ID,
        currency0="0x" + "77" * 20,
        currency1=ROBINHOOD_USDG.lower(),
    )
    monkeypatch.setattr(
        "hlp.data.quote_v4_routes.decode_v4_pool_initialized",
        lambda raw: observed,
    )

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            return iter([object()])

    with pytest.raises(ValueError, match="currency mismatch"):
        validate_v4_usdg_pool_candidate(
            Rpc(),
            {
                "quote_token": TOKEN,
                "symbol": "TEST",
                "quote_decimals": 18,
                "first_launch_block": 1000,
                "launches": 3,
            },
            pool_id=POOL_ID,
            from_block=90,
            to_block=110,
        )


def test_validate_known_v4_candidate_requires_exactly_one_initialize():
    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            return iter(())

    with pytest.raises(ValueError, match="exactly one Initialize"):
        validate_v4_usdg_pool_candidate(
            Rpc(),
            {
                "quote_token": TOKEN,
                "symbol": "TEST",
                "quote_decimals": 18,
                "first_launch_block": 1000,
                "launches": 3,
            },
            pool_id=POOL_ID,
            from_block=90,
            to_block=110,
        )
