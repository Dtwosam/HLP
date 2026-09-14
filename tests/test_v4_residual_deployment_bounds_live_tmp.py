import json

from hlp.config import SOLIDRPC_PUBLIC_RPC_URL
from hlp.data.rpc import RpcClient


RESIDUAL = {
    "RIVN": ("0xb1bf26c1d20ff267a4f93550d1e0d06ac40a114b", 36_002_595),
    "FIG": ("0x41f4267525a8aff329540ef24fd83d9044758b33", 52_956_726),
    "BULL": ("0xcef9027c7d6985b85f0ba431125073529a947a68", 54_419_647),
}


def test_live_residual_token_deployment_bounds():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_residual_v4_deployment_bounds",
    )
    rows = []
    for symbol, (token, first_use) in RESIDUAL.items():
        deployment = rpc.find_first_code_block(token, low=0, high=first_use)
        rows.append({
            "symbol": symbol,
            "quote_token": token,
            "deployment_block": deployment,
            "first_use": first_use,
            "causal_span_blocks": first_use - deployment,
        })
    raise AssertionError(json.dumps({
        "requests": rpc.requests_made,
        "rows": rows,
    }, sort_keys=True))
