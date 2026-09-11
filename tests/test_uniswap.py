from hlp.data.types import RawLog
from hlp.protocols.uniswap import (
    PONS_V2_POOL_REGISTERED_TOPIC,
    V3_POOL_CREATED_TOPIC,
    V3_SWAP_TOPIC,
    V4_INITIALIZE_TOPIC,
    V4_SWAP_TOPIC,
    decode_pons_v2_pool_registered,
    decode_v3_pool_created,
    decode_v3_swap,
    decode_v4_pool_initialized,
    decode_v4_swap,
)


def uint_word(value: int) -> str:
    return f"{value & ((1 << 256) - 1):064x}"


def topic_addr(address: str) -> str:
    return "0x" + address.removeprefix("0x").rjust(64, "0")


def raw(address, topics, words):
    return RawLog(
        chain_id=4663,
        block_number=99,
        block_hash=None,
        transaction_hash="0x" + "bb" * 32,
        transaction_index=None,
        log_index=3,
        address=address.lower(),
        topics=tuple(t.lower() for t in topics),
        data="0x" + "".join(uint_word(w) for w in words),
        removed=False,
    )


POOL = "0x" + "11" * 20
SENDER = "0x" + "22" * 20
RECIPIENT = "0x" + "33" * 20
TOKEN = "0x" + "44" * 20
QUOTE = "0x" + "55" * 20
CREATOR = "0x" + "66" * 20
POOL_ID = "0x" + "77" * 32


def test_decode_v3_swap_handles_signed_amounts_and_tick():
    log = raw(
        POOL,
        [V3_SWAP_TOPIC, topic_addr(SENDER), topic_addr(RECIPIENT)],
        [-100, 200, 2**96, 1234, -42],
    )
    swap = decode_v3_swap(log)
    assert swap.amount0 == -100
    assert swap.amount1 == 200
    assert swap.tick == -42
    assert swap.sqrt_price_x96 == 2**96


def test_decode_v4_swap_maps_pool_id_and_signed_amounts():
    log = raw(
        POOL,
        [V4_SWAP_TOPIC, POOL_ID, topic_addr(SENDER)],
        [-300, 250, 2**96, 9876, 17, 3000],
    )
    swap = decode_v4_swap(log)
    assert swap.pool_id == POOL_ID
    assert swap.sender == SENDER
    assert swap.amount0 == -300
    assert swap.amount1 == 250
    assert swap.fee == 3000


def test_decode_pons_pool_registration_maps_v4_pool_to_token():
    log = raw(
        POOL,
        [PONS_V2_POOL_REGISTERED_TOPIC, POOL_ID],
        [int(TOKEN, 16), int(QUOTE, 16), int(CREATOR, 16)],
    )
    registration = decode_pons_v2_pool_registered(log)
    assert registration.pool_id == POOL_ID
    assert registration.token == TOKEN
    assert registration.quote_token == QUOTE
    assert registration.creator == CREATOR



def test_decode_v3_pool_created():
    factory = "0x" + "88" * 20
    fee_topic = "0x" + uint_word(10_000)
    log = raw(
        factory,
        [
            V3_POOL_CREATED_TOPIC,
            topic_addr(TOKEN),
            topic_addr(QUOTE),
            fee_topic,
        ],
        [-200, int(POOL, 16)],
    )
    row = decode_v3_pool_created(log)
    assert row.factory == factory
    assert row.token0 == TOKEN
    assert row.token1 == QUOTE
    assert row.fee == 10_000
    assert row.tick_spacing == -200
    assert row.pool == POOL


def test_decode_v4_pool_initialized():
    manager = "0x" + "99" * 20
    hook = "0x" + "aa" * 20
    log = raw(
        manager,
        [
            V4_INITIALIZE_TOPIC,
            POOL_ID,
            topic_addr(TOKEN),
            topic_addr(QUOTE),
        ],
        [0, 60, int(hook, 16), 2**96, -17],
    )
    row = decode_v4_pool_initialized(log)
    assert row.pool_id == POOL_ID
    assert row.currency0 == TOKEN
    assert row.currency1 == QUOTE
    assert row.fee == 0
    assert row.tick_spacing == 60
    assert row.hooks == hook
    assert row.sqrt_price_x96 == 2**96
    assert row.tick == -17
