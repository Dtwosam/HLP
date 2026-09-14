from types import SimpleNamespace

import pytest
from eth_utils import keccak

from hlp.config import ROBINHOOD_USDG
import hlp.data.quote_v4_causal_history as qv4
from hlp.data.quote_v4_causal_history import (
    validate_v4_usdg_causal_swap_witness,
    v4_pool_id,
)
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC


TTWO = "0x5e81213613b6b86eab4c6c50d718d34359459786"
TTWO_POOL = (
    "0xaf313f02e31e8adbc5aabbdfa5b02377"
    "bfa794089b06c60404a63d1a54b042fa"
)
MANAGER = "0x" + "55" * 20
ZERO_HOOKS = "0x" + "00" * 20
POOLS_SLOT = 6
LIQUIDITY_OFFSET = 3


def _source():
    return {
        "quote_token": TTWO,
        "symbol": "TTWO",
        "quote_decimals": 18,
        "first_launch_block": 35_998_356,
        "launches": 3_589,
        "versions": {"v2": 3_589},
    }


def _candidate(*, fee=40_000, tick_spacing=400, initialize_block=35_300_000):
    pool_id = v4_pool_id(
        currency0=TTWO,
        currency1=ROBINHOOD_USDG,
        fee=fee,
        tick_spacing=tick_spacing,
        hooks=ZERO_HOOKS,
    )
    return {
        "pool_id": pool_id,
        "currency0": TTWO,
        "currency1": ROBINHOOD_USDG,
        "fee": fee,
        "tick_spacing": tick_spacing,
        "hooks": ZERO_HOOKS,
        "initialize_block": initialize_block,
    }


def _initialized(candidate, **overrides):
    values = {
        "pool_manager": MANAGER,
        "pool_id": candidate["pool_id"],
        "currency0": candidate["currency0"],
        "currency1": candidate["currency1"],
        "fee": candidate["fee"],
        "tick_spacing": candidate["tick_spacing"],
        "hooks": candidate["hooks"],
        "sqrt_price_x96": 1,
        "tick": 0,
        "block_number": candidate["initialize_block"],
        "transaction_hash": "0x" + "12" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _state_slot(pool_id):
    return keccak(bytes.fromhex(pool_id[2:]) + POOLS_SLOT.to_bytes(32, "big"))


def _extsload_data(slot):
    selector = keccak(text="extsload(bytes32)")[:4]
    return "0x" + (selector + slot).hex()


class StateRpc:
    def __init__(self, states, initialized):
        self.states = states
        self.initialized = initialized
        self.log_calls = []
        self.eth_calls = []

    def get_logs(self, start, end, *, address=None, topics=None):
        self.log_calls.append((start, end, address, topics))
        assert start == end
        assert address == MANAGER
        assert topics[0] == V4_INITIALIZE_TOPIC
        pool_id = topics[1]
        return [pool_id] if pool_id in self.initialized else []

    def eth_call(self, to, data, block):
        self.eth_calls.append((to, data, block))
        assert to == MANAGER
        for pool_id, (sqrt_price_x96, liquidity) in self.states.items():
            slot = _state_slot(pool_id)
            if data == _extsload_data(slot):
                return hex(sqrt_price_x96)
            liquidity_slot = (
                int.from_bytes(slot, "big") + LIQUIDITY_OFFSET
            ).to_bytes(32, "big")
            if data == _extsload_data(liquidity_slot):
                return hex(liquidity)
        raise AssertionError(f"unexpected extsload payload: {data}")

    def iter_logs_chunked(self, *args, **kwargs):
        raise AssertionError("point-state validation must not scan Swap history")


def _patch_initializers(monkeypatch, initialized):
    monkeypatch.setattr(
        qv4,
        "decode_v4_pool_initialized",
        lambda raw: initialized[raw],
    )


def test_v4_pool_id_matches_observed_ttwu_usdg_pool_key():
    assert v4_pool_id(
        currency0=TTWO,
        currency1=ROBINHOOD_USDG,
        fee=40_000,
        tick_spacing=400,
        hooks=ZERO_HOOKS,
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
        hooks=ZERO_HOOKS,
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
            hooks=ZERO_HOOKS,
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
            hooks=ZERO_HOOKS,
            witness_block=35_389_234,
            pool_manager=MANAGER,
        )


def test_point_state_witness_builds_causal_route_without_swap_scan(monkeypatch):
    candidate = _candidate()
    initialized = {candidate["pool_id"]: _initialized(candidate)}
    _patch_initializers(monkeypatch, initialized)
    rpc = StateRpc(
        {candidate["pool_id"]: (1_239_716_949_291_293_853_903_753, 42_810_796_595_208_219)},
        initialized,
    )

    route = qv4.validate_v4_usdg_causal_state_witness(
        rpc,
        _source(),
        **candidate,
        pool_manager=MANAGER,
    )

    assert route["route_type"] == "uniswap_v4_direct_usdg"
    assert route["pool_id"] == candidate["pool_id"]
    assert route["activation_block"] == _source()["first_launch_block"]
    assert route["causal_state_block"] == _source()["first_launch_block"] - 1
    assert route["activation_liquidity"] == 42_810_796_595_208_219
    assert route["state_evidence_type"] == "point_in_time_pool_state"
    assert route["initial_usd_price"] > 0
    assert route["state_transaction_hash"] is None
    assert len(rpc.log_calls) == 1
    assert len(rpc.eth_calls) == 2


def test_point_state_witness_rejects_zero_active_liquidity(monkeypatch):
    candidate = _candidate()
    initialized = {candidate["pool_id"]: _initialized(candidate)}
    _patch_initializers(monkeypatch, initialized)
    rpc = StateRpc({candidate["pool_id"]: (123456, 0)}, initialized)

    with pytest.raises(ValueError, match="positive active liquidity"):
        qv4.validate_v4_usdg_causal_state_witness(
            rpc,
            _source(),
            **candidate,
            pool_manager=MANAGER,
        )


def test_point_state_witness_rejects_initialize_pool_key_mismatch(monkeypatch):
    candidate = _candidate()
    wrong_currency = "0x" + "77" * 20
    initialized = {
        candidate["pool_id"]: _initialized(candidate, currency1=wrong_currency)
    }
    _patch_initializers(monkeypatch, initialized)
    rpc = StateRpc({candidate["pool_id"]: (123456, 789)}, initialized)

    with pytest.raises(ValueError, match="Initialize event does not match pool key"):
        qv4.validate_v4_usdg_causal_state_witness(
            rpc,
            _source(),
            **candidate,
            pool_manager=MANAGER,
        )


def test_point_state_selection_prefers_highest_liquidity_then_pool_id(monkeypatch):
    low = _candidate(fee=10_000, tick_spacing=100)
    tie_a = _candidate(fee=20_000, tick_spacing=200)
    tie_b = _candidate(fee=30_000, tick_spacing=300)
    initialized = {
        row["pool_id"]: _initialized(row)
        for row in (low, tie_a, tie_b)
    }
    _patch_initializers(monkeypatch, initialized)
    high_pool_id = max(tie_a["pool_id"], tie_b["pool_id"])
    rpc = StateRpc(
        {
            low["pool_id"]: (111, 1_000),
            tie_a["pool_id"]: (222, 2_000),
            tie_b["pool_id"]: (333, 2_000),
        },
        initialized,
    )

    route = qv4.select_v4_usdg_causal_state_witness(
        rpc,
        _source(),
        [low, tie_a, tie_b],
        pool_manager=MANAGER,
    )

    assert route["activation_liquidity"] == 2_000
    assert route["pool_id"] == high_pool_id
