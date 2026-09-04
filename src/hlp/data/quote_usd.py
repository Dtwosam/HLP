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
        for token, price in (initial_quote_usd or {}).items():
            value = Decimal(price)
            if value <= 0:
                raise ValueError(f"initial USD price must be positive: {token}")
            self._active[token.lower()] = value

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
            if token == ROBINHOOD_WETH.lower():
                self._active[ZERO_ADDRESS] = price
            self._next = next(self._updates, None)

    def price(self, quote_token: str) -> Decimal | None:
        return self._active.get(quote_token.lower())

    def pricing_status(self, quote_token: str) -> str:
        token = quote_token.lower()
        if token in {ZERO_ADDRESS, ROBINHOOD_WETH.lower()}:
            return "priced_weth_usdg"
        if token == ROBINHOOD_USDG.lower():
            return "priced_usdg_nominal"
        if token in self._active:
            return "priced_chainlink_stock_token"
        return "unsupported_quote"
