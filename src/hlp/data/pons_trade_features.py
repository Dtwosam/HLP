"""Causal wallet-participation features for normalized Pons trades."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from hlp.data.reconstruct import event_order


def build_pons_causal_trade_features(
    trades: Iterable[dict],
) -> list[dict]:
    """Annotate each trade using only same-token history observable beforehand.

    No fixed time windows or drawdown thresholds are used here. Each row
    carries cumulative state that a live system could have known immediately
    after that trade.
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for source in trades:
        grouped[source["token"].lower()].append(dict(source))

    output: list[dict] = []
    for token, rows in grouped.items():
        rows.sort(key=event_order)

        trader_trade_count: dict[str, int] = defaultdict(int)
        trader_buy_count: dict[str, int] = defaultdict(int)
        trader_sell_count: dict[str, int] = defaultdict(int)
        buyers: set[str] = set()
        sellers: set[str] = set()
        traders: set[str] = set()
        buy_trades = 0
        sell_trades = 0
        consecutive_side = None
        consecutive_side_count = 0

        first_timestamp = None
        for index, row in enumerate(rows, start=1):
            initiator = row["initiator"].lower()
            side = row["side"]

            prior_trade_count = trader_trade_count[initiator]
            prior_buy_count = trader_buy_count[initiator]
            prior_sell_count = trader_sell_count[initiator]
            was_known_trader = initiator in traders
            was_known_buyer = initiator in buyers
            was_known_seller = initiator in sellers

            trader_trade_count[initiator] += 1
            traders.add(initiator)
            if side == "buy":
                trader_buy_count[initiator] += 1
                buyers.add(initiator)
                buy_trades += 1
            elif side == "sell":
                trader_sell_count[initiator] += 1
                sellers.add(initiator)
                sell_trades += 1
            else:
                raise ValueError(f"unknown Pons normalized trade side: {side}")

            if side == consecutive_side:
                consecutive_side_count += 1
            else:
                consecutive_side = side
                consecutive_side_count = 1

            timestamp = row.get("block_timestamp")
            if timestamp is not None:
                timestamp = int(timestamp)
                if first_timestamp is None:
                    first_timestamp = timestamp
                seconds_since_first_trade = timestamp - first_timestamp
                if seconds_since_first_trade < 0:
                    raise ValueError("Pons trade timestamps are not chronological")
            else:
                seconds_since_first_trade = None

            total_trades = buy_trades + sell_trades
            out = dict(row)
            out.update(
                {
                    "token_trade_number": index,
                    "wallet_prior_trade_count": prior_trade_count,
                    "wallet_trade_number": trader_trade_count[initiator],
                    "wallet_prior_buy_count": prior_buy_count,
                    "wallet_prior_sell_count": prior_sell_count,
                    "wallet_buy_number": (
                        trader_buy_count[initiator] if side == "buy" else None
                    ),
                    "wallet_sell_number": (
                        trader_sell_count[initiator] if side == "sell" else None
                    ),
                    "is_new_trader": not was_known_trader,
                    "is_new_buyer": side == "buy" and not was_known_buyer,
                    "is_repeat_buyer": side == "buy" and was_known_buyer,
                    "is_new_seller": side == "sell" and not was_known_seller,
                    "is_repeat_seller": side == "sell" and was_known_seller,
                    "unique_traders_so_far": len(traders),
                    "unique_buyers_so_far": len(buyers),
                    "unique_sellers_so_far": len(sellers),
                    "buy_trades_so_far": buy_trades,
                    "sell_trades_so_far": sell_trades,
                    "buy_trade_share_so_far": str(
                        Decimal(buy_trades) / Decimal(total_trades)
                    ),
                    "repeat_buyer_trade_share_so_far": str(
                        Decimal(
                            sum(max(0, value - 1) for value in trader_buy_count.values())
                        )
                        / Decimal(buy_trades)
                        if buy_trades
                        else Decimal(0)
                    ),
                    "current_side_streak": side,
                    "current_side_streak_trades": consecutive_side_count,
                    "seconds_since_first_trade": seconds_since_first_trade,
                }
            )
            output.append(out)

    output.sort(key=lambda row: (event_order(row), row["token"]))
    return output
