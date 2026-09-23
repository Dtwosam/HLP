"""Persistent trench.today launch and curve-lifecycle registry."""

from __future__ import annotations

from typing import Iterable

from hlp.config import normalize_address
from hlp.data.types import TrenchEvent
from hlp.protocols.erc20 import Erc20StaticState


def _order(row: TrenchEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def build_trench_launch_registry_ordered(
    events: Iterable[TrenchEvent],
) -> list[dict]:
    """Build event-sourced launch/LimitReach records from chronological events."""
    states: dict[str, dict] = {}
    previous_order = None
    for event in events:
        order = _order(event)
        if previous_order is not None and order < previous_order:
            raise ValueError("trench.today event stream is not chronological")
        previous_order = order
        token = normalize_address(event.token)

        if event.event_type == "token_create":
            if token in states:
                raise ValueError(
                    f"duplicate trench.today TokenCreate: {token}"
                )
            if (
                event.quote_token is None
                or event.curve is None
                or event.actor is None
            ):
                raise ValueError(
                    f"incomplete trench.today TokenCreate: {token}"
                )
            states[token] = {
                "venue": "trench.today",
                "token": token,
                "creator": normalize_address(event.actor),
                "curve": normalize_address(event.curve),
                "quote_token": normalize_address(event.quote_token),
                "name": event.name,
                "symbol": event.symbol,
                "token_uri": event.token_uri,
                "event_timestamp": event.timestamp,
                "launch_block": event.block_number,
                "launch_transaction_hash": event.transaction_hash.lower(),
                "launch_transaction_index": event.transaction_index,
                "launch_log_index": event.log_index,
                "limit_reach_block": None,
                "limit_reach_transaction_hash": None,
                "limit_reach_transaction_index": None,
                "limit_reach_log_index": None,
                "supply_raw": None,
                "token_decimals": None,
                "state_block": None,
            }
            continue

        state = states.get(token)
        if state is None:
            # Later shards can contain curve events for earlier launches.
            continue
        if event.event_type == "limit_reach":
            if state["limit_reach_block"] is not None:
                raise ValueError(
                    f"duplicate trench.today LimitReach: {token}"
                )
            state["limit_reach_block"] = event.block_number
            state["limit_reach_transaction_hash"] = (
                event.transaction_hash.lower()
            )
            state["limit_reach_transaction_index"] = (
                event.transaction_index
            )
            state["limit_reach_log_index"] = event.log_index

    output = list(states.values())
    output.sort(
        key=lambda row: (
            int(row["launch_block"]),
            -1
            if row["launch_transaction_index"] is None
            else int(row["launch_transaction_index"]),
            int(row["launch_log_index"]),
            row["token"],
        )
    )
    return output


def build_trench_launch_registry(
    events: Iterable[TrenchEvent],
) -> list[dict]:
    """Build launch registry from an arbitrary event iterable."""
    return build_trench_launch_registry_ordered(
        sorted(list(events), key=_order)
    )


def attach_trench_launch_static_states(
    registry_rows: Iterable[dict],
    static_states: Iterable[Erc20StaticState],
) -> list[dict]:
    """Attach exact launch-block ERC-20 supply/decimals to every launch."""
    registry = [dict(row) for row in registry_rows]
    states: dict[tuple[str, int], Erc20StaticState] = {}
    for state in static_states:
        token = normalize_address(state.token)
        if not isinstance(state.block_number, int):
            raise ValueError(
                "trench.today launch state must use an exact block"
            )
        key = (token, int(state.block_number))
        if key in states:
            raise ValueError(
                f"duplicate trench.today launch state: {token} @ {key[1]}"
            )
        states[key] = state

    output = []
    used: set[tuple[str, int]] = set()
    for raw in registry:
        row = dict(raw)
        token = normalize_address(str(row["token"]))
        launch_block = int(row["launch_block"])
        key = (token, launch_block)
        state = states.get(key)
        if state is None:
            raise KeyError(
                f"missing trench.today launch state: {token} @ {launch_block}"
            )
        if int(state.total_supply) <= 0:
            raise ValueError(
                f"trench.today launch has non-positive supply: {token}"
            )
        decimals = int(state.decimals)
        if decimals < 0 or decimals > 255:
            raise ValueError(
                f"trench.today launch has invalid decimals: {token}"
            )
        row["supply_raw"] = int(state.total_supply)
        row["token_decimals"] = decimals
        row["state_block"] = launch_block
        output.append(row)
        used.add(key)

    extra = sorted(set(states) - used)
    if extra:
        raise ValueError(
            "trench.today state set contains tokens absent from registry: "
            f"{extra[:5]}"
        )
    return output
