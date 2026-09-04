"""Shared point-in-time USD quote-oracle tapes."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Iterator

from hlp.config import normalize_address
from hlp.data.rpc import RpcClient
from hlp.protocols.chainlink import (
    ANSWER_UPDATED_TOPIC,
    decode_chainlink_answer_updated,
    read_chainlink_aggregator,
    read_chainlink_latest_round,
)


def reconstruct_chainlink_usd_tape(
    rpc: RpcClient,
    *,
    quote_token: str,
    feed: str,
    symbol: str,
    from_block: int,
    to_block: int,
    chunk_size: int = 100_000,
    min_chunk_size: int = 1,
) -> tuple[dict, Iterator[dict]]:
    """Return prior-window state plus causal USD update events for one feed.

    The current implementation fails closed if the Chainlink proxy changes
    underlying aggregator during the shard. That is safer than silently
    stitching phases incorrectly; phase-aware segmentation can be added when a
    real historical shard proves it is needed.
    """
    if from_block <= 0:
        raise ValueError("from_block must be > 0")
    if to_block < from_block:
        raise ValueError("to_block must be >= from_block")

    quote_token = normalize_address(quote_token)
    feed = normalize_address(feed)
    symbol = symbol.upper().strip()
    prior_block = from_block - 1

    start_aggregator = read_chainlink_aggregator(rpc, feed, block=prior_block)
    end_aggregator = read_chainlink_aggregator(rpc, feed, block=to_block)
    if start_aggregator != end_aggregator:
        raise RuntimeError(
            f"Chainlink aggregator changed inside shard for {symbol}: "
            f"{start_aggregator} -> {end_aggregator}"
        )

    initial = read_chainlink_latest_round(rpc, feed, block=prior_block)
    expected_description = f"RH{symbol} / USD"
    if initial.description != expected_description:
        raise ValueError(
            f"Chainlink description mismatch for {symbol}: "
            f"{initial.description!r} != {expected_description!r}"
        )

    state = {
        "quote_token": quote_token,
        "symbol": symbol,
        "feed": feed,
        "aggregator": start_aggregator,
        "block_number": prior_block,
        "proxy_round_id": initial.round_id,
        "aggregator_round_id": initial.round_id & ((1 << 64) - 1),
        "updated_at": initial.updated_at,
        "decimals": initial.decimals,
        "usd_price": str(initial.answer),
        "description": initial.description,
    }

    raw_logs = rpc.iter_logs_chunked(
        from_block,
        to_block,
        address=start_aggregator,
        topics=[ANSWER_UPDATED_TOPIC],
        chunk_size=chunk_size,
        min_chunk_size=min_chunk_size,
    )

    def updates() -> Iterator[dict]:
        previous_round = initial.round_id & ((1 << 64) - 1)
        for raw in raw_logs:
            event = decode_chainlink_answer_updated(raw)
            if event.round_id <= previous_round:
                # Aggregator round ids should advance. Fail closed rather than
                # let a duplicate/out-of-order event corrupt point-in-time USD.
                raise ValueError(
                    f"non-increasing Chainlink round for {symbol}: "
                    f"{event.round_id} <= {previous_round}"
                )
            previous_round = event.round_id
            price = Decimal(event.answer_raw) / (Decimal(10) ** initial.decimals)
            yield {
                "quote_token": quote_token,
                "symbol": symbol,
                "feed": feed,
                "aggregator": start_aggregator,
                "block_number": event.block_number,
                "transaction_hash": event.transaction_hash,
                "transaction_index": event.transaction_index,
                "log_index": event.log_index,
                "round_id": event.round_id,
                "updated_at": event.updated_at,
                "decimals": initial.decimals,
                "usd_price": str(price),
            }

    return state, updates()


def merge_oracle_updates(
    update_groups: Iterable[Iterable[dict]],
) -> list[dict]:
    """Materialize and globally order independent quote-asset oracle tapes."""
    rows = [row for group in update_groups for row in group]
    rows.sort(
        key=lambda row: (
            int(row["block_number"]),
            -1 if row.get("transaction_index") is None else int(row["transaction_index"]),
            int(row["log_index"]),
            row["quote_token"],
        )
    )
    return rows



def reconstruct_chainlink_usd_tapes(
    rpc: RpcClient,
    *,
    feeds: Iterable[dict],
    from_block: int,
    to_block: int,
    chunk_size: int = 100_000,
    min_chunk_size: int = 1,
) -> tuple[list[dict], Iterator[dict]]:
    """Reconstruct many Stock Token/USD feeds with one shared event scan.

    Each feed dict requires: quote_token, symbol, feed. Optional
    heartbeat_seconds is preserved in state/update provenance.
    """
    if from_block <= 0:
        raise ValueError("from_block must be > 0")
    if to_block < from_block:
        raise ValueError("to_block must be >= from_block")

    prior_block = from_block - 1
    states: list[dict] = []
    by_aggregator: dict[str, dict] = {}

    for raw_spec in feeds:
        quote_token = normalize_address(raw_spec["quote_token"])
        feed = normalize_address(raw_spec["feed"])
        symbol = str(raw_spec["symbol"]).upper().strip()
        heartbeat = raw_spec.get("heartbeat_seconds")

        start_aggregator = read_chainlink_aggregator(rpc, feed, block=prior_block)
        end_aggregator = read_chainlink_aggregator(rpc, feed, block=to_block)
        if start_aggregator != end_aggregator:
            raise RuntimeError(
                f"Chainlink aggregator changed inside shard for {symbol}: "
                f"{start_aggregator} -> {end_aggregator}"
            )
        if start_aggregator in by_aggregator:
            raise ValueError(
                f"multiple quote feeds share aggregator {start_aggregator}"
            )

        initial = read_chainlink_latest_round(rpc, feed, block=prior_block)
        expected_description = f"RH{symbol} / USD"
        if initial.description != expected_description:
            raise ValueError(
                f"Chainlink description mismatch for {symbol}: "
                f"{initial.description!r} != {expected_description!r}"
            )
        aggregator_round = initial.round_id & ((1 << 64) - 1)
        spec = {
            "quote_token": quote_token,
            "symbol": symbol,
            "feed": feed,
            "aggregator": start_aggregator,
            "heartbeat_seconds": heartbeat,
            "decimals": initial.decimals,
            "initial_aggregator_round_id": aggregator_round,
        }
        by_aggregator[start_aggregator] = spec
        states.append(
            {
                **spec,
                "block_number": prior_block,
                "proxy_round_id": initial.round_id,
                "aggregator_round_id": aggregator_round,
                "updated_at": initial.updated_at,
                "usd_price": str(initial.answer),
                "description": initial.description,
            }
        )

    aggregators = sorted(by_aggregator)
    raw_logs = rpc.iter_logs_chunked(
        from_block,
        to_block,
        address=aggregators,
        topics=[ANSWER_UPDATED_TOPIC],
        chunk_size=chunk_size,
        min_chunk_size=min_chunk_size,
    )
    previous = {
        aggregator: int(spec["initial_aggregator_round_id"])
        for aggregator, spec in by_aggregator.items()
    }

    def updates() -> Iterator[dict]:
        for raw in raw_logs:
            aggregator = raw.address.lower()
            spec = by_aggregator.get(aggregator)
            if spec is None:
                raise KeyError(
                    f"shared oracle log came from unknown aggregator {aggregator}"
                )
            event = decode_chainlink_answer_updated(raw)
            if event.round_id <= previous[aggregator]:
                raise ValueError(
                    f"non-increasing Chainlink round for {spec['symbol']}: "
                    f"{event.round_id} <= {previous[aggregator]}"
                )
            previous[aggregator] = event.round_id
            price = Decimal(event.answer_raw) / (
                Decimal(10) ** int(spec["decimals"])
            )
            yield {
                "quote_token": spec["quote_token"],
                "symbol": spec["symbol"],
                "feed": spec["feed"],
                "aggregator": aggregator,
                "heartbeat_seconds": spec["heartbeat_seconds"],
                "block_number": event.block_number,
                "transaction_hash": event.transaction_hash,
                "transaction_index": event.transaction_index,
                "log_index": event.log_index,
                "aggregator_round_id": event.round_id,
                "updated_at": event.updated_at,
                "decimals": spec["decimals"],
                "usd_price": str(price),
            }

    states.sort(key=lambda row: row["quote_token"])
    return states, updates()
