"""Pons V2 graduation and Uniswap V4 market-cap reconstruction."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.reconstruct import event_order
from hlp.price import human_amount, v3_v4_quote_per_token


ZERO_ADDRESS = "0x" + "00" * 20


def _quote_usd(pair_token: str, active_weth_usd: Decimal):
    pair = pair_token.lower()
    if pair in {ZERO_ADDRESS, ROBINHOOD_WETH.lower()}:
        return "priced_native_or_weth", active_weth_usd
    if pair == ROBINHOOD_USDG.lower():
        return "priced_usdg_nominal", Decimal(1)
    return "unsupported_quote", None


def _attach_usd(
    row: dict,
    launch: dict,
    quote_per_token: Decimal,
    active_weth_usd: Decimal,
) -> dict:
    status, quote_usd = _quote_usd(launch["pair_token"], active_weth_usd)
    out = dict(row)
    out.update(
        {
            "token": launch["token"].lower(),
            "curve": launch["curve"].lower(),
            "quote_token": launch["pair_token"].lower(),
            "launch_block": int(launch["block_number"]),
            "quote_per_token": str(quote_per_token),
            "pricing_status": status,
            "quote_usd": None if quote_usd is None else str(quote_usd),
            "token_price_usd": None,
            "market_cap_proxy_usd": None,
        }
    )
    if quote_usd is not None:
        price_usd = quote_per_token * quote_usd
        supply = human_amount(
            int(launch["supply_raw"]),
            int(launch["token_decimals"]),
        )
        out["token_price_usd"] = str(price_usd)
        out["market_cap_proxy_usd"] = str(price_usd * supply)
    return out


def build_v2_graduation_seed_points(
    registry_rows: Iterable[dict],
    graduation_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
) -> Iterator[dict]:
    """Price the exact V4 seed ratio emitted by PoolGraduated."""
    registry = {row["token"].lower(): row for row in registry_rows}
    anchors = iter(weth_usd_anchor_points)
    next_anchor = next(anchors, None)
    active_weth_usd = initial_weth_usd

    for graduation in graduation_rows:
        order = event_order(graduation)
        while next_anchor is not None and event_order(next_anchor) <= order:
            active_weth_usd = Decimal(next_anchor["quote_per_token"])
            next_anchor = next(anchors, None)

        token = graduation["token"].lower()
        launch = registry.get(token)
        if launch is None:
            raise KeyError(f"graduated token is absent from V2 registry: {token}")
        token_amount = human_amount(
            int(graduation["token_amount"]),
            int(launch["token_decimals"]),
        )
        quote_amount = human_amount(
            int(graduation["pair_token_amount"]),
            int(launch["quote_decimals"]),
        )
        if token_amount <= 0 or quote_amount <= 0:
            raise ValueError(f"invalid graduation seed amounts for {token}")
        quote_per_token = quote_amount / token_amount
        base = dict(graduation)
        base["phase"] = "v4_seed"
        base["event_type"] = "pool_graduated"
        yield _attach_usd(base, launch, quote_per_token, active_weth_usd)


def build_v2_v4_market_cap_points(
    registry_rows: Iterable[dict],
    registration_rows: Iterable[dict],
    swap_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    initial_weth_usd: Decimal,
) -> Iterator[dict]:
    """Price post-graduation V4 swaps through the Pons pool-id registry."""
    registry = {row["token"].lower(): row for row in registry_rows}
    registrations = {row["pool_id"].lower(): row for row in registration_rows}
    anchors = iter(weth_usd_anchor_points)
    next_anchor = next(anchors, None)
    active_weth_usd = initial_weth_usd

    for swap in swap_rows:
        order = event_order(swap)
        while next_anchor is not None and event_order(next_anchor) <= order:
            active_weth_usd = Decimal(next_anchor["quote_per_token"])
            next_anchor = next(anchors, None)

        pool_id = swap["pool_id"].lower()
        registration = registrations.get(pool_id)
        if registration is None:
            raise KeyError(f"V4 swap pool id absent from Pons registrations: {pool_id}")
        token = registration["token"].lower()
        launch = registry.get(token)
        if launch is None:
            raise KeyError(f"registered V4 token absent from V2 registry: {token}")
        if registration["quote_token"].lower() != launch["pair_token"].lower():
            raise ValueError(f"V4 registration quote mismatch for {token}")

        token_is_token0 = int(token, 16) < int(launch["pair_token"], 16)
        quote_per_token = v3_v4_quote_per_token(
            int(swap["sqrt_price_x96"]),
            token_is_token0=token_is_token0,
            token_decimals=int(launch["token_decimals"]),
            quote_decimals=int(launch["quote_decimals"]),
        )
        base = dict(swap)
        base["phase"] = "v4"
        base["event_type"] = "v4_swap"
        yield _attach_usd(base, launch, quote_per_token, active_weth_usd)
