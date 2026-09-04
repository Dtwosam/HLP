"""Point-in-time Pons V1 configuration timeline."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import asdict
from typing import Iterable

from hlp.data.types import PonsLaunch, PonsV1LaunchConfig


def event_order(row) -> tuple[int, int, int]:
    tx = row.transaction_index
    return (
        int(row.block_number),
        -1 if tx is None else int(tx),
        int(row.log_index),
    )


class PonsV1ConfigTimeline:
    """Lookup the exact config state visible when a token launched."""

    def __init__(self, rows: Iterable[PonsV1LaunchConfig]):
        grouped: dict[int, list[PonsV1LaunchConfig]] = defaultdict(list)
        for row in rows:
            grouped[row.config_id].append(row)
        self._rows: dict[int, tuple[PonsV1LaunchConfig, ...]] = {}
        self._keys: dict[int, tuple[tuple[int, int, int], ...]] = {}
        for config_id, values in grouped.items():
            values.sort(key=event_order)
            self._rows[config_id] = tuple(values)
            self._keys[config_id] = tuple(event_order(value) for value in values)

    def at_launch(self, launch: PonsLaunch) -> PonsV1LaunchConfig:
        if launch.version != "v1":
            raise ValueError("PonsV1ConfigTimeline only supports V1 launches")
        if launch.launch_config_id is None:
            raise ValueError("launch is missing launch_config_id")
        config_id = launch.launch_config_id
        rows = self._rows.get(config_id)
        keys = self._keys.get(config_id)
        if not rows or not keys:
            raise KeyError(f"no Pons V1 config history for id {config_id}")
        index = bisect_right(keys, event_order(launch)) - 1
        if index < 0:
            raise KeyError(
                f"no config {config_id} visible before launch at {event_order(launch)}"
            )
        return rows[index]


def enrich_v1_launch(launch: PonsLaunch, timeline: PonsV1ConfigTimeline) -> dict:
    config = timeline.at_launch(launch)
    row = asdict(launch)
    row.update(
        {
            "supply_raw": config.supply,
            "token_decimals": 18,
            "config_pair_token": config.pair_token,
            "config_initial_tick": config.initial_tick,
            "config_graduation_threshold": config.graduation_threshold,
            "config_enabled": config.enabled,
            "config_action_block": config.block_number,
            "config_action_transaction_index": config.transaction_index,
            "config_action_log_index": config.log_index,
        }
    )
    if launch.pair_token.lower() != config.pair_token.lower():
        raise ValueError(
            f"launch pair token disagrees with config {config.config_id}: "
            f"{launch.pair_token} != {config.pair_token}"
        )
    return row
