"""Causal fallback route discovery for Pons quote assets without USD feeds."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from hlp.config import (
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    SUSHISWAP_V3_FACTORY,
    UNISWAP_V3_FACTORY,
    UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
)
from hlp.data.reconstruct import event_order, v3_quote_price_at_block
from hlp.price import v3_v4_quote_per_token
from hlp.protocols.state import (
    read_v3_factory_pool,
    read_v3_liquidity,
    read_v3_pool_static,
    read_v3_slot0,
)
from hlp.protocols.uniswap import V3_SWAP_TOPIC, decode_v3_swap


V3_CANONICAL_FEES = (100, 500, 3000, 10000)


def _has_code(value: str) -> bool:
    return value not in {"0x", "0x0", ""}


def _v3_venue(factory: str) -> str:
    value = factory.lower()
    if value == UNISWAP_V3_FACTORY.lower():
        return "uniswap_v3"
    if value == SUSHISWAP_V3_FACTORY.lower():
        return "sushiswap_v3"
    return "v3_factory"


def audit_unpriced_v3_quote_routes(
    rpc,
    quote_rows: Iterable[dict],
    *,
    factory: str = UNISWAP_V3_FACTORY,
    fees: tuple[int, ...] = V3_CANONICAL_FEES,
) -> list[dict]:
    """Find direct V3 routes and prove each existed before first Pons use."""
    rows = list(quote_rows)
    factory = factory.lower()
    venue = _v3_venue(factory)
    special_decimals = {
        ROBINHOOD_USDG.lower(): 6,
        ROBINHOOD_WETH.lower(): 18,
    }
    for row in rows:
        if row.get("quote_decimals") is None:
            continue
        token = row["quote_token"].lower()
        observed = int(row["quote_decimals"])
        expected = special_decimals.get(token)
        if expected is not None and observed != expected:
            raise ValueError(
                f"canonical quote decimals disagree for {token}: "
                f"expected={expected} observed={observed}"
            )
        special_decimals[token] = observed
    anchor_specs = (
        (ROBINHOOD_USDG.lower(), "usdg_nominal"),
        (ROBINHOOD_WETH.lower(), "weth_usdg"),
    )
    weth_usd_cache: dict[int, Decimal] = {}
    output = []

    for source in rows:
        if source.get("pricing_status") != "missing_chainlink_feed":
            continue
        token = source["quote_token"].lower()
        first_use = int(source["first_launch_block"])
        if first_use <= 0:
            raise ValueError("first Pons quote use must be after block zero")
        prior = first_use - 1
        token_decimals = int(source["quote_decimals"])
        candidates = []
        lookup_errors = []

        searched_anchors = []
        for anchor, usd_semantics in anchor_specs:
            searched_anchors.append(anchor)
            anchor_decimals = special_decimals.get(anchor)
            if anchor_decimals is None:
                raise ValueError(
                    f"quote registry is missing decimals for anchor {anchor}"
                )
            for fee in fees:
                try:
                    # V3 getPool mappings are immutable after creation.
                    # Discover the pool cheaply from current factory state,
                    # then prove that exact pool already existed at the causal
                    # pre-Pons block before accepting it.
                    pool = read_v3_factory_pool(
                        rpc,
                        factory,
                        token_a=token,
                        token_b=anchor,
                        fee=fee,
                        block="latest",
                    )
                except Exception as exc:
                    lookup_errors.append({
                        "anchor_token": anchor,
                        "fee": fee,
                        "error": f"{type(exc).__name__}: {exc}",
                    })
                    continue
                if pool is None:
                    continue

                candidate = {
                    "factory": factory,
                    "venue": venue,
                    "anchor_token": anchor,
                    "usd_semantics": usd_semantics,
                    "fee": fee,
                    "pool": pool,
                    "pool_has_code": False,
                    "active_liquidity": None,
                    "sqrt_price_x96": None,
                    "quote_per_token": None,
                    "quote_usd": None,
                    "token_price_usd": None,
                    "causal_ready": False,
                    "error": None,
                }
                try:
                    candidate["pool_has_code"] = _has_code(
                        rpc.get_code(pool, prior)
                    )
                    if not candidate["pool_has_code"]:
                        raise RuntimeError(
                            "V3 factory returned pool without code at causal block"
                        )
                    pool_state = read_v3_pool_static(rpc, pool, block=prior)
                    if {
                        pool_state.token0.lower(),
                        pool_state.token1.lower(),
                    } != {token, anchor}:
                        raise ValueError("V3 factory pool assets mismatch")

                    slot0 = read_v3_slot0(rpc, pool, block=prior)
                    liquidity = read_v3_liquidity(rpc, pool, block=prior)
                    if slot0.sqrt_price_x96 <= 0:
                        raise ValueError("V3 pool is not initialized")
                    if liquidity <= 0:
                        raise ValueError("V3 pool has zero active liquidity")

                    token_is_token0 = pool_state.token0.lower() == token
                    quote_per_token = v3_v4_quote_per_token(
                        slot0.sqrt_price_x96,
                        token_is_token0=token_is_token0,
                        token_decimals=token_decimals,
                        quote_decimals=anchor_decimals,
                    )
                    if quote_per_token <= 0:
                        raise ValueError("V3 route price is not positive")

                    if anchor == ROBINHOOD_USDG.lower():
                        anchor_usd = Decimal(1)
                    else:
                        anchor_usd = weth_usd_cache.get(prior)
                        if anchor_usd is None:
                            anchor_usd = v3_quote_price_at_block(
                                rpc,
                                token=ROBINHOOD_WETH,
                                quote_token=ROBINHOOD_USDG,
                                pool=UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
                                block=prior,
                            )
                            weth_usd_cache[prior] = anchor_usd

                    candidate.update({
                        "active_liquidity": liquidity,
                        "sqrt_price_x96": slot0.sqrt_price_x96,
                        "quote_per_token": str(quote_per_token),
                        "quote_usd": str(anchor_usd),
                        "token_price_usd": str(
                            quote_per_token * anchor_usd
                        ),
                        "causal_ready": True,
                    })
                except Exception as exc:
                    candidate["error"] = f"{type(exc).__name__}: {exc}"
                candidates.append(candidate)

            # Prefer a direct USDG source. WETH is only a fallback because
            # probing both anchors doubles archive state reads without
            # improving coverage once a causal USDG route is already known.
            if (
                anchor == ROBINHOOD_USDG.lower()
                and any(
                    row["causal_ready"]
                    and row["anchor_token"] == anchor
                    for row in candidates
                )
            ):
                break

        ready = [row for row in candidates if row["causal_ready"]]
        output.append({
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": token_decimals,
            "factory": factory,
            "venue": venue,
            "first_launch_block": first_use,
            "causal_state_block": prior,
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "v3_candidates": candidates,
            "v3_ready_candidates": len(ready),
            "searched_anchors": searched_anchors,
            "route_search_policy": "direct_usdg_then_weth_fallback",
            "direct_usdg_ready": any(
                row["causal_ready"]
                and row["anchor_token"] == ROBINHOOD_USDG.lower()
                for row in candidates
            ),
            "direct_weth_ready": any(
                row["causal_ready"]
                and row["anchor_token"] == ROBINHOOD_WETH.lower()
                for row in candidates
            ),
            "v3_causal_ready": bool(ready),
            "lookup_errors": lookup_errors,
        })

    output.sort(key=lambda row: (
        row["first_launch_block"],
        row["quote_token"],
    ))
    return output




def discover_delayed_v3_usdg_routes(
    rpc,
    audit_rows: Iterable[dict],
    *,
    to_block: int,
    max_forward_blocks: int = 100_000,
    chunk_size: int = 2_000,
    min_chunk_size: int = 25,
) -> list[dict]:
    """Activate unresolved direct USDG routes at their first later V3 swap."""
    if max_forward_blocks <= 0:
        raise ValueError("max_forward_blocks must be positive")
    output = []
    for source in audit_rows:
        if bool(source.get("v3_causal_ready")):
            continue
        token = source["quote_token"].lower()
        first_use = int(source["first_launch_block"])
        end = min(int(to_block), first_use + int(max_forward_blocks))
        candidates = {
            row["pool"].lower(): row
            for row in source.get("v3_candidates", [])
            if row["anchor_token"].lower() == ROBINHOOD_USDG.lower()
        }
        result = {
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": int(source["quote_decimals"]),
            "first_launch_block": first_use,
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "searched_to_block": end,
            "candidate_pools": sorted(candidates),
            "delayed_route_ready": False,
            "route": None,
        }
        if not candidates or end < first_use:
            output.append(result)
            continue

        raw_logs = rpc.iter_logs_chunked(
            first_use,
            end,
            address=sorted(candidates),
            topics=[V3_SWAP_TOPIC],
            chunk_size=chunk_size,
            min_chunk_size=min_chunk_size,
        )
        first_raw = next(iter(raw_logs), None)
        if first_raw is None:
            output.append(result)
            continue

        swap = decode_v3_swap(first_raw)
        pool = swap.pool.lower()
        candidate = candidates.get(pool)
        if candidate is None:
            raise KeyError(f"delayed V3 swap came from unknown pool {pool}")
        if swap.liquidity <= 0:
            raise ValueError("first delayed V3 swap has zero active liquidity")

        state = read_v3_pool_static(rpc, pool, block=swap.block_number)
        if {state.token0.lower(), state.token1.lower()} != {
            token,
            ROBINHOOD_USDG.lower(),
        }:
            raise ValueError("delayed V3 route pool assets mismatch")
        token_is_token0 = state.token0.lower() == token
        quote_per_token = v3_v4_quote_per_token(
            swap.sqrt_price_x96,
            token_is_token0=token_is_token0,
            token_decimals=int(source["quote_decimals"]),
            quote_decimals=6,
        )
        if quote_per_token <= 0:
            raise ValueError("delayed V3 route price is not positive")

        result["delayed_route_ready"] = True
        result["route"] = {
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": int(source["quote_decimals"]),
            "activation_block": int(swap.block_number),
            "activation_transaction_index": swap.transaction_index,
            "activation_log_index": int(swap.log_index),
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "pool": pool,
            "block_number": int(swap.block_number),
            "anchor_token": ROBINHOOD_USDG.lower(),
            "anchor_decimals": 6,
            "fee": int(candidate["fee"]),
            "route_type": "uniswap_v3_direct_usdg_delayed",
            "activation_liquidity": int(swap.liquidity),
            "first_observed_quote_per_token": str(quote_per_token),
            "first_observed_usd_price": str(quote_per_token),
        }
        output.append(result)

    output.sort(
        key=lambda row: (row["first_launch_block"], row["quote_token"])
    )
    return output


def discover_delayed_v3_weth_routes(
    rpc,
    audit_rows: Iterable[dict],
    *,
    from_block: int | None,
    to_block: int,
    max_forward_blocks: int = 500_000,
    chunk_size: int = 2_000,
    min_chunk_size: int = 25,
) -> list[dict]:
    """Find first later WETH V3 swap for unresolved quote assets."""
    if max_forward_blocks <= 0:
        raise ValueError("max_forward_blocks must be positive")
    output = []
    for source in audit_rows:
        if bool(source.get("v3_causal_ready")):
            continue
        token = source["quote_token"].lower()
        first_use = int(source["first_launch_block"])
        start = first_use if from_block is None else max(
            first_use,
            int(from_block),
        )
        end = min(
            int(to_block),
            start + int(max_forward_blocks) - 1,
        )
        candidates = {
            row["pool"].lower(): row
            for row in source.get("v3_candidates", [])
            if row["anchor_token"].lower() == ROBINHOOD_WETH.lower()
        }
        result = {
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": int(source["quote_decimals"]),
            "first_launch_block": first_use,
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "searched_from_block": start,
            "searched_to_block": end,
            "candidate_pools": sorted(candidates),
            "delayed_route_ready": False,
            "route": None,
        }
        if not candidates or end < start:
            output.append(result)
            continue

        raw_logs = rpc.iter_logs_chunked(
            start,
            end,
            address=sorted(candidates),
            topics=[V3_SWAP_TOPIC],
            chunk_size=chunk_size,
            min_chunk_size=min_chunk_size,
        )
        first_raw = next(iter(raw_logs), None)
        if first_raw is None:
            output.append(result)
            continue

        swap = decode_v3_swap(first_raw)
        pool = swap.pool.lower()
        candidate = candidates.get(pool)
        if candidate is None:
            raise KeyError(
                f"delayed V3 WETH swap came from unknown pool {pool}"
            )
        if swap.liquidity <= 0:
            raise ValueError(
                "first delayed V3 WETH swap has zero active liquidity"
            )

        state = read_v3_pool_static(rpc, pool, block=swap.block_number)
        if {state.token0.lower(), state.token1.lower()} != {
            token,
            ROBINHOOD_WETH.lower(),
        }:
            raise ValueError("delayed V3 WETH route pool assets mismatch")
        token_is_token0 = state.token0.lower() == token
        quote_per_token = v3_v4_quote_per_token(
            swap.sqrt_price_x96,
            token_is_token0=token_is_token0,
            token_decimals=int(source["quote_decimals"]),
            quote_decimals=18,
        )
        if quote_per_token <= 0:
            raise ValueError(
                "delayed V3 WETH route price is not positive"
            )

        result["delayed_route_ready"] = True
        result["route"] = {
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": int(source["quote_decimals"]),
            "activation_block": int(swap.block_number),
            "activation_transaction_index": swap.transaction_index,
            "activation_log_index": int(swap.log_index),
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "pool": pool,
            "block_number": int(swap.block_number),
            "anchor_token": ROBINHOOD_WETH.lower(),
            "anchor_decimals": 18,
            "fee": int(candidate["fee"]),
            "route_type": "uniswap_v3_direct_weth_delayed",
            "activation_liquidity": int(swap.liquidity),
            "first_observed_quote_per_token": str(quote_per_token),
            # Exact USD conversion is intentionally deferred to
            # build_v3_route_usd_updates, which advances the WETH/USD anchor
            # by event order and avoids end-of-block lookahead.
            "first_observed_usd_price": None,
        }
        output.append(result)

    output.sort(
        key=lambda row: (row["first_launch_block"], row["quote_token"])
    )
    return output


def select_v3_quote_routes(audit_rows: Iterable[dict]) -> list[dict]:
    """Select one deterministic causal V3 route for each covered quote asset."""
    selected = []
    for source in audit_rows:
        ready = [
            row
            for row in source.get("v3_candidates", [])
            if bool(row.get("causal_ready"))
        ]
        if not ready:
            continue
        usdg = [
            row
            for row in ready
            if row["anchor_token"] == ROBINHOOD_USDG.lower()
        ]
        candidates = usdg or [
            row
            for row in ready
            if row["anchor_token"] == ROBINHOOD_WETH.lower()
        ]
        if not candidates:
            continue
        # Liquidity units are comparable here because candidates now share the
        # same token/anchor pair. Break ties toward lower fee, then address.
        best = sorted(
            candidates,
            key=lambda row: (
                -int(row["active_liquidity"]),
                int(row["fee"]),
                row["pool"].lower(),
            ),
        )[0]
        token = source["quote_token"].lower()
        anchor = best["anchor_token"].lower()
        factory = best.get(
            "factory",
            source.get("factory", UNISWAP_V3_FACTORY),
        ).lower()
        venue = best.get("venue") or _v3_venue(factory)
        selected.append({
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": int(source["quote_decimals"]),
            "activation_block": int(source["first_launch_block"]),
            "causal_state_block": int(source["causal_state_block"]),
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "pool": best["pool"].lower(),
            "factory": factory,
            "venue": venue,
            "block_number": int(source["first_launch_block"]),
            "anchor_token": anchor,
            "anchor_decimals": (
                6 if anchor == ROBINHOOD_USDG.lower() else 18
            ),
            "fee": int(best["fee"]),
            "route_type": (
                f"{venue}_direct_usdg"
                if anchor == ROBINHOOD_USDG.lower()
                else f"{venue}_direct_weth"
            ),
            "activation_liquidity": int(best["active_liquidity"]),
            "initial_usd_price": str(best["token_price_usd"]),
            "initial_quote_per_token": str(best["quote_per_token"]),
            "initial_anchor_usd": str(best["quote_usd"]),
        })

    selected.sort(key=lambda row: (
        row["activation_block"],
        row["quote_token"],
    ))
    return selected



def merge_v3_quote_routes(
    causal_routes: Iterable[dict],
    delayed_audit_rows: Iterable[dict] = (),
) -> list[dict]:
    """Merge pre-use and delayed route choices with one route per quote token."""
    by_token = {}
    for raw in causal_routes:
        row = dict(raw)
        token = row["quote_token"].lower()
        if token in by_token:
            raise ValueError(f"duplicate causal V3 quote route for {token}")
        by_token[token] = row

    for source in delayed_audit_rows:
        if not bool(source.get("delayed_route_ready")):
            continue
        route = source.get("route")
        if not route:
            raise ValueError("delayed route row is marked ready without route")
        row = dict(route)
        token = row["quote_token"].lower()
        if token in by_token:
            raise ValueError(
                f"quote token has both causal and delayed V3 routes: {token}"
            )
        by_token[token] = row

    rows = list(by_token.values())
    rows.sort(key=lambda row: (
        int(row["activation_block"]),
        row["quote_token"].lower(),
    ))
    return rows


def build_v3_route_initial_usd_states(
    route_rows: Iterable[dict],
) -> list[dict]:
    """Convert selected route activation states to generic quote/USD state."""
    rows = []
    for route in route_rows:
        if route.get("causal_state_block") is None:
            continue
        rows.append({
            "quote_token": route["quote_token"].lower(),
            "symbol": route.get("symbol"),
            "pricing_source": route["route_type"],
            "source_pool": route["pool"].lower(),
            "block_number": int(route["causal_state_block"]),
            "activation_block": int(route["activation_block"]),
            "usd_price": str(route["initial_usd_price"]),
        })
    rows.sort(key=lambda row: (
        row["activation_block"],
        row["quote_token"],
    ))
    return rows


def build_v3_route_usd_updates(
    route_rows: Iterable[dict],
    v3_price_events: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict] = (),
    *,
    initial_weth_usd: Decimal | None = None,
):
    """Convert selected V3 route price events into causal quote/USD updates."""
    routes = {
        row["pool"].lower(): dict(row)
        for row in route_rows
    }
    if not routes:
        return
    from hlp.data.quote_usd import QuoteUsdTimeline
    from hlp.data.reconstruct import event_order

    needs_weth = any(
        row["anchor_token"].lower() == ROBINHOOD_WETH.lower()
        for row in routes.values()
    )
    usd = None
    if needs_weth:
        if initial_weth_usd is None or initial_weth_usd <= 0:
            raise ValueError(
                "positive initial WETH/USD is required for WETH fallback routes"
            )
        usd = QuoteUsdTimeline(
            initial_weth_usd=initial_weth_usd,
            weth_anchor_points=weth_usd_anchor_points,
        )
    last_order = None
    for event in v3_price_events:
        order = event_order(event)
        if last_order is not None and order < last_order:
            raise ValueError("V3 fallback quote tape is not chronological")
        last_order = order

        pool = event["pool"].lower()
        route = routes.get(pool)
        if route is None:
            raise KeyError(
                f"V3 fallback event pool is absent from route registry: {pool}"
            )
        activation_order = (
            int(route["activation_block"]),
            -1 if route.get("activation_transaction_index") is None
            else int(route["activation_transaction_index"]),
            -1 if route.get("activation_log_index") is None
            else int(route["activation_log_index"]),
        )
        if order < activation_order:
            continue

        if usd is not None:
            usd.advance_to(order)
        token = route["quote_token"].lower()
        anchor = route["anchor_token"].lower()
        token_is_token0 = int(token, 16) < int(anchor, 16)
        quote_per_token = v3_v4_quote_per_token(
            int(event["sqrt_price_x96"]),
            token_is_token0=token_is_token0,
            token_decimals=int(route["quote_decimals"]),
            quote_decimals=int(route["anchor_decimals"]),
        )
        if anchor == ROBINHOOD_USDG.lower():
            anchor_usd = Decimal(1)
        elif anchor == ROBINHOOD_WETH.lower():
            if usd is None:
                raise ValueError("WETH/USD timeline is unavailable")
            anchor_usd = usd.price(ROBINHOOD_WETH)
            if anchor_usd is None:
                raise ValueError("WETH/USD price is unavailable")
        else:
            raise ValueError(f"unsupported V3 fallback anchor {anchor}")

        yield {
            "quote_token": token,
            "symbol": route.get("symbol"),
            "pricing_source": route["route_type"],
            "source_pool": pool,
            "block_number": int(event["block_number"]),
            "transaction_hash": event["transaction_hash"],
            "transaction_index": event.get("transaction_index"),
            "log_index": int(event["log_index"]),
            "quote_per_token": str(quote_per_token),
            "anchor_usd": str(anchor_usd),
            "usd_price": str(quote_per_token * anchor_usd),
        }
