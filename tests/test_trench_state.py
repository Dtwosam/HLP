from hlp.config import TRENCH_MANAGER
from hlp.protocols.trench_state import TOKEN_INFO_SELECTOR, read_trench_token_info


TOKEN = "0x" + "11" * 20
CURVE = "0x" + "22" * 20
CREATOR = "0x" + "33" * 20
ZERO = "0x" + "00" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def addr_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


class FakeRpc:
    def eth_call(self, to, data, block="latest"):
        assert to == TRENCH_MANAGER.lower()
        assert data.startswith(TOKEN_INFO_SELECTOR)
        assert block == 123
        return (
            "0x"
            + addr_word(CURVE)
            + addr_word(CREATOR)
            + addr_word(ZERO)
            + word(1)
            + word(2)
            + word(3)
            + word(4)
            + word(0)
            + word(1)
        )


def test_read_trench_token_info():
    row = read_trench_token_info(FakeRpc(), TOKEN, block=123)
    assert row.curve == CURVE
    assert row.creator == CREATOR
    assert row.quote_token == ZERO
    assert row.virtual_quote_raw == 3
    assert row.virtual_token_raw == 4
    assert row.is_migrated is True
