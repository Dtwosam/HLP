"""Uniswap V3/V4 event decoders used by HLP.

V3 source:
Uniswap/v3-core contracts/interfaces/pool/IUniswapV3PoolEvents.sol

V4 source:
Uniswap v4-core IPoolManager.sol (vendored by the verified Pons repository).
"""

from __future__ import annotations

from hlp.data.types import PonsV2PoolRegistration, RawLog, V3Swap, V4Swap
from hlp.protocols.evm import (
    data_words,
    event_topic,
    signed_word,
    topic_address,
    topic_bytes32,
    word_address,
)


V3_SWAP_SIG = "Swap(address,address,int256,int256,uint160,uint128,int24)"
V4_SWAP_SIG = "Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)"
PONS_V2_POOL_REGISTERED_SIG = "PoolRegistered(bytes32,address,address,address)"

V3_SWAP_TOPIC = event_topic(V3_SWAP_SIG)
V4_SWAP_TOPIC = event_topic(V4_SWAP_SIG)
PONS_V2_POOL_REGISTERED_TOPIC = event_topic(PONS_V2_POOL_REGISTERED_SIG)


def decode_v3_swap(log: RawLog) -> V3Swap:
    if not log.topics or log.topics[0] != V3_SWAP_TOPIC:
        raise ValueError("not a Uniswap V3 Swap event")
    if len(log.topics) != 3:
        raise ValueError("unexpected Uniswap V3 Swap topic count")
    words = data_words(log.data)
    if len(words) != 5:
        raise ValueError("unexpected Uniswap V3 Swap data length")
    return V3Swap(
        pool=log.address,
        sender=topic_address(log.topics[1]),
        recipient=topic_address(log.topics[2]),
        amount0=signed_word(words[0]),
        amount1=signed_word(words[1]),
        sqrt_price_x96=words[2],
        liquidity=words[3],
        tick=signed_word(words[4]),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_v4_swap(log: RawLog) -> V4Swap:
    if not log.topics or log.topics[0] != V4_SWAP_TOPIC:
        raise ValueError("not a Uniswap V4 Swap event")
    if len(log.topics) != 3:
        raise ValueError("unexpected Uniswap V4 Swap topic count")
    words = data_words(log.data)
    if len(words) != 6:
        raise ValueError("unexpected Uniswap V4 Swap data length")
    return V4Swap(
        pool_manager=log.address,
        pool_id=topic_bytes32(log.topics[1]),
        sender=topic_address(log.topics[2]),
        amount0=signed_word(words[0]),
        amount1=signed_word(words[1]),
        sqrt_price_x96=words[2],
        liquidity=words[3],
        tick=signed_word(words[4]),
        fee=words[5],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_pons_v2_pool_registered(log: RawLog) -> PonsV2PoolRegistration:
    if not log.topics or log.topics[0] != PONS_V2_POOL_REGISTERED_TOPIC:
        raise ValueError("not a Pons V2 PoolRegistered event")
    if len(log.topics) != 2:
        raise ValueError("unexpected Pons V2 PoolRegistered topic count")
    words = data_words(log.data)
    if len(words) != 3:
        raise ValueError("unexpected Pons V2 PoolRegistered data length")
    return PonsV2PoolRegistration(
        hook=log.address,
        pool_id=topic_bytes32(log.topics[1]),
        token=word_address(words[0]),
        quote_token=word_address(words[1]),
        creator=word_address(words[2]),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
