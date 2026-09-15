from types import SimpleNamespace

import pytest

from hlp.config import ROBINHOOD_USDG
from hlp.data.quote_v4_causal_history import (
    extend_v4_usdg_causal_history,
    select_v4_quote_routes_after_causal_history,
)
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC


TOKEN = "0x" + "11" * 20
POOL_ID = "0x" + "aa" * 32
MANAGER = "0x" + "55" * 20


def _delayed_candidate():
    return {
        "pool_id": "0x" + "bb" * 32,
        "initialize": {
            "pool_manager": MANAGER,
            "pool_id": "0x" + "bb" * 32,
            "currency0": TOKEN,
            "currency1": ROBINHOOD_USDG.lower(),
            "fee": 500,
            "tick_spacing": 10,
            "hooks": "0x" + "00" * 20,
            "block_number": 1040,
        },
        "latest_pre_use_swap": None,
        "first_post_use_swap": {
            "pool_id": "0x" + "bb" * 32,
            "block_number": 1050,
            "transaction_hash": "0x" + "44" * 32,
            "transaction_index": 1,
            "log_index": 0,
            "liquidity": 100,
            "quote_per_token": "1",
            "usd_price": "1",
        },
        "swap_count_in_window": 1,
    }


def _prior_row():
    delayed = _delayed_candidate()
    return {
        "quote_token": TOKEN,
        "symbol": "TEST",
        "quote_decimals": 18,
        "first_launch_block": 1000,
        "launches": 3,
        "versions": {"v2": 3},
        "search_from_block": 900,
        "search_to_block": 1100,
        "initialize_events": 1,
        "v4_candidates": [delayed],
        "causal_route_ready": False,
        "delayed_route_ready": True,
        "selected_causal_candidate": None,
        "selected_delayed_candidate": delayed,
    }


def test_causal_history_reaches_pool_more_than_lookaround_before_first_use(monkeypatch):
    initialized = SimpleNamespace(
        pool_manager=MANAGER,
        pool_id=POOL_ID,
        currency0=TOKEN,
        currency1=ROBINHOOD_USDG.lower(),
        fee=500,
        tick_spacing=10,
        hooks="0x" + "00" * 20,
        sqrt_price_x96=2**96,
        tick=0,
        block_number=650,
        transaction_hash="0x" + "10" * 32,
        transaction_index=1,
        log_index=0,
    )
    swaps = {
        "swap-700": SimpleNamespace(
            pool_manager=MANAGER,
            pool_id=POOL_ID,
            sender="0x" + "66" * 20,
            amount0=1,
            amount1=-1,
            sqrt_price_x96=2**96,
            liquidity=100,
            tick=0,
            fee=500,
            block_number=700,
            transaction_hash="0x" + "20" * 32,
            transaction_index=1,
            log_index=0,
        ),
        "swap-950": SimpleNamespace(
            pool_manager=MANAGER,
            pool_id=POOL_ID,
            sender="0x" + "66" * 20,
            amount0=1,
            amount1=-1,
            sqrt_price_x96=2**96,
            liquidity=200,
            tick=0,
            fee=500,
            block_number=950,
            transaction_hash="0x" + "30" * 32,
            transaction_index=2,
            log_index=0,
        ),
    }
    monkeypatch.setattr(
        "hlp.data.quote_v4_causal_history.decode_v4_pool_initialized",
        lambda raw: initialized,
    )
    monkeypatch.setattr(
        "hlp.data.quote_v4_causal_history.decode_v4_swap",
        lambda raw: swaps[raw],
    )

    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            topic0 = kwargs["topics"][0]
            if topic0 == V4_INITIALIZE_TOPIC:
                return iter(["init"] if start <= 650 <= end else [])
            assert topic0 == V4_SWAP_TOPIC
            found = []
            if start <= 700 <= end:
                found.append("swap-700")
            if start <= 950 <= end:
                found.append("swap-950")
            return iter(found)

    rows = [_prior_row()]
    for expected_end in (749, 899):
        rows = extend_v4_usdg_causal_history(
            Rpc(),
            rows,
            lower_bound_by_token={TOKEN: 600},
            segment_blocks=150,
            pool_manager=MANAGER,
        )
        row = rows[0]
        assert row["causal_history_scanned_through"] == expected_end
        assert row["causal_history_complete"] is False
        assert row["causal_route_ready"] is False
        assert row["delayed_route_ready"] is False
        assert row["selected_delayed_candidate"] is None

    rows = extend_v4_usdg_causal_history(
        Rpc(),
        rows,
        lower_bound_by_token={TOKEN: 600},
        segment_blocks=150,
        pool_manager=MANAGER,
    )
    row = rows[0]
    assert row["causal_history_scanned_through"] == 999
    assert row["causal_history_complete"] is True
    assert row["causal_route_ready"] is True
    assert row["delayed_route_ready"] is False
    assert row["selected_causal_candidate"]["pool_id"] == POOL_ID
    assert row["selected_causal_candidate"]["latest_pre_use_swap"][
        "block_number"
    ] == 950


def test_complete_history_without_causal_swap_restores_delayed_route():
    class Rpc:
        def iter_logs_chunked(self, start, end, **kwargs):
            assert kwargs["topics"][0] == V4_INITIALIZE_TOPIC
            return iter(())

    row = extend_v4_usdg_causal_history(
        Rpc(),
        [_prior_row()],
        lower_bound_by_token={TOKEN: 600},
        segment_blocks=400,
        pool_manager=MANAGER,
    )[0]

    assert row["causal_history_complete"] is True
    assert row["causal_route_ready"] is False
    assert row["delayed_route_ready"] is True
    route = select_v4_quote_routes_after_causal_history([row])[0]
    assert route["route_type"] == "uniswap_v4_direct_usdg_delayed"
    assert route["activation_block"] == 1050


def test_complete_history_is_chain_safe_noop():
    complete = _prior_row()
    complete.update({
        "causal_history_required": True,
        "causal_history_from_block": 600,
        "causal_history_to_block": 999,
        "causal_history_scanned_through": 999,
        "causal_history_complete": True,
    })

    class Rpc:
        def iter_logs_chunked(self, *args, **kwargs):
            raise AssertionError("completed causal history must not issue RPC")

    rows = extend_v4_usdg_causal_history(
        Rpc(),
        [complete],
        lower_bound_by_token={TOKEN: 600},
        segment_blocks=100,
        pool_manager=MANAGER,
    )
    assert rows == [complete]


def test_causal_history_segment_is_hard_capped_at_100k():
    with pytest.raises(ValueError, match="between 1 and 100000"):
        extend_v4_usdg_causal_history(
            object(),
            [_prior_row()],
            lower_bound_by_token={TOKEN: 600},
            segment_blocks=100_001,
            pool_manager=MANAGER,
        )


def test_select_rejects_required_but_incomplete_causal_history():
    row = _prior_row()
    row.update({
        "causal_history_required": True,
        "causal_history_complete": False,
    })
    with pytest.raises(ValueError, match="causal history is incomplete"):
        select_v4_quote_routes_after_causal_history([row])
