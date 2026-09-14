import json
from dataclasses import asdict

from hlp.config import (
    ROBINHOOD_USDG,
    SOLIDRPC_PUBLIC_RPC_URL,
    UNISWAP_V4_POOL_MANAGER,
)
from hlp.data.quote_v4_routes import _address_topic
from hlp.data.rpc import RpcClient
from hlp.protocols.uniswap import V4_INITIALIZE_TOPIC, decode_v4_pool_initialized


RIVN = "0xb1bf26c1d20ff267a4f93550d1e0d06ac40a114b"
FIRST_USE = 36_002_595
OLD_SEARCH_FROM = 35_902_595
SCAN_FROM = FIRST_USE - 1_000_000
SCAN_TO = OLD_SEARCH_FROM - 1


def test_live_rivn_pre_window_v4_initializes():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_rivn_pre_window_v4_initializes",
    )
    currency0, currency1 = sorted(
        (RIVN.lower(), ROBINHOOD_USDG.lower()),
        key=lambda value: int(value, 16),
    )
    events = [
        decode_v4_pool_initialized(raw)
        for raw in rpc.iter_logs_chunked(
            SCAN_FROM,
            SCAN_TO,
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
    ]
    raise AssertionError(json.dumps({
        "scan_from": SCAN_FROM,
        "scan_to": SCAN_TO,
        "requests": rpc.requests_made,
        "events": [asdict(row) for row in events],
    }, sort_keys=True, default=str))
