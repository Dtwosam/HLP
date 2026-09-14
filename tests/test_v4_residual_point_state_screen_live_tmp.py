import json

from eth_utils import keccak

from hlp.config import SOLIDRPC_PUBLIC_RPC_URL, UNISWAP_V4_POOL_MANAGER
from hlp.data.rpc import RpcClient


POOLS_SLOT = 6
LIQUIDITY_OFFSET = 3

CANDIDATES = {
    "RIVN": {
        "causal_block": 36_002_594,
        "pools": {
            "gt_0.5pct": "0xfa29e6cd2536e82e12ef269a80a42df4685ef5177066ecd5f0698d0458e0ec3d",
            "gt_4.5pct": "0x487bf4c9902fe3849a5ffa5e4634575838df62c01124155bd9f396f0b5207ab1",
            "frozen_delayed": "0x64cf594c0cfb72275038a3f9986a54863d5f947aa5f94e94a94f458cc755ceba",
        },
    },
    "FIG": {
        "causal_block": 52_956_725,
        "pools": {
            "gt_0.2pct": "0xaf27a553752048ba61dabfa8f197d725460d6dbd6433a61ad94e19b592c7f0ce",
            "gt_0.5pct": "0x8d7e57e6fca7c6ed5744549b19f35be72c8004ab6b3d12c9dd972e31994c4ba1",
            "gt_0.9pct": "0xed082e86f7da3bc6b13df594876c4fed041464d1ab7219ca4c61f0d5c5bc6e7d",
            "gt_2pct": "0xaee7f2e61946d4e2a096f44dc686c5b6ba8b2ce0857fa167f2e95c3d2eeb62b8",
            "gt_4.97pct": "0x21aa57b4a7170a2c81654cc219c35b41b2237cb9a742652b3a0e3e335a18946e",
            "frozen_delayed": "0xb1504248cbaa71d6b8c4547db5f5f8347e6a54ad8a286ea553384f113e3ab8a1",
        },
    },
    "BULL": {
        "causal_block": 54_419_646,
        "pools": {
            "gt_0.66pct": "0x2bb4bbc0f835c7702bff0f43cabd6890c0b67fe2f8daa854bce2ea9575909fd3",
            "gt_0.8pct": "0xdfc620485cebd394955e7cde9e3d336ec8dabe24a7c80c4b9de71ea896208e79",
            "gt_3pct": "0x1bda41eb5701e01bb4ff3659e9e614cd92260efa25731ce3d6ee18e1e25e2cd6",
            "gt_5pct": "0x62983dc730394865ecaeb5a8132f47cb49798052dc13457dff41c5b7593b27a4",
            "frozen_delayed": "0xf0db7beabf7443ef500ee96d410b3ea79d1fd6d003bcc21b8becd528beb21051",
        },
    },
}


def _extsload_data(slot: bytes) -> str:
    selector = keccak(text="extsload(bytes32)")[:4]
    return "0x" + (selector + slot).hex()


def _read_word(rpc: RpcClient, slot: bytes, block: int) -> int:
    return int(rpc.eth_call(UNISWAP_V4_POOL_MANAGER, _extsload_data(slot), block), 16)


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


def test_live_residual_v4_point_state_screen():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_residual_v4_point_state_screen",
    )
    output = {}
    for symbol, spec in CANDIDATES.items():
        block = spec["causal_block"]
        rows = []
        for label, pool_id in spec["pools"].items():
            state_slot = keccak(bytes.fromhex(pool_id[2:]) + POOLS_SLOT.to_bytes(32, "big"))
            liquidity_slot = (
                int.from_bytes(state_slot, "big") + LIQUIDITY_OFFSET
            ).to_bytes(32, "big")
            slot0_word = _read_word(rpc, state_slot, block)
            liquidity_word = _read_word(rpc, liquidity_slot, block)
            decoded = _decode_slot0(slot0_word)
            liquidity = liquidity_word & ((1 << 128) - 1)
            rows.append({
                "label": label,
                "pool_id": pool_id,
                **decoded,
                "liquidity": liquidity,
                "positive_state": decoded["sqrt_price_x96"] > 0 and liquidity > 0,
            })
        output[symbol] = {"causal_block": block, "rows": rows}

    raise AssertionError(json.dumps({
        "requests": rpc.requests_made,
        "assets": output,
    }, sort_keys=True))
