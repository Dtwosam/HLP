"""pools.trade Crowd Launch / Uniswap LBP strategy decoder."""

from __future__ import annotations

from hlp.config import normalize_address
from hlp.data.types import PoolsTradeLbpInitializerCreated, RawLog
from hlp.protocols.evm import data_words, event_topic, signed_word, topic_address, word_address


POOLS_TRADE_LBP_STRATEGY = "0x05d552391067389ee44fec3924157ed33f976000"

INITIALIZER_CREATED_SIG = (
    "InitializerCreated(address,"
    "(address,address,uint64,uint128,address,address,"
    "(uint24,int24,address),bytes,bytes))"
)
INITIALIZER_CREATED_TOPIC = event_topic(INITIALIZER_CREATED_SIG)


def decode_pools_trade_lbp_initializer_created(
    log: RawLog,
) -> PoolsTradeLbpInitializerCreated:
    strategy = normalize_address(POOLS_TRADE_LBP_STRATEGY)
    if log.address != strategy:
        raise ValueError("not the pools.trade LBP strategy")
    if not log.topics or log.topics[0] != INITIALIZER_CREATED_TOPIC:
        raise ValueError("not pools.trade InitializerCreated")
    if len(log.topics) != 2:
        raise ValueError("unexpected InitializerCreated topic count")
    words = data_words(log.data)
    if len(words) < 12:
        raise ValueError("unexpected InitializerCreated data length")
    # The only non-indexed argument is a dynamic MigratorParameters tuple,
    # so the first word is an offset to the tuple body.
    if words[0] != 32:
        raise ValueError("unexpected MigratorParameters tuple offset")
    return PoolsTradeLbpInitializerCreated(
        strategy=strategy,
        initializer=topic_address(log.topics[1]),
        token=word_address(words[1]),
        currency=word_address(words[2]),
        migration_block=words[3],
        reserved_token_amount_for_lp=words[4],
        recipient=word_address(words[5]),
        position_recipient=word_address(words[6]),
        pool_fee=words[7],
        pool_tick_spacing=signed_word(words[8], bits=24),
        pool_hook=word_address(words[9]),
        position_definitions_offset=words[10],
        lp_allocation_schedule_offset=words[11],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
