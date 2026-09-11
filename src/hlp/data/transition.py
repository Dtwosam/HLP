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

    v4_initializes: dict[str, list[dict]] = {}
    v4_swaps: dict[str, list[dict]] = {}
    for row in v4_points:
        token = row["token"]
        kind = row.get("event_type") or "v4_swap"
        if kind == "v4_initialize":
            v4_initializes.setdefault(token, []).append(row)
        elif kind == "v4_swap":
            v4_swaps.setdefault(token, []).append(row)
    for groups in (v4_initializes, v4_swaps):
        for rows in groups.values():
            rows.sort(key=event_order)

    output = []
    for seed in sorted(seed_points, key=event_order):
        token = seed["token"]
        seed_order = event_order(seed)
        curve_rows = curves.get(token, [])
        eligible_curve = [
            row
            for row in curve_rows
            if event_order(row) <= seed_order
        ]
        last_curve = eligible_curve[-1] if eligible_curve else None

        initialize_rows = v4_initializes.get(token, [])
        first_initialize = initialize_rows[0] if initialize_rows else None
        first_swap_after_seed = next(
            (
                row
                for row in v4_swaps.get(token, [])
                if event_order(row) >= seed_order
            ),
            None,
        )

        row = {
            "token": token,
            "graduation_block": seed["block_number"],
            "last_curve_block": None,
            "first_v4_initialize_block": None,
            "first_v4_swap_block": None,
            "curve_quote_per_token": None,
            "v4_initialize_quote_per_token": None,
            "seed_quote_per_token": seed["quote_per_token"],
            "first_v4_quote_per_token": None,
            "curve_to_v4_initialize_bps": None,
            "v4_initialize_to_seed_bps": None,
            "curve_to_seed_bps": None,
            "seed_to_first_v4_bps": None,
        }
        seed_price = Decimal(seed["quote_per_token"])

        if last_curve is not None:
            curve_price = Decimal(last_curve["quote_per_token"])
            row["last_curve_block"] = last_curve["block_number"]
            row["curve_quote_per_token"] = last_curve["quote_per_token"]
            row["curve_to_seed_bps"] = str(_relative_bps(seed_price, curve_price))

        if first_initialize is not None:
            initialize_price = Decimal(first_initialize["quote_per_token"])
            initialize_order = event_order(first_initialize)
            row["first_v4_initialize_block"] = first_initialize["block_number"]
            row["v4_initialize_quote_per_token"] = first_initialize["quote_per_token"]
            row["v4_initialize_to_seed_bps"] = str(
                _relative_bps(seed_price, initialize_price)
            )
            curve_before_initialize = [
                curve
                for curve in curve_rows
                if event_order(curve) <= initialize_order
            ]
            if curve_before_initialize:
                row["curve_to_v4_initialize_bps"] = str(
                    _relative_bps(
                        initialize_price,
                        Decimal(curve_before_initialize[-1]["quote_per_token"]),
                    )
                )

        if first_swap_after_seed is not None:
            v4_price = Decimal(first_swap_after_seed["quote_per_token"])
            row["first_v4_swap_block"] = first_swap_after_seed["block_number"]
            row["first_v4_quote_per_token"] = first_swap_after_seed["quote_per_token"]
            row["seed_to_first_v4_bps"] = str(
                _relative_bps(v4_price, seed_price)
            )

        output.append(row)
    return output
