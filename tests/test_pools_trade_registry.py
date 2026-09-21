import pytest

from hlp.data.pools_trade_registry import (
    attach_pools_trade_instant_initializations,
    build_pools_trade_instant_registry,
    build_pools_trade_lbp_registry,
)
from hlp.data.types import (
    PoolsTradeLbpInitializerCreated,
    PoolsTradeTokenCreated,
    PoolsTradeTokenDistributed,
    PoolsTradeTokenLaunched,
)


TOKEN = "0x" + "11" * 20
ZERO = "0x" + "00" * 20
STRATEGY = "0x" + "22" * 20
POOL_ID = "0x" + "33" * 32


def test_join_pools_trade_instant_launch():
    created = PoolsTradeTokenCreated(
        launcher="0x" + "44" * 20,
        token=TOKEN,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=0,
    )
    distributed = PoolsTradeTokenDistributed(
        launcher=created.launcher,
        token=TOKEN,
        strategy=STRATEGY,
        amount_raw=10**27,
        block_number=10,
        transaction_hash=created.transaction_hash,
        transaction_index=1,
        log_index=1,
    )
    launched = PoolsTradeTokenLaunched(
        strategy=STRATEGY,
        pool_id=POOL_ID,
        token=TOKEN,
        final_position_recipient="0x" + "55" * 20,
        currency0=ZERO,
        currency1=TOKEN,
        fee=2500,
        tick_spacing=25,
        hooks=ZERO,
        block_number=10,
        transaction_hash=created.transaction_hash,
        transaction_index=1,
        log_index=2,
    )
    rows = build_pools_trade_instant_registry(
        [created], [distributed], [launched]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["token"] == TOKEN
    assert row["quote_token"] == ZERO
    assert row["pool_id"] == POOL_ID
    assert row["supply_raw"] == 10**27



def test_join_pools_trade_lbp_launch_registry():
    created = PoolsTradeTokenCreated(
        launcher="0x" + "44" * 20,
        token=TOKEN,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=0,
    )
    strategy = "0x" + "66" * 20
    distributed = PoolsTradeTokenDistributed(
        launcher=created.launcher,
        token=TOKEN,
        strategy=strategy,
        amount_raw=1_000_000_000 * 10**18,
        block_number=10,
        transaction_hash=created.transaction_hash,
        transaction_index=1,
        log_index=1,
    )
    initializer = PoolsTradeLbpInitializerCreated(
        strategy=strategy,
        initializer="0x" + "77" * 20,
        token=TOKEN,
        currency=ZERO,
        migration_block=1000,
        reserved_token_amount_for_lp=200_000_000 * 10**18,
        recipient="0x" + "88" * 20,
        position_recipient="0x" + "99" * 20,
        pool_fee=2500,
        pool_tick_spacing=50,
        pool_hook=ZERO,
        position_definitions_offset=352,
        lp_allocation_schedule_offset=576,
        block_number=10,
        transaction_hash=created.transaction_hash,
        transaction_index=1,
        log_index=2,
    )

    rows = build_pools_trade_lbp_registry(
        [created], [distributed], [initializer]
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["launch_kind"] == "crowd_lbp"
    assert row["token"] == TOKEN
    assert row["quote_token"] == ZERO
    assert row["supply_raw"] == 1_000_000_000 * 10**18
    assert row["reserved_token_amount_for_lp"] == 200_000_000 * 10**18
    assert row["migration_block"] == 1000
    assert row["currency0"] == ZERO
    assert row["currency1"] == TOKEN
    assert row["pool_id"].startswith("0x")
    assert len(row["pool_id"]) == 66


def test_lbp_registry_requires_matching_strategy_distribution():
    created = PoolsTradeTokenCreated(
        launcher="0x" + "44" * 20,
        token=TOKEN,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=0,
    )
    initializer = PoolsTradeLbpInitializerCreated(
        strategy="0x" + "66" * 20,
        initializer="0x" + "77" * 20,
        token=TOKEN,
        currency=ZERO,
        migration_block=1000,
        reserved_token_amount_for_lp=0,
        recipient="0x" + "88" * 20,
        position_recipient="0x" + "99" * 20,
        pool_fee=2500,
        pool_tick_spacing=50,
        pool_hook=ZERO,
        position_definitions_offset=352,
        lp_allocation_schedule_offset=576,
        block_number=10,
        transaction_hash=created.transaction_hash,
        transaction_index=1,
        log_index=2,
    )

    with pytest.raises(ValueError, match="matching distribution"):
        build_pools_trade_lbp_registry([created], [], [initializer])


def test_lbp_registry_rejects_reserved_allocation_above_supply():
    created = PoolsTradeTokenCreated(
        launcher="0x" + "44" * 20,
        token=TOKEN,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=0,
    )
    strategy = "0x" + "66" * 20
    distributed = PoolsTradeTokenDistributed(
        launcher=created.launcher,
        token=TOKEN,
        strategy=strategy,
        amount_raw=100,
        block_number=10,
        transaction_hash=created.transaction_hash,
        transaction_index=1,
        log_index=1,
    )
    initializer = PoolsTradeLbpInitializerCreated(
        strategy=strategy,
        initializer="0x" + "77" * 20,
        token=TOKEN,
        currency=ZERO,
        migration_block=1000,
        reserved_token_amount_for_lp=101,
        recipient="0x" + "88" * 20,
        position_recipient="0x" + "99" * 20,
        pool_fee=2500,
        pool_tick_spacing=50,
        pool_hook=ZERO,
        position_definitions_offset=352,
        lp_allocation_schedule_offset=576,
        block_number=10,
        transaction_hash=created.transaction_hash,
        transaction_index=1,
        log_index=2,
    )

    with pytest.raises(ValueError, match="exceeds supply"):
        build_pools_trade_lbp_registry(
            [created], [distributed], [initializer]
        )


def test_attach_pools_trade_instant_initialization():
    registry = [{
        "venue": "pools.trade",
        "launch_kind": "instant_v4",
        "token": TOKEN,
        "quote_token": ZERO,
        "supply_raw": 10**27,
        "pool_id": POOL_ID,
        "currency0": ZERO,
        "currency1": TOKEN,
        "fee": 2500,
        "tick_spacing": 25,
        "hooks": ZERO,
        "created_block": 10,
        "launch_block": 11,
        "launch_transaction_hash": "0x" + "aa" * 32,
        "launch_transaction_index": 1,
        "launch_log_index": 4,
    }]
    init = [{
        "pool_id": POOL_ID,
        "currency0": ZERO,
        "currency1": TOKEN,
        "fee": 2500,
        "tick_spacing": 25,
        "hooks": ZERO,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 11,
        "transaction_hash": "0x" + "aa" * 32,
        "transaction_index": 1,
        "log_index": 3,
    }]

    rows = attach_pools_trade_instant_initializations(
        registry,
        init,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["source_id"] == "pools_trade_instant"
    assert row["source_kind"] == "launchpad"
    assert row["initialize_block"] == 11
    assert row["initialize_log_index"] == 3
    assert row["initial_sqrt_price_x96"] == 2**96


def test_attach_pools_trade_instant_initialization_rejects_poolkey_drift():
    registry = [{
        "venue": "pools.trade",
        "launch_kind": "instant_v4",
        "token": TOKEN,
        "quote_token": ZERO,
        "supply_raw": 10**27,
        "pool_id": POOL_ID,
        "currency0": ZERO,
        "currency1": TOKEN,
        "fee": 2500,
        "tick_spacing": 25,
        "hooks": ZERO,
        "created_block": 10,
        "launch_block": 11,
        "launch_transaction_hash": "0x" + "aa" * 32,
        "launch_transaction_index": 1,
        "launch_log_index": 4,
    }]
    init = [{
        "pool_id": POOL_ID,
        "currency0": ZERO,
        "currency1": TOKEN,
        "fee": 3000,
        "tick_spacing": 25,
        "hooks": ZERO,
        "sqrt_price_x96": 2**96,
        "tick": 0,
        "block_number": 11,
        "transaction_hash": "0x" + "aa" * 32,
        "transaction_index": 1,
        "log_index": 3,
    }]

    with pytest.raises(ValueError, match="PoolKey drift"):
        attach_pools_trade_instant_initializations(
            registry,
            init,
        )

