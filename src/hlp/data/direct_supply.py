"""Causal total-supply reconstruction for direct DEX token populations."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.reconstruct import event_order


ZERO_ADDRESS = "0x" + "00" * 20


def _row_dict(raw) -> dict:
    if is_dataclass(raw):
        return asdict(raw)
    return dict(raw)


def build_direct_supply_delta_rows(
    transfer_rows: Iterable[Mapping[str, object]],
) -> list[dict]:
    """Reduce ERC-20 Transfer rows to mint/burn total-supply deltas."""
    output = []
    seen: set[tuple[str, str, int]] = set()
    for raw in transfer_rows:
        row = _row_dict(raw)
        token = normalize_address(str(row["token"]))
        from_address = normalize_address(str(row["from_address"]))
        to_address = normalize_address(str(row["to_address"]))
        value = int(row["value_raw"])
        if value < 0:
            raise ValueError("ERC-20 supply delta value cannot be negative")
        is_mint = from_address == ZERO_ADDRESS
        is_burn = to_address == ZERO_ADDRESS
        if not is_mint and not is_burn:
            continue
        if is_mint and is_burn:
            delta = 0
        elif is_mint:
            delta = value
        else:
            delta = -value

        tx_hash = str(row["transaction_hash"]).lower()
        log_index = int(row["log_index"])
        key = (token, tx_hash, log_index)
        if key in seen:
            raise ValueError(
                f"duplicate direct supply delta event: {token} {tx_hash} {log_index}"
            )
        seen.add(key)
        output.append({
            "token": token,
            "from_address": from_address,
            "to_address": to_address,
            "value_raw": value,
            "supply_delta_raw": delta,
            "is_mint": is_mint,
            "is_burn": is_burn,
            "block_number": int(row["block_number"]),
            "transaction_hash": tx_hash,
            "transaction_index": row.get("transaction_index"),
            "log_index": log_index,
        })

    output.sort(
        key=lambda row: (
            event_order(row),
            row["token"],
        )
    )
    previous_by_token: dict[str, tuple[int, int, int]] = {}
    for row in output:
        token = row["token"]
        order = event_order(row)
        previous = previous_by_token.get(token)
        if previous is not None and order <= previous:
            raise ValueError(
                f"direct supply deltas are not strictly chronological: {token}"
            )
        previous_by_token[token] = order
    return output


class DirectSupplyTimeline:
    """Resolve event-time supply from block-end seeds plus mint/burn deltas."""

    def __init__(
        self,
        registry_rows: Iterable[Mapping[str, object]],
        supply_delta_rows: Iterable[Mapping[str, object]],
        *,
        seed_order: str = "initialize",
    ):
        seed_order = str(seed_order).strip().lower()
        if seed_order not in {"initialize", "initializer", "launch"}:
            raise ValueError(
                f"unsupported direct supply seed order: {seed_order!r}"
            )
        seed_label = {
            "initialize": "Initialize",
            "initializer": "Initializer",
            "launch": "launch",
        }[seed_order]
        deltas_by_token: dict[str, list[dict]] = {}
        for raw in supply_delta_rows:
            row = _row_dict(raw)
            token = normalize_address(str(row["token"]))
            delta = int(row["supply_delta_raw"])
            item = dict(row)
            item["token"] = token
            item["supply_delta_raw"] = delta
            deltas_by_token.setdefault(token, []).append(item)

        for token, rows in deltas_by_token.items():
            rows.sort(key=event_order)
            previous = None
            for row in rows:
                order = event_order(row)
                if previous is not None and order <= previous:
                    raise ValueError(
                        f"direct supply deltas repeat order for {token}"
                    )
                previous = order

        seeds_by_token: dict[str, list[dict]] = {}
        for raw in registry_rows:
            row = _row_dict(raw)
            token = normalize_address(str(row["token"]))
            raw_block = row.get(f"{seed_order}_block")
            raw_log = row.get(f"{seed_order}_log_index")
            if raw_block is None or raw_log is None:
                raise ValueError(
                    "direct supply registry lacks "
                    f"{seed_label} order: {token}"
                )
            raw_tx = row.get(f"{seed_order}_transaction_index")
            order = (
                int(raw_block),
                -1 if raw_tx is None else int(raw_tx),
                int(raw_log),
            )
            block_end_supply = int(row["supply_raw"])
            if block_end_supply <= 0:
                raise ValueError(
                    f"direct supply block-end seed is non-positive: {token}"
                )

            after_delta = sum(
                int(delta["supply_delta_raw"])
                for delta in deltas_by_token.get(token, [])
                if int(delta["block_number"]) == order[0]
                and event_order(delta) > order
            )
            event_supply = block_end_supply - after_delta
            if event_supply <= 0:
                raise ValueError(
                    f"derived {seed_label}-order supply is non-positive: {token}"
                )
            seeds_by_token.setdefault(token, []).append({
                "order": order,
                "event_supply_raw": event_supply,
                "block_end_supply_raw": block_end_supply,
            })

        if not seeds_by_token:
            raise ValueError("direct supply timeline has no registry seeds")

        self._state: dict[str, dict] = {}
        for token, seeds in seeds_by_token.items():
            seeds.sort(key=lambda row: row["order"])
            for left, right in zip(seeds, seeds[1:]):
                if left["order"] == right["order"] and (
                    left["event_supply_raw"] != right["event_supply_raw"]
                ):
                    raise ValueError(
                        f"direct supply seeds disagree at same order: {token}"
                    )
            first = seeds[0]
            updates = [
                row
                for row in deltas_by_token.get(token, [])
                if event_order(row) > first["order"]
            ]
            checks = []
            last_order = None
            for seed in seeds[1:]:
                if seed["order"] == last_order:
                    continue
                checks.append(seed)
                last_order = seed["order"]

            self._state[token] = {
                "supply": int(first["event_supply_raw"]),
                "order": first["order"],
                "updates": updates,
                "update_index": 0,
                "checks": checks,
                "check_index": 0,
                "seed_label": seed_label,
            }

    def _advance(self, token: str, target: tuple[int, int, int]) -> int:
        state = self._state.get(token)
        if state is None:
            raise KeyError(f"direct supply timeline has no token: {token}")
        if target < state["order"]:
            raise ValueError(
                f"direct supply target predates current state for {token}"
            )

        updates = state["updates"]
        checks = state["checks"]
        while True:
            update = (
                updates[state["update_index"]]
                if state["update_index"] < len(updates)
                else None
            )
            check = (
                checks[state["check_index"]]
                if state["check_index"] < len(checks)
                else None
            )
            update_order = None if update is None else event_order(update)
            check_order = None if check is None else check["order"]

            candidates = [
                order
                for order in (update_order, check_order)
                if order is not None and order <= target
            ]
            if not candidates:
                break
            next_order = min(candidates)

            if check_order is not None and check_order == next_order:
                expected = int(check["event_supply_raw"])
                if state["supply"] != expected:
                    raise ValueError(
                        "direct supply replay disagrees with later "
                        f"{state['seed_label']} seed for {token}: "
                        f"{state['supply']} != {expected}"
                    )
                state["check_index"] += 1
                state["order"] = next_order
                continue

            delta = int(update["supply_delta_raw"])
            state["supply"] += delta
            if state["supply"] <= 0:
                raise ValueError(
                    f"direct supply replay became non-positive: {token}"
                )
            state["update_index"] += 1
            state["order"] = next_order

        return int(state["supply"])

    def supply_at(
        self,
        token: str,
        order: tuple[int, int, int],
    ) -> int:
        token = normalize_address(token)
        return self._advance(token, order)
