"""Persistent trench.today launch registry."""

from __future__ import annotations

from typing import Iterable

from hlp.data.types import TrenchEvent


def _order(row: TrenchEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def build_trench_launch_registry(events: Iterable[TrenchEvent]) -> list[dict]:
    """Build immutable launch metadata from TokenCreate events."""
    output: list[dict] = []
    seen: set[str] = set()
    for event in sorted(list(events), key=_order):
        if event.event_type != "token_create":
            continue
        token = event.token.lower()
        if token in seen:
            raise ValueError(f"duplicate trench.today TokenCreate: {token}")
        if event.quote_token is None or event.curve is None or event.actor is None:
            raise ValueError(f"incomplete trench.today TokenCreate: {token}")
        seen.add(token)
        output.append(
            {
                "venue": "trench.today",
                "token": token,
                "creator": event.actor.lower(),
                "curve": event.curve.lower(),
                "quote_token": event.quote_token.lower(),
                "name": event.name,
                "symbol": event.symbol,
                "token_uri": event.token_uri,
                "event_timestamp": event.timestamp,
                "launch_block": event.block_number,
                "launch_transaction_hash": event.transaction_hash,
                "launch_transaction_index": event.transaction_index,
                "launch_log_index": event.log_index,
                "supply_raw": 1_000_000_000 * 10**18,
                "token_decimals": 18,
                "quote_decimals": 18,
            }
        )
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output
