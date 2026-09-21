"""Sparse causal Chainlink/USD sampling at target event orders."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping, Any

from hlp.config import normalize_address
from hlp.data.reconstruct import event_order
from hlp.data.rpc import RpcClient
from hlp.protocols.chainlink import (
    ANSWER_UPDATED_TOPIC,
    decode_chainlink_answer_updated,
    read_chainlink_aggregator,
    read_chainlink_latest_round,
)


def _target_dict(raw: Any) -> dict:
    return dict(raw)


def _accepted_descriptions(spec: Mapping[str, object]) -> set[str]:
    symbol = str(spec["symbol"]).upper().strip()
    accepted = {
        f"RH{symbol} / USD",
        f"Robinhood {symbol} / USD",
        f"{symbol} / USD",
    }
    directory_name = spec.get("directory_name")
    if directory_name:
        accepted.add(str(directory_name))
    return accepted


def build_sparse_chainlink_usd_points(
    rpc: RpcClient,
    targets: Iterable[Mapping[str, object]],
    *,
    feed_specs: Iterable[Mapping[str, object]],
    window_size: int = 200,
) -> list[dict]:
    """Resolve quote/USD only around target events with same-block causality.

    Each target must carry quote_token plus normal event-order fields. For every
    quote/window pair, the proxy state is read at window_start - 1 and only
    AnswerUpdated events through the final target block are replayed. Synthetic
    USD points are emitted at the target event order, so later same-block oracle
    updates cannot leak backward into a market event.
    """
    size = int(window_size)
    if size <= 0:
        raise ValueError("sparse Chainlink window size must be positive")

    specs: dict[str, dict] = {}
    for raw in feed_specs:
        spec = dict(raw)
        token = normalize_address(str(spec["quote_token"]))
        if token in specs:
            raise ValueError(f"duplicate sparse Chainlink quote spec: {token}")
        feed = normalize_address(str(spec["feed"]))
        symbol = str(spec.get("symbol") or "").upper().strip()
        if not symbol:
            raise ValueError(f"sparse Chainlink quote spec has no symbol: {token}")
        spec["quote_token"] = token
        spec["feed"] = feed
        spec["symbol"] = symbol
        specs[token] = spec

    ordered = []
    for raw in targets:
        row = _target_dict(raw)
        token = normalize_address(str(row["quote_token"]))
        if token not in specs:
            raise KeyError(f"missing sparse Chainlink quote spec: {token}")
        row["quote_token"] = token
        ordered.append(row)
    ordered.sort(key=lambda row: (event_order(row), row["quote_token"]))
    if not ordered:
        return []

    buckets: dict[tuple[str, int], list[dict]] = {}
    for row in ordered:
        block = int(row["block_number"])
        start = (block // size) * size
        buckets.setdefault((row["quote_token"], start), []).append(row)

    output: list[dict] = []
    for token, window_start in sorted(
        buckets,
        key=lambda key: (key[1], key[0]),
    ):
        spec = specs[token]
        window_targets = buckets[(token, window_start)]
        window_targets.sort(key=event_order)
        last_target_block = int(window_targets[-1]["block_number"])
        window_end = min(window_start + size - 1, last_target_block)
        state_block = window_start - 1
        if state_block < 0:
            raise ValueError(
                "sparse Chainlink window requires a prior state block"
            )

        start_aggregator = read_chainlink_aggregator(
            rpc,
            spec["feed"],
            block=state_block,
        )
        end_aggregator = read_chainlink_aggregator(
            rpc,
            spec["feed"],
            block=window_end,
        )
        if start_aggregator != end_aggregator:
            raise RuntimeError(
                "Chainlink aggregator changed inside sparse window for "
                f"{spec['symbol']}: {start_aggregator} -> {end_aggregator}"
            )

        initial = read_chainlink_latest_round(
            rpc,
            spec["feed"],
            block=state_block,
        )
        accepted = _accepted_descriptions(spec)
        if initial.description not in accepted:
            raise ValueError(
                f"Chainlink description mismatch for {spec['symbol']}: "
                f"{initial.description!r} not in {sorted(accepted)!r}"
            )
        active = Decimal(initial.answer)
        if active <= 0:
            raise ValueError(
                f"Chainlink prior-window price is non-positive: {token}"
            )

        updates = []
        previous_round = initial.round_id & ((1 << 64) - 1)
        for raw in rpc.get_logs(
            window_start,
            window_end,
            address=start_aggregator,
            topics=[ANSWER_UPDATED_TOPIC],
        ):
            event = decode_chainlink_answer_updated(raw)
            if event.round_id <= previous_round:
                raise ValueError(
                    f"non-increasing sparse Chainlink round for "
                    f"{spec['symbol']}: {event.round_id} <= {previous_round}"
                )
            previous_round = event.round_id
            price = Decimal(event.answer_raw) / (
                Decimal(10) ** int(initial.decimals)
            )
            updates.append((event_order({
                "block_number": event.block_number,
                "transaction_index": event.transaction_index,
                "log_index": event.log_index,
            }), price, event.round_id, event.updated_at))
        updates.sort(key=lambda item: item[0])

        update_index = 0
        active_round = initial.round_id & ((1 << 64) - 1)
        active_updated_at = initial.updated_at
        for target in window_targets:
            target_order = event_order(target)
            while (
                update_index < len(updates)
                and updates[update_index][0] <= target_order
            ):
                _, active, active_round, active_updated_at = updates[update_index]
                update_index += 1
            if active <= 0:
                raise ValueError(
                    f"sparse Chainlink active price is non-positive: {token}"
                )
            output.append({
                "quote_token": token,
                "symbol": spec["symbol"],
                "feed": spec["feed"],
                "aggregator": start_aggregator,
                "pricing_status": spec.get(
                    "pricing_status",
                    "priced_chainlink_stock_token",
                ),
                "block_number": target_order[0],
                "transaction_index": (
                    None if target_order[1] < 0 else target_order[1]
                ),
                "log_index": target_order[2],
                "usd_price": str(active),
                "round_id": int(active_round),
                "updated_at": int(active_updated_at),
                "pricing_source": "sparse_chainlink_state_and_updates",
                "window_from_block": window_start,
                "window_to_block": window_end,
                "state_block": state_block,
                "oracle_updates_in_window": len(updates),
                "oracle_updates_applied": update_index,
            })

    output.sort(key=lambda row: (event_order(row), row["quote_token"]))
    if len(output) != len(ordered):
        raise ValueError(
            "sparse Chainlink output count does not match targets"
        )
    return output
