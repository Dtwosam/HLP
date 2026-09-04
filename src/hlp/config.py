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

PONS_V1_FACTORY = "0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB"
PONS_V2_FACTORY = "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e"
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
