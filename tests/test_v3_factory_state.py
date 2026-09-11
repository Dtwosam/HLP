from hlp.protocols.state import (
    GET_POOL_SELECTOR,
    LIQUIDITY_SELECTOR,
    read_v3_factory_pool,
    read_v3_liquidity,
)


FACTORY = "0x" + "11" * 20
TOKEN_A = "0x" + "22" * 20
TOKEN_B = "0x" + "33" * 20
POOL = "0x" + "44" * 20


def word(value: int) -> str:
    return f"{value:064x}"


def address_word(address: str) -> str:
    return address.removeprefix("0x").rjust(64, "0")


class Rpc:
    def __init__(self, pool=POOL):
        self.pool = pool
        self.calls = []

    def eth_call(self, to, data, block):
        self.calls.append((to, data, block))
        if to == FACTORY:
            return "0x" + (
                word(0) if self.pool is None else address_word(self.pool)
            )
        if to == POOL and data == LIQUIDITY_SELECTOR:
            return "0x" + word(123456)
        raise AssertionError((to, data, block))


def test_read_v3_factory_pool_encodes_sorted_tokens_and_fee():
    rpc = Rpc()
    pool = read_v3_factory_pool(
        rpc,
        FACTORY,
        token_a=TOKEN_B,
        token_b=TOKEN_A,
        fee=3000,
        block=99,
    )
    assert pool == POOL
    _, calldata, block = rpc.calls[0]
    assert block == 99
    assert calldata.startswith(GET_POOL_SELECTOR)
    assert calldata[10:74] == address_word(TOKEN_A)
    assert calldata[74:138] == address_word(TOKEN_B)
    assert calldata[138:202] == word(3000)


def test_read_v3_factory_pool_returns_none_for_zero_address():
    assert read_v3_factory_pool(
        Rpc(pool=None),
        FACTORY,
        token_a=TOKEN_A,
        token_b=TOKEN_B,
        fee=500,
        block=99,
    ) is None


def test_read_v3_liquidity():
    assert read_v3_liquidity(Rpc(), POOL, block=99) == 123456
