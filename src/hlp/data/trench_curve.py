"""trench.today bonding-curve USD market-cap reconstruction."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.data.quote_usd import QuoteUsdTimeline
from hlp.data.types import TrenchEvent


TRENCH_FIXED_SUPPLY = Decimal("1000000000")


def _order(row: TrenchEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def build_trench_curve_market_cap_points(
    events: Iterable[TrenchEvent],
    launch_registry: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
) -> Iterator[dict]:
    """Price each authoritative trench Sync snapshot without look-ahead.

    Sync carries post-trade virtual quote/token reserves. Both assets use
    18-decimal raw units in the validated Robinhood regime, so the raw reserve
    ratio directly yields quote-token-per-token.
    """
    registry = {
        row["token"].lower(): row
        for row in launch_registry
    }
    timeline = QuoteUsdTimeline(
        initial_weth_usd=initial_weth_usd,
        weth_anchor_points=weth_usd_anchor_points,
        initial_quote_usd=initial_quote_usd,
        oracle_updates=quote_usd_updates,
    )

    for event in sorted(list(events), key=_order):
        order = _order(event)
        timeline.advance_to(order)
        if event.event_type != "sync":
            continue
        token = event.token.lower()
        launch = registry.get(token)
        if launch is None:
            raise ValueError(
                f"trench.today Sync token absent from persistent registry: {token}"
            )
        if event.virtual_quote_raw is None or event.virtual_token_raw is None:
            raise ValueError(f"trench.today Sync missing virtual reserves: {token}")
        if event.virtual_quote_raw <= 0 or event.virtual_token_raw <= 0:
            raise ValueError(f"trench.today Sync has non-positive virtual reserves: {token}")

        quote_token = launch["quote_token"].lower()
        quote_per_token = (
            Decimal(event.virtual_quote_raw) / Decimal(event.virtual_token_raw)
        )
        quote_usd = timeline.price(quote_token)
        pricing_status = timeline.pricing_status(quote_token)
        token_price_usd = (
            None if quote_usd is None else quote_per_token * quote_usd
        )
        market_cap = (
            None
            if token_price_usd is None
            else token_price_usd * TRENCH_FIXED_SUPPLY
        )

        yield {
            "venue": "trench.today",
            "phase": "curve",
            "event_type": "sync",
            "token": token,
            "curve": launch["curve"],
            "quote_token": quote_token,
            "block_number": event.block_number,
            "transaction_hash": event.transaction_hash,
            "transaction_index": event.transaction_index,
            "log_index": event.log_index,
            "real_quote_reserves_raw": event.real_quote_reserves_raw,
            "real_token_reserves_raw": event.real_token_reserves_raw,
            "virtual_quote_raw": event.virtual_quote_raw,
            "virtual_token_raw": event.virtual_token_raw,
            "quote_per_token": str(quote_per_token),
            "pricing_status": pricing_status,
            "quote_usd": None if quote_usd is None else str(quote_usd),
            "token_price_usd": (
                None if token_price_usd is None else str(token_price_usd)
            ),
            "market_cap_proxy_usd": (
                None if market_cap is None else str(market_cap)
            ),
        }


def summarize_trench_curve_market_caps(rows: Iterable[dict]) -> list[dict]:
    summary: dict[str, dict] = {}
    for row in rows:
        token = row["token"]
        value = row.get("market_cap_proxy_usd")
        mcap = Decimal(value) if value is not None else None
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": "trench.today",
                "quote_token": row["quote_token"],
                "price_points": 0,
                "priced_points": 0,
                "pricing_statuses": set(),
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            summary[token] = current
        current["price_points"] += 1
        current["pricing_statuses"].add(row["pricing_status"])
        if mcap is None:
            continue
        current["priced_points"] += 1
        prior = current["max_market_cap_proxy_usd"]
        if prior is None or mcap > prior:
            current["max_market_cap_proxy_usd"] = mcap
            current["max_market_cap_block"] = row["block_number"]
        if mcap >= Decimal("100000"):
            current["crossed_100k"] = True

    output: list[dict] = []
    for current in summary.values():
        row = dict(current)
        row["pricing_statuses"] = sorted(row["pricing_statuses"])
        if row["max_market_cap_proxy_usd"] is not None:
            row["max_market_cap_proxy_usd"] = str(row["max_market_cap_proxy_usd"])
        output.append(row)
    output.sort(key=lambda row: row["token"])
    return output
