"""pools.trade CCA price-path helpers.

CCA event decoding is already evidence-backed. Price orientation is kept
explicit until migration evidence freezes which Q96 direction represents
quote-per-token.
"""

from __future__ import annotations

from decimal import Decimal, getcontext, localcontext
from typing import Iterable

from hlp.data.direct_supply import DirectSupplyTimeline
from hlp.data.quote_usd import QuoteUsdTimeline
from hlp.data.types import CcaPriceEvent


CCA_DECIMAL_PRECISION = 80
getcontext().prec = max(getcontext().prec, CCA_DECIMAL_PRECISION)
Q96 = Decimal(2) ** 96
CCA_ORIENTATIONS = frozenset({"quote_per_token", "token_per_quote"})


def cca_price_candidates(clearing_price_x96: int) -> dict[str, Decimal]:
    """Return quote-per-token under both possible Q96 interpretations."""
    raw = int(clearing_price_x96)
    if raw <= 0:
        raise ValueError("CCA clearing_price_x96 must be positive")
    value = Decimal(raw)
    with localcontext() as context:
        context.prec = CCA_DECIMAL_PRECISION
        return {
            "quote_per_token": value / Q96,
            "token_per_quote": Q96 / value,
        }


def cca_quote_per_token(
    clearing_price_x96: int,
    *,
    orientation: str,
) -> Decimal:
    """Return quote-per-token only for an explicitly frozen orientation."""
    orientation = str(orientation)
    if orientation not in CCA_ORIENTATIONS:
        raise ValueError(f"invalid CCA price orientation: {orientation!r}")
    candidates = cca_price_candidates(clearing_price_x96)
    return candidates[orientation]


def infer_cca_price_orientation(
    clearing_price_x96: int,
    *,
    migrated_quote_per_token: Decimal | str,
) -> dict:
    """Compare both CCA orientations with an observed migrated-market price."""
    migrated = Decimal(str(migrated_quote_per_token))
    if migrated <= 0:
        raise ValueError("migrated quote-per-token must be positive")

    candidates = cca_price_candidates(clearing_price_x96)
    direct_quote = candidates["quote_per_token"]
    inverse_quote = candidates["token_per_quote"]
    with localcontext() as context:
        context.prec = CCA_DECIMAL_PRECISION
        direct_error = abs(direct_quote / migrated - Decimal(1))
        inverse_error = abs(inverse_quote / migrated - Decimal(1))

    if direct_error == inverse_error:
        raise ValueError("CCA price orientation is ambiguous")
    orientation = (
        "quote_per_token"
        if direct_error < inverse_error
        else "token_per_quote"
    )
    return {
        "orientation": orientation,
        "direct_quote_per_token": direct_quote,
        "inverse_quote_per_token": inverse_quote,
        "direct_relative_error": direct_error,
        "inverse_relative_error": inverse_error,
        "best_relative_error": min(direct_error, inverse_error),
    }


def build_cca_quote_price_points(
    events: Iterable[CcaPriceEvent],
    *,
    orientation: str,
) -> list[dict]:
    """Build a deterministic CCA quote-price event tape."""
    if orientation not in CCA_ORIENTATIONS:
        raise ValueError(f"invalid CCA price orientation: {orientation!r}")

    ordered = sorted(
        list(events),
        key=lambda row: (
            int(row.block_number),
            -1 if row.transaction_index is None else int(row.transaction_index),
            int(row.log_index),
        ),
    )
    output: list[dict] = []
    previous_order: tuple[int, int, int] | None = None
    for row in ordered:
        order = (
            int(row.block_number),
            -1 if row.transaction_index is None else int(row.transaction_index),
            int(row.log_index),
        )
        if previous_order == order:
            raise ValueError(f"duplicate CCA price event order: {order}")
        previous_order = order
        price = cca_quote_per_token(
            row.clearing_price_x96,
            orientation=orientation,
        )
        if price <= 0:
            raise ValueError("CCA quote-per-token must be positive")
        output.append(
            {
                "auction": row.auction.lower(),
                "event_type": row.event_type,
                "checkpoint_block": int(row.checkpoint_block),
                "clearing_price_x96": int(row.clearing_price_x96),
                "cumulative_mps": row.cumulative_mps,
                "quote_per_token": str(price),
                "orientation": orientation,
                "block_number": int(row.block_number),
                "transaction_hash": row.transaction_hash.lower(),
                "transaction_index": row.transaction_index,
                "log_index": int(row.log_index),
            }
        )
    return output



