"""Point-in-time market-path reconstruction helpers for Phase 1.

These functions deliberately stop at quote-asset prices. USD conversion is a
separate versioned layer so a future oracle/route choice cannot contaminate
raw DEX reconstruction.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterator

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.price import human_amount, v3_v4_quote_per_token
from hlp.protocols.erc20 import read_erc20_static
from hlp.protocols.state import read_v3_pool_static
from hlp.protocols.uniswap import V3_SWAP_TOPIC, decode_v3_swap


def reconstruct_v3_price_points(
    rpc: RpcClient,
    *,
    token: str,
    quote_token: str,
    pool: str,
    from_block: int,
    to_block: int,
    chunk_size: int = 100_000,
    min_chunk_size: int = 1,
) -> Iterator[dict]:
    """Yield swap-close price points known at each historical V3 Swap event."""
    token = normalize_address(token)
    quote_token = normalize_address(quote_token)
    pool = normalize_address(pool)

    pool_state = read_v3_pool_static(rpc, pool, block=from_block)
    if {pool_state.token0, pool_state.token1} != {token, quote_token}:
        raise ValueError(
            f"pool assets do not match token/quote: "
            f"{pool_state.token0}, {pool_state.token1}"
        )

    token_state = read_erc20_static(rpc, token, block=from_block)
    quote_state = read_erc20_static(rpc, quote_token, block=from_block)
    token_is_token0 = pool_state.token0 == token
    supply = human_amount(token_state.total_supply, token_state.decimals)

    logs = rpc.iter_logs_chunked(
        from_block,
        to_block,
        address=pool,
        topics=[V3_SWAP_TOPIC],
        chunk_size=chunk_size,
        min_chunk_size=min_chunk_size,
    )
    for raw in logs:
        swap = decode_v3_swap(raw)
        quote_per_token = v3_v4_quote_per_token(
            swap.sqrt_price_x96,
            token_is_token0=token_is_token0,
            token_decimals=token_state.decimals,
            quote_decimals=quote_state.decimals,
        )
        token_amount_raw = swap.amount0 if token_is_token0 else swap.amount1
        quote_amount_raw = swap.amount1 if token_is_token0 else swap.amount0
        market_cap_quote = quote_per_token * supply
        yield {
            "token": token,
            "quote_token": quote_token,
            "pool": pool,
            "block_number": swap.block_number,
            "transaction_hash": swap.transaction_hash,
            "log_index": swap.log_index,
            "quote_per_token": str(quote_per_token),
            "market_cap_quote": str(market_cap_quote),
            "token_amount_raw": token_amount_raw,
            "quote_amount_raw": quote_amount_raw,
            "sqrt_price_x96": swap.sqrt_price_x96,
            "liquidity": swap.liquidity,
            "tick": swap.tick,
            "token_is_token0": token_is_token0,
            "token_decimals": token_state.decimals,
            "quote_decimals": quote_state.decimals,
            "total_supply_raw": token_state.total_supply,
        }
