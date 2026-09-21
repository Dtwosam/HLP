from hlp.data.pools_fun_registry import (
    POOLS_FUN_FIXED_SUPPLY_RAW,
    attach_pools_fun_initializations,
    build_pools_fun_registry,
)
from hlp.data.types import PoolsFunLaunch


def test_build_pools_fun_registry():
    launch = PoolsFunLaunch(
        token="0x" + "11" * 20,
        pool="0x" + "22" * 20,
        paired_asset="0x" + "33" * 20,
        creator="0x" + "44" * 20,
        deployer="0x" + "55" * 20,
        fee_recipient="0x" + "66" * 20,
        start_tick=-100,
        metadata_uri="ipfs://cat",
        dev_buy_amount_out=123,
        block_number=10,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
    )
    rows = build_pools_fun_registry([launch])
    assert len(rows) == 1
    row = rows[0]
    assert row["venue"] == "pools.fun"
    assert row["supply_raw"] == POOLS_FUN_FIXED_SUPPLY_RAW
    assert row["quote_token"] == launch.paired_asset



def test_attach_pools_fun_initialization():
    registry = build_pools_fun_registry([
        PoolsFunLaunch(
            token="0x" + "11" * 20,
            pool="0x" + "22" * 20,
            paired_asset="0x" + "33" * 20,
            creator="0x" + "44" * 20,
            deployer="0x" + "55" * 20,
            fee_recipient="0x" + "66" * 20,
            start_tick=-100,
            metadata_uri="ipfs://cat",
            dev_buy_amount_out=123,
            block_number=10,
            transaction_hash="0x" + "aa" * 32,
            transaction_index=1,
            log_index=2,
        )
    ])
    rows = attach_pools_fun_initializations(
        registry,
        [{
            "pool": "0x" + "22" * 20,
            "sqrt_price_x96": 2**96,
            "tick": -50,
            "block_number": 10,
            "transaction_hash": "0x" + "bb" * 32,
            "transaction_index": 1,
            "log_index": 1,
        }],
    )
    assert rows[0]["initialize_block"] == 10
    assert rows[0]["initialize_transaction_hash"] == "0x" + "bb" * 32
    assert rows[0]["initial_sqrt_price_x96"] == 2**96
    assert rows[0]["initial_tick"] == -50


def test_attach_pools_fun_initialization_requires_every_pool():
    registry = build_pools_fun_registry([
        PoolsFunLaunch(
            token="0x" + "11" * 20,
            pool="0x" + "22" * 20,
            paired_asset="0x" + "33" * 20,
            creator="0x" + "44" * 20,
            deployer="0x" + "55" * 20,
            fee_recipient="0x" + "66" * 20,
            start_tick=-100,
            metadata_uri="ipfs://cat",
            dev_buy_amount_out=123,
            block_number=10,
            transaction_hash="0x" + "aa" * 32,
            transaction_index=1,
            log_index=2,
        )
    ])
    import pytest

    with pytest.raises(ValueError, match="missing V3 Initialize"):
        attach_pools_fun_initializations(registry, [])
