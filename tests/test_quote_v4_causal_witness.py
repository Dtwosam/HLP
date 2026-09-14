from dataclasses import replace
from types import SimpleNamespace

import pytest

import hlp.data.quote_v4_causal_history as qv4
from hlp.config import ROBINHOOD_USDG
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, V4_SWAP_TOPIC


TTWO = "0x5e81213613b6b86eab4c6c50d718d34359459786"
MANAGER = "0x" + "99" * 20
ZERO_HOOKS = "0x" + "00" * 20


class FakeRpc:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def iter_logs_chunked(
        self,
        from_block,
        to_block,
        *,
        address=None,
        topics=None,
        chunk_size=100_000,
        min_chunk_size=1,
    ):
        self.calls.append({
            "from_block": from_block,
            "to_block": to_block,
            "address": address,
            "topics": topics,
            "chunk_size": chunk_size,
            "min_chunk_size": min_chunk_size,
        })
        return iter(self.rows)


class StateRpc:
    def __init__(self, pool_states, initialize_rows):
        self.pool_states = pool_states
        self.initialize_rows = initialize_rows
        self.log_calls = []
        self.eth_calls = []

    def get_logs(self, from_block, to_block, *, address=None, topics=None):
        self.log_calls.append({
            "from_block": from_block,
            "to_block": to_block,
            "address": address,
            "topics": topics,
        })
        pool_id = topics[1].lower()
        return [self.initialize_rows[pool_id]]

    def eth_call(self, to, data, block="latest"):
        self.eth_calls.append({"to": to, "data": data, "block": block})
        pool_id = next(
            pool
            for pool, slots in self.pool_states.items()
            if data in {slots["slot0_data"], slots["liquidity_data"]}
        )
        slots = self.pool_states[pool_id]
        if data == slots["slot0_data"]:
            return hex(slots["sqrt_price_x96"])
        return hex(slots["liquidity"])


def _source():
    return {
        "quote_token": TTWO,
        "symbol": "TTWO",
        "quote_decimals": 18,
        "first_launch_block": 35_998_356,
        "launches": 16,
        "versions": {"v2": 16},
    }