def build_cca_market_cap_points(
    registry_rows: Iterable[dict],
    events: Iterable[CcaPriceEvent],
    weth_usd_anchor_points: Iterable[dict],
    *,
    orientation: str,
    initial_weth_usd: Decimal,
    quote_decimals: dict[str, int],
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
    supply_delta_rows: Iterable[dict] | None = None,
) -> list[dict]:
    """Build causal pools.trade CCA market-cap points.

    The CCA Q96 value is treated as a raw-unit quote/token ratio, matching the
    raw-unit market-cap formulation used by V3/V4 reconstructors:

        raw_quote_per_raw_token * supply_raw / 10**quote_decimals

    Orientation must already be frozen by independent migration evidence.
    """
    if orientation not in CCA_ORIENTATIONS:
        raise ValueError(f"invalid CCA price orientation: {orientation!r}")

    registry: dict[str, dict] = {}
    for raw in registry_rows:
        row = dict(raw)
        initializer = str(row.get("initializer") or "").lower()
        if not initializer:
            raise ValueError("CCA registry row has no initializer")
        if initializer in registry:
            raise ValueError(
                f"duplicate CCA registry initializer: {initializer}"
            )
        supply_raw = int(row.get("supply_raw", 0))
        if supply_raw <= 0:
            raise ValueError(
                f"CCA registry has non-positive supply: {initializer}"
            )
        quote = str(row.get("quote_token") or "").lower()
        token = str(row.get("token") or "").lower()
        if not quote or not token:
            raise ValueError(
                f"CCA registry row lacks token/quote: {initializer}"
            )
        registry[initializer] = row

    timeline = QuoteUsdTimeline(
        initial_weth_usd=initial_weth_usd,
        weth_anchor_points=weth_usd_anchor_points,
        initial_quote_usd=initial_quote_usd,
        oracle_updates=quote_usd_updates,
    )
    supply_timeline = (
        None
        if supply_delta_rows is None
        else DirectSupplyTimeline(
            registry.values(),
            supply_delta_rows,
            seed_order="initializer",
        )
    )

    ordered = sorted(
        list(events),
        key=lambda row: (
            int(row.block_number),
            -1 if row.transaction_index is None
            else int(row.transaction_index),
            int(row.log_index),
        ),
    )
    output: list[dict] = []
    previous_order: tuple[int, int, int] | None = None
    for event in ordered:
        order = (
            int(event.block_number),
            -1 if event.transaction_index is None
            else int(event.transaction_index),
            int(event.log_index),
        )
        if previous_order == order:
            raise ValueError(f"duplicate CCA price event order: {order}")
        previous_order = order

        initializer = event.auction.lower()
        launch = registry.get(initializer)
        if launch is None:
            raise ValueError(
                "CCA price event missing launch registry row: "
                f"{initializer}"
            )

        timeline.advance_to(order)
        quote = str(launch["quote_token"]).lower()
        decimals = quote_decimals.get(quote)
        if decimals is None:
            raise KeyError(
                f"missing quote decimals for CCA quote {quote}"
            )
        decimals = int(decimals)
        if decimals < 0 or decimals > 255:
            raise ValueError(
                f"invalid quote decimals for CCA quote {quote}: {decimals}"
            )

        supply_raw = (
            int(launch["supply_raw"])
            if supply_timeline is None
            else supply_timeline.supply_at(
                token,
                order,
            )
        )
        raw_quote_per_raw_token = cca_quote_per_token(
            event.clearing_price_x96,
            orientation=orientation,
        )
        market_cap_quote = (
            raw_quote_per_raw_token
            * Decimal(supply_raw)
            / (Decimal(10) ** decimals)
        )
        quote_usd = timeline.price(quote)
        pricing_status = timeline.pricing_status(quote)
        market_cap_usd = (
            None
            if quote_usd is None
            else market_cap_quote * quote_usd
        )

        output.append({
            "venue": "pools.trade",
            "phase": "cca",
            "event_type": event.event_type,
            "token": str(launch["token"]).lower(),
            "initializer": initializer,
            "quote_token": quote,
            "quote_decimals": decimals,
            "supply_raw": supply_raw,
            "orientation": orientation,
            "checkpoint_block": int(event.checkpoint_block),
            "clearing_price_x96": int(event.clearing_price_x96),
            "cumulative_mps": event.cumulative_mps,
            "block_number": int(event.block_number),
            "transaction_hash": event.transaction_hash.lower(),
            "transaction_index": event.transaction_index,
            "log_index": int(event.log_index),
            "raw_quote_per_raw_token": str(
                raw_quote_per_raw_token
            ),
            "market_cap_quote": str(market_cap_quote),
            "pricing_status": pricing_status,
            "quote_usd": (
                None if quote_usd is None else str(quote_usd)
            ),
            "market_cap_proxy_usd": (
                None
                if market_cap_usd is None
                else str(market_cap_usd)
            ),
        })
    return output


