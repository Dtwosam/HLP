from hlp.data.pools_trade_registry import build_pools_trade_instant_registry
from hlp.data.types import (
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