def _candidate(*, fee=40_000, tick_spacing=400):
    currency0, currency1 = sorted(
        (TTWO.lower(), ROBINHOOD_USDG.lower()),
        key=lambda value: int(value, 16),
    )
    pool_id = qv4.v4_pool_id(
        currency0=currency0,
        currency1=currency1,
        fee=fee,
        tick_spacing=tick_spacing,
        hooks=ZERO_HOOKS,
    )
    return {
        "pool_id": pool_id,
        "currency0": currency0,
        "currency1": currency1,
        "fee": fee,
        "tick_spacing": tick_spacing,
        "hooks": ZERO_HOOKS,
        "initialize_block": 35_300_000,
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
        "sqrt_price_x96": 123,
        "tick": 1,
        "block_number": candidate["initialize_block"],
        "transaction_hash": "0x" + "ab" * 32,
        "transaction_index": 2,
        "log_index": 3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_initializers(monkeypatch, initialized):
    monkeypatch.setattr(
        qv4,
        "decode_v4_pool_initialized",
        lambda raw: raw,
    )
    for pool_id, state in list(initialized.items()):
        slot = qv4._v4_pool_state_slot(pool_id)
        liquidity_slot = (
            int.from_bytes(slot, "big") + qv4._V4_LIQUIDITY_OFFSET
        ).to_bytes(32, "big")
        initialized[pool_id] = state
        yield_data = {
            "slot0_data": qv4._v4_extsload_data(slot),
            "liquidity_data": qv4._v4_extsload_data(liquidity_slot),
        }
        if not hasattr(state, "pool_state_calls"):
            state.pool_state_calls = yield_data


def _state_rpc(pool_states, initialized):
    prepared = {}
    for pool_id, (sqrt_price_x96, liquidity) in pool_states.items():
        slot = qv4._v4_pool_state_slot(pool_id)
        liquidity_slot = (
            int.from_bytes(slot, "big") + qv4._V4_LIQUIDITY_OFFSET
        ).to_bytes(32, "big")
        prepared[pool_id] = {
            "slot0_data": qv4._v4_extsload_data(slot),
            "liquidity_data": qv4._v4_extsload_data(liquidity_slot),
            "sqrt_price_x96": sqrt_price_x96,
            "liquidity": liquidity,
        }
    return StateRpc(prepared, initialized)


def test_v4_pool_id_matches_known_ttwu_pool():
    assert qv4.v4_pool_id(
        currency0=TTWO,
        currency1=ROBINHOOD_USDG,
        fee=40_000,
        tick_spacing=400,
        hooks=ZERO_HOOKS,
    ) == (
        "0xaf313f02e31e8adbc5aabbdfa5b02377"
        "bfa794089b06c60404a63d1a54b042fa"
    )


def test_positive_pre_use_swap_witness_builds_causal_route(monkeypatch):
    raw = object()
    swap = SimpleNamespace(
        pool_manager=MANAGER,
        pool_id=(
            "0xaf313f02e31e8adbc5aabbdfa5b02377"
            "bfa794089b06c60404a63d1a54b042fa"
        ),
        sender="0x" + "44" * 20,
        amount0=1,
        amount1=-1,
        sqrt_price_x96=1_239_716_949_291_293_853_903_753,
        liquidity=42_810_796_595_208_219,
        tick=-221_344,
        fee=40_960,
        block_number=35_389_234,
        transaction_hash="0x" + "55" * 32,
        transaction_index=1,
        log_index=2,
    )
    monkeypatch.setattr(qv4, "decode_v4_swap", lambda value: swap)
    rpc = FakeRpc([raw])

    route = qv4.validate_v4_usdg_causal_swap_witness(
        rpc,
        _source(),
        pool_id=swap.pool_id,
        currency0=TTWO,
        currency1=ROBINHOOD_USDG,
        fee=40_000,
        tick_spacing=400,
        hooks=ZERO_HOOKS,
        witness_block=35_389_234,
        pool_manager=MANAGER,
    )

    assert route["route_type"] == "uniswap_v4_direct_usdg"
    assert route["pool_id"] == swap.pool_id
    assert route["activation_block"] == _source()["first_launch_block"]
    assert route["causal_state_block"] == 35_389_234
    assert route["activation_liquidity"] == swap.liquidity
    assert route["witness_validation"] == "single_block_positive_v4_swap"
    assert route["pool_key_verified"] is True
    assert rpc.calls == [{
        "from_block": 35_389_234,
        "to_block": 35_389_234,
        "address": MANAGER,
        "topics": [V4_SWAP_TOPIC, swap.pool_id],
        "chunk_size": 1,
        "min_chunk_size": 1,
    }]


def test_witness_rejects_non_positive_liquidity(monkeypatch):
    swap = SimpleNamespace(
        pool_manager=MANAGER,
        pool_id=(
            "0xaf313f02e31e8adbc5aabbdfa5b02377"
            "bfa794089b06c60404a63d1a54b042fa"
        ),
        sqrt_price_x96=123,
        liquidity=0,
        block_number=35_389_234,
        transaction_index=1,
        log_index=2,
    )
    monkeypatch.setattr(qv4, "decode_v4_swap", lambda value: swap)
    with pytest.raises(ValueError, match="positive-liquidity"):
        qv4.validate_v4_usdg_causal_swap_witness(
            FakeRpc([object()]),
            _source(),
            pool_id=swap.pool_id,
            currency0=TTWO,
            currency1=ROBINHOOD_USDG,
            fee=40_000,
            tick_spacing=400,
            hooks=ZERO_HOOKS,
            witness_block=35_389_234,
            pool_manager=MANAGER,
        )


def test_witness_rejects_pool_key_mismatch():
    with pytest.raises(ValueError, match="pool id does not match pool key"):
        qv4.validate_v4_usdg_causal_swap_witness(
            FakeRpc([]),
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
    monkeypatch.setattr(qv4, "decode_v4_pool_initialized", lambda raw: raw)
    rpc = _state_rpc(
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
    assert isinstance(route["initial_usd_price"], str)
    assert float(route["initial_usd_price"]) > 0
    assert isinstance(route["initial_quote_per_token"], str)
    assert route["state_transaction_hash"] is None
    assert len(rpc.log_calls) == 1
    assert len(rpc.eth_calls) == 2


def test_point_state_witness_rejects_zero_active_liquidity(monkeypatch):
    candidate = _candidate()
    initialized = {candidate["pool_id"]: _initialized(candidate)}
    monkeypatch.setattr(qv4, "decode_v4_pool_initialized", lambda raw: raw)
    rpc = _state_rpc({candidate["pool_id"]: (123456, 0)}, initialized)

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
    monkeypatch.setattr(qv4, "decode_v4_pool_initialized", lambda raw: raw)
    rpc = _state_rpc({candidate["pool_id"]: (123456, 789)}, initialized)

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
    monkeypatch.setattr(qv4, "decode_v4_pool_initialized", lambda raw: raw)
    high_pool_id = max(tie_a["pool_id"], tie_b["pool_id"])
    rpc = _state_rpc(
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
