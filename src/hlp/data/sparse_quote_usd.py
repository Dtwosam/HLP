"""Sparse causal WETH/USD sampling for event-driven launchpad pricing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Any

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.price import v3_v4_quote_per_token
from hlp.protocols.erc20 import read_erc20_static
from hlp.protocols.state import read_v3_pool_static, read_v3_slot0
from hlp.protocols.uniswap import V3_SWAP_TOPIC, decode_v3_swap


@dataclass(frozen=True, slots=True)
class SparseV3QuoteContext:
    token: str
    quote_token: str
    pool: str
    token_is_token0: bool
    token_decimals: int
    quote_decimals: int


def _order(row: Any) -> tuple[int, int, int]:
    if isinstance(row, Mapping):
        block = int(row["block_number"])
        tx = row.get("transaction_index")
        log_index = int(row["log_index"])
    else:
        block = int(row.block_number)
        tx = row.transaction_index
        log_index = int(row.log_index)
    return (
        block,
        -1 if tx is None else int(tx),
        log_index,
    )


def read_sparse_v3_quote_context(
    rpc: RpcClient,
    *,
    token: str,
    quote_token: str,
    pool: str,
    block: int,
) -> SparseV3QuoteContext:
    """Freeze immutable V3 asset/decimal context once for sparse sampling."""
    token = normalize_address(token)
    quote_token = normalize_address(quote_token)
    pool = normalize_address(pool)
    pool_state = read_v3_pool_static(rpc, pool, block=block)
    if {pool_state.token0, pool_state.token1} != {token, quote_token}:
        raise ValueError(
            "sparse V3 quote pool assets do not match token/quote"
        )
    token_state = read_erc20_static(rpc, token, block=block)
    quote_state = read_erc20_static(rpc, quote_token, block=block)
    return SparseV3QuoteContext(
        token=token,
        quote_token=quote_token,
        pool=pool,
        token_is_token0=pool_state.token0 == token,
        token_decimals=token_state.decimals,
        quote_decimals=quote_state.decimals,
    )


def _quote_from_sqrt_price(
    sqrt_price_x96: int,
    context: SparseV3QuoteContext,
) -> Decimal:
    return v3_v4_quote_per_token(
        sqrt_price_x96,
        token_is_token0=context.token_is_token0,
        token_decimals=context.token_decimals,
        quote_decimals=context.quote_decimals,
    )


def build_sparse_v3_quote_points(
    rpc: RpcClient,
    targets: Iterable[Any],
    *,
    token: str,
    quote_token: str,
    pool: str,
    window_size: int = 2_000,
) -> list[dict]:
    """Price only windows containing target events, with strict causality.

    Each active window reads V3 slot0 at the block immediately before the
    window, then replays only V3 Swap logs inside that window. A synthetic
    quote-price point is emitted at each target event order. Same-block swaps
    affect a target only when their transaction/log order is not later than the
    target, matching the project's point-in-time anti-leakage rule.
    """
    if window_size <= 0:
        raise ValueError("sparse V3 quote window size must be positive")

    ordered = sorted(list(targets), key=_order)
    if not ordered:
        return []

    context = read_sparse_v3_quote_context(
        rpc,
        token=token,
        quote_token=quote_token,
        pool=pool,
        block=_order(ordered[0])[0],
    )

    buckets: dict[int, list[Any]] = {}
    for target in ordered:
        block = _order(target)[0]
        window_start = (block // window_size) * window_size
        buckets.setdefault(window_start, []).append(target)

    output: list[dict] = []
    for window_start in sorted(buckets):
        window_targets = buckets[window_start]
        last_target_block = _order(window_targets[-1])[0]
        window_end = min(
            window_start + window_size - 1,
            last_target_block,
        )
        state_block = window_start - 1
        if state_block < 0:
            raise ValueError(
                "sparse V3 quote window requires a prior state block"
            )

        slot0 = read_v3_slot0(
            rpc,
            context.pool,
            block=state_block,
        )
        active = _quote_from_sqrt_price(
            slot0.sqrt_price_x96,
            context,
        )
        if active <= 0:
            raise ValueError(
                "sparse V3 quote prior-window price must be positive"
            )

        swaps = []
        for raw in rpc.get_logs(
            window_start,
            window_end,
            address=context.pool,
            topics=[V3_SWAP_TOPIC],
        ):
            swap = decode_v3_swap(raw)
            swaps.append(
                (
                    _order(swap),
                    _quote_from_sqrt_price(
                        swap.sqrt_price_x96,
                        context,
                    ),
                )
            )
        swaps.sort(key=lambda item: item[0])

        swap_index = 0
        for target in window_targets:
            target_order = _order(target)
            while (
                swap_index < len(swaps)
                and swaps[swap_index][0] <= target_order
            ):
                active = swaps[swap_index][1]
                swap_index += 1
            if active <= 0:
                raise ValueError(
                    "sparse V3 quote active price must be positive"
                )
            output.append(
                {
                    "block_number": target_order[0],
                    "transaction_index": (
                        None
                        if target_order[1] < 0
                        else target_order[1]
                    ),
                    "log_index": target_order[2],
                    "quote_per_token": str(active),
                    "pricing_source": "sparse_v3_state_and_swaps",
                    "pool": context.pool,
                    "token": context.token,
                    "quote_token": context.quote_token,
                    "window_from_block": window_start,
                    "window_to_block": window_end,
                    "state_block": state_block,
                    "anchor_swaps_in_window": len(swaps),
                    "anchor_swaps_applied": swap_index,
                }
            )

    if len(output) != len(ordered):
        raise ValueError(
            "sparse V3 quote output count does not match targets"
        )
    for left, right in zip(output, output[1:]):
        if _order(left) > _order(right):
            raise ValueError(
                "sparse V3 quote output is not chronological"
            )
    return output
