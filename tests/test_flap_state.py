from hlp.config import FLAP_PORTAL
from hlp.protocols.flap_state import GET_TOKEN_V8_SELECTOR, read_flap_token_v8


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def address_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


class FakeRpc:
    def eth_call(self, to, data, block="latest"):
        assert to == FLAP_PORTAL.lower()
        assert data.startswith(GET_TOKEN_V8_SELECTOR)
        assert block == 123
        values = [
            word(1),
            word(4 * 10**18),
            word(500_000_000 * 10**18),
            word(25_000_000),
            word(7),
            word(1),
            word(2),
            word(3),
            word(800_000_000 * 10**18),
            address_word(QUOTE),
            word(1),
            word(99),
            word(100),
            word(200),
            address_word(POOL),
            word(5 * 10**17),
            word(2),
            word(1),
        ]
        return "0x" + "".join(values)


def test_read_flap_token_v8():
    row = read_flap_token_v8(FakeRpc(), TOKEN, block=123)
    assert row.token == TOKEN
    assert row.quote_token == QUOTE
    assert row.reserve_raw == 4 * 10**18
    assert row.circulating_supply_raw == 500_000_000 * 10**18
    assert row.price_raw == 25_000_000
    assert row.pool == POOL
    assert row.buy_tax_rate == 100
    assert row.sell_tax_rate == 200
