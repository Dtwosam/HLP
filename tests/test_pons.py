from hlp.config import PONS_V1_FACTORY, PONS_V2_FACTORY
from hlp.data.types import RawLog
from hlp.protocols.evm import event_topic
from hlp.protocols.pons import (
    V1_TOKEN_LAUNCHED_SIG,
    V1_TOKEN_LAUNCHED_TOPIC,
    V2_CURVE_BUY_SIG,
    V2_CURVE_BUY_TOPIC,
    V2_CURVE_SELL_SIG,
    V2_CURVE_SELL_TOPIC,
    V2_TOKEN_LAUNCHED_SIG,
    V2_TOKEN_LAUNCHED_TOPIC,
    decode_v1_launch,
    decode_v2_curve_trade,
    decode_v2_launch,
)


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


def uint_word(value: int) -> str:
    return f"{value:064x}"


def topic_addr(address: str) -> str:
    return "0x" + addr_word(address)


TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20
DEPLOYER = "0x" + "33" * 20
PAIR = "0x" + "44" * 20
POOL = "0x" + "55" * 20
BUYER = "0x" + "66" * 20
RECIPIENT = "0x" + "77" * 20


def raw(address, topics, data):
    return RawLog(
        chain_id=4663,
        block_number=123,
        block_hash="0x" + "aa" * 32,
        transaction_hash="0x" + "bb" * 32,
        transaction_index=1,
        log_index=2,
        address=address.lower(),
        topics=tuple(t.lower() for t in topics),
        data=data.lower(),
        removed=False,
    )


def test_event_topics_are_ethereum_keccak():
    assert V1_TOKEN_LAUNCHED_TOPIC == event_topic(V1_TOKEN_LAUNCHED_SIG)
    assert V2_TOKEN_LAUNCHED_TOPIC == event_topic(V2_TOKEN_LAUNCHED_SIG)
    assert V2_CURVE_BUY_TOPIC == event_topic(V2_CURVE_BUY_SIG)
    assert V2_CURVE_SELL_TOPIC == event_topic(V2_CURVE_SELL_SIG)


def test_decode_v2_launch():
    log = raw(
        PONS_V2_FACTORY,
        [V2_TOKEN_LAUNCHED_TOPIC, topic_addr(TOKEN), topic_addr(CURVE), topic_addr(DEPLOYER)],
        "0x" + addr_word(PAIR) + uint_word(7) + uint_word(123456),
    )
    launch = decode_v2_launch(log)
    assert launch.version == "v2"
    assert launch.token == TOKEN
    assert launch.curve == CURVE
    assert launch.deployer == DEPLOYER
    assert launch.pair_token == PAIR
    assert launch.launch_config_id == 7
    assert launch.graduation_threshold == 123456


def test_decode_v1_launch():
    log = raw(
        PONS_V1_FACTORY,
        [V1_TOKEN_LAUNCHED_TOPIC, topic_addr(TOKEN), topic_addr(DEPLOYER), topic_addr("0x" + "88" * 20)],
        "0x"
        + addr_word(PAIR)
        + addr_word(POOL)
        + uint_word(3)
        + uint_word(4)
        + uint_word(5)
        + uint_word(6)
        + uint_word(7),
    )
    launch = decode_v1_launch(log)
    assert launch.version == "v1"
    assert launch.token == TOKEN
    assert launch.pool == POOL
    assert launch.launch_config_id == 4


def test_decode_v2_curve_buy_and_sell():
    buy = raw(
        CURVE,
        [V2_CURVE_BUY_TOPIC, topic_addr(BUYER), topic_addr(RECIPIENT)],
        "0x" + uint_word(1000) + uint_word(2000) + uint_word(10) + uint_word(2),
    )
    decoded_buy = decode_v2_curve_trade(buy, token=TOKEN)
    assert decoded_buy.side == "buy"
    assert decoded_buy.quote_amount == 1000
    assert decoded_buy.token_amount == 2000

    sell = raw(
        CURVE,
        [V2_CURVE_SELL_TOPIC, topic_addr(BUYER), topic_addr(RECIPIENT)],
        "0x" + uint_word(3000) + uint_word(1500) + uint_word(15) + uint_word(3),
    )
    decoded_sell = decode_v2_curve_trade(sell, token=TOKEN)
    assert decoded_sell.side == "sell"
    assert decoded_sell.token_amount == 3000
    assert decoded_sell.quote_amount == 1500
