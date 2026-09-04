"""Bounded causal Uniswap V4 fallback discovery for Pons quote assets."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from hlp.config import ROBINHOOD_USDG, UNISWAP_V4_POOL_MANAGER
from hlp.data.reconstruct import event_order
from hlp.price import v3_v4_quote_per_token
from hlp.protocols.uniswap import (
    V4_INITIALIZE_TOPIC,
    V4_SWAP_TOPIC,
    decode_v4_pool_initialized,
    decode_v4_swap,
)


def _address_topic(address: str) -> str:
    value = address.lower()
    if not value.startswith("0x") or len(value) != 42:
        raise ValueError(f"invalid EVM address for topic: {address!r}")
    int(value[2:], 16)
    return "0x" + value[2:].rjust(64, "0")


def probe_v4_usdg_routes(
    rpc,
    quote_rows: Iterable[dict],
    *,
    snapshot_head: int,
    lookaround_blocks: int = 100_000,
    chunk_size: int = 2_000,
    min_chunk_size: int = 25,
    pool_manager: str = UNISWAP_V4_POOL_MANAGER,
) -> list[dict]:
    """Find V4 USDG pools and causal/delayed swap evidence near first Pons use."""
    if snapshot_head <= 0:
        raise ValueError("snapshot_head must be positive")
    if lookaround_blocks < 0:
        raise ValueError("lookaround_blocks cannot be negative")

    usdg = ROBINHOOD_USDG.lower()
    output = []
    for source in quote_rows:
        if source.get("pricing_status") != "missing_chainlink_feed":
            continue
        token = source["quote_token"].lower()
        first_use = int(source["first_launch_block"])
        lo = max(0, first_use - lookaround_blocks)
        hi = min(int(snapshot_head), first_use + lookaround_blocks)
        currency0, currency1 = sorted(
            (token, usdg),
            key=lambda value: int(value, 16),
        )
        init_logs = rpc.iter_logs_chunked(
            lo,
            hi,
            address=pool_manager,
            topics=[
                V4_INITIALIZE_TOPIC,
                None,
                _address_topic(currency0),
                _address_topic(currency1),
            ],
            chunk_size=chunk_size,
            min_chunk_size=min_chunk_size,
        )
        initializes = []
        for raw in init_logs:
            event = decode_v4_pool_initialized(raw)
            if {
                event.currency0.lower(),
                event.currency1.lower(),
            } != {token, usdg}:
                raise ValueError("V4 Initialize currency filter mismatch")
            initializes.append(event)

        candidates = []
        for initialized in initializes:
            swap_logs = rpc.iter_logs_chunked(
                initialized.block_number,
                hi,
                address=pool_manager,
                topics=[V4_SWAP_TOPIC, initialized.pool_id],
                chunk_size=chunk_size,
                min_chunk_size=min_chunk_size,
            )
            swaps = [
                decode_v4_swap(raw)
                for raw in swap_logs
            ]
            swaps = [
                swap
                for swap in swaps
                if swap.sqrt_price_x96 > 0 and swap.liquidity > 0
            ]
            pre = [
                swap
                for swap in swaps
                if int(swap.block_number) < first_use
            ]
            post = [
                swap
                for swap in swaps
                if int(swap.block_number) >= first_use
            ]
            latest_pre = max(
                pre,
                key=lambda swap: (
                    swap.block_number,
                    -1 if swap.transaction_index is None
                    else swap.transaction_index,
                    swap.log_index,
                ),
                default=None,
            )
            first_post = min(
                post,
                key=lambda swap: (
                    swap.block_number,
                    -1 if swap.transaction_index is None
                    else swap.transaction_index,
                    swap.log_index,
                ),
                default=None,
            )

            token_is_token0 = initialized.currency0.lower() == token

            def swap_evidence(swap):
                if swap is None:
                    return None
                quote_per_token = v3_v4_quote_per_token(
                    swap.sqrt_price_x96,
                    token_is_token0=token_is_token0,
                    token_decimals=int(source["quote_decimals"]),
                    quote_decimals=6,
                )
                if quote_per_token <= 0:
                    raise ValueError("V4 fallback price is not positive")
                row = asdict(swap)
                row.update({
                    "quote_per_token": str(quote_per_token),
                    "usd_price": str(quote_per_token),
                })
                return row

            candidates.append({
                "pool_id": initialized.pool_id.lower(),
                "initialize": asdict(initialized),
                "latest_pre_use_swap": swap_evidence(latest_pre),
                "first_post_use_swap": swap_evidence(first_post),
                "swap_count_in_window": len(swaps),
            })

        causal = [
            row for row in candidates
            if row["latest_pre_use_swap"] is not None
        ]
        delayed = [
            row for row in candidates
            if row["first_post_use_swap"] is not None
        ]
        best_causal = (
            max(
                causal,
                key=lambda row: (
                    int(row["latest_pre_use_swap"]["liquidity"]),
                    event_order(row["latest_pre_use_swap"]),
                    row["pool_id"],
                ),
            )
            if causal else None
        )
        best_delayed = (
            min(
                delayed,
                key=lambda row: (
                    event_order(row["first_post_use_swap"]),
                    -int(row["first_post_use_swap"]["liquidity"]),
                    row["pool_id"],
                ),
            )
            if delayed else None
        )

        output.append({
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": int(source["quote_decimals"]),
            "first_launch_block": first_use,
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "search_from_block": lo,
            "search_to_block": hi,
            "initialize_events": len(initializes),
            "v4_candidates": candidates,
            "causal_route_ready": best_causal is not None,
            "delayed_route_ready": (
                best_causal is None and best_delayed is not None
            ),
            "selected_causal_candidate": best_causal,
            "selected_delayed_candidate": (
                None if best_causal is not None else best_delayed
            ),
        })

    output.sort(
        key=lambda row: (row["first_launch_block"], row["quote_token"])
    )
    return output
