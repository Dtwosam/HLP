"""Universe-stage market-cap reconstruction.

This module intentionally derives only market paths and eligibility evidence.
It does not define a first-major-dump or any predictive signal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.reconstruct import event_order
from hlp.price import human_amount, v3_v4_quote_per_token


def _lower(address: str) -> str:
    return address.lower()


def build_v1_market_cap_points(
    registry_rows: Iterable[dict],
    swap_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
) -> Iterator[dict]:
    """Join shared Pons V1 swaps to supply/config and point-in-time USD.

    Supported canonical quote assets in the initial V1 implementation:
    - WETH, priced from the shared WETH/USDG V3 anchor tape;
    - USDG, treated as nominal $1 for the chart market-cap proxy.

    Other pair assets are preserved with pricing_status=unsupported_quote
    rather than silently guessed.
    """
    if initial_weth_usd <= 0:
        raise ValueError("initial_weth_usd must be positive")

    registry = {
        _lower(row["pool"]): row
        for row in registry_rows
        if row.get("pool")
    }
    anchors = iter(weth_usd_anchor_points)
    next_anchor = next(anchors, None)
    active_weth_usd = initial_weth_usd

    weth = _lower(ROBINHOOD_WETH)
    usdg = _lower(ROBINHOOD_USDG)

    last_swap_order: tuple[int, int, int] | None = None

    for swap in swap_rows:
        order = event_order(swap)
        if last_swap_order is not None and order < last_swap_order:
            raise ValueError("Pons V1 swap tape is not chronological")
        last_swap_order = order

        while next_anchor is not None and event_order(next_anchor) <= order:
            active_weth_usd = Decimal(next_anchor["quote_per_token"])
            next_anchor = next(anchors, None)

        pool = _lower(swap["pool"])
        launch = registry.get(pool)
        if launch is None:
            raise KeyError(f"swap pool is absent from V1 launch registry: {pool}")

        token = _lower(launch["token"])
        quote = _lower(launch["pair_token"])
        token_decimals = int(launch["token_decimals"])
        supply_raw = int(launch["supply_raw"])

        # Uniswap V3 token ordering is ascending address order.
        token_is_token0 = int(token, 16) < int(quote, 16)

        if quote == weth:
            quote_decimals = 18
            quote_usd = active_weth_usd
            pricing_status = "priced_weth_usdg"
        elif quote == usdg:
            quote_decimals = 18
            quote_usd = Decimal(1)
            pricing_status = "priced_usdg_nominal"
        else:
            out = dict(swap)
            out.update(
                {
                    "token": token,
                    "quote_token": quote,
                    "launch_block": int(launch["block_number"]),
                    "supply_raw": supply_raw,
                    "token_decimals": token_decimals,
                    "pricing_status": "unsupported_quote",
                    "quote_usd": None,
                    "quote_per_token": None,
                    "token_price_usd": None,
                    "market_cap_proxy_usd": None,
                }
            )
            yield out
            continue

        quote_per_token = v3_v4_quote_per_token(
            int(swap["sqrt_price_x96"]),
            token_is_token0=token_is_token0,
            token_decimals=token_decimals,
            quote_decimals=quote_decimals,
        )
        supply = human_amount(supply_raw, token_decimals)
        token_price_usd = quote_per_token * quote_usd
        market_cap = token_price_usd * supply

        out = dict(swap)
        out.update(
            {
                "token": token,
                "quote_token": quote,
                "launch_block": int(launch["block_number"]),
                "supply_raw": supply_raw,
                "token_decimals": token_decimals,
                "token_is_token0": token_is_token0,
                "pricing_status": pricing_status,
                "quote_usd": str(quote_usd),
                "quote_per_token": str(quote_per_token),
                "token_price_usd": str(token_price_usd),
                "market_cap_proxy_usd": str(market_cap),
            }
        )
        yield out


def summarize_v1_market_caps(rows: Iterable[dict]) -> list[dict]:
    """Return one eligibility summary per token from reconstructed swap points."""
    summary: dict[str, dict] = {}
    for row in rows:
        token = row["token"]
        current = summary.get(token)
        value = row.get("market_cap_proxy_usd")
        mcap = Decimal(value) if value is not None else None
        if current is None:
            current = {
                "token": token,
                "pool": row["pool"],
                "quote_token": row["quote_token"],
                "launch_block": row["launch_block"],
                "pricing_statuses": set(),
                "price_points": 0,
                "priced_points": 0,
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            summary[token] = current
        current["pricing_statuses"].add(row["pricing_status"])
        current["price_points"] += 1
        if mcap is None:
            continue
        current["priced_points"] += 1
        previous = current["max_market_cap_proxy_usd"]
        if previous is None or mcap > previous:
            current["max_market_cap_proxy_usd"] = mcap
            current["max_market_cap_block"] = row["block_number"]
        if mcap >= Decimal("100000"):
            current["crossed_100k"] = True

    output = []
    for current in summary.values():
        row = dict(current)
        row["pricing_statuses"] = sorted(row["pricing_statuses"])
        if row["max_market_cap_proxy_usd"] is not None:
            row["max_market_cap_proxy_usd"] = str(row["max_market_cap_proxy_usd"])
        output.append(row)
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output
