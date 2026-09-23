from hlp.data.types import RawLog
from hlp.protocols.evm import event_topic
from decimal import Decimal

from hlp.protocols.chainlink import (
    DECIMALS_SELECTOR,
    DESCRIPTION_SELECTOR,
    AGGREGATOR_SELECTOR,
    ANSWER_UPDATED_SIG,
    ANSWER_UPDATED_TOPIC,
    LATEST_ROUND_DATA_SELECTOR,
    decode_chainlink_answer_updated,
    read_chainlink_aggregator,
    read_chainlink_latest_round,
)


FEED = "0x" + "11" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def abi_string(value: str) -> str:
    raw = value.encode()
    padded = raw + b"\x00" * ((32 - len(raw) % 32) % 32)
    return "0x" + word(32) + word(len(raw)) + padded.hex()


class FakeRpc:
    def eth_call(self, to, data, block="latest"):
        assert to == FEED
        assert block == 123
        if data == DECIMALS_SELECTOR:
            return "0x" + word(8)
        if data == DESCRIPTION_SELECTOR:
            return abi_string("Robinhood NVDA / USD")
        if data == AGGREGATOR_SELECTOR:
            return "0x" + ("22" * 20).rjust(64, "0")
        if data == LATEST_ROUND_DATA_SELECTOR:
            return (
                "0x"
                + word(7)
                + word(219_12000000)
                + word(100)
                + word(110)
                + word(7)
            )
        raise AssertionError(data)


def test_read_chainlink_latest_round():
    row = read_chainlink_latest_round(FakeRpc(), FEED, block=123)
    assert row.feed == FEED
    assert row.description == "Robinhood NVDA / USD"
    assert row.decimals == 8
    assert row.updated_at == 110
    assert row.answer == Decimal("219.12")



def test_read_chainlink_aggregator():
    assert read_chainlink_aggregator(FakeRpc(), FEED, block=123) == "0x" + "22" * 20



def test_answer_updated_topic_and_decoder():
    assert ANSWER_UPDATED_TOPIC == event_topic(ANSWER_UPDATED_SIG)
    log = RawLog(
        chain_id=4663,
        block_number=200,
        block_hash=None,
        transaction_hash="0x" + "aa" * 32,
        transaction_index=2,
        log_index=5,
        address="0x" + "22" * 20,
        topics=(
            ANSWER_UPDATED_TOPIC,
            "0x" + word(219_90960000),
            "0x" + word(694),
        ),
        data="0x" + word(1786090584),
        removed=False,
    )
    row = decode_chainlink_answer_updated(log)
    assert row.answer_raw == 219_90960000
    assert row.round_id == 694
    assert row.updated_at == 1786090584
    assert row.transaction_index == 2
    assert row.log_index == 5
