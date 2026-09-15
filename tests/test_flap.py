from hlp.config import FLAP_PORTAL
from hlp.data.types import RawLog
from hlp.protocols.flap import (
    LAUNCHED_TO_DEX_TOPIC,
    TOKEN_BOUGHT_TOPIC,
    TOKEN_CREATED_TOPIC,
    decode_flap_event,
)


TOKEN = "0x" + "11" * 20
CREATOR = "0x" + "22" * 20
BUYER = "0x" + "33" * 20
POOL = "0x" + "44" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def address_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def raw(topic, data, *, log_index=1):
    return RawLog(
        chain_id=4663,
        block_number=100,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=log_index,
        address=FLAP_PORTAL.lower(),
        topics=(topic,),
        data=data,
        removed=False,
    )


def encode_string_event_head():
    values = [b"Flap Cat", b"FCAT", b"ipfs://abc"]
    head_words = 7
    offsets = []
    tail = ""
    cursor = head_words * 32
    for value in values:
        offsets.append(cursor)
        padding = b"\x00" * ((32 - len(value) % 32) % 32)
        encoded = word(len(value)) + (value + padding).hex()
        tail += encoded
        cursor += len(encoded) // 2
    return (
        "0x"
        + word(1234)
        + address_word(CREATOR)
        + word(9)
        + address_word(TOKEN)
        + "".join(word(offset) for offset in offsets)
        + tail
    )


def test_decode_token_created_with_dynamic_strings():
    row = decode_flap_event(raw(TOKEN_CREATED_TOPIC, encode_string_event_head()))
    assert row.event_type == "token_created"
    assert row.token == TOKEN
    assert row.actor == CREATOR
    assert row.value_raw == 9
    assert row.name == "Flap Cat"
    assert row.symbol == "FCAT"
    assert row.meta == "ipfs://abc"


def test_decode_token_bought():
    data = (
        "0x"
        + word(1234)
        + address_word(TOKEN)
        + address_word(BUYER)
        + word(10 * 10**18)
        + word(2 * 10**18)
        + word(2 * 10**16)
        + word(200_000_000)
    )
    row = decode_flap_event(raw(TOKEN_BOUGHT_TOPIC, data))
    assert row.event_type == "token_bought"
    assert row.token == TOKEN
    assert row.actor == BUYER
    assert row.amount_raw == 10 * 10**18
    assert row.quote_amount_raw == 2 * 10**18
    assert row.post_price_raw == 200_000_000


def test_decode_graduation():
    data = (
        "0x"
        + address_word(TOKEN)
        + address_word(POOL)
        + word(100)
        + word(200)
    )
    row = decode_flap_event(raw(LAUNCHED_TO_DEX_TOPIC, data))
    assert row.event_type == "launched_to_dex"
    assert row.pool == POOL
    assert row.amount_raw == 100
    assert row.quote_amount_raw == 200
