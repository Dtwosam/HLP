"""pools.fun PartyFactory launch adapter for Robinhood Chain."""

from __future__ import annotations

from hlp.config import POOLS_FUN_FACTORY, normalize_address
from hlp.data.types import PoolsFunLaunch, RawLog
from hlp.protocols.evm import (
    abi_string_at,
    data_words,
    event_topic,
    signed_word,
    topic_address,
    word_address,
)


TOKEN_LAUNCHED_SIG = (
    "TokenLaunched(address,address,address,address,address,address,int24,string,uint256)"
)
TOKEN_LAUNCHED_TOPIC = event_topic(TOKEN_LAUNCHED_SIG)


def decode_pools_fun_launch(log: RawLog) -> PoolsFunLaunch:
    if log.address != normalize_address(POOLS_FUN_FACTORY):
        raise ValueError("not a pools.fun PartyFactory log")
    if not log.topics or log.topics[0] != TOKEN_LAUNCHED_TOPIC:
        raise ValueError("not pools.fun TokenLaunched")
    if len(log.topics) != 4:
        raise ValueError("unexpected pools.fun TokenLaunched topic count")
    words = data_words(log.data)
    if len(words) < 6:
        raise ValueError("unexpected pools.fun TokenLaunched data length")
    return PoolsFunLaunch(
        token=topic_address(log.topics[1]),
        pool=topic_address(log.topics[2]),
        creator=topic_address(log.topics[3]),
        paired_asset=word_address(words[0]),
        deployer=word_address(words[1]),
        fee_recipient=word_address(words[2]),
        start_tick=signed_word(words[3], bits=24),
        metadata_uri=abi_string_at(log.data, 4),
        dev_buy_amount_out=words[5],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
