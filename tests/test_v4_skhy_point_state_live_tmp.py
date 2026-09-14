import json
from dataclasses import asdict

from eth_utils import keccak

from hlp.config import ROBINHOOD_USDG, SOLIDRPC_PUBLIC_RPC_URL, UNISWAP_V4_POOL_MANAGER
from hlp.data.rpc import RpcClient
from hlp.price import v3_v4_quote_per_token
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, decode_v4_pool_initialized


SKHY = "0x84cab63bc87912e71ad199ff14a0ba45de68fef8"
POOL_ID = "0x4c4a74bd3b9a224b06379c60af2843c2238156446c8003e3796456a3192f5e6b"
INITIALIZE_BLOCK = 33_534_851
CAUSAL_BLOCK = 52_263_524
POOLS_SLOT = 6
LIQUIDITY_OFFSET = 3


def _extsload_data(slot: bytes) -> str:
    selector = keccak(text="extsload(bytes32)")[:4]
    return "0x" + (selector + slot).hex()


def _read_word(rpc: RpcClient, slot: bytes, block: int) -> int:
    raw = rpc.eth_call(UNISWAP_V4_POOL_MANAGER, _extsload_data(slot), block)
    return int(raw, 16)


def _decode_slot0(word: int) -> dict:
    sqrt_price_x96 = word & ((1 << 160) - 1)
    tick = (word >> 160) & ((1 << 24) - 1)
    if tick >= 1 << 23:
        tick -= 1 << 24
    return {
        "sqrt_price_x96": sqrt_price_x96,
        "tick": tick,
        "protocol_fee": (word >> 184) & ((1 << 24) - 1),
        "lp_fee": (word >> 208) & ((1 << 24) - 1),
    }


def test_live_skhy_point_in_time_v4_state():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_skhy_v4_point_state",
    )

    init_logs = rpc.get_logs(
        INITIALIZE_BLOCK,
        INITIALIZE_BLOCK,
        address=UNISWAP_V4_POOL_MANAGER,
        topics=[V4_INITIALIZE_TOPIC, POOL_ID],
    )
    assert len(init_logs) == 1
    initialized = decode_v4_pool_initialized(init_logs[0])
    assert initialized.pool_id.lower() == POOL_ID
    assert {initialized.currency0.lower(), initialized.currency1.lower()} == {
        SKHY.lower(),
        ROBINHOOD_USDG.lower(),
    }

    state_slot = keccak(bytes.fromhex(POOL_ID[2:]) + POOLS_SLOT.to_bytes(32, "big"))
    liquidity_slot = (int.from_bytes(state_slot, "big") + LIQUIDITY_OFFSET).to_bytes(32, "big")

    rows = []
    for block in (INITIALIZE_BLOCK - 1, INITIALIZE_BLOCK, CAUSAL_BLOCK):
        slot0_word = _read_word(rpc, state_slot, block)
        liquidity_word = _read_word(rpc, liquidity_slot, block)
        decoded = _decode_slot0(slot0_word)
        liquidity = liquidity_word & ((1 << 128) - 1)
        token_is_token0 = initialized.currency0.lower() == SKHY.lower()
        price = None
        if decoded["sqrt_price_x96"] > 0:
            price = str(
                v3_v4_quote_per_token(
                    decoded["sqrt_price_x96"],
                    token_is_token0=token_is_token0,
                    token_decimals=18,
                    quote_decimals=6,
                )
            )
        rows.append({
            "block": block,
            **decoded,
            "liquidity": liquidity,
            "quote_per_token": price,
        })

    raise AssertionError(json.dumps({
        "requests": rpc.requests_made,
        "initialize": asdict(initialized),
        "state_slot": "0x" + state_slot.hex(),
        "liquidity_slot": "0x" + liquidity_slot.hex(),
        "rows": rows,
    }, sort_keys=True, default=str))
