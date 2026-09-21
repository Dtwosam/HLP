"""Deterministic discovery of directly initialized DEX markets.

This module discovers priceable candidate markets from canonical V3/V4 pool
events. It deliberately does not claim launch origin or choose a canonical
market when a token has multiple pools; those remain separate Phase-2 steps.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.types import V3PoolCreated, V3PoolInitialized, V4PoolInitialized
from hlp.protocols.erc20 import Erc20StaticState


def _state_index(
    rows: Iterable[Erc20StaticState],
) -> dict[tuple[str, int], Erc20StaticState]:
    output: dict[tuple[str, int], Erc20StaticState] = {}
    for row in rows:
        if not isinstance(row.block_number, int):
            raise ValueError("direct-market ERC20 state must use an exact block")
        token = normalize_address(row.token)
        key = (token, int(row.block_number))
        if key in output:
            raise ValueError(
                f"duplicate direct-market ERC20 state: {token} @ {row.block_number}"
            )
        if int(row.total_supply) <= 0:
            raise ValueError(
                f"direct-market ERC20 state has non-positive supply: {token}"
            )
        if int(row.decimals) < 0 or int(row.decimals) > 255:
            raise ValueError(
                f"direct-market ERC20 state has invalid decimals: {token}"
            )
        output[key] = row
    return output


def _quote_map(
    quote_decimals: Mapping[str, int],
) -> dict[str, int]:
    output: dict[str, int] = {}
    for raw, decimals in quote_decimals.items():
        address = normalize_address(str(raw))
        value = int(decimals)
        if value < 0 or value > 255:
            raise ValueError(f"invalid quote decimals for {address}: {value}")
        if address in output:
            raise ValueError(f"duplicate supported quote asset: {address}")
        output[address] = value
    return output


def _classify_pair(
    left: str,
    right: str,
    *,
    supported_quotes: Mapping[str, int],
) -> tuple[str, str] | None:
    left = normalize_address(left)
    right = normalize_address(right)
    if left == right:
        raise ValueError(f"DEX market has identical currencies: {left}")

    left_quote = left in supported_quotes
    right_quote = right in supported_quotes
    if left_quote and right_quote:
        return None
    if not left_quote and not right_quote:
        return None
    return (right, left) if left_quote else (left, right)


def build_v3_direct_market_registry(
    pool_created_rows: Iterable[V3PoolCreated],
    initialize_rows: Iterable[V3PoolInitialized],
    erc20_states: Iterable[Erc20StaticState],
    *,
    source_id: str,
    venue: str,
    factory: str,
    quote_decimals: Mapping[str, int],
) -> list[dict]:
    """Build priceable V3 candidate markets with supply pinned to initialization."""
    expected_factory = normalize_address(factory)
    supported_quotes = _quote_map(quote_decimals)
    states = _state_index(erc20_states)

    created: dict[str, V3PoolCreated] = {}
    for row in pool_created_rows:
        if normalize_address(row.factory) != expected_factory:
            continue
        pool = normalize_address(row.pool)
        if pool in created:
            raise ValueError(f"duplicate V3 PoolCreated for {pool}")
        created[pool] = row

    initialized: dict[str, V3PoolInitialized] = {}
    for row in initialize_rows:
        pool = normalize_address(row.pool)
        if pool not in created:
            continue
        if pool in initialized:
            raise ValueError(f"multiple V3 Initialize events for {pool}")
        initialized[pool] = row

    output: list[dict] = []
    for pool in sorted(created):
        creation = created[pool]
        init = initialized.get(pool)
        if init is None:
            continue
        pair = _classify_pair(
            creation.token0,
            creation.token1,
            supported_quotes=supported_quotes,
        )
        if pair is None:
            continue
        token, quote = pair
        state = states.get((token, int(init.block_number)))
        if state is None:
            raise KeyError(
                f"missing exact-block ERC20 state for V3 candidate "
                f"{token} @ {init.block_number}"
            )

        output.append(
            {
                "source_id": str(source_id),
                "venue": str(venue),
                "source_kind": "direct_dex",
                "origin_classification": "unresolved",
                "token": token,
                "quote_token": quote,
                "quote_decimals": supported_quotes[quote],
                "token_decimals": int(state.decimals),
                "supply_raw": int(state.total_supply),
                "pool": pool,
                "factory": expected_factory,
                "token0": normalize_address(creation.token0),
                "token1": normalize_address(creation.token1),
                "fee": int(creation.fee),
                "tick_spacing": int(creation.tick_spacing),
                "pool_created_block": int(creation.block_number),
                "pool_created_transaction_hash": creation.transaction_hash.lower(),
                "pool_created_transaction_index": creation.transaction_index,
                "pool_created_log_index": int(creation.log_index),
                "initialize_block": int(init.block_number),
                "initialize_transaction_hash": init.transaction_hash.lower(),
                "initialize_transaction_index": init.transaction_index,
                "initialize_log_index": int(init.log_index),
                "initial_sqrt_price_x96": int(init.sqrt_price_x96),
                "initial_tick": int(init.tick),
                "state_block": int(state.block_number),
            }
        )

    output.sort(
        key=lambda row: (
            row["initialize_block"],
            row["token"],
            row["pool"],
        )
    )
    return output


def build_v4_direct_market_registry(
    initialize_rows: Iterable[V4PoolInitialized],
    erc20_states: Iterable[Erc20StaticState],
    *,
    source_id: str,
    venue: str,
    pool_manager: str,
    quote_decimals: Mapping[str, int],
) -> list[dict]:
    """Build priceable V4 candidate markets with exact initialization supply."""
    expected_manager = normalize_address(pool_manager)
    supported_quotes = _quote_map(quote_decimals)
    states = _state_index(erc20_states)

    output: list[dict] = []
    seen_pools: set[str] = set()
    for init in initialize_rows:
        if normalize_address(init.pool_manager) != expected_manager:
            continue
        pool_id = init.pool_id.lower()
        if pool_id in seen_pools:
            raise ValueError(f"multiple V4 Initialize events for {pool_id}")
        seen_pools.add(pool_id)

        pair = _classify_pair(
            init.currency0,
            init.currency1,
            supported_quotes=supported_quotes,
        )
        if pair is None:
            continue
        token, quote = pair
        state = states.get((token, int(init.block_number)))
        if state is None:
            raise KeyError(
                f"missing exact-block ERC20 state for V4 candidate "
                f"{token} @ {init.block_number}"
            )

        output.append(
            {
                "source_id": str(source_id),
                "venue": str(venue),
                "source_kind": "direct_dex",
                "origin_classification": "unresolved",
                "token": token,
                "quote_token": quote,
                "quote_decimals": supported_quotes[quote],
                "token_decimals": int(state.decimals),
                "supply_raw": int(state.total_supply),
                "pool_id": pool_id,
                "pool_manager": expected_manager,
                "currency0": normalize_address(init.currency0),
                "currency1": normalize_address(init.currency1),
                "fee": int(init.fee),
                "tick_spacing": int(init.tick_spacing),
                "hooks": normalize_address(init.hooks),
                "initialize_block": int(init.block_number),
                "initialize_transaction_hash": init.transaction_hash.lower(),
                "initialize_transaction_index": init.transaction_index,
                "initialize_log_index": int(init.log_index),
                "initial_sqrt_price_x96": int(init.sqrt_price_x96),
                "initial_tick": int(init.tick),
                "state_block": int(state.block_number),
            }
        )

    output.sort(
        key=lambda row: (
            row["initialize_block"],
            row["token"],
            row["pool_id"],
        )
    )
    return output


def summarize_direct_market_registry(rows: Iterable[Mapping[str, object]]) -> dict:
    """Return coverage counts while keeping origin and pool selection unresolved."""
    data = [dict(row) for row in rows]
    tokens = {
        normalize_address(str(row["token"]))
        for row in data
    }
    quotes = {
        normalize_address(str(row["quote_token"]))
        for row in data
    }
    sources = {str(row["source_id"]) for row in data}
    unresolved = sum(
        str(row.get("origin_classification")) == "unresolved"
        for row in data
    )
    return {
        "markets": len(data),
        "tokens": len(tokens),
        "quote_assets": len(quotes),
        "source_ids": sorted(sources),
        "unresolved_origin_markets": unresolved,
        "canonical_market_selection_complete": False,
    }
