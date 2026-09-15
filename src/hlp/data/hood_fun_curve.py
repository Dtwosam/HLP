"""hood.fun bonding-curve USD market-cap reconstruction."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from hlp.data.quote_usd import QuoteUsdTimeline
from hlp.data.types import HoodFunEvent


TOKEN_SCALE = Decimal(10) ** 18
NATIVE_QUOTE = "0x" + "00" * 20


def _order(row: HoodFunEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def _market_cap_eth(
    virtual_quote_raw: int,
    virtual_token_raw: int,
    supply_raw: int,
) -> Decimal:
    if virtual_quote_raw <= 0 or virtual_token_raw <= 0 or supply_raw <= 0:
        raise ValueError("hood.fun reserves and supply must be positive")
    # (wei / token-base-unit) * token-base-units / 1e18 = ETH FDV.
    return (
        Decimal(virtual_quote_raw)
        / Decimal(virtual_token_raw)
        * Decimal(supply_raw)
        / TOKEN_SCALE
    )


def build_hood_fun_curve_market_cap_points(
    events: Iterable[HoodFunEvent],
    launch_registry: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
) -> list[dict]:
    """Price launch state and every post-trade virtual-reserve snapshot.

    Trade events emit the post-trade virtual ETH/token reserves directly, so
    later shards can be priced without replaying every earlier trade. The
    persistent launch registry is still required for the chosen total supply.
    """
    registry = {
        row["token"].lower(): row
        for row in launch_registry
    }
    timeline = QuoteUsdTimeline(
        initial_weth_usd=initial_weth_usd,
        weth_anchor_points=weth_usd_anchor_points,
    )

    output = []
    for event in sorted(list(events), key=_order):
        order = _order(event)
        timeline.advance_to(order)
        token = event.token.lower()
        launch = registry.get(token)
        if launch is None:
            if event.event_type == "token_created":
                raise ValueError(
                    f"hood.fun TokenCreated absent from supplied registry: {token}"
                )
            raise ValueError(
                f"hood.fun trade token absent from persistent registry: {token}"
            )
        if event.event_type not in {"token_created", "trade"}:
            continue
        if event.virtual_quote_raw is None or event.virtual_token_raw is None:
            raise ValueError(f"hood.fun price event missing reserves: {token}")

        market_cap_eth = _market_cap_eth(
            event.virtual_quote_raw,
            event.virtual_token_raw,
            int(launch["supply_raw"]),
        )
        quote_usd = timeline.price(NATIVE_QUOTE)
        status = timeline.pricing_status(NATIVE_QUOTE)
        market_cap_usd = (
            None if quote_usd is None else market_cap_eth * quote_usd
        )
        output.append(
            {
                "venue": "hood.fun",
                "phase": "curve",
                "event_type": event.event_type,
                "token": token,
                "quote_token": NATIVE_QUOTE,
                "block_number": event.block_number,
                "transaction_hash": event.transaction_hash,
                "transaction_index": event.transaction_index,
                "log_index": event.log_index,
                "is_buy": event.is_buy,
                "quote_amount_raw": event.quote_amount_raw,
                "token_amount_raw": event.token_amount_raw,
                "fee_raw": event.fee_raw,
                "virtual_quote_raw": event.virtual_quote_raw,
                "virtual_token_raw": event.virtual_token_raw,
                "supply_raw": int(launch["supply_raw"]),
                "market_cap_quote": str(market_cap_eth),
                "pricing_status": status,
                "quote_usd": None if quote_usd is None else str(quote_usd),
                "market_cap_proxy_usd": (
                    None if market_cap_usd is None else str(market_cap_usd)
                ),
            }
        )
    return output


def summarize_hood_fun_curve_market_caps(rows: Iterable[dict]) -> list[dict]:
    summary: dict[str, dict] = {}
    for row in rows:
        token = row["token"]
        value = row.get("market_cap_proxy_usd")
        mcap = Decimal(value) if value is not None else None
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": "hood.fun",
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
