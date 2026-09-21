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



def _market_event_order(
    row: Mapping[str, object],
) -> tuple[int, int, int, str]:
    block = int(row["block_number"])
    tx_raw = row.get("transaction_index")
    tx = -1 if tx_raw is None else int(tx_raw)
    log_index = int(row["log_index"])
    market_id = str(row.get("market_id") or "").lower()
    if block < 0 or tx < -1 or log_index < 0 or not market_id:
        raise ValueError("invalid market-quality event order")
    return block, tx, log_index, market_id


def build_causal_market_quality_trace(
    rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Build event-time multi-market comparison snapshots without look-ahead.

    A market enters the comparison only after a row has both a priced market
    cap and an active quote-liquidity metric. At each subsequent event, the
    latest already-observed state of every market for that token is compared.
    The deepest market is retained as a research candidate only; this function
    does not freeze the production canonical selector.
    """
    ordered = [dict(row) for row in rows]
    ordered.sort(key=_market_event_order)

    latest: dict[str, dict[str, dict]] = {}
    seen_events: set[tuple[str, tuple[int, int, int, str]]] = set()
    output: list[dict] = []

    for row in ordered:
        token = str(row.get("token") or "").lower()
        market_id = str(row.get("market_id") or "").lower()
        if not token or not market_id:
            raise ValueError("market-quality event lacks token/market_id")
        order = _market_event_order(row)
        event_key = (token, order)
        if event_key in seen_events:
            raise ValueError(
                f"duplicate market-quality event: {token} {order}"
            )
        seen_events.add(event_key)

        raw_depth = row.get("active_quote_liquidity_usd")
        raw_mcap = row.get("market_cap_proxy_usd")
        if raw_depth is not None and raw_mcap is not None:
            depth = Decimal(str(raw_depth))
            mcap = Decimal(str(raw_mcap))
            if depth < 0:
                raise ValueError(
                    f"negative active quote liquidity: {market_id}"
                )
            if mcap < 0:
                raise ValueError(
                    f"negative market cap proxy: {market_id}"
                )
            state = dict(row)
            state["token"] = token
            state["market_id"] = market_id
            state["active_quote_liquidity_usd"] = str(depth)
            state["market_cap_proxy_usd"] = str(mcap)
            latest.setdefault(token, {})[market_id] = state

        current = list(latest.get(token, {}).values())
        if not current:
            continue
        ranked = rank_market_quality_snapshot(current)
        candidate = ranked[0]
        caps = [
            Decimal(item["market_cap_proxy_usd"])
            for item in ranked
        ]
        min_cap = min(caps)
        max_cap = max(caps)
        dispersion_multiple = (
            None
            if min_cap <= 0
            else max_cap / min_cap
        )

        output.append(
            {
                "token": token,
                "event_market_id": market_id,
                "block_number": order[0],
                "transaction_index": (
                    None if order[1] == -1 else order[1]
                ),
                "log_index": order[2],
                "observed_markets": len(ranked),
                "candidate_market_id": candidate["market_id"],
                "candidate_market_cap_proxy_usd": (
                    candidate["market_cap_proxy_usd"]
                ),
                "candidate_active_quote_liquidity_usd": (
                    candidate["active_quote_liquidity_usd"]
                ),
                "min_observed_market_cap_proxy_usd": str(min_cap),
                "max_observed_market_cap_proxy_usd": str(max_cap),
                "market_cap_dispersion_multiple": (
                    None
                    if dispersion_multiple is None
                    else str(dispersion_multiple)
                ),
                "ranked_market_ids": [
                    item["market_id"] for item in ranked
                ],
                "selection_rule_frozen": False,
            }
        )

    return output
