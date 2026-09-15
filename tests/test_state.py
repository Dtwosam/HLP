import json

from hlp.data.rpc import RpcClient
from hlp.protocols.erc20 import read_erc20_static
from hlp.protocols.state import read_v3_pool_static, read_v3_slot0


def word(value: int) -> str:
    return "0x" + f"{value & ((1 << 256) - 1):064x}"


def addr_word(address: str) -> str:
    return word(int(address, 16))


TOKEN = "0x" + "11" * 20
TOKEN0 = "0x" + "22" * 20
TOKEN1 = "0x" + "33" * 20
POOL = "0x" + "44" * 20


def transport_for(results):
    queue = list(results)

    def transport(request, timeout):
        payload = json.loads(request.data)
        assert payload["method"] == "eth_call"
        return json.dumps(
            {"jsonrpc": "2.0", "id": 1, "result": queue.pop(0)}
        ).encode()

    return transport


def test_read_erc20_static_at_explicit_block():
    rpc = RpcClient(
        "https://example.invalid",
        transport=transport_for([word(18), word(1_000_000)]),
    )
    state = read_erc20_static(rpc, TOKEN, block=123)
    assert state.decimals == 18
    assert state.total_supply == 1_000_000
    assert state.block_number == 123


def test_read_v3_pool_static_orientation():
    rpc = RpcClient(
        "https://example.invalid",
        transport=transport_for([addr_word(TOKEN0), addr_word(TOKEN1)]),
    )
    state = read_v3_pool_static(rpc, POOL, block=123)
    assert state.token0 == TOKEN0
    assert state.token1 == TOKEN1


def test_read_v3_slot0_signed_tick():
    payload = (
        "0x"
        + f"{2**96:064x}"
        + f"{(-123) & ((1 << 256) - 1):064x}"
        + "00" * (32 * 5)
    )
    rpc = RpcClient(
        "https://example.invalid",
        transport=transport_for([payload]),
    )
    state = read_v3_slot0(rpc, POOL, block=123)
    assert state.sqrt_price_x96 == 2**96
    assert state.tick == -123
