"""pools.trade / Uniswap Liquidity Launcher event adapter."""

from __future__ import annotations

from hlp.config import (
    POOLS_TRADE_INSTANT_STRATEGIES,
    POOLS_TRADE_LAUNCHER_CURRENT,
    POOLS_TRADE_LAUNCHER_ORIGINAL,
    normalize_address,
)
from hlp.data.types import (
    PoolsTradeTokenCreated,
    PoolsTradeTokenDistributed,
    PoolsTradeTokenLaunched,
    RawLog,
)
from hlp.protocols.evm import (
    data_words,
    event_topic,
    signed_word,
    topic_address,
    topic_bytes32,
    word_address,
)


TOKEN_CREATED_SIG = "TokenCreated(address)"
TOKEN_DISTRIBUTED_SIG = "TokenDistributed(address,address,uint256)"
TOKEN_LAUNCHED_SIG = "TokenLaunched(bytes32,address,address,(address,address,uint24,int24,address))"
TOKEN_CREATED_TOPIC = event_topic(TOKEN_CREATED_SIG)
TOKEN_DISTRIBUTED_TOPIC = event_topic(TOKEN_DISTRIBUTED_SIG)
TOKEN_LAUNCHED_TOPIC = event_topic(TOKEN_LAUNCHED_SIG)

LAUNCHERS = {
    normalize_address(POOLS_TRADE_LAUNCHER_CURRENT),
    normalize_address(POOLS_TRADE_LAUNCHER_ORIGINAL),
}
STRATEGIES = {
    normalize_address(address)
    for address in POOLS_TRADE_INSTANT_STRATEGIES
}


def decode_pools_trade_token_created(log: RawLog) -> PoolsTradeTokenCreated:
    if log.address not in LAUNCHERS:
        raise ValueError("not a pools.trade LiquidityLauncher log")
    if not log.topics or log.topics[0] != TOKEN_CREATED_TOPIC:
        raise ValueError("not pools.trade TokenCreated")
    if len(log.topics) != 2 or data_words(log.data):
        raise ValueError("unexpected pools.trade TokenCreated layout")
    return PoolsTradeTokenCreated(
        launcher=log.address,
        token=topic_address(log.topics[1]),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )



def decode_pools_trade_token_distributed(log: RawLog) -> PoolsTradeTokenDistributed:
    if log.address not in LAUNCHERS:
        raise ValueError("not a pools.trade LiquidityLauncher log")
    if not log.topics or log.topics[0] != TOKEN_DISTRIBUTED_TOPIC:
        raise ValueError("not pools.trade TokenDistributed")
    if len(log.topics) != 3:
        raise ValueError("unexpected pools.trade TokenDistributed topic count")
    words = data_words(log.data)
    if len(words) != 1:
        raise ValueError("unexpected pools.trade TokenDistributed data length")
    return PoolsTradeTokenDistributed(
        launcher=log.address,
        token=topic_address(log.topics[1]),
        strategy=topic_address(log.topics[2]),
        amount_raw=words[0],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_pools_trade_token_launched(log: RawLog) -> PoolsTradeTokenLaunched:
    if log.address not in STRATEGIES:
        raise ValueError("not a pools.trade InstantLaunchStrategy log")
    if not log.topics or log.topics[0] != TOKEN_LAUNCHED_TOPIC:
        raise ValueError("not pools.trade TokenLaunched")
    if len(log.topics) != 4:
        raise ValueError("unexpected pools.trade TokenLaunched topic count")
    words = data_words(log.data)
    if len(words) != 5:
        raise ValueError("unexpected pools.trade TokenLaunched data length")
    return PoolsTradeTokenLaunched(
        strategy=log.address,
        pool_id=topic_bytes32(log.topics[1]),
        token=topic_address(log.topics[2]),
        final_position_recipient=topic_address(log.topics[3]),
        currency0=word_address(words[0]),
        currency1=word_address(words[1]),
        fee=words[2],
        tick_spacing=signed_word(words[3], bits=24),
        hooks=word_address(words[4]),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
