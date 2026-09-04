"""Canonical Robinhood Chain configuration.

Addresses in this module must come from verified official/protocol sources.
Never identify canonical assets by symbol alone.
"""

from __future__ import annotations

from dataclasses import dataclass


ROBINHOOD_CHAIN_ID = 4663
DEFAULT_RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
SOLIDRPC_PUBLIC_RPC_URL = "https://rpc.solidrpc.io/public/evm/4663"
SOLIDRPC_AUTH_RPC_URL = "https://rpc.solidrpc.io/evm/4663"
DEFAULT_SEQUENCER_WS_URL = "wss://feed.mainnet.chain.robinhood.com"
NODEFLARE_PUBLIC_RPC_URL = "https://rpc.nodeflare.app/robinhood/public"

ROBINHOOD_WETH = "0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73"
ROBINHOOD_USDG = "0x5fc5360D0400a0Fd4f2af552ADD042D716F1d168"

# Provisional Phase-1 USD anchor discovered from the deepest current
# Uniswap V3 WETH/USDG market and verified on-chain before use.
# Final anchor-selection policy remains a Phase-1 acceptance item.
UNISWAP_V3_WETH_USDG_ANCHOR_POOL = "0x52e65b17fb6e5ba00ed806f37afcd2daa50271ca"
UNISWAP_V3_FACTORY = "0x1f7d7550B1b028f7571E69A784071F0205FD2EfA"

PONS_V1_FACTORY_LEGACY = "0x0c37a24f5d23a486fa692d1500881d698b1f77a4"
PONS_V1_FACTORY = "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB"
PONS_V1_FACTORY_CURRENT = "0xf4fc0cd27fc8ecf17e55ee4c3f7201897df3eb75"
PONS_V1_FACTORIES = (
    PONS_V1_FACTORY_LEGACY,
    PONS_V1_FACTORY,
    PONS_V1_FACTORY_CURRENT,
)
PONS_V1_FACTORY_DEPLOYMENT_BLOCKS = {
    PONS_V1_FACTORY_LEGACY.lower(): 8_600_612,
    PONS_V1_FACTORY.lower(): 8_991_118,
    PONS_V1_FACTORY_CURRENT.lower(): 39_010_564,
}
PONS_V2_FACTORY = "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e"
NOXA_LAUNCH_FACTORY = "0xD9eC2db5f3D1b236843925949fe5bd8a3836FCcB"
FLAP_PORTAL = "0x26605f322f7fF986f381bB9A6e3f5DAb0bEaEb09"
TRENCH_MANAGER = "0x77dc6f6361b7b99456fc3761ce5b7dda80d83f9d"
PONS_V1_FIRST_DEPLOYMENT_BLOCK = 8_600_612
# Kept for backward compatibility: deployment block of the primary V1 factory.
PONS_V1_DEPLOYMENT_BLOCK = 8_991_118
PONS_V2_DEPLOYMENT_BLOCK = 26_841_846
PONS_V2_MEME_HOOK = "0xe5e702641ea86f4ae6cc3cdaed2b886f976be044"
UNISWAP_V4_POOL_MANAGER = "0x8366a39CC670B4001A1121B8F6A443A643e40951"


@dataclass(frozen=True, slots=True)
class ChainConfig:
    chain_id: int = ROBINHOOD_CHAIN_ID
    rpc_url: str = DEFAULT_RPC_URL
    sequencer_ws_url: str = DEFAULT_SEQUENCER_WS_URL


def normalize_address(address: str) -> str:
    """Return a deterministic lowercase 0x-prefixed EVM address."""
    value = address.strip().lower()
    if not value.startswith("0x"):
        value = "0x" + value
    if len(value) != 42:
        raise ValueError(f"invalid EVM address length: {address!r}")
    int(value[2:], 16)
    return value


POOLS_TRADE_LAUNCHER_CURRENT = "0x0000FffFBE8efE702c8703aE3477FF5dE3d319C0"
POOLS_TRADE_LAUNCHER_ORIGINAL = "0x00004c4ccc709Ef590F7C81102C0689F0263D4e9"
POOLS_TRADE_INSTANT_STRATEGIES = (
    "0x23f8209572b4a1c2ad88a42749e830791fb027f1",
    "0xad44d55e7f8337c3ce113fbb591486e85be104b2",
    "0xce57498d3474dcc244dfb6710ffbe6d4441cd2b2",
    "0x60d73b21cdf2ea846ab3d58699bbbb8f29d72491",
)
