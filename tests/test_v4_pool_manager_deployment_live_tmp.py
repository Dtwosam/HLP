from hlp.config import SOLIDRPC_PUBLIC_RPC_URL, UNISWAP_V4_POOL_MANAGER
from hlp.data.rpc import RpcClient


def test_live_v4_pool_manager_deployment_block():
    rpc = RpcClient(
        SOLIDRPC_PUBLIC_RPC_URL,
        timeout=30,
        attempts=3,
        min_interval_seconds=0.1,
        route_label="solidrpc_public_v4_pool_manager_deployment",
    )
    deployment = rpc.find_first_code_block(
        UNISWAP_V4_POOL_MANAGER,
        low=0,
        high=33_534_851,
    )
    raise AssertionError(
        f"pool_manager_deployment_block={deployment} requests={rpc.requests_made}"
    )
