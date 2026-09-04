from decimal import Decimal

from hlp.protocols.chainlink import (
    DECIMALS_SELECTOR,
    DESCRIPTION_SELECTOR,
    LATEST_ROUND_DATA_SELECTOR,
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
