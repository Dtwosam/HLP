"""Point-in-time Pons V2 registry and lifecycle joins."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, Iterator

from hlp.config import normalize_address
from hlp.data.types import (
    PonsV2LaunchConfig,
    PonsV2PairEconomics,
    RawLog,
)
from hlp.protocols.pons import (
    V2_LAUNCH_CONFIG_ADDED_TOPIC,
    V2_LAUNCH_CONFIG_UPDATED_TOPIC,
    V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC,
    V2_TOKEN_LAUNCHED_TOPIC,
    decode_v2_launch,
    decode_v2_launch_config_event_id,
    decode_v2_pair_token_economics,
)


ZERO_ADDRESS = "0x" + "00" * 20


def raw_event_order(row: RawLog) -> tuple[int, int, int]:
    return (
        row.block_number,
        -1 if row.transaction_index is None else row.transaction_index,
        row.log_index,
    )


def iter_enriched_v2_launches(
    rows: Iterable[RawLog],
    *,
    bootstrap_configs: Iterable[PonsV2LaunchConfig] = (),
    bootstrap_pair_economics: Iterable[PonsV2PairEconomics] = (),
    resolved_config_events: dict[tuple[int, int, int], PonsV2LaunchConfig] | None = None,
) -> Iterator[dict]:
    """Yield V2 launches with the exact economics visible at launch time."""
    configs = {row.config_id: row for row in bootstrap_configs}
    pair_economics = {
        normalize_address(row.pair_token): row for row in bootstrap_pair_economics
    }
    resolved = resolved_config_events or {}
    last_order: tuple[int, int, int] | None = None

    for raw in rows:
        order = raw_event_order(raw)
        if last_order is not None and order < last_order:
            raise ValueError("Pons V2 registry input is not chronological")
        last_order = order
        topic0 = raw.topics[0] if raw.topics else None

        if topic0 in {
            V2_LAUNCH_CONFIG_ADDED_TOPIC,
            V2_LAUNCH_CONFIG_UPDATED_TOPIC,
        }:
            action, config_id = decode_v2_launch_config_event_id(raw)
            config = resolved.get(order)
            if config is None:
                raise KeyError(
                    f"V2 {action} config {config_id} at {order} was not resolved"
                )
            if config.config_id != config_id:
                raise ValueError("resolved V2 config id disagrees with event")
            configs[config_id] = config
            continue

        if topic0 == V2_PAIR_TOKEN_ECONOMICS_UPDATED_TOPIC:
            economics = decode_v2_pair_token_economics(raw)
            pair_economics[economics.pair_token] = economics
            continue

        if topic0 != V2_TOKEN_LAUNCHED_TOPIC:
            continue

        launch = decode_v2_launch(raw)
        if launch.launch_config_id is None:
            raise ValueError("V2 launch missing config id")
        config = configs.get(launch.launch_config_id)
        if config is None:
            raise KeyError(
                f"V2 config {launch.launch_config_id} unavailable for {launch.token}"
            )

        pair = normalize_address(launch.pair_token)
        if pair == ZERO_ADDRESS:
            phantom_quote = config.phantom_quote
            threshold = config.graduation_threshold
            quote_decimals = 18
            economics_source = "native_launch_config"
        else:
            economics = pair_economics.get(pair)
            if economics is None or economics.phantom_quote == 0:
                raise KeyError(
                    f"V2 pair-token economics unavailable for {pair} at {order}"
                )
            phantom_quote = economics.phantom_quote
            threshold = economics.graduation_threshold
            quote_decimals = economics.decimals
            economics_source = "pair_token_economics"

        if launch.graduation_threshold != threshold:
            raise ValueError(
                f"V2 launch threshold mismatch for {launch.token}: "
                f"event={launch.graduation_threshold}, economics={threshold}"
            )

        out = asdict(launch)
        out.update(
            {
                "supply_raw": config.supply,
                "token_decimals": 18,
                "quote_decimals": quote_decimals,
                "phantom_quote": phantom_quote,
                "curve_fee_bps": config.curve_fee_bps,
                "config_pool_fee": config.pool_fee,
                "config_tick_spacing": config.tick_spacing,
                "economics_source": economics_source,
                "config_action": config.action,
                "config_action_block": config.block_number,
            }
        )
        yield out
