from hlp.config import HOOD_FUN_CURRENT
from hlp.data.types import RawLog
from hlp.protocols.hood_fun import (
    TOKEN_CREATED_SIG,
    TOKEN_CREATED_TOPIC,
    TRADE_SIG,
    TRADE_TOPIC,
    decode_hood_fun_event,
)
from hlp.protocols.evm import event_topic


TOKEN = "0x" + "11" * 20
CREATOR = "0x" + "22" * 20
TRADER = "0x" + "33" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def topic_addr(address: str) -> str:
    return "0x" + address.removeprefix("0x").rjust(64, "0")


def raw(topics, data):
    return RawLog(
        chain_id=4663,
        block_number=100,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=3,
        address=HOOD_FUN_CURRENT.lower(),
        topics=tuple(topic.lower() for topic in topics),
        data=data,
        removed=False,
    )


def encode_created():
    strings = [b"Hood Cat", b"HCAT", b'{"description":"cat"}']
    head_words = 6
    offsets = []
    tail = ""
    cursor = head_words * 32
    for value in strings:
        offsets.append(cursor)
        padding = b"\x00" * ((32 - len(value) % 32) % 32)
        encoded = word(len(value)) + (value + padding).hex()
        tail += encoded
        cursor += len(encoded) // 2
    return (
        "0x"
        + word(offsets[0])
        + word(offsets[1])
        + word(offsets[2])
        + word(281 * 10**16)
        + word(1_145_000_000 * 10**18)
        + word(800_000_000 * 10**18)
        + tail
    )


def test_published_and_observed_topics_are_exact_keccak():
    assert TOKEN_CREATED_TOPIC == event_topic(TOKEN_CREATED_SIG)
    assert TOKEN_CREATED_TOPIC == (
        "0x91de26bc430b3a4f1d6cfb11d72f2e5ca75d7622d37b2a88a8998ec28e747a11"
    )
    assert TRADE_TOPIC == event_topic(TRADE_SIG)
    assert TRADE_TOPIC == (
        "0x2c76e7a47fd53e2854856ac3f0a5f3ee40d15cfaa82266357ea9779c486ab9c3"
    )


def test_decode_hood_fun_token_created():
    row = decode_hood_fun_event(
        raw(
            [TOKEN_CREATED_TOPIC, topic_addr(TOKEN), topic_addr(CREATOR)],
            encode_created(),
        )
    )
    assert row.event_type == "token_created"
    assert row.token == TOKEN
    assert row.actor == CREATOR
    assert row.name == "Hood Cat"
    assert row.symbol == "HCAT"
    assert row.virtual_quote_raw == 281 * 10**16
    assert row.virtual_token_raw == 1_145_000_000 * 10**18
    assert row.curve_inventory_raw == 800_000_000 * 10**18


def test_decode_hood_fun_trade():
    row = decode_hood_fun_event(
        raw(
            [TRADE_TOPIC, topic_addr(TOKEN), topic_addr(TRADER)],
            "0x"
            + word(1)
            + word(2 * 10**15)
            + word(806_229 * 10**18)
            + word(2 * 10**13)
            + word(2_811_980_000_000_000_000)
            + word(1_144_193_771 * 10**18),
        )
    )
    assert row.event_type == "trade"
    assert row.is_buy is True
    assert row.quote_amount_raw == 2 * 10**15
    assert row.fee_raw == 2 * 10**13
