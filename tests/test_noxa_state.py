from hlp.config import NOXA_LAUNCH_FACTORY
from hlp.protocols.noxa_state import (
    GET_LAUNCH_CONFIG_SELECTOR,
    read_noxa_launch_config,
)


PAIR = "0x" + "11" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def address_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


class FakeRpc:
    def eth_call(self, to, data, block="latest"):
        assert to == NOXA_LAUNCH_FACTORY.lower()
        assert data.startswith(GET_LAUNCH_CONFIG_SELECTOR)
        assert block == 100
        return (
            "0x"
            + address_word(PAIR)
            + word(0)
            + word((1 << 256) - 120)
            + word(1_000_000_000 * 10**18)
            + word(200)
            + word(220)
            + word(100)
            + word(3000)
            + word(1)
        )


def test_read_noxa_launch_config():
    row = read_noxa_launch_config(FakeRpc(), 0, block=100)
    assert row.pair_token == PAIR
    assert row.dex_id == 0
    assert row.initial_tick == -120
    assert row.supply == 1_000_000_000 * 10**18
    assert row.buy_pair_hop_fee == 3000
    assert row.enabled is True
