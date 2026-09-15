"""Uniswap V3/V4 event decoders used by HLP.

V3 source:
Uniswap/v3-core contracts/interfaces/pool/IUniswapV3PoolEvents.sol

V4 source:
Uniswap v4-core IPoolManager.sol (vendored by the verified Pons repository).
"""

from __future__ import annotations

from hlp.data.types import (
    PonsV2PoolRegistration,
    RawLog,
    V3PoolCreated,
    V3PoolInitialized,
    V3Swap,
    V4PoolInitialized,
    V4Swap,
)
from hlp.protocols.evm import (
    data_words,
    event_topic,
    signed_word,
    topic_address,
    topic_bytes32,
    word_address,
)


V3_POOL_CREATED_SIG = "PoolCreated(address,address,uint24,int24,address)"
V3_INITIALIZE_SIG = "Initialize(uint160,int24)"
V3_SWAP_SIG = "Swap(address,address,int256,int256,uint160,uint128,int24)"
V4_INITIALIZE_SIG = "Initialize(bytes32,address,address,uint24,int24,address,uint160,int24)"
V4_SWAP_SIG = "Swap(bytes32,address,int128,int128,uint160,uint128,int24,uint24)"
PONS_V2_POOL_REGISTERED_SIG = "PoolRegistered(bytes32,address,address,address)"

V3_POOL_CREATED_TOPIC = event_topic(V3_POOL_CREATED_SIG)
V3_INITIALIZE_TOPIC = event_topic(V3_INITIALIZE_SIG)
V3_SWAP_TOPIC = event_topic(V3_SWAP_SIG)
V4_INITIALIZE_TOPIC = event_topic(V4_INITIALIZE_SIG)
V4_SWAP_TOPIC = event_topic(V4_SWAP_SIG)
PONS_V2_POOL_REGISTERED_TOPIC = event_topic(PONS_V2_POOL_REGISTERED_SIG)



def decode_v3_pool_created(log: RawLog) -> V3PoolCreated:
    if not log.topics or log.topics[0] != V3_POOL_CREATED_TOPIC:
        raise ValueError("not a Uniswap V3 PoolCreated event")
    if len(log.topics) != 4:
        raise ValueError("unexpected Uniswap V3 PoolCreated topic count")
    words = data_words(log.data)
    if len(words) != 2:
        raise ValueError("unexpected Uniswap V3 PoolCreated data length")
    return V3PoolCreated(
        factory=log.address,
        token0=topic_address(log.topics[1]),
        token1=topic_address(log.topics[2]),
        fee=int(log.topics[3], 16),
        tick_spacing=signed_word(words[0], bits=24),
        pool=word_address(words[1]),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_v4_pool_initialized(log: RawLog) -> V4PoolInitialized:
    if not log.topics or log.topics[0] != V4_INITIALIZE_TOPIC:
        raise ValueError("not a Uniswap V4 Initialize event")
    if len(log.topics) != 4:
        raise ValueError("unexpected Uniswap V4 Initialize topic count")
    words = data_words(log.data)
    if len(words) != 5:
        raise ValueError("unexpected Uniswap V4 Initialize data length")
    return V4PoolInitialized(
        pool_manager=log.address,
        pool_id=topic_bytes32(log.topics[1]),
        currency0=topic_address(log.topics[2]),
        currency1=topic_address(log.topics[3]),
        fee=words[0],
        tick_spacing=signed_word(words[1], bits=24),
        hooks=word_address(words[2]),
        sqrt_price_x96=words[3],
        tick=signed_word(words[4], bits=24),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )



def decode_v3_pool_initialized(log: RawLog) -> V3PoolInitialized:
    if not log.topics or log.topics[0] != V3_INITIALIZE_TOPIC:
        raise ValueError("not a Uniswap V3 Initialize event")
    if len(log.topics) != 1:
        raise ValueError("unexpected Uniswap V3 Initialize topic count")
    words = data_words(log.data)
    if len(words) != 2:
        raise ValueError("unexpected Uniswap V3 Initialize data length")
    return V3PoolInitialized(
        pool=log.address,
        sqrt_price_x96=words[0],
        tick=signed_word(words[1], bits=24),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


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
