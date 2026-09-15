"""trench.today raw event adapter for Robinhood Chain."""

from __future__ import annotations

from hlp.config import TRENCH_MANAGER, normalize_address
from hlp.data.types import RawLog, TrenchEvent
from hlp.protocols.evm import abi_string_at, data_words, event_topic, topic_address, word_address


TOKEN_CREATE_SIG = "TokenCreate(address,address,address,address,string,string,uint256,string)"
TOKEN_PURCHASE_SIG = "TokenPurchase(address,address,uint256,uint256,uint256,uint256,address,uint256)"
TOKEN_SALE_SIG = "TokenSale(address,address,uint256,uint256,uint256,uint256,address)"
SYNC_SIG = "Sync(address,uint256,uint256,uint256,uint256)"
LIMIT_REACH_SIG = "LimitReach(address)"

TOKEN_CREATE_TOPIC = event_topic(TOKEN_CREATE_SIG)
TOKEN_PURCHASE_TOPIC = event_topic(TOKEN_PURCHASE_SIG)
TOKEN_SALE_TOPIC = event_topic(TOKEN_SALE_SIG)
SYNC_TOPIC = event_topic(SYNC_SIG)
LIMIT_REACH_TOPIC = event_topic(LIMIT_REACH_SIG)

TRENCH_CURVE_TOPICS = (
    TOKEN_CREATE_TOPIC,
    TOKEN_PURCHASE_TOPIC,
    TOKEN_SALE_TOPIC,
    SYNC_TOPIC,
    LIMIT_REACH_TOPIC,
)


def _base(log: RawLog, event_type: str, token: str, **kwargs) -> TrenchEvent:
    return TrenchEvent(
        event_type=event_type,
        token=token,
        actor=kwargs.get("actor"),
        curve=kwargs.get("curve"),
        quote_token=kwargs.get("quote_token"),
        amount_raw=kwargs.get("amount_raw"),
        quote_amount_raw=kwargs.get("quote_amount_raw"),
        protocol_fee_raw=kwargs.get("protocol_fee_raw"),
        extra_fee_raw=kwargs.get("extra_fee_raw"),
        extra_fee_receiver=kwargs.get("extra_fee_receiver"),
        extra_fee_rate=kwargs.get("extra_fee_rate"),
        real_quote_reserves_raw=kwargs.get("real_quote_reserves_raw"),
        real_token_reserves_raw=kwargs.get("real_token_reserves_raw"),
        virtual_quote_raw=kwargs.get("virtual_quote_raw"),
        virtual_token_raw=kwargs.get("virtual_token_raw"),
        name=kwargs.get("name"),
        symbol=kwargs.get("symbol"),
        token_uri=kwargs.get("token_uri"),
        timestamp=kwargs.get("timestamp"),
        block_number=log.block_number,
        transaction_hash=log.transaction_hash,
        transaction_index=log.transaction_index,
        log_index=log.log_index,
    )


def decode_trench_event(log: RawLog) -> TrenchEvent:
    if log.address != normalize_address(TRENCH_MANAGER):
        raise ValueError("not a trench.today manager log")
    if not log.topics:
        raise ValueError("trench.today log has no topic0")
    topic0 = log.topics[0]
    words = data_words(log.data)

    if topic0 == TOKEN_CREATE_TOPIC:
        if len(log.topics) != 4 or len(words) < 5:
            raise ValueError("unexpected trench TokenCreate layout")
        return _base(
            log,
            "token_create",
            topic_address(log.topics[3]),
            actor=topic_address(log.topics[1]),
            curve=topic_address(log.topics[2]),
            quote_token=word_address(words[0]),
            name=abi_string_at(log.data, 1),
            symbol=abi_string_at(log.data, 2),
            timestamp=words[3],
            token_uri=abi_string_at(log.data, 4),
        )

    if topic0 == TOKEN_PURCHASE_TOPIC:
        if len(log.topics) != 3 or len(words) != 6:
            raise ValueError("unexpected trench TokenPurchase layout")
        return _base(
            log,
            "token_purchase",
            topic_address(log.topics[1]),
            actor=topic_address(log.topics[2]),
            amount_raw=words[0],
            quote_amount_raw=words[1],
            protocol_fee_raw=words[2],
            extra_fee_raw=words[3],
            extra_fee_receiver=word_address(words[4]),
            extra_fee_rate=words[5],
        )

    if topic0 == TOKEN_SALE_TOPIC:
        if len(log.topics) != 3 or len(words) != 5:
            raise ValueError("unexpected trench TokenSale layout")
        return _base(
            log,
            "token_sale",
            topic_address(log.topics[1]),
            actor=topic_address(log.topics[2]),
            amount_raw=words[0],
            quote_amount_raw=words[1],
            protocol_fee_raw=words[2],
            extra_fee_raw=words[3],
            extra_fee_receiver=word_address(words[4]),
        )

    if topic0 == SYNC_TOPIC:
        if len(log.topics) != 2 or len(words) != 4:
            raise ValueError("unexpected trench Sync layout")
        return _base(
            log,
            "sync",
            topic_address(log.topics[1]),
            real_quote_reserves_raw=words[0],
            real_token_reserves_raw=words[1],
            virtual_quote_raw=words[2],
            virtual_token_raw=words[3],
        )

    if topic0 == LIMIT_REACH_TOPIC:
        if len(log.topics) != 2 or words:
            raise ValueError("unexpected trench LimitReach layout")
        return _base(log, "limit_reach", topic_address(log.topics[1]))

    raise ValueError(f"unsupported trench.today topic: {topic0}")
