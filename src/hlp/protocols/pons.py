"""Pons V1/V2 protocol adapter.

Source of event signatures:
https://github.com/ponsdotdev/ponsfamily

The adapter uses factory events for launch discovery. V2 curve addresses are
then used to decode pre-graduation CurveBuy/CurveSell events.
"""

from __future__ import annotations

from dataclasses import dataclass

from hlp.config import (
    PONS_V1_FACTORIES,
    PONS_V1_FACTORY,
    PONS_V2_FACTORY,
    normalize_address,
)
from hlp.data.types import (
    CurveBuyback,
    CurveTrade,
    PonsLaunch,
    PonsV1LaunchConfig,
    PonsV2PairEconomics,
    PonsV2PoolGraduation,
    RawLog,
)
from hlp.protocols.evm import data_words, event_topic, signed_word, topic_address, word_address


V1_TOKEN_DEPLOYED_SIG = (
    "TokenDeployed(address,address,address,address,uint256,uint256)"
)
V1_TOKEN_LAUNCHED_SIG = (
    "TokenLaunched(address,address,address,address,address,uint256,uint256,uint256,uint256,uint256)"
)
V1_LAUNCH_CONFIG_ADDED_SIG = (
    "LaunchConfigAdded(uint256,address,uint256,int24,uint256,uint16,uint16,uint32,uint24,bool,bool)"
)
V1_LAUNCH_CONFIG_UPDATED_SIG = (
    "LaunchConfigUpdated(uint256,address,uint256,int24,uint256,uint16,uint16,uint32,uint24,bool,bool)"
)
V2_TOKEN_LAUNCHED_SIG = (
    "TokenLaunched(address,address,address,address,uint256,uint256)"
)
V2_POOL_GRADUATED_SIG = "PoolGraduated(address,uint256,uint256,uint256)"
V2_LAUNCH_CONFIG_ADDED_SIG = "LaunchConfigAdded(uint256)"
V2_LAUNCH_CONFIG_UPDATED_SIG = "LaunchConfigUpdated(uint256)"
V2_PAIR_TOKEN_ECONOMICS_UPDATED_SIG = (
    "PairTokenEconomicsUpdated(address,uint256,uint256,uint8)"
)
V2_CURVE_BUYBACK_LOCKED_SIG = "BuybackLocked(uint256,uint256)"
V2_CURVE_BUY_SIG = "CurveBuy(address,address,uint256,uint256,uint256,uint256)"
V2_CURVE_SELL_SIG = "CurveSell(address,address,uint256,uint256,uint256,uint256)"

V1_TOKEN_DEPLOYED_TOPIC = event_topic(V1_TOKEN_DEPLOYED_SIG)
V1_TOKEN_LAUNCHED_TOPIC = event_topic(V1_TOKEN_LAUNCHED_SIG)
V1_LAUNCH_CONFIG_ADDED_TOPIC = event_topic(V1_LAUNCH_CONFIG_ADDED_SIG)
V1_LAUNCH_CONFIG_UPDATED_TOPIC = event_topic(V1_LAUNCH_CONFIG_UPDATED_SIG)
V2_TOKEN_LAUNCHED_TOPIC = event_topic(V2_TOKEN_LAUNCHED_SIG)
V2_POOL_GRADUATED_TOPIC = event_topic(V2_POOL_GRADUATED_SIG)
V2_LAUNCH_CONFIG_ADDED_TOPIC = event_topic(V2_LAUNCH_CONFIG_ADDED_SIG)
V2_LAUNCH_CONFIG_UPDATED_TOPIC = event_topic(V2_LAUNCH_CONFIG_UPDATED_SIG)
V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC = event_topic(
    V2_PAIR_TOKEN_ECONOMICS_UPDATED_SIG
)
V2_CURVE_BUYBACK_LOCKED_TOPIC = event_topic(V2_CURVE_BUYBACK_LOCKED_SIG)
V2_CURVE_BUY_TOPIC = event_topic(V2_CURVE_BUY_SIG)
V2_CURVE_SELL_TOPIC = event_topic(V2_CURVE_SELL_SIG)


@dataclass(frozen=True, slots=True)
class PonsFactory:
    version: str
    address: str
    launch_topic: str


PONS_V1_FACTORY_SET = {
    normalize_address(address)
    for address in PONS_V1_FACTORIES
}

PONS_FACTORIES = (
    *(
        PonsFactory("v1", normalize_address(address), V1_TOKEN_LAUNCHED_TOPIC)
        for address in PONS_V1_FACTORIES
    ),
    PonsFactory("v2", normalize_address(PONS_V2_FACTORY), V2_TOKEN_LAUNCHED_TOPIC),
)



