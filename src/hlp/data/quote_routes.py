"""Causal fallback route discovery for Pons quote assets without USD feeds."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from hlp.config import (
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    UNISWAP_V3_FACTORY,
    UNISWAP_V3_WETH_USDG_ANCHOR_POOL,
)
from hlp.data.reconstruct import v3_quote_price_at_block
from hlp.price import v3_v4_quote_per_token
from hlp.protocols.state import (
    read_v3_factory_pool,
    read_v3_liquidity,
    read_v3_pool_static,
    read_v3_slot0,
)


V3_CANONICAL_FEES = (100, 500, 3000, 10000)


def _has_code(value: str) -> bool:
    return value not in {"0x", "0x0", ""}


def audit_unpriced_v3_quote_routes(
    rpc,
    quote_rows: Iterable[dict],
    *,
    factory: str = UNISWAP_V3_FACTORY,
    fees: tuple[int, ...] = V3_CANONICAL_FEES,
) -> list[dict]:
    """Find direct USDG/WETH V3 routes visible before first Pons quote use."""
    rows = list(quote_rows)
    special_decimals = {
        row["quote_token"].lower(): int(row["quote_decimals"])
        for row in rows
        if row.get("quote_decimals") is not None
    }
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

        for anchor, usd_semantics in anchor_specs:
            anchor_decimals = special_decimals.get(anchor)
            if anchor_decimals is None:
                raise ValueError(
                    f"quote registry is missing decimals for anchor {anchor}"
                )
            for fee in fees:
                try:
                    pool = read_v3_factory_pool(
                        rpc,
                        factory,
                        token_a=token,
                        token_b=anchor,
                        fee=fee,
                        block=prior,
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

        ready = [row for row in candidates if row["causal_ready"]]
        output.append({
            "quote_token": token,
            "symbol": source.get("symbol"),
            "quote_decimals": token_decimals,
            "first_launch_block": first_use,
            "causal_state_block": prior,
            "launches": int(source["launches"]),
            "versions": source.get("versions", {}),
            "v3_candidates": candidates,
            "v3_ready_candidates": len(ready),
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
