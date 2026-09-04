"""Flap.sh raw Portal event adapter for Robinhood Chain.

Portal identity is confirmed by Flap's own Robinhood repositories. Event
signatures match the published Flap Portal ABI and independent production
integrations. HLP validates them against raw Robinhood Chain logs before use.
"""

from __future__ import annotations

from hlp.config import FLAP_PORTAL, normalize_address
from hlp.data.types import FlapEvent, RawLog
from hlp.protocols.evm import abi_string_at, data_words, event_topic, word_address


TOKEN_CREATED_SIG = "TokenCreated(uint256,address,uint256,address,string,string,string)"
TOKEN_BOUGHT_SIG = "TokenBought(uint256,address,address,uint256,uint256,uint256,uint256)"
TOKEN_SOLD_SIG = "TokenSold(uint256,address,address,uint256,uint256,uint256,uint256)"
PROGRESS_CHANGED_SIG = "FlapTokenProgressChanged(address,uint256)"
SUPPLY_CHANGED_SIG = "FlapTokenCirculatingSupplyChanged(address,uint256)"
LAUNCHED_TO_DEX_SIG = "LaunchedToDEX(address,address,uint256,uint256)"
CURVE_SET_V2_SIG = "TokenCurveSetV2(address,uint256,uint256,uint256)"
DEX_SUPPLY_THRESH_SET_SIG = "TokenDexSupplyThreshSet(address,uint256)"
QUOTE_SET_SIG = "TokenQuoteSet(address,address)"
TOKEN_VERSION_SET_SIG = "TokenVersionSet(address,uint8)"
MIGRATOR_SET_SIG = "TokenMigratorSet(address,uint8)"
DEX_PREFERENCE_SET_SIG = "TokenDexPreferenceSet(address,uint8,uint8)"

TOKEN_CREATED_TOPIC = event_topic(TOKEN_CREATED_SIG)
TOKEN_BOUGHT_TOPIC = event_topic(TOKEN_BOUGHT_SIG)
TOKEN_SOLD_TOPIC = event_topic(TOKEN_SOLD_SIG)
PROGRESS_CHANGED_TOPIC = event_topic(PROGRESS_CHANGED_SIG)
SUPPLY_CHANGED_TOPIC = event_topic(SUPPLY_CHANGED_SIG)
LAUNCHED_TO_DEX_TOPIC = event_topic(LAUNCHED_TO_DEX_SIG)
CURVE_SET_V2_TOPIC = event_topic(CURVE_SET_V2_SIG)
DEX_SUPPLY_THRESH_SET_TOPIC = event_topic(DEX_SUPPLY_THRESH_SET_SIG)
QUOTE_SET_TOPIC = event_topic(QUOTE_SET_SIG)
TOKEN_VERSION_SET_TOPIC = event_topic(TOKEN_VERSION_SET_SIG)
MIGRATOR_SET_TOPIC = event_topic(MIGRATOR_SET_SIG)
DEX_PREFERENCE_SET_TOPIC = event_topic(DEX_PREFERENCE_SET_SIG)

FLAP_RECONSTRUCTION_TOPICS = (
    TOKEN_CREATED_TOPIC,
    TOKEN_BOUGHT_TOPIC,
    TOKEN_SOLD_TOPIC,
    PROGRESS_CHANGED_TOPIC,
    SUPPLY_CHANGED_TOPIC,
    LAUNCHED_TO_DEX_TOPIC,
    CURVE_SET_V2_TOPIC,
    DEX_SUPPLY_THRESH_SET_TOPIC,
    QUOTE_SET_TOPIC,
    TOKEN_VERSION_SET_TOPIC,
    MIGRATOR_SET_TOPIC,
    DEX_PREFERENCE_SET_TOPIC,
)


