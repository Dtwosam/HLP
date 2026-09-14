import json

from hlp.config import (
    ROBINHOOD_USDG,
    SOLIDRPC_PUBLIC_RPC_URL,
    UNISWAP_V4_POOL_MANAGER,
)
from hlp.data.quote_v4_routes import _address_topic
from hlp.data.rpc import RpcClient
from hlp.protocols.uniswap import (
    V4_INITIALIZE_TOPIC,
    V4_SWAP_TOPIC,
    decode_v4_pool_initialized,
    decode_v4_swap,
)


RESIDUAL = {
    "TTWO": ("0x5e81213613b6b86eab4c6c50d718d34359459786", 35_997_893),
    "RIVN": ("0xb1bf26c1d20ff267a4f93550d1e0d06ac40a114b", 36_002_595),
    "SKHY": ("0x84cab63bc87912e71ad199ff14a0ba45de68fef8", 52_263_525),
    "FIG": ("0x41f4267525a8aff329540ef24fd83d9044758b33", 52_956_726),
    "BULL": ("0xcef9027c7d6985b85f0ba431125073529a947a68", 54_419_647),
}


def test_live_residual_v4_causal_history_diagnostic():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_v4_causal_history_diagnostic",
    )
    rows = []
    usdg = ROBINHOOD_USDG.lower()
    for symbol, (token, first_use) in RESIDUAL.items():
        token = token.lower()
        deployment = rpc.find_first_code_block(token, low=0, high=first_use)
        currency0, currency1 = sorted((token, usdg), key=lambda value: int(value, 16))
        initialize_logs = list(
            rpc.iter_logs_chunked(
                deployment,
                first_use - 1,
                address=UNISWAP_V4_POOL_MANAGER,
                topics=[
                    V4_INITIALIZE_TOPIC,
                    None,
                    _address_topic(currency0),
                    _address_topic(currency1),
                ],
                chunk_size=50_000,
                min_chunk_size=25,
            )
        )
        pools = []
        for raw in initialize_logs:
            initialized = decode_v4_pool_initialized(raw)
            positive = []
            for swap_raw in rpc.iter_logs_chunked(
                int(initialized.block_number),
                first_use - 1,
                address=UNISWAP_V4_POOL_MANAGER,
                topics=[V4_SWAP_TOPIC, initialized.pool_id],
                chunk_size=50_000,
                min_chunk_size=25,
            ):
                swap = decode_v4_swap(swap_raw)
                if int(swap.sqrt_price_x96) > 0 and int(swap.liquidity) > 0:
                    positive.append({
                        "block_number": int(swap.block_number),
                        "transaction_hash": swap.transaction_hash,
                        "transaction_index": swap.transaction_index,
                        "log_index": int(swap.log_index),
                        "liquidity": int(swap.liquidity),
                    })
            pools.append({
                "pool_id": initialized.pool_id,
                "initialize_block": int(initialized.block_number),
                "currency0": initialized.currency0,
                "currency1": initialized.currency1,
                "fee": int(initialized.fee),
                "tick_spacing": int(initialized.tick_spacing),
                "hooks": initialized.hooks,
                "positive_swaps": positive,
            })
        rows.append({
            "symbol": symbol,
            "quote_token": token,
            "first_use": first_use,
            "deployment_block": deployment,
            "pools": pools,
        })
    raise AssertionError(json.dumps({"requests": rpc.requests_made, "rows": rows}, sort_keys=True))
