"""Persistent Flap launch registry reconstructed from Portal events."""

from __future__ import annotations

from typing import Iterable

from hlp.data.types import FlapEvent


def _order(row: FlapEvent) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def build_flap_launch_registry_ordered(
    events: Iterable[FlapEvent],
) -> list[dict]:
    """Build registry from an already chronological Portal event stream.

    The ordered variant is intentionally streaming-friendly for the Phase-2
    chain-wide backfill. It rejects ordering drift instead of sorting the full
    history in memory.
    """
    states: dict[str, dict] = {}
    previous_order = None
    for event in events:
        order = _order(event)
        if previous_order is not None and order < previous_order:
            raise ValueError("Flap event stream is not chronological")
        previous_order = order
        token = event.token.lower()
        if event.event_type == "token_created":
            if token in states:
                raise ValueError(f"duplicate Flap TokenCreated: {token}")
            states[token] = {
                "venue": "flap",
                "token": token,
                "creator": event.actor,
                "name": event.name,
                "symbol": event.symbol,
                "meta": event.meta,
                "creation_nonce": event.value_raw,
                "launch_block": event.block_number,
                "launch_transaction_hash": event.transaction_hash,
                "launch_transaction_index": event.transaction_index,
                "launch_log_index": event.log_index,
                "quote_token": None,
                "quote_set_block": None,
                "quote_set_transaction_index": None,
                "quote_set_log_index": None,
                "curve_kind": None,
                "curve_address": None,
                "curve_parameter": None,
                "r": None,
                "h": None,
                "k": None,
                "dex_supply_thresh_raw": None,
                "token_version": None,
                "migrator_type": None,
                "dex_id": None,
                "lp_fee_profile": None,
                "graduation_block": None,
                "graduation_transaction_hash": None,
                "graduation_transaction_index": None,
                "graduation_log_index": None,
                "graduation_pool": None,
                "graduation_token_amount_raw": None,
                "graduation_quote_amount_raw": None,
                "graduation_quote_token": None,
                "graduation_dex_id": None,
                "graduation_lp_fee_profile": None,
                "graduation_migrator_type": None,
                "graduation_token_version": None,
                "supply_raw": 1_000_000_000 * 10**18,
                "token_decimals": 18,
            }
            continue

        state = states.get(token)
        if state is None:
            # This event belongs to a token created before the supplied tape.
            # A later shard must bootstrap from an earlier persistent registry.
            continue

        if event.event_type == "quote_set":
            if event.actor is None:
                raise ValueError(f"Flap quote_set missing quote token: {token}")
            state["quote_token"] = event.actor.lower()
            state["quote_set_block"] = event.block_number
            state["quote_set_transaction_index"] = event.transaction_index
            state["quote_set_log_index"] = event.log_index
        elif event.event_type == "curve_set":
            state["curve_kind"] = "legacy"
            state["curve_address"] = event.actor
            state["curve_parameter"] = event.value_raw
        elif event.event_type == "curve_set_v2":
            state["curve_kind"] = "v2"
            state["r"] = event.value_raw
            state["h"] = event.value2_raw
            state["k"] = event.amount_raw
        elif event.event_type == "dex_supply_thresh_set":
            state["dex_supply_thresh_raw"] = event.value_raw
        elif event.event_type == "token_version_set":
            state["token_version"] = event.value_raw
        elif event.event_type == "migrator_set":
            state["migrator_type"] = event.value_raw
        elif event.event_type == "dex_preference_set":
            state["dex_id"] = event.value_raw
            state["lp_fee_profile"] = event.value2_raw
        elif event.event_type == "launched_to_dex":
            if event.pool is None:
                raise ValueError(
                    f"Flap launched_to_dex missing pool: {token}"
                )
            if state["graduation_block"] is not None:
                raise ValueError(
                    f"duplicate Flap LaunchedToDEX: {token}"
                )
            state["graduation_block"] = event.block_number
            state["graduation_transaction_hash"] = event.transaction_hash
            state["graduation_transaction_index"] = event.transaction_index
            state["graduation_log_index"] = event.log_index
            state["graduation_pool"] = event.pool.lower()
            state["graduation_token_amount_raw"] = event.amount_raw
            state["graduation_quote_amount_raw"] = event.quote_amount_raw
            state["graduation_quote_token"] = state["quote_token"]
            state["graduation_dex_id"] = state["dex_id"]
            state["graduation_lp_fee_profile"] = state["lp_fee_profile"]
            state["graduation_migrator_type"] = state["migrator_type"]
            state["graduation_token_version"] = state["token_version"]

    output = list(states.values())
    output.sort(key=lambda row: (row["launch_block"], row["token"]))
    return output


def build_flap_launch_registry(events: Iterable[FlapEvent]) -> list[dict]:
    """Build per-token launch/config records from an arbitrary event iterable.

    Configuration is event-sourced rather than fetched from current state, so
    later Portal upgrades cannot rewrite historical launch parameters.
    """
    return build_flap_launch_registry_ordered(
        sorted(list(events), key=_order)
    )