def summarize_cca_market_caps(
    rows: Iterable[dict],
) -> list[dict]:
    """Summarize CCA eligibility evidence without hiding unpriced points."""
    summary: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        token = str(row["token"]).lower()
        value = row.get("market_cap_proxy_usd")
        market_cap = (
            None if value is None else Decimal(str(value))
        )
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": "pools.trade",
                "phase": "cca",
                "initializer": row["initializer"],
                "quote_token": row["quote_token"],
                "orientation": row["orientation"],
                "price_points": 0,
                "priced_points": 0,
                "pricing_statuses": set(),
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            summary[token] = current
        if current["initializer"] != row["initializer"]:
            raise ValueError(
                f"CCA token appears under multiple initializers: {token}"
            )
        if current["orientation"] != row["orientation"]:
            raise ValueError(
                f"CCA token mixes price orientations: {token}"
            )

        current["price_points"] += 1
        current["pricing_statuses"].add(
            str(row.get("pricing_status") or "")
        )
        if market_cap is None:
            continue
        current["priced_points"] += 1
        prior = current["max_market_cap_proxy_usd"]
        if prior is None or market_cap > prior:
            current["max_market_cap_proxy_usd"] = market_cap
            current["max_market_cap_block"] = int(
                row["block_number"]
            )
        if market_cap >= Decimal("100000"):
            current["crossed_100k"] = True

    output: list[dict] = []
    for current in summary.values():
        row = dict(current)
        row["pricing_statuses"] = sorted(
            status for status in row["pricing_statuses"] if status
        )
        if row["max_market_cap_proxy_usd"] is not None:
            row["max_market_cap_proxy_usd"] = str(
                row["max_market_cap_proxy_usd"]
            )
        output.append(row)
    output.sort(key=lambda row: row["token"])
    return output

def merge_cca_market_cap_summaries(
    rows: Iterable[dict],
) -> list[dict]:
    """Merge deterministic per-window CCA token summaries."""
    merged: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        token = str(row.get("token") or "").lower()
        if not token:
            raise ValueError("CCA summary row has no token")
        initializer = str(row.get("initializer") or "").lower()
        quote = str(row.get("quote_token") or "").lower()
        orientation = str(row.get("orientation") or "")
        points = int(row.get("price_points", 0))
        priced = int(row.get("priced_points", 0))
        if points < 0 or priced < 0 or priced > points:
            raise ValueError(
                f"invalid CCA summary point counts: {token}"
            )

        current = merged.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": "pools.trade",
                "phase": "cca",
                "initializer": initializer,
                "quote_token": quote,
                "orientation": orientation,
                "price_points": 0,
                "priced_points": 0,
                "pricing_statuses": set(),
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            merged[token] = current
        elif (
            current["initializer"] != initializer
            or current["quote_token"] != quote
            or current["orientation"] != orientation
        ):
            raise ValueError(
                f"CCA summary identity drift across windows: {token}"
            )

        current["price_points"] += points
        current["priced_points"] += priced
        current["pricing_statuses"].update(
            str(status)
            for status in row.get("pricing_statuses", [])
            if str(status)
        )
        current["crossed_100k"] = (
            current["crossed_100k"]
            or bool(row.get("crossed_100k", False))
        )

        raw_max = row.get("max_market_cap_proxy_usd")
        if raw_max is None:
            if priced > 0:
                raise ValueError(
                    f"priced CCA summary row has no maximum: {token}"
                )
            continue
        value = Decimal(str(raw_max))
        block = row.get("max_market_cap_block")
        if value < 0 or block is None:
            raise ValueError(
                f"invalid CCA summary maximum: {token}"
            )
        block = int(block)
        prior = current["max_market_cap_proxy_usd"]
        prior_block = current["max_market_cap_block"]
        if (
            prior is None
            or value > prior
            or (value == prior and block < int(prior_block))
        ):
            current["max_market_cap_proxy_usd"] = value
            current["max_market_cap_block"] = block

    output = []
    for current in merged.values():
        row = dict(current)
        row["pricing_statuses"] = sorted(row["pricing_statuses"])
        maximum = row["max_market_cap_proxy_usd"]
        if maximum is not None:
            row["max_market_cap_proxy_usd"] = str(maximum)
        if row["crossed_100k"] and (
            maximum is None or maximum < Decimal("100000")
        ):
            raise ValueError(
                "CCA threshold flag contradicts merged maximum: "
                f"{row['token']}"
            )
        output.append(row)
    output.sort(key=lambda row: row["token"])
    return output

