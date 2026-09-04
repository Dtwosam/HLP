"""hood.fun raw launch/trade adapter for Robinhood Chain.

The current hood.fun contract uses a TokenCreated payload with configurable
virtual reserves and curve inventory, plus a FriendTech-signature Trade event
whose indexed addresses are token then trader. HLP validates the field
semantics against raw reserve conservation before using them for pricing.
"""

from __future__ import annotations

from hlp.config import HOOD_FUN_CURRENT, normalize_address
from hlp.data.types import HoodFunEvent, RawLog
from hlp.protocols.evm import abi_string_at, data_words, event_topic, topic_address


TOKEN_CREATED_SIG = (
    "TokenCreated(address,address,string,string,string,uint256,uint256,uint256)"
)
TRADE_SIG = "Trade(address,address,bool,uint256,uint256,uint256,uint256,uint256)"

TOKEN_CREATED_TOPIC = event_topic(TOKEN_CREATED_SIG)
TRADE_TOPIC = event_topic(TRADE_SIG)
HOOD_FUN_CURVE_TOPICS = (TOKEN_CREATED_TOPIC, TRADE_TOPIC)


def _base(log: RawLog, event_type: str, token: str, **kwargs) -> HoodFunEvent:
    return HoodFunEvent(
        event_type=event_type,
        token=token,
        actor=kwargs.get("actor"),
        is_buy=kwargs.get("is_buy"),
        quote_amount_raw=kwargs.get("quote_amount_raw"),
        token_amount_raw=kwargs.get("token_amount_raw"),
        fee_raw=kwargs.get("fee_raw"),
        virtual_quote_raw=kwargs.get("virtual_quote_raw"),
        virtual_token_raw=kwargs.get("virtual_token_raw"),
        curve_inventory_raw=kwargs.get("curve_inventory_raw"),
        name=kwargs.get("name"),
        symbol=kwargs.get("symbol"),
        metadata_uri=kwargs.get("metadata_uri"),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_hood_fun_event(log: RawLog) -> HoodFunEvent:
    if log.address != normalize_address(HOOD_FUN_CURRENT):
        raise ValueError("not the validated current hood.fun contract")
    if not log.topics:
        raise ValueError("hood.fun log has no topic0")

    topic0 = log.topics[0]
    words = data_words(log.data)

    if topic0 == TOKEN_CREATED_TOPIC:
        if len(log.topics) != 3 or len(words) < 6:
            raise ValueError("unexpected hood.fun TokenCreated layout")
        return _base(
            log,
            "token_created",
            topic_address(log.topics[1]),
            actor=topic_address(log.topics[2]),
            name=abi_string_at(log.data, 0),
            symbol=abi_string_at(log.data, 1),
            metadata_uri=abi_string_at(log.data, 2),
            virtual_quote_raw=words[3],
            virtual_token_raw=words[4],
            curve_inventory_raw=words[5],
        )

    if topic0 == TRADE_TOPIC:
        if len(log.topics) != 3 or len(words) != 6:
            raise ValueError("unexpected hood.fun Trade layout")
        if words[0] not in {0, 1}:
            raise ValueError("hood.fun Trade bool word is not 0/1")
        return _base(
            log,
            "trade",
            topic_address(log.topics[1]),
            actor=topic_address(log.topics[2]),
            is_buy=bool(words[0]),
            quote_amount_raw=words[1],
            token_amount_raw=words[2],
            fee_raw=words[3],
            virtual_quote_raw=words[4],
            virtual_token_raw=words[5],
        )

    raise ValueError(f"unsupported hood.fun topic: {topic0}")