def decode_v1_launch_config(log: RawLog) -> PonsV1LaunchConfig:
    """Decode a V1 LaunchConfigAdded/LaunchConfigUpdated event."""
    if log.address not in PONS_V1_FACTORY_SET:
        raise ValueError("not a known Pons V1 factory log")
    if not log.topics:
        raise ValueError("missing Pons V1 config topic")
    if log.topics[0] == V1_LAUNCH_CONFIG_ADDED_TOPIC:
        action = "added"
    elif log.topics[0] == V1_LAUNCH_CONFIG_UPDATED_TOPIC:
        action = "updated"
    else:
        raise ValueError("not a Pons V1 launch-config event")
    if len(log.topics) != 2:
        raise ValueError("unexpected Pons V1 launch-config topic count")
    words = data_words(log.data)
    if len(words) != 10:
        raise ValueError("unexpected Pons V1 launch-config data length")
    return PonsV1LaunchConfig(
        action=action,
        config_id=int(log.topics[1], 16),
        pair_token=word_address(words[0]),
        graduation_threshold=words[1],
        initial_tick=signed_word(words[2], bits=24),
        supply=words[3],
        max_wallet_bps=words[4],
        max_tx_bps=words[5],
        restriction_blocks=words[6],
        reserved_fee=words[7],
        enabled=bool(words[8]),
        router_requires_deadline=bool(words[9]),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
        factory=log.address,
    )




def decode_v2_launch_config_event_id(log: RawLog) -> tuple[str, int]:
    if log.address != normalize_address(PONS_V2_FACTORY):
        raise ValueError("not a Pons V2 factory log")
    if not log.topics:
        raise ValueError("missing V2 launch-config topic")
    if log.topics[0] == V2_LAUNCH_CONFIG_ADDED_TOPIC:
        action = "added"
    elif log.topics[0] == V2_LAUNCH_CONFIG_UPDATED_TOPIC:
        action = "updated"
    else:
        raise ValueError("not a V2 launch-config id event")
    if len(log.topics) != 2:
        raise ValueError("unexpected V2 launch-config topic count")
    if data_words(log.data):
        raise ValueError("unexpected V2 launch-config event data")
    return action, int(log.topics[1], 16)


def decode_v2_pair_token_economics(log: RawLog) -> PonsV2PairEconomics:
    if log.address != normalize_address(PONS_V2_FACTORY):
        raise ValueError("not a Pons V2 factory log")
    if not log.topics or log.topics[0] != V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC:
        raise ValueError("not a Pons V2 PairTokenEconomicsUpdated event")
    if len(log.topics) != 2:
        raise ValueError("unexpected pair-economics topic count")
    words = data_words(log.data)
    if len(words) != 3:
        raise ValueError("unexpected pair-economics data length")
    decimals = words[2]
    if decimals > 255:
        raise ValueError("invalid pair-token decimals")
    return PonsV2PairEconomics(
        pair_token=topic_address(log.topics[1]),
        phantom_quote=words[0],
        graduation_threshold=words[1],
        decimals=decimals,
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_v2_curve_buyback(log: RawLog) -> CurveBuyback:
    if not log.topics or log.topics[0] != V2_CURVE_BUYBACK_LOCKED_TOPIC:
        raise ValueError("not a Pons V2 BuybackLocked event")
    if len(log.topics) != 1:
        raise ValueError("unexpected BuybackLocked topic count")
    words = data_words(log.data)
    if len(words) != 2:
        raise ValueError("unexpected BuybackLocked data length")
    return CurveBuyback(
        curve=log.address,
        quote_spent=words[0],
        tokens_locked=words[1],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_v2_pool_graduation(log: RawLog) -> PonsV2PoolGraduation:
    if log.address != normalize_address(PONS_V2_FACTORY):
        raise ValueError("not a Pons V2 factory log")
    if not log.topics or log.topics[0] != V2_POOL_GRADUATED_TOPIC:
        raise ValueError("not a Pons V2 PoolGraduated event")
    if len(log.topics) != 2:
        raise ValueError("unexpected PoolGraduated topic count")
    words = data_words(log.data)
    if len(words) != 3:
        raise ValueError("unexpected PoolGraduated data length")
    return PonsV2PoolGraduation(
        token=topic_address(log.topics[1]),
        position_id=words[0],
        token_amount=words[1],
        pair_token_amount=words[2],
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
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
    if log.address not in PONS_V1_FACTORY_SET:
        raise ValueError("not a known Pons V1 factory log")
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
        dex_factory=topic_address(log.topics[3]),
        pair_token=word_address(words[0]),
        pool=word_address(words[1]),
        dex_id=words[2],
        launch_config_id=words[3],
        position_id=words[4],
        restrictions_end_block=words[5],
        initial_buy_amount=words[6],
        factory=log.address,
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
    )
