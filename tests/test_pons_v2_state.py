from hlp.config import PONS_V2_FACTORY
from hlp.protocols.pons_state import (
    GET_V2_LAUNCH_CONFIG_SELECTOR,
    V2_PAIR_TOKEN_ECONOMICS_SELECTOR,
    read_v2_launch_config_state,
    read_v2_pair_token_economics_state,
)


PAIR = "0x" + "11" * 20


def word(value: int) -> str:
    return f"{value:064x}"


class FakeRpc:
    def eth_call(self, to, data, block="latest"):
        assert to == PONS_V2_FACTORY.lower()
        assert block == 99
        if data.startswith(GET_V2_LAUNCH_CONFIG_SELECTOR):
            negative_spacing = (1 << 256) - 60
            return (
                "0x"
                + word(1_000_000_000 * 10**18)
                + word(100)
                + word(5 * 10**18)
                + word(50 * 10**18)
                + word(0)
                + word(negative_spacing)
                + word(1)
            )
        if data.startswith(V2_PAIR_TOKEN_ECONOMICS_SELECTOR):
            return "0x" + word(5_000_000) + word(50_000_000) + word(6)
        raise AssertionError(data)


def test_read_v2_launch_config_state():
    row = read_v2_launch_config_state(FakeRpc(), 3, block=99)
    assert row.config_id == 3
    assert row.supply == 1_000_000_000 * 10**18
    assert row.curve_fee_bps == 100
    assert row.tick_spacing == -60
    assert row.enabled is True


def test_read_v2_pair_token_economics_state():
    row = read_v2_pair_token_economics_state(FakeRpc(), PAIR, block=99)
    assert row.pair_token == PAIR
    assert row.phantom_quote == 5_000_000
    assert row.graduation_threshold == 50_000_000
    assert row.decimals == 6
