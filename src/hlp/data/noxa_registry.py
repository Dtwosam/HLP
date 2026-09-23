"""Persistent NOXA instant-V3 launch registry assembly."""

from __future__ import annotations

from typing import Iterable

from hlp.config import normalize_address
from hlp.data.types import InstantV3Launch, NoxaLaunchedToken


def build_noxa_launch_registry(
    launches: Iterable[InstantV3Launch],
    launched_token_states: Iterable[NoxaLaunchedToken],
) -> list[dict]:
    """Join NOXA TokenLaunched events to immutable per-token launch state.

    State rows must be read at the launch block. Every overlapping immutable
    field is checked against the event before supply is accepted.
    """
    states: dict[str, NoxaLaunchedToken] = {}
    for state in launched_token_states:
        token = normalize_address(state.token)
        if token in states:
            raise ValueError(f"duplicate NOXA launched-token state: {token}")
        states[token] = state

    output: list[dict] = []
    seen_tokens: set[str] = set()
    seen_pools: set[str] = set()

    for launch in launches:
        if launch.venue != "noxa":
            raise ValueError(f"non-NOXA launch supplied: {launch.venue!r}")

        token = normalize_address(launch.token)
        pair = normalize_address(launch.pair_token)
        pool = normalize_address(launch.pool)
        deployer = normalize_address(launch.deployer)
        state = states.get(token)
        if state is None:
            raise KeyError(f"missing NOXA launched-token state: {token}")
        if int(state.block_number) != int(launch.block_number):
            raise ValueError(
                "NOXA state must be read at launch block: "
                f"{token} state={state.block_number} launch={launch.block_number}"
            )

        expected = {
            "token": token,
            "deployer": deployer,
            "paired_token": pair,
            "position_id": int(launch.position_id),
            "dex_id": int(launch.dex_id),
            "launch_config_id": int(launch.launch_config_id),
            "restrictions_end_block": int(launch.restrictions_end_block),
        }
        observed = {
            "token": normalize_address(state.token),
            "deployer": normalize_address(state.deployer),
            "paired_token": normalize_address(state.paired_token),
            "position_id": int(state.position_id),
            "dex_id": int(state.dex_id),
            "launch_config_id": int(state.launch_config_id),
            "restrictions_end_block": int(state.restrictions_end_block),
        }
        mismatched = {
            key: {"expected": value, "observed": observed[key]}
            for key, value in expected.items()
            if observed[key] != value
        }
        if mismatched:
            raise ValueError(
                f"NOXA launch/state identity mismatch for {token}: {mismatched}"
            )
        if int(state.supply) <= 0:
            raise ValueError(f"NOXA launch has non-positive supply: {token}")
        if token in seen_tokens:
            raise ValueError(f"duplicate NOXA launch token: {token}")
        if pool in seen_pools:
            raise ValueError(f"duplicate NOXA launch pool: {pool}")

        seen_tokens.add(token)
        seen_pools.add(pool)
        output.append(
            {
                "venue": "noxa",
                "launch_kind": "instant_v3",
                "token": token,
                "quote_token": pair,
                "pool": pool,
                "dex_factory": normalize_address(launch.dex_factory),
                "deployer": deployer,
                "position_manager": normalize_address(state.position_manager),
                "position_id": int(launch.position_id),
                "dex_id": int(launch.dex_id),
                "launch_config_id": int(launch.launch_config_id),
                "restrictions_end_block": int(launch.restrictions_end_block),
                "initial_buy_amount": int(launch.initial_buy_amount),
                "supply_raw": int(state.supply),
                "launch_block": int(launch.block_number),
                "launch_transaction_hash": launch.transaction_hash.lower(),
                "launch_transaction_index": launch.transaction_index,
                "launch_log_index": int(launch.log_index),
                "state_block": int(state.block_number),
            }
        )

    extra_states = sorted(set(states) - seen_tokens)
    if extra_states:
        raise ValueError(
            "NOXA state set contains tokens absent from launch tape: "
            f"{extra_states[:5]}"
        )

    output.sort(
        key=lambda row: (
            int(row["launch_block"]),
            -1
            if row.get("launch_transaction_index") is None
            else int(row["launch_transaction_index"]),
            int(row["launch_log_index"]),
            row["token"],
        )
    )
    return output


def attach_noxa_initializations(
    registry_rows: Iterable[dict],
    initialize_rows: Iterable[dict],
) -> list[dict]:
    """Join every NOXA launch pool to its exact V3 Initialize event."""
    registry = [dict(row) for row in registry_rows]
    by_pool: dict[str, dict] = {}
    for row in registry:
        pool = normalize_address(str(row["pool"]))
        if pool in by_pool:
            raise ValueError(f"duplicate NOXA registry pool: {pool}")
        by_pool[pool] = row

    initializes: dict[str, dict] = {}
    for raw in initialize_rows:
        row = dict(raw)
        pool = normalize_address(str(row["pool"]))
        if pool not in by_pool:
            continue
        if pool in initializes:
            raise ValueError(
                f"multiple V3 Initialize events for NOXA pool: {pool}"
            )
        initializes[pool] = row

    missing = sorted(set(by_pool) - set(initializes))
    if missing:
        raise ValueError(
            "NOXA registry pools missing V3 Initialize: "
            + ", ".join(missing[:10])
        )

    output = []
    for row in registry:
        pool = normalize_address(str(row["pool"]))
        init = initializes[pool]
        launch_order = (
            int(row["launch_block"]),
            -1
            if row.get("launch_transaction_index") is None
            else int(row["launch_transaction_index"]),
            int(row["launch_log_index"]),
        )
        initialize_order = (
            int(init["block_number"]),
            -1
            if init.get("transaction_index") is None
            else int(init["transaction_index"]),
            int(init["log_index"]),
        )
        if initialize_order < launch_order:
            raise ValueError(
                f"NOXA Initialize precedes launch order: {pool}"
            )
        initialize_block = initialize_order[0]
        item = dict(row)
        item.update({
            "initialize_block": initialize_block,
            "initialize_transaction_hash": str(
                init["transaction_hash"]
            ).lower(),
            "initialize_transaction_index": init.get(
                "transaction_index"
            ),
            "initialize_log_index": int(init["log_index"]),
            "initial_sqrt_price_x96": int(init["sqrt_price_x96"]),
            "initial_tick": int(init["tick"]),
        })
        output.append(item)

    output.sort(
        key=lambda row: (
            int(row["launch_block"]),
            row["token"],
        )
    )
    return output

