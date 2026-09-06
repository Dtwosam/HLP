"""Causal USD quote timeline shared by market-path reconstructors."""

from __future__ import annotations

from decimal import Decimal
from heapq import merge
from typing import Iterable, Iterator

from hlp.config import ROBINHOOD_USDG, ROBINHOOD_WETH
from hlp.data.reconstruct import event_order


ZERO_ADDRESS = "0x" + "00" * 20


class QuoteUsdTimeline:
    """Resolve the latest already-observable USD price for quote assets."""

    def __init__(
        self,
        *,
        initial_weth_usd: Decimal,
        weth_anchor_points: Iterable[dict] = (),
        initial_quote_usd: dict[str, Decimal] | None = None,
        oracle_updates: Iterable[dict] = (),
    ):
        if initial_weth_usd <= 0:
            raise ValueError("initial_weth_usd must be positive")

        self._active: dict[str, Decimal] = {
            ROBINHOOD_WETH.lower(): initial_weth_usd,
            ZERO_ADDRESS: initial_weth_usd,
            ROBINHOOD_USDG.lower(): Decimal(1),
        }
        self._active_status: dict[str, str] = {
            ROBINHOOD_WETH.lower(): "priced_weth_usdg",
            ZERO_ADDRESS: "priced_weth_usdg",
            ROBINHOOD_USDG.lower(): "priced_usdg_nominal",
        }
        for token, price in (initial_quote_usd or {}).items():
            value = Decimal(price)
            if value <= 0:
                raise ValueError(f"initial USD price must be positive: {token}")
            normalized = token.lower()
            self._active[normalized] = value
            self._active_status[normalized] = "priced_chainlink_stock_token"

        def checked_source(
            rows: Iterable[dict],
            *,
            kind: str,
        ) -> Iterator[dict]:
            previous_key = None
            for source in rows:
                if kind == "weth_usdg_anchor":
                    price = Decimal(source["quote_per_token"])
                    if price <= 0:
                        raise ValueError("WETH/USD anchor must be positive")
                    row = {
                        "block_number": source["block_number"],
                        "transaction_index": source.get("transaction_index"),
                        "log_index": source["log_index"],
                        "quote_token": ROBINHOOD_WETH.lower(),
                        "usd_price": str(price),
                        "kind": kind,
                    }
                else:
                    price = Decimal(source["usd_price"])
                    if price <= 0:
                        raise ValueError("oracle USD price must be positive")
                    row = dict(source)

                key = (
                    event_order(row),
                    row["quote_token"].lower(),
                )
                if previous_key is not None and key < previous_key:
                    raise ValueError(f"{kind} USD tape is not chronological")
                previous_key = key
                yield row

        # Both source artifacts are already chronological. heapq.merge keeps
        # only the next row from each source in memory instead of sorting the
        # complete multi-year USD history for every lifecycle replay.
        self._updates = merge(
            checked_source(
                weth_anchor_points,
                kind="weth_usdg_anchor",
            ),
            checked_source(
                oracle_updates,
                kind="chainlink_oracle",
            ),
            key=lambda row: (
                event_order(row),
                row["quote_token"].lower(),
            ),
        )
        self._next = next(self._updates, None)
        self._last_target_order: tuple[int, int, int] | None = None

    def advance_to(self, order: tuple[int, int, int]) -> None:
        if self._last_target_order is not None and order < self._last_target_order:
            raise ValueError("quote USD timeline targets are not chronological")
        self._last_target_order = order

        while self._next is not None and event_order(self._next) <= order:
            token = self._next["quote_token"].lower()
            price = Decimal(self._next["usd_price"])
            self._active[token] = price
            status = self._next.get("pricing_status")
            if status is None:
                source = str(self._next.get("pricing_source") or "").lower()
                if "v4" in source:
                    status = "priced_v4_quote_fallback"
                elif "v3" in source:
                    status = "priced_v3_quote_fallback"
                elif token == ROBINHOOD_WETH.lower():
                    status = "priced_weth_usdg"
                elif token == ROBINHOOD_USDG.lower():
                    status = "priced_usdg_nominal"
                else:
                    status = "priced_chainlink_stock_token"
            self._active_status[token] = str(status)
            if token == ROBINHOOD_WETH.lower():
                self._active[ZERO_ADDRESS] = price
                self._active_status[ZERO_ADDRESS] = "priced_weth_usdg"
            self._next = next(self._updates, None)

    def price(self, quote_token: str) -> Decimal | None:
        return self._active.get(quote_token.lower())

    def pricing_status(self, quote_token: str) -> str:
        token = quote_token.lower()
        if token not in self._active:
            return "unsupported_quote"
        return self._active_status.get(
            token,
            "priced_chainlink_stock_token",
        )



