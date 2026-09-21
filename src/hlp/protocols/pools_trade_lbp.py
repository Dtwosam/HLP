"""pools.trade Crowd Launch / Uniswap LBP strategy decoder."""

from __future__ import annotations

from hlp.config import normalize_address
from hlp.data.types import CcaPriceEvent, PoolsTradeLbpInitializerCreated, RawLog
from hlp.protocols.evm import data_words, event_topic, signed_word, topic_address, word_address


POOLS_TRADE_LBP_STRATEGY = "0x05d552391067389ee44fec3924157ed33f976000"

INITIALIZER_CREATED_SIG = (
    "InitializerCreated(address,"
    "(address,address,uint64,uint128,address,address,"
    "(uint24,int24,address),bytes,bytes))"
)
INITIALIZER_CREATED_TOPIC = event_topic(INITIALIZER_CREATED_SIG)

# These two CCA initializer topics are frozen from raw Robinhood Chain logs in
# Phase-2 evidence run 35614449062. Their Solidity source signatures have not
# been independently frozen, so HLP names them by the fields/layout actually
# observed rather than inventing ABI provenance.
CCA_CLEARING_PRICE_TOPIC = (
    "0x30adbe996d7a69a21fdebcc1f8a46270bf6c22d505a7d872c1ab4767aa707609"
)
CCA_CHECKPOINT_TOPIC = (
    "0xf1e4b6d7d0d7c5deb6393a39862d66a2f2ecb034f3283a8a597f9bf0c36f76fa"
)
CCA_PRICE_TOPICS = (
    CCA_CLEARING_PRICE_TOPIC,
    CCA_CHECKPOINT_TOPIC,
)


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



def decode_pools_trade_cca_price_event(log: RawLog) -> CcaPriceEvent:
    """Decode the observed CCA clearing-price/checkpoint event surface."""
    if not log.topics or log.topics[0] not in CCA_PRICE_TOPICS:
        raise ValueError("not an observed pools.trade CCA price event")
    if len(log.topics) != 1:
        raise ValueError("unexpected pools.trade CCA price topic count")

    words = data_words(log.data)
    topic0 = log.topics[0]
    if topic0 == CCA_CLEARING_PRICE_TOPIC:
        if len(words) != 2:
            raise ValueError(
                "unexpected pools.trade CCA clearing-price layout"
            )
        checkpoint_block, clearing_price_x96 = words
        cumulative_mps = None
        event_type = "clearing_price"
    else:
        if len(words) != 3:
            raise ValueError(
                "unexpected pools.trade CCA checkpoint layout"
            )
        checkpoint_block, clearing_price_x96, cumulative_mps = words
        event_type = "checkpoint"

    if checkpoint_block <= 0:
        raise ValueError("pools.trade CCA checkpoint block must be positive")
    if clearing_price_x96 <= 0:
        raise ValueError(
            "pools.trade CCA clearing price must be positive"
        )

    return CcaPriceEvent(
        auction=normalize_address(log.address),
        event_type=event_type,
        checkpoint_block=checkpoint_block,
        clearing_price_x96=clearing_price_x96,
        cumulative_mps=cumulative_mps,
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