def _base(log: RawLog, event_type: str, token: str, **kwargs) -> FlapEvent:
    return FlapEvent(
        event_type=event_type,
        token=token,
        actor=kwargs.get("actor"),
        amount_raw=kwargs.get("amount_raw"),
        quote_amount_raw=kwargs.get("quote_amount_raw"),
        fee_raw=kwargs.get("fee_raw"),
        post_price_raw=kwargs.get("post_price_raw"),
        value_raw=kwargs.get("value_raw"),
        value2_raw=kwargs.get("value2_raw"),
        pool=kwargs.get("pool"),
        name=kwargs.get("name"),
        symbol=kwargs.get("symbol"),
        meta=kwargs.get("meta"),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_flap_event(log: RawLog) -> FlapEvent:
    if log.address != normalize_address(FLAP_PORTAL):
        raise ValueError("not a Flap Portal log")
    if len(log.topics) != 1:
        raise ValueError("Flap Portal reconstruction events must be non-indexed")
    topic0 = log.topics[0]
    words = data_words(log.data)

    if topic0 == TOKEN_CREATED_TOPIC:
        if len(words) < 7:
            raise ValueError("unexpected Flap TokenCreated data length")
        return _base(
            log,
            "token_created",
            word_address(words[3]),
            actor=word_address(words[1]),
            value_raw=words[2],  # creation nonce
            name=abi_string_at(log.data, 4),
            symbol=abi_string_at(log.data, 5),
            meta=abi_string_at(log.data, 6),
        )

    if topic0 in {TOKEN_BOUGHT_TOPIC, TOKEN_SOLD_TOPIC}:
        if len(words) != 7:
            raise ValueError("unexpected Flap trade data length")
        return _base(
            log,
            "token_bought" if topic0 == TOKEN_BOUGHT_TOPIC else "token_sold",
            word_address(words[1]),
            actor=word_address(words[2]),
            amount_raw=words[3],
            quote_amount_raw=words[4],
            fee_raw=words[5],
            post_price_raw=words[6],
            value_raw=words[0],  # event timestamp
        )

    if topic0 in {PROGRESS_CHANGED_TOPIC, SUPPLY_CHANGED_TOPIC, DEX_SUPPLY_THRESH_SET_TOPIC}:
        if len(words) != 2:
            raise ValueError("unexpected Flap two-word state event")
        kind = {
            PROGRESS_CHANGED_TOPIC: "progress_changed",
            SUPPLY_CHANGED_TOPIC: "circulating_supply_changed",
            DEX_SUPPLY_THRESH_SET_TOPIC: "dex_supply_thresh_set",
        }[topic0]
        return _base(log, kind, word_address(words[0]), value_raw=words[1])

    if topic0 == LAUNCHED_TO_DEX_TOPIC:
        if len(words) != 4:
            raise ValueError("unexpected Flap LaunchedToDEX data length")
        return _base(
            log,
            "launched_to_dex",
            word_address(words[0]),
            pool=word_address(words[1]),
            amount_raw=words[2],
            quote_amount_raw=words[3],
        )

    if topic0 == CURVE_SET_V2_TOPIC:
        if len(words) != 4:
            raise ValueError("unexpected Flap TokenCurveSetV2 data length")
        return _base(
            log,
            "curve_set_v2",
            word_address(words[0]),
            value_raw=words[1],
            value2_raw=words[2],
            amount_raw=words[3],  # k
        )

    if topic0 == QUOTE_SET_TOPIC:
        if len(words) != 2:
            raise ValueError("unexpected Flap TokenQuoteSet data length")
        return _base(
            log,
            "quote_set",
            word_address(words[0]),
            actor=word_address(words[1]),  # quote token
        )

    if topic0 in {TOKEN_VERSION_SET_TOPIC, MIGRATOR_SET_TOPIC}:
        if len(words) != 2:
            raise ValueError("unexpected Flap enum state event")
        return _base(
            log,
            "token_version_set" if topic0 == TOKEN_VERSION_SET_TOPIC else "migrator_set",
            word_address(words[0]),
            value_raw=words[1],
        )

    if topic0 == DEX_PREFERENCE_SET_TOPIC:
        if len(words) != 3:
            raise ValueError("unexpected Flap TokenDexPreferenceSet data length")
        return _base(
            log,
            "dex_preference_set",
            word_address(words[0]),
            value_raw=words[1],
            value2_raw=words[2],
        )

    raise ValueError(f"unsupported Flap Portal topic: {topic0}")
