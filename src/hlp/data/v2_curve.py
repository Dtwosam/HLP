"""Pons V2 bonding-curve event tape and exact reserve replay."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.reconstruct import event_order
from hlp.price import constant_product_spot_quote_per_token, human_amount


ZERO_ADDRESS = "0x" + "00" * 20


def _launch_order(row: dict) -> tuple[int, int, int]:
    return event_order(row)


def _quote_usd_status(pair_token: str, active_weth_usd: Decimal):
    pair = pair_token.lower()
    if pair in {ZERO_ADDRESS, ROBINHOOD_WETH.lower()}:
        return "priced_native_or_weth", active_weth_usd
    if pair == ROBINHOOD_USDG.lower():
        return "priced_usdg_nominal", Decimal(1)
    return "unsupported_quote", None


def build_v2_curve_market_cap_points(
    registry_rows: Iterable[dict],
    curve_event_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
) -> Iterator[dict]:
    """Replay every V2 curve from launch using only observable event deltas.

    Reserve transitions mirror PonsV2BondingCurve:
    - buy: quote += quoteIn - fee - tax; token -= tokensOut
    - sell: quote -= quoteOut + fee + tax; token += tokensIn
    - BuybackLocked: quote += quoteSpent; token -= tokensLocked

    Fee sweeps without a buyback do not move getReserves(), so they require no
    price event. Graduation is handled separately by the V4 phase.
    """
    if initial_weth_usd <= 0:
        raise ValueError("initial_weth_usd must be positive")

    registry_list = sorted(list(registry_rows), key=_launch_order)
    launches = iter(registry_list)
    events = iter(curve_event_rows)
    anchors = iter(weth_usd_anchor_points)
    next_launch = next(launches, None)
    next_event = next(events, None)
    next_anchor = next(anchors, None)
    active_weth_usd = initial_weth_usd
    states: dict[str, dict[str, int]] = {}

    def advance_anchor(order):
        nonlocal next_anchor, active_weth_usd
        while next_anchor is not None and event_order(next_anchor) <= order:
            active_weth_usd = Decimal(next_anchor["quote_per_token"])
            next_anchor = next(anchors, None)

    def price_row(base: dict, launch: dict, *, event_type: str):
        curve_address = launch["curve"].lower()
        state = states[curve_address]
        quote_per_token = constant_product_spot_quote_per_token(
            quote_reserve_raw=state["quote_reserve_raw"],
            token_reserve_raw=state["token_reserve_raw"],
            quote_decimals=int(launch["quote_decimals"]),
            token_decimals=int(launch["token_decimals"]),
        )
        pricing_status, quote_usd = _quote_usd_status(
            launch["pair_token"],
            active_weth_usd,
        )
        out = dict(base)
        out.update(
            {
                "phase": "curve",
                "event_type": event_type,
                "token": launch["token"].lower(),
                "curve": curve_address,
                "quote_token": launch["pair_token"].lower(),
                "launch_block": int(launch["block_number"]),
                "quote_reserve_raw": state["quote_reserve_raw"],
                "token_reserve_raw": state["token_reserve_raw"],
                "quote_per_token": str(quote_per_token),
                "pricing_status": pricing_status,
                "quote_usd": None if quote_usd is None else str(quote_usd),
                "token_price_usd": None,
                "market_cap_proxy_usd": None,
            }
        )
        if quote_usd is not None:
            token_price_usd = quote_per_token * quote_usd
            supply = human_amount(
                int(launch["supply_raw"]),
                int(launch["token_decimals"]),
            )
            out["token_price_usd"] = str(token_price_usd)
            out["market_cap_proxy_usd"] = str(token_price_usd * supply)
        return out

    registry_by_curve = {
        row["curve"].lower(): row
        for row in registry_list
    }

    # Merge launch initialization and reserve-changing events in exact order.
    # Anchor events are advanced immediately before each emitted point.
    while next_launch is not None or next_event is not None:
        launch_order = _launch_order(next_launch) if next_launch is not None else None
        event_ord = event_order(next_event) if next_event is not None else None

        if next_launch is not None and (
            next_event is None or launch_order <= event_ord
        ):
            launch = next_launch
            order = launch_order
            advance_anchor(order)
            curve_address = launch["curve"].lower()
            if curve_address in states:
                raise ValueError(f"duplicate V2 curve launch: {curve_address}")
            states[curve_address] = {
                "quote_reserve_raw": int(launch["phantom_quote"]),
                "token_reserve_raw": int(launch["supply_raw"]),
            }
            base = {
                "block_number": int(launch["block_number"]),
                "transaction_hash": launch["transaction_hash"],
                "transaction_index": launch.get("transaction_index"),
                "log_index": int(launch["log_index"]),
            }
            yield price_row(base, launch, event_type="curve_initialized")
            next_launch = next(launches, None)
            continue

        event = next_event
        order = event_ord
        advance_anchor(order)
        curve_address = event["curve"].lower()
        launch = registry_by_curve.get(curve_address)
        state = states.get(curve_address)
        if launch is None:
            raise KeyError(f"curve event is absent from V2 registry: {curve_address}")
        if state is None:
            raise ValueError(
                f"curve event precedes initialization in supplied history: {curve_address}"
            )

        kind = event["event_type"]
        if kind == "curve_buy":
            net_quote = (
                int(event["quote_amount"])
                - int(event["fee"])
                - int(event["tax"])
            )
            if net_quote < 0:
                raise ValueError("curve buy fees exceed quote input")
            state["quote_reserve_raw"] += net_quote
            state["token_reserve_raw"] -= int(event["token_amount"])
        elif kind == "curve_sell":
            gross_quote = (
                int(event["quote_amount"])
                + int(event["fee"])
                + int(event["tax"])
            )
            state["quote_reserve_raw"] -= gross_quote
            state["token_reserve_raw"] += int(event["token_amount"])
        elif kind == "curve_buyback":
            state["quote_reserve_raw"] += int(event["quote_spent"])
            state["token_reserve_raw"] -= int(event["tokens_locked"])
        else:
            raise ValueError(f"unknown V2 curve event type: {kind}")

        if state["quote_reserve_raw"] <= 0 or state["token_reserve_raw"] <= 0:
            raise ValueError(
                f"invalid replayed V2 reserves for {curve_address}: {state}"
            )
        yield price_row(event, launch, event_type=kind)
        next_event = next(events, None)
