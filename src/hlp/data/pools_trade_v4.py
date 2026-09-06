"""pools.trade V4 market-cap reconstruction.

Market cap is computed directly in raw units, so token decimals cancel:
raw_quote_per_raw_token * total_supply_raw / 10**quote_decimals.
"""

from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Iterable

from hlp.data.quote_usd import QuoteUsdTimeline
from hlp.data.reconstruct import event_order


Q192 = 1 << 192


def _raw_quote_per_raw_token(
    sqrt_price_x96: int,
    *,
    token_is_currency0: bool,
) -> Decimal:
    if sqrt_price_x96 <= 0:
        raise ValueError("sqrtPriceX96 must be positive")
    ratio1_per_0 = Decimal(sqrt_price_x96) ** 2 / Decimal(Q192)
    return ratio1_per_0 if token_is_currency0 else Decimal(1) / ratio1_per_0


def build_pools_trade_v4_market_cap_points(
    registry_rows: Iterable[dict],
    initialize_rows: Iterable[dict],
    swap_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
    quote_decimals: dict[str, int],
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
) -> list[dict]:
    """Build initialization + swap market-cap points for instant launches."""
    getcontext().prec = max(getcontext().prec, 80)
    registry = {
        row["pool_id"].lower(): row
        for row in registry_rows
    }
    timeline = QuoteUsdTimeline(
        initial_weth_usd=initial_weth_usd,
        weth_anchor_points=weth_usd_anchor_points,
        initial_quote_usd=initial_quote_usd,
        oracle_updates=quote_usd_updates,
    )

    events: list[dict] = []
    for row in initialize_rows:
        pool_id = row["pool_id"].lower()
        if pool_id in registry:
            events.append({**row, "_kind": "v4_initialize"})
    for row in swap_rows:
        pool_id = row["pool_id"].lower()
        if pool_id in registry:
            events.append({**row, "_kind": "v4_swap"})
    events.sort(key=event_order)

    output = []
    initialized: set[str] = set()
    for event in events:
        order = event_order(event)
        timeline.advance_to(order)
        pool_id = event["pool_id"].lower()
        launch = registry[pool_id]
        token = launch["token"].lower()
        quote = launch["quote_token"].lower()
        decimals = quote_decimals.get(quote)
        if decimals is None:
            raise KeyError(f"missing quote decimals for pools.trade quote {quote}")

        if event["_kind"] == "v4_initialize":
            initialized.add(pool_id)
        elif pool_id not in initialized:
            raise ValueError(f"pools.trade V4 swap precedes Initialize: {pool_id}")

        token_is_currency0 = launch["currency0"].lower() == token
        raw_quote_per_raw_token = _raw_quote_per_raw_token(
            int(event["sqrt_price_x96"]),
            token_is_currency0=token_is_currency0,
        )
        market_cap_quote = (
            raw_quote_per_raw_token
            * Decimal(int(launch["supply_raw"]))
            / (Decimal(10) ** decimals)
        )
        quote_usd = timeline.price(quote)
        status = timeline.pricing_status(quote)
        market_cap_usd = (
            None if quote_usd is None else market_cap_quote * quote_usd
        )
        output.append(
            {
                "venue": "pools.trade",
                "phase": "v4",
                "event_type": event["_kind"],
                "token": token,
                "pool_id": pool_id,
                "quote_token": quote,
                "supply_raw": int(launch["supply_raw"]),
                "block_number": int(event["block_number"]),
                "transaction_hash": event["transaction_hash"],
                "transaction_index": event.get("transaction_index"),
                "log_index": int(event["log_index"]),
                "sqrt_price_x96": int(event["sqrt_price_x96"]),
                "raw_quote_per_raw_token": str(raw_quote_per_raw_token),
                "market_cap_quote": str(market_cap_quote),
                "pricing_status": status,
                "quote_usd": None if quote_usd is None else str(quote_usd),
                "market_cap_proxy_usd": (
                    None if market_cap_usd is None else str(market_cap_usd)
                ),
            }
        )
    return output


def summarize_pools_trade_market_caps(rows: Iterable[dict]) -> list[dict]:
    summary: dict[str, dict] = {}
    for row in rows:
        token = row["token"]
        value = row.get("market_cap_proxy_usd")
        mcap = Decimal(value) if value is not None else None
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": "pools.trade",
                "pool_id": row["pool_id"],
                "quote_token": row["quote_token"],
                "price_points": 0,
                "priced_points": 0,
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            summary[token] = current
        current["price_points"] += 1
        if mcap is None:
            continue
        current["priced_points"] += 1
        prior = current["max_market_cap_proxy_usd"]
        if prior is None or mcap > prior:
            current["max_market_cap_proxy_usd"] = mcap
            current["max_market_cap_block"] = row["block_number"]
        if mcap >= Decimal("100000"):
            current["crossed_100k"] = True
    output = []
    for row in summary.values():
        item = dict(row)
        if item["max_market_cap_proxy_usd"] is not None:
            item["max_market_cap_proxy_usd"] = str(item["max_market_cap_proxy_usd"])
        output.append(item)
    output.sort(key=lambda row: row["token"])
    return output
