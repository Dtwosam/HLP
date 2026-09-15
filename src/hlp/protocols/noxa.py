"""NOXA Robinhood Chain launch adapter.

Factory identity:
https://docs.noxa.fi/contracts/noxa-fun/

The event ABI is independently recovered from NOXA's production frontend and
is byte-for-byte proven against successful Robinhood mainnet launch calldata
by nirholas/robinhood-chain-launcher. HLP still verifies the event stream from
raw chain logs before using it.
"""

from __future__ import annotations

from hlp.config import NOXA_LAUNCH_FACTORY, normalize_address
from hlp.data.types import InstantV3Launch, RawLog
from hlp.protocols.evm import data_words, event_topic, topic_address, word_address


TOKEN_LAUNCHED_SIG = (
    "TokenLaunched(address,address,address,address,address,uint256,uint256,uint256,uint256,uint256)"
)
TOKEN_LAUNCHED_TOPIC = event_topic(TOKEN_LAUNCHED_SIG)


def decode_noxa_launch(log: RawLog) -> InstantV3Launch:
    factory = normalize_address(NOXA_LAUNCH_FACTORY)
    if log.address != factory:
        raise ValueError("not a NOXA launch-factory log")
    if not log.topics or log.topics[0] != TOKEN_LAUNCHED_TOPIC:
        raise ValueError("not a NOXA TokenLaunched event")
    if len(log.topics) != 4:
        raise ValueError("unexpected NOXA TokenLaunched topic count")
    words = data_words(log.data)
    if len(words) != 7:
        raise ValueError("unexpected NOXA TokenLaunched data length")
    return InstantV3Launch(
        venue="noxa",
        factory=factory,
        token=topic_address(log.topics[1]),
        deployer=topic_address(log.topics[2]),
        dex_factory=topic_address(log.topics[3]),
        pair_token=word_address(words[0]),
        pool=word_address(words[1]),
        dex_id=words[2],
        launch_config_id=words[3],
        position_id=words[4],
        restrictions_end_block=words[5],
        initial_buy_amount=words[6],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )
