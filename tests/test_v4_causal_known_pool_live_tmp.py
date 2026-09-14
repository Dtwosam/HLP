import json
from dataclasses import asdict

from hlp.config import SOLIDRPC_PUBLIC_RPC_URL, UNISWAP_V4_POOL_MANAGER
from hlp.data.rpc import RpcClient
from hlp.protocols.uniswap import (
    V4_INITIALIZE_TOPIC,
    V4_SWAP_TOPIC,
    decode_v4_pool_initialized,
    decode_v4_swap,
)


SKHY_POOL = "0x4c4a74bd3b9a224b06379c60af2843c2238156446c8003e3796456a3192f5e6b"
SKHY_INIT_BLOCK = 33_534_851
SKHY_FIRST_USE = 52_263_525


def test_live_skhy_known_pool_pre_use_witness():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_skhy_causal_witness_discovery",
    )
    init_logs = list(
        rpc.iter_logs_chunked(
            SKHY_INIT_BLOCK,
            SKHY_INIT_BLOCK,
            address=UNISWAP_V4_POOL_MANAGER,
            topics=[V4_INITIALIZE_TOPIC, SKHY_POOL],
            chunk_size=1,
            min_chunk_size=1,
        )
    )
    initialized = [decode_v4_pool_initialized(raw) for raw in init_logs]
    swaps = []
    for raw in rpc.iter_logs_chunked(
        SKHY_FIRST_USE - 100_000,
        SKHY_FIRST_USE - 1,
        address=UNISWAP_V4_POOL_MANAGER,
        topics=[V4_SWAP_TOPIC, SKHY_POOL],
        chunk_size=50_000,
        min_chunk_size=25,
    ):
        swap = decode_v4_swap(raw)
        if int(swap.sqrt_price_x96) > 0 and int(swap.liquidity) > 0:
            swaps.append({
                "block_number": int(swap.block_number),
                "transaction_hash": swap.transaction_hash,
                "transaction_index": int(swap.transaction_index),
                "log_index": int(swap.log_index),
                "liquidity": int(swap.liquidity),
            })
    raise AssertionError(json.dumps({
        "requests": rpc.requests_made,
        "initialize": [asdict(row) for row in initialized],
        "positive_swaps": swaps,
    }, sort_keys=True, default=str))
