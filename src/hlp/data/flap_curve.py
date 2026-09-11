"""Flap bonding-curve USD market-cap reconstruction."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.data.quote_usd import QuoteUsdTimeline
from hlp.data.types import FlapEvent


FLAP_FIXED_SUPPLY = Decimal("1000000000")
PRICE_SCALE = Decimal(10) ** 18


def _order(row: FlapEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def build_flap_curve_market_cap_points(
    events: Iterable[FlapEvent],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
    launch_registry: Iterable[dict] = (),
) -> Iterator[dict]:
    """Price Flap TokenBought/TokenSold events without look-ahead.

    Flap's Portal interface defines TokenStateV8.price/postPrice as quote-token
    units with 18 decimals. Robinhood mainnet launch samples independently
    verify a fixed 1B token supply with 18 decimals.

    A token is not assigned a quote asset until its TokenQuoteSet event has
    already occurred in the event tape.
    """
    timeline = QuoteUsdTimeline(
        initial_weth_usd=initial_weth_usd,
        weth_anchor_points=weth_usd_anchor_points,
        initial_quote_usd=initial_quote_usd,
        oracle_updates=quote_usd_updates,
    )
    registry_rows = list(launch_registry)
    quote_by_token: dict[str, str] = {
        row["token"].lower(): row["quote_token"].lower()
        for row in registry_rows
        if row.get("quote_token")
    }
    seen_launches: set[str] = {
        row["token"].lower()
        for row in registry_rows
    }

    rows = sorted(list(events), key=_order)
    for event in rows:
        order = _order(event)
        timeline.advance_to(order)
        token = event.token.lower()

        if event.event_type == "token_created":
            seen_launches.add(token)
            continue
        if event.event_type == "quote_set":
            if event.actor is None:
                raise ValueError(f"Flap quote_set has no quote token: {token}")
            quote_by_token[token] = event.actor.lower()
            continue
        if event.event_type not in {"token_bought", "token_sold"}:
            continue
        if token not in seen_launches:
            raise ValueError(f"Flap trade precedes TokenCreated in supplied history: {token}")
        if event.post_price_raw is None:
            raise ValueError(f"Flap trade has no postPrice: {token}")

        quote_token = quote_by_token.get(token)
        quote_per_token = Decimal(event.post_price_raw) / PRICE_SCALE
        quote_usd = None if quote_token is None else timeline.price(quote_token)
        if quote_token is None:
            pricing_status = "missing_quote_event"
        else:
            pricing_status = timeline.pricing_status(quote_token)

        token_price_usd = (
            None if quote_usd is None else quote_per_token * quote_usd
        )
        market_cap = (
            None if token_price_usd is None
            else token_price_usd * FLAP_FIXED_SUPPLY
        )
        yield {
            "venue": "flap",
            "phase": "curve",
            "event_type": event.event_type,
            "token": token,
            "actor": event.actor,
            "quote_token": quote_token,
            "block_number": event.block_number,
            "transaction_hash": event.transaction_hash,
            "transaction_index": event.transaction_index,
            "log_index": event.log_index,
            "amount_raw": event.amount_raw,
            "quote_amount_raw": event.quote_amount_raw,
            "fee_raw": event.fee_raw,
            "post_price_raw": event.post_price_raw,
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


def summarize_flap_curve_market_caps(rows: Iterable[dict]) -> list[dict]:
    summary: dict[str, dict] = {}
    for row in rows:
        token = row["token"]
        value = row.get("market_cap_proxy_usd")
        mcap = Decimal(value) if value is not None else None
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": "flap",
                "quote_tokens": set(),
                "pricing_statuses": set(),
                "price_points": 0,
                "priced_points": 0,
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            summary[token] = current
        if row.get("quote_token"):
            current["quote_tokens"].add(row["quote_token"])
        current["pricing_statuses"].add(row["pricing_status"])
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
    for current in summary.values():
        row = dict(current)
        row["quote_tokens"] = sorted(row["quote_tokens"])
        row["pricing_statuses"] = sorted(row["pricing_statuses"])
        if row["max_market_cap_proxy_usd"] is not None:
            row["max_market_cap_proxy_usd"] = str(row["max_market_cap_proxy_usd"])
        output.append(row)
    output.sort(key=lambda row: row["token"])
    return output
