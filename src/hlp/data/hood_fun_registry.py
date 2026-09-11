"""Persistent hood.fun launch registry."""

from __future__ import annotations

from typing import Iterable

from hlp.data.types import HoodFunEvent


TOKEN_DECIMALS = 18


def _order(row: HoodFunEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def build_hood_fun_launch_registry(events: Iterable[HoodFunEvent]) -> list[dict]:
    """Build immutable per-launch curve parameters.

    hood.fun reserves 80% of chosen token supply for the curve and 20% for
    post-graduation liquidity. Mainnet conservation audits verify the
    TokenCreated curve-inventory field obeys that split exactly.
    """
    output: list[dict] = []
    seen: set[str] = set()
    for event in sorted(list(events), key=_order):
        if event.event_type != "token_created":
            continue
        token = event.token.lower()
        if token in seen:
            raise ValueError(f"duplicate hood.fun TokenCreated: {token}")
        if (
            event.curve_inventory_raw is None
            or event.virtual_quote_raw is None
            or event.virtual_token_raw is None
            or event.actor is None
        ):
            raise ValueError(f"incomplete hood.fun TokenCreated: {token}")
        if event.curve_inventory_raw <= 0:
            raise ValueError(f"non-positive hood.fun curve inventory: {token}")

        supply_numerator = event.curve_inventory_raw * 5
        if supply_numerator % 4:
            raise ValueError(
                f"hood.fun curve inventory is not an exact 80% supply: {token}"
            )
        supply_raw = supply_numerator // 4
        if event.virtual_token_raw <= event.curve_inventory_raw:
            raise ValueError(
                f"hood.fun virtual token reserve must exceed sale inventory: {token}"
            )

        seen.add(token)
        output.append(
            {
                "venue": "hood.fun",
                "generation": "current",
                "token": token,
                "creator": event.actor.lower(),
                "name": event.name,
                "symbol": event.symbol,
                "metadata_uri": event.metadata_uri,
                "token_decimals": TOKEN_DECIMALS,
                "supply_raw": supply_raw,
                "curve_inventory_raw": event.curve_inventory_raw,
                "initial_virtual_quote_raw": event.virtual_quote_raw,
                "initial_virtual_token_raw": event.virtual_token_raw,
                "quote_token": "0x" + "00" * 20,
                "launch_block": event.block_number,
                "launch_transaction_hash": event.transaction_hash,
                "launch_transaction_index": event.transaction_index,
                "launch_log_index": event.log_index,
            }
        )
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output
