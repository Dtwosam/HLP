"""Candidate market-quality metrics for Phase-2 multi-pool research.

These helpers do not freeze the canonical market-selection rule. They provide a
causal, comparable active-liquidity measure that Phase 2 can evaluate before a
versioned selection policy is adopted.
"""

from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Iterable, Mapping


Q96 = Decimal(1 << 96)


def active_quote_liquidity_usd(
    *,
    sqrt_price_x96: int,
    liquidity_raw: int,
    token_is_currency0: bool,
    quote_decimals: int,
    quote_usd: Decimal | str,
) -> Decimal:
    """Estimate active one-sided quote liquidity at the current V3/V4 tick.

    For concentrated-liquidity AMMs, active virtual reserves are approximately
    x=L/sqrt(P) and y=L*sqrt(P). The quote-side reserve is converted to human
    quote units and then point-in-time USD. This is a quality/audit metric, not
    a claim about withdrawable TVL outside the active tick.
    """
    getcontext().prec = max(getcontext().prec, 80)
    sqrt_raw = int(sqrt_price_x96)
    liquidity = int(liquidity_raw)
    decimals = int(quote_decimals)
    price = Decimal(str(quote_usd))

    if sqrt_raw <= 0:
        raise ValueError("sqrt_price_x96 must be positive")
    if liquidity < 0:
        raise ValueError("liquidity_raw cannot be negative")
    if decimals < 0 or decimals > 255:
        raise ValueError("quote_decimals must be between 0 and 255")
    if price <= 0:
        raise ValueError("quote_usd must be positive")

    sqrt_p = Decimal(sqrt_raw) / Q96
    if token_is_currency0:
        quote_raw = Decimal(liquidity) * sqrt_p
    else:
        quote_raw = Decimal(liquidity) / sqrt_p

    quote_human = quote_raw / (Decimal(10) ** decimals)
    return quote_human * price


def rank_market_quality_snapshot(
    rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Rank same-token market states by active quote USD liquidity.

    The caller is responsible for supplying states from one causal comparison
    timestamp. Ties are broken only by stable market_id so output is fully
    deterministic.
    """
    data = [dict(row) for row in rows]
    if not data:
        return []

    tokens = {str(row.get("token") or "").lower() for row in data}
    if len(tokens) != 1 or "" in tokens:
        raise ValueError(
            "market-quality snapshot must contain exactly one token"
        )

    seen_markets: set[str] = set()
    normalized: list[dict] = []
    for row in data:
        market_id = str(row.get("market_id") or "").lower()
        if not market_id:
            raise ValueError("market-quality row has no market_id")
        if market_id in seen_markets:
            raise ValueError(
                f"market-quality snapshot repeats market: {market_id}"
            )
        seen_markets.add(market_id)

        value = row.get("active_quote_liquidity_usd")
        if value is None:
            raise ValueError(
                f"market-quality row has no liquidity metric: {market_id}"
            )
        liquidity = Decimal(str(value))
        if liquidity < 0:
            raise ValueError(
                f"market-quality row has negative liquidity: {market_id}"
            )

        item = dict(row)
        item["market_id"] = market_id
        item["active_quote_liquidity_usd"] = str(liquidity)
        normalized.append(item)

    normalized.sort(
        key=lambda row: (
            -Decimal(row["active_quote_liquidity_usd"]),
            row["market_id"],
        )
    )
    for index, row in enumerate(normalized, start=1):
        row["market_quality_rank"] = index
        row["market_quality_candidate"] = index == 1
    return normalized


def summarize_market_competition(
    rows: Iterable[Mapping[str, object]],
) -> dict:
    """Count how often tokens have multiple candidate markets."""
    markets_by_token: dict[str, set[str]] = {}
    for row in rows:
        token = str(row.get("token") or "").lower()
        market_id = str(row.get("market_id") or "").lower()
        if not token or not market_id:
            raise ValueError("market competition row lacks token/market_id")
        markets_by_token.setdefault(token, set()).add(market_id)

    counts = {
        token: len(markets)
        for token, markets in markets_by_token.items()
    }
    multi = {
        token: count
        for token, count in counts.items()
        if count > 1
    }
    return {
        "tokens": len(counts),
        "markets": sum(counts.values()),
        "multi_market_tokens": len(multi),
        "max_markets_per_token": max(counts.values(), default=0),
        "multi_market_counts": dict(sorted(multi.items())),
        "selection_rule_frozen": False,
    }
