from hlp.config import PONS_V1_FACTORY
from hlp.protocols.pons_state import (
    GET_V1_LAUNCH_CONFIG_SELECTOR,
    read_v1_launch_config_state,
)


PAIR = "0x" + "11" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def address_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


class FakeRpc:
    def eth_call(self, to, data, block="latest"):
        assert to == PONS_V1_FACTORY.lower()
        assert data.startswith(GET_V1_LAUNCH_CONFIG_SELECTOR)
        assert int(data[-64:], 16) == 7
        assert block == 99
        negative_120 = (1 << 256) - 120
        return (
            "0x"
            + address_word(PAIR)
            + word(500)
            + word(negative_120)
            + word(1_000_000_000 * 10**18)
            + word(200)
            + word(220)
            + word(50)
            + word(0)
            + word(1)
            + word(0)
        )


def test_read_v1_launch_config_state():
    row = read_v1_launch_config_state(FakeRpc(), 7, block=99)
    assert row.action == "bootstrap"
    assert row.config_id == 7
    assert row.pair_token == PAIR
    assert row.initial_tick == -120
    assert row.supply == 1_000_000_000 * 10**18
    assert row.block_number == 99
