import json
from dataclasses import asdict

from eth_utils import keccak

from hlp.config import ROBINHOOD_USDG, SOLIDRPC_PUBLIC_RPC_URL, UNISWAP_V4_POOL_MANAGER
from hlp.data.rpc import RpcClient
from hlp.price import v3_v4_quote_per_token
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, decode_v4_pool_initialized


POOLS_SLOT = 6
LIQUIDITY_OFFSET = 3

ASSETS = {
    "FIG": {
        "token": "0x41f4267525a8aff329540ef24fd83d9044758b33",
        "causal_block": 52_956_725,
        "pools": {
            "gt_0.5pct": "0x8d7e57e6fca7c6ed5744549b19f35be72c8004ab6b3d12c9dd972e31994c4ba1",
            "gt_2pct": "0xaee7f2e61946d4e2a096f44dc686c5b6ba8b2ce0857fa167f2e95c3d2eeb62b8",
        },
    },
    "BULL": {
        "token": "0xcef9027c7d6985b85f0ba431125073529a947a68",
        "causal_block": 54_419_646,
        "pools": {
            "gt_0.8pct": "0xdfc620485cebd394955e7cde9e3d336ec8dabe24a7c80c4b9de71ea896208e79",
            "gt_3pct": "0x1bda41eb5701e01bb4ff3659e9e614cd92260efa25731ce3d6ee18e1e25e2cd6",
            "gt_5pct": "0x62983dc730394865ecaeb5a8132f47cb49798052dc13457dff41c5b7593b27a4",
        },
    },
}


def _state_slot(pool_id: str) -> bytes:
    return keccak(bytes.fromhex(pool_id[2:]) + POOLS_SLOT.to_bytes(32, "big"))


def _extsload_data(slot: bytes) -> str:
    selector = keccak(text="extsload(bytes32)")[:4]
    return "0x" + (selector + slot).hex()


def _read_word(rpc: RpcClient, slot: bytes, block: int) -> int:
    return int(rpc.eth_call(UNISWAP_V4_POOL_MANAGER, _extsload_data(slot), block), 16)


def _sqrt_price(word: int) -> int:
    return word & ((1 << 160) - 1)


def _first_nonzero_state_block(rpc: RpcClient, slot: bytes, high: int) -> int:
    lo = 0
    hi = high
    assert _sqrt_price(_read_word(rpc, slot, hi)) > 0
    while lo < hi:
        mid = (lo + hi) // 2
        if _sqrt_price(_read_word(rpc, slot, mid)) > 0:
            hi = mid
        else:
            lo = mid + 1
    return lo


def test_live_fig_bull_v4_causal_pool_identity_proof():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_fig_bull_v4_causal_identity",
    )
    output = {}
    for symbol, spec in ASSETS.items():
        token = spec["token"].lower()
        causal_block = spec["causal_block"]
        rows = []
        for label, pool_id in spec["pools"].items():
            slot = _state_slot(pool_id)
            first_state = _first_nonzero_state_block(rpc, slot, causal_block)
            assert first_state > 0
            assert _sqrt_price(_read_word(rpc, slot, first_state - 1)) == 0

            init_logs = rpc.get_logs(
                first_state,
                first_state,
                address=UNISWAP_V4_POOL_MANAGER,
                topics=[V4_INITIALIZE_TOPIC, pool_id],
            )
            assert len(init_logs) == 1
            initialized = decode_v4_pool_initialized(init_logs[0])
            assert initialized.pool_id.lower() == pool_id
            assert int(initialized.block_number) == first_state
            assert {initialized.currency0.lower(), initialized.currency1.lower()} == {
                token,
                ROBINHOOD_USDG.lower(),
            }

            causal_word = _read_word(rpc, slot, causal_block)
            sqrt_price_x96 = _sqrt_price(causal_word)
            liquidity_slot = (
                int.from_bytes(slot, "big") + LIQUIDITY_OFFSET
            ).to_bytes(32, "big")
            liquidity = _read_word(rpc, liquidity_slot, causal_block) & ((1 << 128) - 1)
            assert sqrt_price_x96 > 0
            assert liquidity > 0
            token_is_token0 = initialized.currency0.lower() == token
            quote_per_token = v3_v4_quote_per_token(
                sqrt_price_x96,
                token_is_token0=token_is_token0,
                token_decimals=18,
                quote_decimals=6,
            )
            rows.append({
                "label": label,
                "pool_id": pool_id,
                "first_state_block": first_state,
                "initialize": asdict(initialized),
                "causal_block": causal_block,
                "sqrt_price_x96": sqrt_price_x96,
                "liquidity": liquidity,
                "quote_per_token": str(quote_per_token),
            })
        output[symbol] = rows

    raise AssertionError(json.dumps({
        "requests": rpc.requests_made,
        "assets": output,
    }, sort_keys=True, default=str))
