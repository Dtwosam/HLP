"""Pons V1/V2 protocol adapter.

Source of event signatures:
https://github.com/ponsdotdev/ponsfamily

The adapter uses factory events for launch discovery. V2 curve addresses are
then used to decode pre-graduation CurveBuy/CurveSell events.
"""

from __future__ import annotations

from dataclasses import dataclass

from hlp.config import PONS_V1_FACTORY, PONS_V2_FACTORY, normalize_address
from hlp.data.types import CurveTrade, PonsLaunch, RawLog
from hlp.protocols.evm import data_words, event_topic, topic_address, word_address


V1_TOKEN_DEPLOYED_SIG = (
    "TokenDeployed(address,address,address,address,uint256,uint256)"
)
V1_TOKEN_LAUNCHED_SIG = (
    "TokenLaunched(address,address,address,address,address,uint256,uint256,uint256,uint256,uint256)"
)
V2_TOKEN_LAUNCHED_SIG = (
    "TokenLaunched(address,address,address,address,uint256,uint256)"
)
V2_POOL_GRADUATED_SIG = "PoolGraduated(address,uint256,uint256,uint256)"
V2_CURVE_BUY_SIG = "CurveBuy(address,address,uint256,uint256,uint256,uint256)"
V2_CURVE_SELL_SIG = "CurveSell(address,address,uint256,uint256,uint256,uint256)"

V1_TOKEN_DEPLOYED_TOPIC = event_topic(V1_TOKEN_DEPLOYED_SIG)
V1_TOKEN_LAUNCHED_TOPIC = event_topic(V1_TOKEN_LAUNCHED_SIG)
V2_TOKEN_LAUNCHED_TOPIC = event_topic(V2_TOKEN_LAUNCHED_SIG)
V2_POOL_GRADUATED_TOPIC = event_topic(V2_POOL_GRADUATED_SIG)
V2_CURVE_BUY_TOPIC = event_topic(V2_CURVE_BUY_SIG)
V2_CURVE_SELL_TOPIC = event_topic(V2_CURVE_SELL_SIG)


@dataclass(frozen=True, slots=True)
class PonsFactory:
    version: str
    address: str
    launch_topic: str


PONS_FACTORIES = (
    PonsFactory("v1", normalize_address(PONS_V1_FACTORY), V1_TOKEN_LAUNCHED_TOPIC),
    PonsFactory("v2", normalize_address(PONS_V2_FACTORY), V2_TOKEN_LAUNCHED_TOPIC),
)


def decode_v2_launch(log: RawLog) -> PonsLaunch:
    if log.address != normalize_address(PONS_V2_FACTORY):
        raise ValueError("not a Pons V2 factory log")
    if not log.topics or log.topics[0] != V2_TOKEN_LAUNCHED_TOPIC:
        raise ValueError("not a Pons V2 TokenLaunched event")
    if len(log.topics) != 4:
        raise ValueError("unexpected Pons V2 TokenLaunched topic count")
    words = data_words(log.data)
    if len(words) != 3:
        raise ValueError("unexpected Pons V2 TokenLaunched data length")
    token = topic_address(log.topics[1])
    curve = topic_address(log.topics[2])
    deployer = topic_address(log.topics[3])
    pair_token = word_address(words[0])
    return PonsLaunch(
        version="v2",
        token=token,
        curve=curve,
        deployer=deployer,
        pair_token=pair_token,
        launch_config_id=words[1],
        graduation_threshold=words[2],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_v1_launch(log: RawLog) -> PonsLaunch:
    if log.address != normalize_address(PONS_V1_FACTORY):
        raise ValueError("not a Pons V1 factory log")
    if not log.topics or log.topics[0] != V1_TOKEN_LAUNCHED_TOPIC:
        raise ValueError("not a Pons V1 TokenLaunched event")
    if len(log.topics) != 4:
        raise ValueError("unexpected Pons V1 TokenLaunched topic count")
    words = data_words(log.data)
    # pairToken, pool, dexId, launchConfigId, positionId,
    # restrictionsEndBlock, initialBuyAmount
    if len(words) != 7:
        raise ValueError("unexpected Pons V1 TokenLaunched data length")
    return PonsLaunch(
        version="v1",
        token=topic_address(log.topics[1]),
        deployer=topic_address(log.topics[2]),
        pair_token=word_address(words[0]),
        pool=word_address(words[1]),
        launch_config_id=words[3],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_v2_curve_trade(log: RawLog, *, token: str) -> CurveTrade:
    if len(log.topics) != 3:
        raise ValueError("unexpected curve trade topic count")
    words = data_words(log.data)
    if len(words) != 4:
        raise ValueError("unexpected curve trade data length")

    topic0 = log.topics[0]
    if topic0 == V2_CURVE_BUY_TOPIC:
        side = "buy"
        actor = topic_address(log.topics[1])
        recipient = topic_address(log.topics[2])
        quote_amount, token_amount, fee, tax = words
    elif topic0 == V2_CURVE_SELL_TOPIC:
        side = "sell"
        actor = topic_address(log.topics[1])
        recipient = topic_address(log.topics[2])
        token_amount, quote_amount, fee, tax = words
    else:
        raise ValueError("not a supported Pons V2 curve trade")

    return CurveTrade(
        token=normalize_address(token),
        curve=log.address,
        side=side,
        actor=actor,
        recipient=recipient,
        quote_amount=quote_amount,
        token_amount=token_amount,
        fee=fee,
        tax=tax,
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
        log_index=log.log_index,
    )
