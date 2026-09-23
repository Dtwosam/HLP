"""trench.today bonding-curve USD market-cap reconstruction."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.data.quote_usd import QuoteUsdTimeline
from hlp.data.types import TrenchEvent


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
    quote_decimals: dict[str, int] | None = None,
) -> Iterator[dict]:
    """Price each authoritative trench Sync snapshot without look-ahead.

    Sync carries post-trade virtual quote/token reserves. Market cap is
    computed in raw units so token decimals cancel:
    raw_quote/raw_token * total_supply_raw / 10**quote_decimals.
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
        if (
            launch.get("launch_block") is None
            or launch.get("launch_log_index") is None
        ):
            raise ValueError(
                f"trench.today registry missing launch order: {token}"
            )
        launch_order = (
            int(launch["launch_block"]),
            -1
            if launch.get("launch_transaction_index") is None
            else int(launch["launch_transaction_index"]),
            int(launch["launch_log_index"]),
        )
        if order <= launch_order:
            raise ValueError(
                f"trench.today Sync precedes recorded launch: {token}"
            )
        if launch.get("limit_reach_block") is not None:
            if launch.get("limit_reach_log_index") is None:
                raise ValueError(
                    f"trench.today registry missing LimitReach order: {token}"
                )
            limit_order = (
                int(launch["limit_reach_block"]),
                -1
                if launch.get("limit_reach_transaction_index") is None
                else int(launch["limit_reach_transaction_index"]),
                int(launch["limit_reach_log_index"]),
            )
            if order > limit_order:
                raise ValueError(
                    f"trench.today Sync follows recorded LimitReach: {token}"
                )
        if event.virtual_quote_raw is None or event.virtual_token_raw is None:
            raise ValueError(f"trench.today Sync missing virtual reserves: {token}")
        if event.virtual_quote_raw <= 0 or event.virtual_token_raw <= 0:
            raise ValueError(f"trench.today Sync has non-positive virtual reserves: {token}")

        quote_token = launch["quote_token"].lower()
        supply_raw = launch.get("supply_raw")
        token_decimals = launch.get("token_decimals")
        if supply_raw is None or token_decimals is None:
            raise ValueError(
                f"trench.today registry lacks launch supply state: {token}"
            )
        supply_raw = int(supply_raw)
        token_decimals = int(token_decimals)
        decimals = (
            None
            if quote_decimals is None
            else quote_decimals.get(quote_token)
        )
        if decimals is None:
            raw_decimals = launch.get("quote_decimals")
            if raw_decimals is None:
                raise KeyError(
                    f"missing trench.today quote decimals: {quote_token}"
                )
            decimals = int(raw_decimals)
        decimals = int(decimals)
        if decimals < 0 or decimals > 255:
            raise ValueError(
                f"invalid trench.today quote decimals: {quote_token}"
            )

        raw_quote_per_raw_token = (
            Decimal(event.virtual_quote_raw)
            / Decimal(event.virtual_token_raw)
        )
        quote_per_token = (
            raw_quote_per_raw_token
            * (Decimal(10) ** token_decimals)
            / (Decimal(10) ** decimals)
        )
        market_cap_quote = (
            raw_quote_per_raw_token
            * Decimal(supply_raw)
            / (Decimal(10) ** decimals)
        )
        quote_usd = timeline.price(quote_token)
        pricing_status = timeline.pricing_status(quote_token)
        token_price_usd = (
            None if quote_usd is None else quote_per_token * quote_usd
        )
        market_cap = (
            None
            if quote_usd is None
            else market_cap_quote * quote_usd
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
            "supply_raw": supply_raw,
            "token_decimals": token_decimals,
            "quote_decimals": decimals,
            "raw_quote_per_raw_token": str(raw_quote_per_raw_token),
            "quote_per_token": str(quote_per_token),
            "market_cap_quote": str(market_cap_quote),
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
