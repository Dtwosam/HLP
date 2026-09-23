import pytest

from hlp.data.noxa_registry import (
    attach_noxa_initializations,
    build_noxa_launch_registry,
)
from hlp.data.types import InstantV3Launch, NoxaLaunchedToken


TOKEN = "0x" + "11" * 20
DEPLOYER = "0x" + "22" * 20
DEX = "0x" + "33" * 20
PAIR = "0x" + "44" * 20
POOL = "0x" + "55" * 20
POSITION_MANAGER = "0x" + "66" * 20


def launch():
    return InstantV3Launch(
        venue="noxa",
        factory="0x" + "77" * 20,
        token=TOKEN,
        deployer=DEPLOYER,
        dex_factory=DEX,
        pair_token=PAIR,
        pool=POOL,
        dex_id=3,
        launch_config_id=7,
        position_id=9,
        restrictions_end_block=150,
        initial_buy_amount=123,
        block_number=100,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )


def state(**overrides):
    values = {
        "token": TOKEN,
        "deployer": DEPLOYER,
        "paired_token": PAIR,
        "position_manager": POSITION_MANAGER,
        "position_id": 9,
        "dex_id": 3,
        "launch_config_id": 7,
        "restrictions_end_block": 150,
        "supply": 1_000_000_000 * 10**18,
        "block_number": 100,
    }
    values.update(overrides)
    return NoxaLaunchedToken(**values)


def test_build_noxa_registry_joins_launch_state_without_symbol_assumptions():
    rows = build_noxa_launch_registry([launch()], [state()])

    assert rows == [
        {
            "venue": "noxa",
            "launch_kind": "instant_v3",
            "token": TOKEN,
            "quote_token": PAIR,
            "pool": POOL,
            "dex_factory": DEX,
            "deployer": DEPLOYER,
            "position_manager": POSITION_MANAGER,
            "position_id": 9,
            "dex_id": 3,
            "launch_config_id": 7,
            "restrictions_end_block": 150,
            "initial_buy_amount": 123,
            "supply_raw": 1_000_000_000 * 10**18,
            "launch_block": 100,
            "launch_transaction_hash": "0x" + "aa" * 32,
            "launch_transaction_index": 1,
            "launch_log_index": 2,
            "state_block": 100,
        }
    ]


def test_noxa_registry_rejects_state_from_later_block():
    with pytest.raises(ValueError, match="read at launch block"):
        build_noxa_launch_registry([launch()], [state(block_number=101)])


def test_noxa_registry_rejects_event_state_identity_drift():
    with pytest.raises(ValueError, match="identity mismatch"):
        build_noxa_launch_registry(
            [launch()],
            [state(paired_token="0x" + "99" * 20)],
        )


def test_noxa_registry_rejects_unmatched_state_rows():
    other = state(token="0x" + "88" * 20)
    with pytest.raises(ValueError, match="absent from launch tape"):
        build_noxa_launch_registry([], [other])


def test_attach_noxa_initializations_requires_exact_pool():
    rows = build_noxa_launch_registry(
        [launch()],
        [state()],
    )
    initialized = attach_noxa_initializations(
        rows,
        [{
            "pool": POOL,
            "sqrt_price_x96": 2**96,
            "tick": 0,
            "block_number": 100,
            "transaction_hash": "0x" + "03" * 32,
            "transaction_index": 2,
            "log_index": 4,
        }],
    )
    assert len(initialized) == 1
    assert initialized[0]["initialize_block"] == 100
    assert initialized[0]["initial_sqrt_price_x96"] == 2**96


def test_attach_noxa_initializations_rejects_missing_pool():
    rows = build_noxa_launch_registry(
        [launch()],
        [state()],
    )
    import pytest

    with pytest.raises(ValueError, match="missing V3 Initialize"):
        attach_noxa_initializations(rows, [])


def test_attach_noxa_initializations_rejects_same_block_prelaunch_order():
    rows = build_noxa_launch_registry(
        [launch()],
        [state()],
    )
    with pytest.raises(ValueError, match="Initialize precedes launch order"):
        attach_noxa_initializations(
            rows,
            [{
                "pool": POOL,
                "sqrt_price_x96": 2**96,
                "tick": 0,
                "block_number": 100,
                "transaction_hash": "0x" + "03" * 32,
                "transaction_index": 0,
                "log_index": 1,
            }],
        )

