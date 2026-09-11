from hlp.config import TRENCH_MANAGER
from hlp.data.types import RawLog
from hlp.protocols.trench import (
    SYNC_TOPIC,
    TOKEN_CREATE_TOPIC,
    TOKEN_PURCHASE_TOPIC,
    TOKEN_SALE_TOPIC,
    decode_trench_event,
)


TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20
CREATOR = "0x" + "33" * 20
BUYER = "0x" + "44" * 20
ZERO = "0x" + "00" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def topic_addr(address: str) -> str:
    return "0x" + addr_word(address)


def log(topic, topics, data):
    return RawLog(
        chain_id=4663,
        block_number=100,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=3,
        address=TRENCH_MANAGER.lower(),
        topics=(topic, *topics),
        data=data,
        removed=False,
    )


def encode_create_data():
    strings = [b"Trench Cat", b"TCAT", b"ipfs://trench"]
    # non-indexed head: quote,nameOffset,symbolOffset,timestamp,uriOffset
    head_words = 5
    offsets = []
    tail = ""
    cursor = head_words * 32
    for raw in strings:
        offsets.append(cursor)
        padding = b"\x00" * ((32 - len(raw) % 32) % 32)
        encoded = word(len(raw)) + (raw + padding).hex()
        tail += encoded
        cursor += len(encoded) // 2
    return (
        "0x"
        + addr_word(ZERO)
        + word(offsets[0])
        + word(offsets[1])
        + word(123456)
        + word(offsets[2])
        + tail
    )


def test_topics_match_published_robinhood_archive_hashes():
    assert TOKEN_CREATE_TOPIC == "0xe2eb7016a2fc7f0aec441cc8bc9a7ecd75d29d94478782bab1cfa9c5b0dbdf1b"
    assert TOKEN_PURCHASE_TOPIC == "0xb284604a447841f5b5ee1495033bc7db1ab2f84c2624a7b7a3e9f014f32e8e7b"
    assert TOKEN_SALE_TOPIC == "0xfe41490121bfbd4555a4f9aabe1e789de1641611b7edd2a0dc1c594f684ba193"
    assert SYNC_TOPIC == "0x27efe2fec96cb0ff68b9206e3dca402a919bb7172e2f2d12d49b633df3eabc4f"


def test_decode_token_create():
    row = decode_trench_event(
        log(
            TOKEN_CREATE_TOPIC,
            [topic_addr(CREATOR), topic_addr(CURVE), topic_addr(TOKEN)],
            encode_create_data(),
        )
    )
    assert row.event_type == "token_create"
    assert row.token == TOKEN
    assert row.curve == CURVE
    assert row.actor == CREATOR
    assert row.quote_token == ZERO
    assert row.name == "Trench Cat"
    assert row.symbol == "TCAT"
    assert row.token_uri == "ipfs://trench"


def test_decode_purchase_and_sync():
    buy = decode_trench_event(
        log(
            TOKEN_PURCHASE_TOPIC,
            [topic_addr(TOKEN), topic_addr(BUYER)],
            "0x"
            + word(100)
            + word(20)
            + word(1)
            + word(2)
            + addr_word(CREATOR)
            + word(50),
        )
    )
    assert buy.amount_raw == 100
    assert buy.quote_amount_raw == 20
    assert buy.extra_fee_receiver == CREATOR
    assert buy.extra_fee_rate == 50

    sync = decode_trench_event(
        log(
            SYNC_TOPIC,
            [topic_addr(TOKEN)],
            "0x" + word(10) + word(20) + word(30) + word(40),
        )
    )
    assert sync.real_quote_reserves_raw == 10
    assert sync.real_token_reserves_raw == 20
    assert sync.virtual_quote_raw == 30
    assert sync.virtual_token_raw == 40
