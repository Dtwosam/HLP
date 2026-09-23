"""Fail-closed reconciliation of pools.trade CCA bids into executed fills."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from hlp.data.types import CcaBidExited, CcaBidSubmitted


CCA_FILL_VERSION = "pools-trade-cca-fill-v1"
PHASE3_CCA_FILL_BACKFILL_VERSION = (
    "phase3-pools-trade-cca-fill-backfill-v1"
)
PHASE3_CCA_FILL_HANDOFF_VERSION = (
    "phase3-pools-trade-cca-fill-handoff-v1"
)


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


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



def build_phase3_cca_fill_handoff(
    summary: dict,
    *,
    summary_sha256: str,
) -> dict:
    """Freeze complete CCA fill attribution for Phase-3 source coverage."""

    row = dict(summary)
    if str(row.get("version") or "") != PHASE3_CCA_FILL_BACKFILL_VERSION:
        raise ValueError("Phase-3 CCA fill summary version changed")
    if row.get("source_id") != "pools_trade_lbp":
        raise ValueError("Phase-3 CCA fill source changed")
    if row.get("wallet_identity_kind") != "cca_bid_owner":
        raise ValueError("Phase-3 CCA wallet identity kind changed")
    if str(row.get("wallet_identity_source") or "") != "BidSubmitted.owner":
        raise ValueError("Phase-3 CCA wallet identity source changed")
    for flag in (
        "historical_event_scan_complete",
        "complete_fill_attribution",
        "canonical_trade_adapter_complete",
        "source_membership_bound_to_phase2_registry",
        "phase3_cca_fill_backfill_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-3 CCA fill handoff lacks {flag}")
    if row.get("source_coverage_complete") is not False:
        raise ValueError(
            "Phase-3 CCA fill artifact cannot claim source coverage"
        )
    for flag in (
        "outcome_rows_consumed",
        "future_state_allowed",
    ):
        if row.get(flag) is not False:
            raise ValueError(
                f"Phase-3 CCA fill handoff violates {flag}"
            )
    if int(row.get("unresolved_bids", -1)) != 0:
        raise ValueError("Phase-3 CCA fill attribution is unresolved")
    if int(row.get("registered_initializers", 0)) <= 0:
        raise ValueError("Phase-3 CCA fill registry is empty")
    submitted = int(row.get("submitted_bids", -1))
    exited = int(row.get("exited_bids", -1))
    fills = int(row.get("executed_fills", -1))
    refunded = int(row.get("fully_refunded_bids", -1))
    canonical = int(row.get("canonical_trade_rows", -1))
    if min(submitted, exited, fills, refunded, canonical) < 0:
        raise ValueError("Phase-3 CCA fill counts are invalid")
    if exited != submitted:
        raise ValueError("Phase-3 CCA submitted/exited bid count drift")
    if fills + refunded != submitted:
        raise ValueError("Phase-3 CCA fill/refund accounting drift")
    if canonical != fills:
        raise ValueError("Phase-3 CCA canonical trade count drift")

    return {
        "version": PHASE3_CCA_FILL_HANDOFF_VERSION,
        "source_id": "pools_trade_lbp",
        "registry_run_id": int(row["registry_run_id"]),
        "registry_artifact_digest": str(
            row["registry_artifact_digest"]
        ).lower(),
        "registry_sha256": _sha256(
            row.get("registry_sha256"),
            label="Phase-3 CCA registry",
        ),
        "submitted_sharded_sha256": _sha256(
            row.get("submitted_sharded_sha256"),
            label="Phase-3 CCA submissions",
        ),
        "exited_sharded_sha256": _sha256(
            row.get("exited_sharded_sha256"),
            label="Phase-3 CCA exits",
        ),
        "finalized_fills_sha256": _sha256(
            row.get("finalized_fills_sha256"),
            label="Phase-3 CCA finalized fills",
        ),
        "canonical_trade_rows_sha256": _sha256(
            row.get("canonical_trade_rows_sha256"),
            label="Phase-3 CCA canonical trades",
        ),
        "summary_sha256": _sha256(
            summary_sha256,
            label="Phase-3 CCA fill summary",
        ),
        "registered_initializers": int(
            row["registered_initializers"]
        ),
        "required_start_block": int(row["required_start_block"]),
        "snapshot_head_block": int(row["snapshot_head_block"]),
        "submitted_bids": submitted,
        "exited_bids": exited,
        "executed_fills": fills,
        "fully_refunded_bids": refunded,
        "unresolved_bids": 0,
        "canonical_trade_rows": canonical,
        "wallet_identity_kind": "cca_bid_owner",
        "wallet_identity_source": "BidSubmitted.owner",
        "historical_event_scan_complete": True,
        "complete_fill_attribution": True,
        "canonical_trade_adapter_complete": True,
        "source_membership_bound_to_phase2_registry": True,
        "source_coverage_complete": False,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_cca_fill_backfill_ready": True,
    }
