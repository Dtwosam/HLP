from hlp.config import (
    ROBINHOOD_USDG,
    SOLIDRPC_PUBLIC_RPC_URL,
    UNISWAP_V4_POOL_MANAGER,
)
from hlp.data.quote_v4_causal_history import validate_v4_usdg_causal_swap_witness
from hlp.data.rpc import RpcClient


TTWO = "0x5e81213613b6b86eab4c6c50d718d34359459786"
TTWO_POOL = (
    "0xaf313f02e31e8adbc5aabbdfa5b02377"
    "bfa794089b06c60404a63d1a54b042fa"
)


def test_live_archive_ttwu_causal_swap_witness():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.6,
        route_label="solidrpc_public_ttwu_causal_witness",
    )
    route = validate_v4_usdg_causal_swap_witness(
        rpc,
        {
            "quote_token": TTWO,
            "symbol": "TTWO",
            "quote_decimals": 18,
            "first_launch_block": 35_998_356,
            "launches": 3_589,
            "versions": {"v2": 3_589},
        },
        pool_id=TTWO_POOL,
        currency0=TTWO,
        currency1=ROBINHOOD_USDG,
        fee=40_000,
        tick_spacing=400,
        hooks="0x" + "00" * 20,
        witness_block=35_389_234,
        pool_manager=UNISWAP_V4_POOL_MANAGER,
    )
    assert route["causal_state_block"] == 35_389_234
    assert route["activation_block"] == 35_998_356
    assert route["pool_id"] == TTWO_POOL
    assert route["pool_key_verified"] is True
    assert rpc.requests_made == 1
