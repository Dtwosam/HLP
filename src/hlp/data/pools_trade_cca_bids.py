"""Fail-closed reconciliation of pools.trade CCA bids into executed fills."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from hlp.data.types import CcaBidExited, CcaBidSubmitted


CCA_FILL_VERSION = "pools-trade-cca-fill-v1"


def reconcile_cca_bid_fills(
    submitted_rows: Iterable[CcaBidSubmitted],
    exited_rows: Iterable[CcaBidExited],
) -> tuple[list[dict], dict]:
    """Join bid escrow to finalized exit accounting without inventing fills."""

    submissions: dict[tuple[str, int], CcaBidSubmitted] = {}
    for row in submitted_rows:
        key = (row.auction.lower(), int(row.bid_id))
        if key in submissions:
            raise ValueError(f"duplicate CCA bid submission: {key}")
        submissions[key] = row

    exits: dict[tuple[str, int], CcaBidExited] = {}
    for row in exited_rows:
        key = (row.auction.lower(), int(row.bid_id))
        if key in exits:
            raise ValueError(f"duplicate CCA bid exit: {key}")
        exits[key] = row

    unknown_exits = sorted(set(exits) - set(submissions))
    if unknown_exits:
        raise ValueError(
            f"CCA exits lack matching submissions: {unknown_exits[:20]}"
        )

    fills = []
    refunded_bids = 0
    for key in sorted(set(submissions) & set(exits)):
        submitted = submissions[key]
        exited = exits[key]
        if submitted.owner.lower() != exited.owner.lower():
            raise ValueError(f"CCA bid owner drift: {key}")
        if int(exited.currency_refunded_raw) > int(submitted.amount_raw):
            raise ValueError(f"CCA refund exceeds submitted amount: {key}")

        currency_spent = (
            int(submitted.amount_raw) - int(exited.currency_refunded_raw)
        )
        tokens_filled = int(exited.tokens_filled_raw)
        if (currency_spent == 0) != (tokens_filled == 0):
            raise ValueError(
                f"CCA filled-token/currency-spent mismatch: {key}"
            )
        if tokens_filled == 0:
            refunded_bids += 1
            continue

        fills.append({
            "version": CCA_FILL_VERSION,
            "auction": submitted.auction.lower(),
            "bid_id": int(submitted.bid_id),
            "owner": submitted.owner.lower(),
            "max_price_q96": int(submitted.price_q96),
            "currency_amount_submitted_raw": int(submitted.amount_raw),
            "currency_refunded_raw": int(exited.currency_refunded_raw),
            "quote_amount_raw": currency_spent,
            "token_amount_raw": tokens_filled,
            "bid_block_number": int(submitted.block_number),
            "bid_transaction_hash": submitted.transaction_hash.lower(),
            "bid_transaction_index": submitted.transaction_index,
            "bid_log_index": int(submitted.log_index),
            "exit_block_number": int(exited.block_number),
            "exit_transaction_hash": exited.transaction_hash.lower(),
            "exit_transaction_index": exited.transaction_index,
            "exit_log_index": int(exited.log_index),
            "finalized_fill": True,
            "outcome_derived": False,
        })

    unresolved = sorted(set(submissions) - set(exits))
    summary = {
        "version": CCA_FILL_VERSION,
        "submitted_bids": len(submissions),
        "exited_bids": len(exits),
        "executed_fills": len(fills),
        "fully_refunded_bids": refunded_bids,
        "unresolved_bids": len(unresolved),
        "unresolved_bid_keys": [
            {"auction": auction, "bid_id": bid_id}
            for auction, bid_id in unresolved
        ],
        "wallet_identity_source": "BidSubmitted.owner",
        "fill_amount_source": "BidExited.tokensFilled",
        "currency_spent_formula": "submitted_amount_minus_currency_refunded",
        "complete_fill_attribution": bool(submissions) and not unresolved,
        "future_state_allowed": False,
        "outcome_dependency_allowed": False,
    }
    return fills, summary
