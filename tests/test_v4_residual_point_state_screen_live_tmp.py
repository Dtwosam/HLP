import json

from eth_utils import keccak

from hlp.config import SOLIDRPC_PUBLIC_RPC_URL, UNISWAP_V4_POOL_MANAGER
from hlp.data.rpc import RpcClient
from hlp.price import v3_v4_quote_per_token


TTWO = "0x5e81213613b6b86eab4c6c50d718d34359459786"
POOL_ID = "0xaf313f02e31e8adbc5aabbdfa5b02377bfa794089b06c60404a63d1a54b042fa"
CAUSAL_BLOCK = 35_998_355
POOLS_SLOT = 6
LIQUIDITY_OFFSET = 3


def _extsload_data(slot: bytes) -> str:
    selector = keccak(text="extsload(bytes32)")[:4]
    return "0x" + (selector + slot).hex()


def _read_word(rpc: RpcClient, slot: bytes, block: int) -> int:
    return int(rpc.eth_call(UNISWAP_V4_POOL_MANAGER, _extsload_data(slot), block), 16)


def test_live_ttwo_v4_causal_point_state():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_ttwo_v4_causal_point_state",
    )
    slot = keccak(bytes.fromhex(POOL_ID[2:]) + POOLS_SLOT.to_bytes(32, "big"))
    liquidity_slot = (int.from_bytes(slot, "big") + LIQUIDITY_OFFSET).to_bytes(32, "big")
    word = _read_word(rpc, slot, CAUSAL_BLOCK)
    sqrt_price_x96 = word & ((1 << 160) - 1)
    liquidity = _read_word(rpc, liquidity_slot, CAUSAL_BLOCK) & ((1 << 128) - 1)
    price = None
    if sqrt_price_x96 > 0:
        price = str(v3_v4_quote_per_token(
            sqrt_price_x96,
            token_is_token0=True,
            token_decimals=18,
            quote_decimals=6,
        ))
    raise AssertionError(json.dumps({
        "block": CAUSAL_BLOCK,
        "pool_id": POOL_ID,
        "sqrt_price_x96": sqrt_price_x96,
        "liquidity": liquidity,
        "quote_per_token": price,
        "positive_state": sqrt_price_x96 > 0 and liquidity > 0,
        "requests": rpc.requests_made,
    }, sort_keys=True))
