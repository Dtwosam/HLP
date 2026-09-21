"""Generic direct-V4 launchpad market-cap reconstruction."""

from __future__ import annotations

from decimal import Decimal, getcontext
from typing import Iterable

from hlp.data.direct_supply import DirectSupplyTimeline
from hlp.data.market_quality import active_quote_liquidity_usd
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
    ratio1_per_0 = (
        Decimal(sqrt_price_x96) ** 2 / Decimal(Q192)
    )
    return ratio1_per_0 if token_is_currency0 else Decimal(1) / ratio1_per_0


def build_v4_launchpad_market_cap_points(
    registry_rows: Iterable[dict],
    initialize_rows: Iterable[dict],
    swap_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
    quote_decimals: dict[str, int],
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
    allow_registry_initialization: bool = False,
    supply_delta_rows: Iterable[dict] | None = None,
    supply_seed_order: str = "initialize",
) -> list[dict]:
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
    supply_timeline = (
        None
        if supply_delta_rows is None
        else DirectSupplyTimeline(
            registry.values(),
            supply_delta_rows,
            seed_order=supply_seed_order,
        )
    )
    events = []
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
        timeline.advance_to(event_order(event))
        pool_id = event["pool_id"].lower()
        launch = registry[pool_id]
        token = launch["token"].lower()
        quote = launch["quote_token"].lower()
        supply_raw = (
            int(launch["supply_raw"])
            if supply_timeline is None
            else supply_timeline.supply_at(
                token,
                event_order(event),
            )
        )
        decimals = quote_decimals.get(quote)
        if decimals is None:
            raise KeyError(f"missing quote decimals for V4 quote {quote}")

        if event["_kind"] == "v4_initialize":
            initialized.add(pool_id)
        elif pool_id not in initialized:
            if not allow_registry_initialization:
                raise ValueError(f"V4 swap precedes Initialize: {pool_id}")
            raw_block = launch.get("initialize_block")
            raw_log = launch.get("initialize_log_index")
            if raw_block is None or raw_log is None:
                raise ValueError(
                    f"V4 registry lacks Initialize order: {pool_id}"
                )
            raw_tx = launch.get("initialize_transaction_index")
            initialize_order = (
                int(raw_block),
                -1 if raw_tx is None else int(raw_tx),
                int(raw_log),
            )
            if event_order(event) <= initialize_order:
                raise ValueError(
                    f"V4 swap does not follow recorded Initialize: {pool_id}"
                )
            initialized.add(pool_id)

        c0 = launch["currency0"].lower()
        c1 = launch["currency1"].lower()
        if {c0, c1} != {token, quote}:
            raise ValueError(f"V4 registry PoolKey disagrees with token/quote: {pool_id}")
        raw_quote_per_raw_token = _raw_quote_per_raw_token(
            int(event["sqrt_price_x96"]),
            token_is_currency0=(c0 == token),
        )
        market_cap_quote = (
            raw_quote_per_raw_token
            * Decimal(supply_raw)
            / (Decimal(10) ** decimals)
        )
        quote_usd = timeline.price(quote)
        status = timeline.pricing_status(quote)
        market_cap_usd = (
            None if quote_usd is None else market_cap_quote * quote_usd
        )
        liquidity_raw = event.get("liquidity")
        active_liquidity_usd = (
            None
            if quote_usd is None or liquidity_raw is None
            else active_quote_liquidity_usd(
                sqrt_price_x96=int(event["sqrt_price_x96"]),
                liquidity_raw=int(liquidity_raw),
                token_is_currency0=(c0 == token),
                quote_decimals=decimals,
                quote_usd=quote_usd,
            )
        )
        output.append({
            "venue": launch["venue"],
            "phase": "v4",
            "event_type": event["_kind"],
            "token": token,
            "pool_id": pool_id,
            "market_id": pool_id,
            "quote_token": quote,
            "quote_decimals": decimals,
            "token_is_currency0": c0 == token,
            "supply_raw": supply_raw,
            "block_number": int(event["block_number"]),
            "transaction_hash": event["transaction_hash"],
            "transaction_index": event.get("transaction_index"),
            "log_index": int(event["log_index"]),
            "sqrt_price_x96": int(event["sqrt_price_x96"]),
            "liquidity_raw": (
                None if liquidity_raw is None else int(liquidity_raw)
            ),
            "active_quote_liquidity_usd": (
                None
                if active_liquidity_usd is None
                else str(active_liquidity_usd)
            ),
            "raw_quote_per_raw_token": str(raw_quote_per_raw_token),
            "market_cap_quote": str(market_cap_quote),
            "pricing_status": status,
            "quote_usd": None if quote_usd is None else str(quote_usd),
            "market_cap_proxy_usd": (
                None if market_cap_usd is None else str(market_cap_usd)
            ),
        })
    return output


def summarize_v4_launchpad_market_caps(rows: Iterable[dict]) -> list[dict]:
    summary: dict[str, dict] = {}
    for row in rows:
        token = row["token"]
        value = row.get("market_cap_proxy_usd")
        mcap = Decimal(value) if value is not None else None
        current = summary.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": row["venue"],
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

    out = []
    for row in summary.values():
        item = dict(row)
        if item["max_market_cap_proxy_usd"] is not None:
            item["max_market_cap_proxy_usd"] = str(item["max_market_cap_proxy_usd"])
        out.append(item)
    out.sort(key=lambda row: row["token"])
    return out


def merge_v4_launchpad_market_cap_summaries(
    rows: Iterable[dict],
) -> list[dict]:
    """Merge deterministic per-window V4 token summaries."""
    merged: dict[str, dict] = {}
    for raw in rows:
        row = dict(raw)
        token = str(row["token"]).lower()
        identity = (
            str(row["venue"]),
            str(row["pool_id"]).lower(),
            str(row["quote_token"]).lower(),
        )
        current = merged.get(token)
        if current is None:
            current = {
                "token": token,
                "venue": identity[0],
                "pool_id": identity[1],
                "quote_token": identity[2],
                "price_points": 0,
                "priced_points": 0,
                "max_market_cap_proxy_usd": None,
                "max_market_cap_block": None,
                "crossed_100k": False,
            }
            merged[token] = current
        elif (
            current["venue"],
            current["pool_id"],
            current["quote_token"],
        ) != identity:
            raise ValueError(
                f"V4 summary identity drift for token {token}"
            )

        current["price_points"] += int(row["price_points"])
        current["priced_points"] += int(row["priced_points"])
        current["crossed_100k"] = (
            bool(current["crossed_100k"])
            or bool(row["crossed_100k"])
        )

        raw_max = row.get("max_market_cap_proxy_usd")
        if raw_max is None:
            continue
        value = Decimal(str(raw_max))
        block = int(row["max_market_cap_block"])
        prior_raw = current["max_market_cap_proxy_usd"]
        prior_block = current["max_market_cap_block"]
        if (
            prior_raw is None
            or value > Decimal(str(prior_raw))
            or (
                value == Decimal(str(prior_raw))
                and (
                    prior_block is None
                    or block < int(prior_block)
                )
            )
        ):
            current["max_market_cap_proxy_usd"] = str(value)
            current["max_market_cap_block"] = block

    output = list(merged.values())
    output.sort(key=lambda row: row["token"])
    return output

