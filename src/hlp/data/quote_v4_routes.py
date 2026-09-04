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
                    event_order(row["latest_pre_use_swap"]),
                    int(row["latest_pre_use_swap"]["liquidity"]),
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



def select_v4_quote_routes(probe_rows: Iterable[dict]) -> list[dict]:
    """Freeze one deterministic direct-USDG V4 route per covered quote."""
    routes = []
    for source in probe_rows:
        causal = bool(source.get("causal_route_ready"))
        delayed = bool(source.get("delayed_route_ready"))
        if causal and delayed:
            raise ValueError("V4 quote route cannot be both causal and delayed")
        if not causal and not delayed:
            continue

        candidate = (
            source.get("selected_causal_candidate")
            if causal
            else source.get("selected_delayed_candidate")
        )
        if not candidate:
            raise ValueError("ready V4 quote row is missing selected candidate")
        evidence_key = (
            "latest_pre_use_swap" if causal else "first_post_use_swap"
        )
        evidence = candidate.get(evidence_key)
        initialized = candidate.get("initialize")
        if not evidence or not initialized:
            raise ValueError("selected V4 quote candidate is missing evidence")

        token = source["quote_token"].lower()
        usdg = ROBINHOOD_USDG.lower()
        currency0 = initialized["currency0"].lower()
        currency1 = initialized["currency1"].lower()
        if {currency0, currency1} != {token, usdg}:
            raise ValueError("selected V4 quote route currencies mismatch")
        pool_id = candidate["pool_id"].lower()
        if evidence["pool_id"].lower() != pool_id:
            raise ValueError("selected V4 quote swap pool id mismatch")

        common = {
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": int(source["quote_decimals"]),
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "pool_manager": initialized["pool_manager"].lower(),
            "pool_id": pool_id,
            "currency0": currency0,
            "currency1": currency1,
            "token_is_token0": currency0 == token,
            "anchor_token": usdg,
            "anchor_decimals": 6,
            "fee": int(initialized["fee"]),
            "tick_spacing": int(initialized["tick_spacing"]),
            "hooks": initialized["hooks"].lower(),
            "activation_liquidity": int(evidence["liquidity"]),
        }
        if causal:
            route = {
                **common,
                "activation_block": int(source["first_launch_block"]),
                "causal_state_block": int(evidence["block_number"]),
                "route_type": "uniswap_v4_direct_usdg",
                "initial_usd_price": str(evidence["usd_price"]),
                "initial_quote_per_token": str(evidence["quote_per_token"]),
                "state_transaction_hash": evidence["transaction_hash"],
                "state_transaction_index": evidence.get("transaction_index"),
                "state_log_index": int(evidence["log_index"]),
            }
        else:
            route = {
                **common,
                "activation_block": int(evidence["block_number"]),
                "activation_transaction_index": evidence.get(
                    "transaction_index"
                ),
                "activation_log_index": int(evidence["log_index"]),
                "causal_state_block": None,
                "route_type": "uniswap_v4_direct_usdg_delayed",
                "first_observed_usd_price": str(evidence["usd_price"]),
                "first_observed_quote_per_token": str(
                    evidence["quote_per_token"]
                ),
            }
        routes.append(route)

    routes.sort(
        key=lambda row: (
            int(row["activation_block"]),
            row["quote_token"],
        )
    )
    return routes


def build_v4_route_initial_usd_states(
    route_rows: Iterable[dict],
) -> list[dict]:
    """Convert causal V4 route evidence into generic quote/USD state."""
    rows = []
    for route in route_rows:
        if route.get("causal_state_block") is None:
            continue
        rows.append({
            "quote_token": route["quote_token"].lower(),
            "symbol": route.get("symbol"),
            "pricing_source": route["route_type"],
            "source_pool_id": route["pool_id"].lower(),
            "block_number": int(route["causal_state_block"]),
            "activation_block": int(route["activation_block"]),
            "usd_price": str(route["initial_usd_price"]),
        })
    rows.sort(
        key=lambda row: (
            int(row["activation_block"]),
            row["quote_token"],
        )
    )
    return rows


def build_v4_route_usd_updates(
    route_rows: Iterable[dict],
    v4_swap_events: Iterable[dict],
):
    """Convert selected V4 USDG swap closes into generic quote/USD updates."""
    routes = {
        row["pool_id"].lower(): dict(row)
        for row in route_rows
    }
    if not routes:
        return

    prior = None
    for raw in v4_swap_events:
        event = dict(raw)
        order = event_order(event)
        if prior is not None and order < prior:
            raise ValueError("V4 fallback quote tape is not chronological")
        prior = order

        pool_id = event["pool_id"].lower()
        route = routes.get(pool_id)
        if route is None:
            raise KeyError(
                "V4 fallback event pool id is absent from route registry: "
                f"{pool_id}"
            )
        if event.get("pool_manager") and (
            event["pool_manager"].lower() != route["pool_manager"].lower()
        ):
            raise ValueError("V4 fallback event pool manager mismatch")

        activation_order = (
            int(route["activation_block"]),
            -1 if route.get("activation_transaction_index") is None
            else int(route["activation_transaction_index"]),
            -1 if route.get("activation_log_index") is None
            else int(route["activation_log_index"]),
        )
        if order < activation_order:
            continue
        if int(event["sqrt_price_x96"]) <= 0:
            raise ValueError("V4 fallback swap price must be positive")
        if int(event["liquidity"]) <= 0:
            raise ValueError("V4 fallback swap must have positive liquidity")

        quote_per_token = v3_v4_quote_per_token(
            int(event["sqrt_price_x96"]),
            token_is_token0=bool(route["token_is_token0"]),
            token_decimals=int(route["quote_decimals"]),
            quote_decimals=6,
        )
        if quote_per_token <= 0:
            raise ValueError("V4 fallback quote/USD price must be positive")

        yield {
            "quote_token": route["quote_token"].lower(),
            "symbol": route.get("symbol"),
            "pricing_source": route["route_type"],
            "source_pool_id": pool_id,
            "block_number": int(event["block_number"]),
            "transaction_hash": event["transaction_hash"],
            "transaction_index": event.get("transaction_index"),
            "log_index": int(event["log_index"]),
            "quote_per_token": str(quote_per_token),
            "anchor_usd": "1",
            "usd_price": str(quote_per_token),
        }
