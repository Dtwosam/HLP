from types import SimpleNamespace

import pytest

from hlp.config import ROBINHOOD_USDG
from hlp.data.quote_v4_causal_history import (
    validate_v4_usdg_causal_swap_witness,
    v4_pool_id,
)
from hlp.protocols.uniswap import V4_SWAP_TOPIC


TTWO = "0x5e81213613b6b86eab4c6c50d718d34359459786"
TTWO_POOL = (
    "0xaf313f02e31e8adbc5aabbdfa5b02377"
    "bfa794089b06c60404a63d1a54b042fa"
)
MANAGER = "0x" + "55" * 20


def _source():
    return {
        "quote_token": TTWO,
        "symbol": "TTWO",
        "quote_decimals": 18,
        "first_launch_block": 35_998_356,
        "launches": 3_589,
        "versions": {"v2": 3_589},
    }


def test_v4_pool_id_matches_observed_ttwu_usdg_pool_key():
    assert v4_pool_id(
        currency0=TTWO,
        currency1=ROBINHOOD_USDG,
        fee=40_000,
        tick_spacing=400,
        hooks="0x" + "00" * 20,
    ) == TTWO_POOL


def test_single_block_swap_witness_builds_causal_route(monkeypatch):
    swap = SimpleNamespace(
        pool_manager=MANAGER,
        pool_id=TTWO_POOL,
        sender="0x" + "66" * 20,
        amount0=6_986_791_088_871,
        amount1=-1_871,
        sqrt_price_x96=1_269_556_212_042_323_074_855_501,
        liquidity=2_294_501_460_146_696,
        tick=-220_840,
        fee=40_960,
        block_number=35_389_234,
        transaction_hash="0x" + "89" * 32,
        transaction_index=7,
        log_index=10,
    )
    monkeypatch.setattr(
        "hlp.data.quote_v4_causal_history.decode_v4_swap",
        lambda raw: swap,
    )

    class Rpc:
        calls = []

        def iter_logs_chunked(self, start, end, **kwargs):
            self.calls.append((start, end, kwargs))
            return iter(["swap"])

    rpc = Rpc()
    route = validate_v4_usdg_causal_swap_witness(
        rpc,
        _source(),
        pool_id=TTWO_POOL,
        currency0=TTWO,
        currency1=ROBINHOOD_USDG,
        fee=40_000,
        tick_spacing=400,
        hooks="0x" + "00" * 20,
        witness_block=35_389_234,
        pool_manager=MANAGER,
    )

    assert len(rpc.calls) == 1
    start, end, kwargs = rpc.calls[0]
    assert (start, end) == (35_389_234, 35_389_234)
    assert kwargs["topics"] == [V4_SWAP_TOPIC, TTWO_POOL]
    assert route["route_type"] == "uniswap_v4_direct_usdg"
    assert route["activation_block"] == 35_998_356
    assert route["causal_state_block"] == 35_389_234
    assert route["pool_id"] == TTWO_POOL
    assert route["state_transaction_index"] == 7


def test_causal_swap_witness_rejects_post_use_block():
    with pytest.raises(ValueError, match="before first Pons use"):
        validate_v4_usdg_causal_swap_witness(
            object(),
            _source(),
            pool_id=TTWO_POOL,
            currency0=TTWO,
            currency1=ROBINHOOD_USDG,
            fee=40_000,
            tick_spacing=400,
            hooks="0x" + "00" * 20,
            witness_block=35_998_356,
            pool_manager=MANAGER,
        )


def test_causal_swap_witness_rejects_pool_id_key_mismatch():
    with pytest.raises(ValueError, match="pool id does not match pool key"):
        validate_v4_usdg_causal_swap_witness(
            object(),
            _source(),
            pool_id="0x" + "aa" * 32,
            currency0=TTWO,
            currency1=ROBINHOOD_USDG,
            fee=40_000,
            tick_spacing=400,
            hooks="0x" + "00" * 20,
            witness_block=35_389_234,
            pool_manager=MANAGER,
        )
