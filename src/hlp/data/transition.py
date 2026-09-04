"""Cross-phase continuity checks for Pons V2 curve -> V4."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from hlp.data.reconstruct import event_order


def _relative_bps(after: Decimal, before: Decimal) -> Decimal:
    if before <= 0 or after <= 0:
        raise ValueError("prices must be positive")
    return ((after / before) - Decimal(1)) * Decimal(10_000)


def summarize_v2_transition_continuity(
    curve_points: Iterable[dict],
    seed_points: Iterable[dict],
    v4_points: Iterable[dict],
) -> list[dict]:
    curves: dict[str, list[dict]] = {}
    for row in curve_points:
        curves.setdefault(row["token"], []).append(row)
    for rows in curves.values():
        rows.sort(key=event_order)

    first_v4: dict[str, dict] = {}
    for row in v4_points:
        token = row["token"]
        if token not in first_v4 or event_order(row) < event_order(first_v4[token]):
            first_v4[token] = row

    output = []
    for seed in sorted(seed_points, key=event_order):
        token = seed["token"]
        seed_order = event_order(seed)
        eligible_curve = [
            row
            for row in curves.get(token, [])
            if event_order(row) <= seed_order
        ]
        last_curve = eligible_curve[-1] if eligible_curve else None
        first_pool_swap = first_v4.get(token)

        row = {
            "token": token,
            "graduation_block": seed["block_number"],
            "last_curve_block": None,
            "first_v4_swap_block": None,
            "curve_quote_per_token": None,
            "seed_quote_per_token": seed["quote_per_token"],
            "first_v4_quote_per_token": None,
            "curve_to_seed_bps": None,
            "seed_to_first_v4_bps": None,
        }
        seed_price = Decimal(seed["quote_per_token"])

        if last_curve is not None:
            curve_price = Decimal(last_curve["quote_per_token"])
            row["last_curve_block"] = last_curve["block_number"]
            row["curve_quote_per_token"] = last_curve["quote_per_token"]
            row["curve_to_seed_bps"] = str(_relative_bps(seed_price, curve_price))

        if first_pool_swap is not None and event_order(first_pool_swap) >= seed_order:
            v4_price = Decimal(first_pool_swap["quote_per_token"])
            row["first_v4_swap_block"] = first_pool_swap["block_number"]
            row["first_v4_quote_per_token"] = first_pool_swap["quote_per_token"]
            row["seed_to_first_v4_bps"] = str(_relative_bps(v4_price, seed_price))

        output.append(row)
    return output