def prepare_quote_usd_inputs(
    state_rows: Iterable[dict],
    update_groups: Iterable[Iterable[dict]],
) -> tuple[dict[str, Decimal], Iterator[dict]]:
    """Prepare causal quote/USD state without activating future sources early.

    State rows with activation_block become synthetic updates ordered before
    transaction zero of that activation block. State rows without an
    activation block are true pre-window state and remain immediately active.
    """
    initial: dict[str, Decimal] = {}
    activations: list[dict] = []
    seen: set[str] = set()

    for raw in state_rows:
        row = dict(raw)
        token = row["quote_token"].lower()
        if token in seen:
            raise ValueError(f"duplicate quote/USD activation state for {token}")
        seen.add(token)
        price = Decimal(row["usd_price"])
        if price <= 0:
            raise ValueError(f"quote/USD activation price must be positive: {token}")

        activation = row.get("activation_block")
        if activation is None:
            initial[token] = price
            continue
        activation = int(activation)
        if activation <= 0:
            raise ValueError(f"invalid quote/USD activation block for {token}")
        activations.append({
            **row,
            "quote_token": token,
            "block_number": activation,
            "transaction_index": None,
            "log_index": -1,
            "usd_price": str(price),
            "event_type": "quote_usd_activation",
        })

    activations.sort(
        key=lambda row: (event_order(row), row["quote_token"])
    )

    def checked(rows: Iterable[dict], source_index: int) -> Iterator[dict]:
        previous = None
        for raw in rows:
            row = dict(raw)
            row["quote_token"] = row["quote_token"].lower()
            key = (event_order(row), row["quote_token"])
            if previous is not None and key < previous:
                raise ValueError(
                    f"quote/USD update source {source_index} is not chronological"
                )
            previous = key
            yield row

    groups = [iter(activations)]
    groups.extend(
        checked(rows, index)
        for index, rows in enumerate(update_groups)
    )
    merged = merge(
        *groups,
        key=lambda row: (event_order(row), row["quote_token"]),
    )
    return initial, merged



def merge_quote_usd_tapes(
    source_pairs: Iterable[
        tuple[Iterable[dict], Iterable[dict]]
    ],
) -> tuple[list[dict], Iterator[dict]]:
    """Merge disjoint generic quote/USD sources without losing provenance."""
    pairs = list(source_pairs)
    owners: dict[str, int] = {}
    state_seen: set[str] = set()
    states: list[dict] = []
    update_groups = []

    for source_index, (state_rows, update_rows) in enumerate(pairs):
        for raw in state_rows:
            row = dict(raw)
            token = row["quote_token"].lower()
            if token in state_seen:
                raise ValueError(
                    f"duplicate quote/USD state across sources for {token}"
                )
            state_seen.add(token)
            owner = owners.get(token)
            if owner is not None and owner != source_index:
                raise ValueError(
                    f"quote/USD token has multiple source owners: {token}"
                )
            owners[token] = source_index
            row["quote_token"] = token
            states.append(row)

        def checked_updates(
            rows: Iterable[dict],
            *,
            index: int = source_index,
        ) -> Iterator[dict]:
            previous = None
            for raw_update in rows:
                row = dict(raw_update)
                token = row["quote_token"].lower()
                row["quote_token"] = token
                key = (event_order(row), token)
                if previous is not None and key < previous:
                    raise ValueError(
                        f"quote/USD source {index} is not chronological"
                    )
                previous = key

                owner = owners.get(token)
                if owner is None:
                    owners[token] = index
                elif owner != index:
                    raise ValueError(
                        f"quote/USD token appears in multiple sources: {token}"
                    )
                yield row

        update_groups.append(checked_updates(update_rows))

    states.sort(
        key=lambda row: (
            int(row["activation_block"] if row.get("activation_block") is not None else row.get("block_number", -1)),
            row["quote_token"],
        )
    )

    merged = merge(
        *update_groups,
        key=lambda row: (event_order(row), row["quote_token"]),
    )

    def unique_updates() -> Iterator[dict]:
        previous = None
        for row in merged:
            key = (event_order(row), row["quote_token"])
            if previous == key:
                raise ValueError(
                    "duplicate quote/USD update order across sources: "
                    f"{key}"
                )
            previous = key
            yield row

    return states, unique_updates()
