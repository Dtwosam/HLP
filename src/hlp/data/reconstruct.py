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
            "transaction_index": swap.transaction_index,
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



def v3_quote_price_at_block(
    rpc: RpcClient,
    *,
    token: str,
    quote_token: str,
    pool: str,
    block: int,
) -> Decimal:
    """Read a V3 token/quote price from state at the end of a known block."""
    from hlp.protocols.state import read_v3_slot0

    token = normalize_address(token)
    quote_token = normalize_address(quote_token)
    pool = normalize_address(pool)
    pool_state = read_v3_pool_static(rpc, pool, block=block)
    if {pool_state.token0, pool_state.token1} != {token, quote_token}:
        raise ValueError("anchor pool assets do not match token/quote")
    token_state = read_erc20_static(rpc, token, block=block)
    quote_state = read_erc20_static(rpc, quote_token, block=block)
    slot0 = read_v3_slot0(rpc, pool, block=block)
    return v3_v4_quote_per_token(
        slot0.sqrt_price_x96,
        token_is_token0=pool_state.token0 == token,
        token_decimals=token_state.decimals,
        quote_decimals=quote_state.decimals,
    )


def event_order(row: dict) -> tuple[int, int, int]:
    tx_index = row.get("transaction_index")
    return (
        int(row["block_number"]),
        -1 if tx_index is None else int(tx_index),
        int(row["log_index"]),
    )


def attach_quote_usd_anchor(
    target_points,
    anchor_points,
    *,
    initial_quote_usd: Decimal,
):
    """Attach the latest *already observable* quote/USD value to token points.

    target_points contain token price in the target quote (e.g. WETH).
    anchor_points contain USD-anchor units per target quote (e.g. USDG/WETH).

    The initial value must come from the block immediately before the target
    window, not from the target block's final state. Same-block anchor swaps
    are applied only when their transaction/log order precedes the target
    event.
    """
    if initial_quote_usd <= 0:
        raise ValueError("initial_quote_usd must be positive")

    anchors = iter(anchor_points)
    next_anchor = next(anchors, None)
    active = initial_quote_usd

    for row in target_points:
        target_order = event_order(row)
        while next_anchor is not None and event_order(next_anchor) <= target_order:
            active = Decimal(next_anchor["quote_per_token"])
            next_anchor = next(anchors, None)

        token_in_quote = Decimal(row["quote_per_token"])
        supply_quote = Decimal(row["market_cap_quote"])
        out = dict(row)
        out["quote_usd"] = str(active)
        out["token_price_usd"] = str(token_in_quote * active)
        out["market_cap_proxy_usd"] = str(supply_quote * active)
        yield out
