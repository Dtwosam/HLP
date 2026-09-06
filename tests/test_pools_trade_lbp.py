from hlp.config import normalize_address
from hlp.data.types import RawLog
from hlp.protocols.pools_trade_lbp import (
    INITIALIZER_CREATED_TOPIC,
    POOLS_TRADE_LBP_STRATEGY,
    decode_pools_trade_lbp_initializer_created,
)


TOKEN = "0x" + "11" * 20
INITIALIZER = "0x" + "22" * 20
RECIPIENT = "0x" + "33" * 20
POSITION = "0x" + "44" * 20
ZERO = "0x" + "00" * 20


def word(value: int) -> str:
    return f"{value & ((1 << 256) - 1):064x}"


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def topic_addr(address: str) -> str:
    return "0x" + addr_word(address)


def test_initializer_created_topic_matches_robinhood_lbp():
    assert INITIALIZER_CREATED_TOPIC == (
        "0x6d759545eb439f07e70f45431d6339af7a4f1ffef06d43e8ddf47fdb0799708c"
    )


def test_decode_lbp_initializer_created_static_head():
    words = [
        word(32),
        addr_word(TOKEN),
        addr_word(ZERO),
        word(30_100_000),
        word(200_000_000 * 10**18),
        addr_word(RECIPIENT),
        addr_word(POSITION),
        word(2500),
        word(50),
        addr_word(ZERO),
        word(352),
        word(576),
    ]
    # Dynamic tails are irrelevant to the fields HLP uses here.
    words += [word(0)] * 10
    log = RawLog(
        chain_id=4663,
        block_number=30_000_001,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=1,
        log_index=2,
        address=normalize_address(POOLS_TRADE_LBP_STRATEGY),
        topics=(INITIALIZER_CREATED_TOPIC, topic_addr(INITIALIZER)),
        data="0x" + "".join(words),
        removed=False,
    )
    row = decode_pools_trade_lbp_initializer_created(log)
    assert row.initializer == INITIALIZER
    assert row.token == TOKEN
    assert row.currency == ZERO
    assert row.migration_block == 30_100_000
    assert row.reserved_token_amount_for_lp == 200_000_000 * 10**18
    assert row.pool_fee == 2500
    assert row.pool_tick_spacing == 50
