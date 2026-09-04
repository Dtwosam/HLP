"""Normalize Pons V1/V2 market events into wallet-level trade rows."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from hlp.data.reconstruct import event_order


NON_TRADE_EVENT_TYPES = {
    "curve_initialized",
    "pool_graduated",
    "v4_initialize",
}


def _signed_amm_trade(row: dict) -> tuple[str, int, int]:
    token = row["token"].lower()
    quote = row["quote_token"].lower()
    token_is_token0 = int(token, 16) < int(quote, 16)

    if "amount0" not in row or "amount1" not in row:
        raise KeyError(
            f"AMM Pons trade missing amount0/amount1: {row['transaction_hash']}"
        )
    token_leg = int(row["amount0"] if token_is_token0 else row["amount1"])
    quote_leg = int(row["amount1"] if token_is_token0 else row["amount0"])
    if token_leg == 0 or quote_leg == 0:
        raise ValueError("Pons AMM swap contains zero trade leg")

    # Uniswap pool accounting: positive amount is paid into the pool and
    # negative amount leaves the pool. A buyer receives Pons token from pool.
    side = "buy" if token_leg < 0 else "sell"
    if side == "buy" and quote_leg <= 0:
        raise ValueError("Pons buy has non-positive quote input")
    if side == "sell" and quote_leg >= 0:
        raise ValueError("Pons sell has non-negative quote output")
    return side, abs(token_leg), abs(quote_leg)


def normalize_pons_trades(points: Iterable[dict]) -> list[dict]:
    """Return one common trade schema across Pons V1, V2 curve and V4."""
    output = []
    for source in points:
        row = dict(source)
        event_type = row.get("event_type")
        if event_type in NON_TRADE_EVENT_TYPES:
            continue
        if "initiator" not in row:
            raise KeyError("Pons point is missing transaction initiator")

        phase = row["phase"]
        if phase == "curve":
            if event_type not in {"curve_buy", "curve_sell"}:
                # Buyback is a protocol-internal price-changing action rather
                # than a user's directional trade. Keep it out of wallet flow.
                if event_type == "curve_buyback":
                    continue
                raise ValueError(f"unknown Pons curve trade event: {event_type}")
            side = "buy" if event_type == "curve_buy" else "sell"
            token_amount_raw = int(row["token_amount"])
            quote_amount_raw = int(row["quote_amount"])
            fee_raw = int(row.get("fee") or 0)
            tax_raw = int(row.get("tax") or 0)
        elif phase in {"v3", "v4"}:
            side, token_amount_raw, quote_amount_raw = _signed_amm_trade(row)
            fee_raw = None
            tax_raw = None
        elif phase == "v4_seed":
            continue
        else:
            raise ValueError(f"unsupported Pons trade phase: {phase}")

        if token_amount_raw <= 0 or quote_amount_raw <= 0:
            raise ValueError("Pons normalized trade amounts must be positive")

        market_cap = Decimal(row["market_cap_proxy_usd"])
        output.append(
            {
                "token": row["token"].lower(),
                "pons_version": row["pons_version"],
                "phase": phase,
                "side": side,
                "initiator": row["initiator"].lower(),
                "transaction_hash": row["transaction_hash"].lower(),
                "transaction_to": row.get("transaction_to"),
                "input_selector": row.get("input_selector"),
                "block_number": int(row["block_number"]),
                "block_timestamp": row.get("block_timestamp"),
                "transaction_index": row.get("transaction_index"),
                "log_index": int(row["log_index"]),
                "token_amount_raw": token_amount_raw,
                "quote_amount_raw": quote_amount_raw,
                "fee_raw": fee_raw,
                "tax_raw": tax_raw,
                "quote_token": row["quote_token"].lower(),
                "market_cap_proxy_usd": str(market_cap),
                "drawdown_from_running_peak": row.get(
                    "drawdown_from_running_peak"
                ),
                "seconds_since_first_priced_point": row.get(
                    "seconds_since_first_priced_point"
                ),
            }
        )

    output.sort(key=lambda row: (event_order(row), row["token"]))
    return output
