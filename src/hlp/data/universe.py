"""Universe-stage market-cap reconstruction.

This module intentionally derives only market paths and eligibility evidence.
It does not define a first-major-dump or any predictive signal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.quote_usd import QuoteUsdTimeline
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
    weth_decimals: int,
    usdg_decimals: int,
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
    quote_decimals_by_token: dict[str, int] | None = None,
) -> Iterator[dict]:
    """Join Pons V1 V3 price events to causal point-in-time USD quotes.

    WETH uses the WETH/USDG anchor, USDG is nominal $1, and canonical
    Robinhood Stock Token quote assets use their historical Chainlink tape.
    Unknown quote assets are preserved as unsupported rather than guessed.
    """
    if initial_weth_usd <= 0:
        raise ValueError("initial_weth_usd must be positive")

    registry = {
        _lower(row["pool"]): row
        for row in registry_rows
        if row.get("pool")
    }
    usd = QuoteUsdTimeline(
        initial_weth_usd=initial_weth_usd,
        weth_anchor_points=weth_usd_anchor_points,
        initial_quote_usd=initial_quote_usd,
        oracle_updates=quote_usd_updates,
    )
    quote_decimals = {
        token.lower(): int(decimals)
        for token, decimals in (quote_decimals_by_token or {}).items()
    }
    quote_decimals[_lower(ROBINHOOD_WETH)] = int(weth_decimals)
    quote_decimals[_lower(ROBINHOOD_USDG)] = int(usdg_decimals)

    last_order: tuple[int, int, int] | None = None

    for swap in swap_rows:
        order = event_order(swap)
        if last_order is not None and order < last_order:
            raise ValueError("Pons V1 price tape is not chronological")
        last_order = order
        usd.advance_to(order)

        pool = _lower(swap["pool"])
        launch = registry.get(pool)
        if launch is None:
            raise KeyError(
                f"price-event pool is absent from V1 launch registry: {pool}"
            )

        token = _lower(launch["token"])
        quote = _lower(launch["pair_token"])
        token_decimals = int(launch["token_decimals"])
        supply_raw = int(launch["supply_raw"])
        token_is_token0 = int(token, 16) < int(quote, 16)

        decimals = quote_decimals.get(quote)
        quote_usd = usd.price(quote)
        pricing_status = usd.pricing_status(quote)
        if decimals is None or quote_usd is None:
            out = dict(swap)
            out.update(
                {
                    "token": token,
                    "quote_token": quote,
                    "launch_block": int(launch["block_number"]),
                    "supply_raw": supply_raw,
                    "token_decimals": token_decimals,
                    "token_is_token0": token_is_token0,
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
            quote_decimals=decimals,
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
                "unpriced_points": 0,
                "first_priced_block": None,
                "last_priced_block": None,
                "first_unpriced_block": None,
                "last_unpriced_block": None,
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "v3_swap_max_market_cap_proxy_usd": None,
                "v3_swap_max_market_cap_block": None,
                "crossed_100k": False,
            }
            summary[token] = current
        current["pricing_statuses"].add(row["pricing_status"])
        current["price_points"] += 1
        block = int(row["block_number"])
        if mcap is None:
            current["unpriced_points"] += 1
            if current["first_unpriced_block"] is None:
                current["first_unpriced_block"] = block
            current["last_unpriced_block"] = block
            continue
        current["priced_points"] += 1
        if current["first_priced_block"] is None:
            current["first_priced_block"] = block
        current["last_priced_block"] = block
        previous = current["max_market_cap_proxy_usd"]
        if previous is None or mcap > previous:
            current["max_market_cap_proxy_usd"] = mcap
            current["max_market_cap_block"] = row["block_number"]
        if row.get("event_type") == "v3_swap":
            previous_swap = current["v3_swap_max_market_cap_proxy_usd"]
            if previous_swap is None or mcap > previous_swap:
                current["v3_swap_max_market_cap_proxy_usd"] = mcap
                current["v3_swap_max_market_cap_block"] = row["block_number"]
        if mcap >= Decimal("100000"):
            current["crossed_100k"] = True

    output = []
    for current in summary.values():
        row = dict(current)
        row["pricing_statuses"] = sorted(row["pricing_statuses"])
        if row["max_market_cap_proxy_usd"] is not None:
            row["max_market_cap_proxy_usd"] = str(row["max_market_cap_proxy_usd"])
        if row["v3_swap_max_market_cap_proxy_usd"] is not None:
            row["v3_swap_max_market_cap_proxy_usd"] = str(
                row["v3_swap_max_market_cap_proxy_usd"]
            )
        row["pricing_complete"] = row["unpriced_points"] == 0
        row["eligibility_status"] = (
            "eligible"
            if row["crossed_100k"]
            else "unknown"
            if row["unpriced_points"] > 0
            else "ineligible"
        )
        output.append(row)
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output
