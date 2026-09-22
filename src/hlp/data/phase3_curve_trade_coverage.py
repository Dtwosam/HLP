"""Reusable Phase-3 native bonding-curve trade coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_trade_adapters import (
    adapt_flap_trades_to_phase3,
    adapt_hood_fun_trades_to_phase3,
    adapt_trench_trades_to_phase3,
)
from hlp.data.phase3_trade_source_plan import CURVE_SOURCES
from hlp.data.phase3_trade_tape import (
    build_phase3_trade_source_coverage,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_CURVE_TRADE_COVERAGE_VERSION = (
    "phase3-curve-trade-coverage-v1"
)


TRADE_EVENT_TYPES = {
    "flap": frozenset({"token_bought", "token_sold"}),
    "hood_fun_current": frozenset({"trade"}),
    "hood_fun_previous": frozenset({"trade"}),
    "trench_today": frozenset({"token_purchase", "token_sale"}),
}


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int, str]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    tx_hash = str(row.get("transaction_hash") or "").lower()
    if (
        block < 0
        or tx < -1
        or log < 0
        or not tx_hash.startswith("0x")
        or len(tx_hash) != 66
    ):
        raise ValueError("Phase-3 curve trade event position is invalid")
    return block, tx, log, tx_hash


def materialize_phase3_curve_trade_coverage(
    *,
    source_id: str,
    eligible_tokens: Iterable[str],
    registry_rows: Iterable[Mapping[str, object]],
    event_rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
    snapshot_head_block: int,
    historical_event_scan_complete: bool,
    raw_output: Path,
    registry_output: Path,
    wallet_identity_output: Path,
    canonical_output: Path,
    coverage_output: Path,
) -> dict:
    """Build one complete native-curve source coverage artifact."""

    if source_id not in CURVE_SOURCES:
        raise ValueError(
            f"unsupported Phase-3 curve source: {source_id}"
        )
    if historical_event_scan_complete is not True:
        raise ValueError(
            f"{source_id} historical curve-event scan is incomplete"
        )
    snapshot = int(snapshot_head_block)
    if snapshot <= 0:
        raise ValueError("Phase-3 curve snapshot is invalid")

    eligible = {
        normalize_address(str(token))
        for token in eligible_tokens
    }
    if not eligible:
        raise ValueError(
            f"{source_id} Phase-3 curve eligible set is empty"
        )

    registry = []
    registry_by_token = {}
    for raw in registry_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token not in eligible:
            continue
        if token in registry_by_token:
            raise ValueError(
                f"{source_id} Phase-3 registry repeats token: {token}"
            )
        if source_id.startswith("hood_fun_"):
            expected_generation = (
                "current"
                if source_id == "hood_fun_current"
                else "previous"
            )
            if str(row.get("generation") or "") != expected_generation:
                raise ValueError(
                    f"{source_id} registry generation drift: {token}"
                )
        quote = row.get("quote_token")
        if quote is not None:
            row["quote_token"] = normalize_address(str(quote))
        row["token"] = token
        registry_by_token[token] = row
        registry.append(row)
    if set(registry_by_token) != eligible:
        raise ValueError(
            f"{source_id} registry/frozen-universe membership drift: "
            f"missing={sorted(eligible - set(registry_by_token))[:10]}"
        )
    registry.sort(key=lambda row: row["token"])
    registry_manifest = write_jsonl_snapshot(
        registry,
        output=registry_output,
        provenance={
            "version": PHASE3_CURVE_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "eligible_tokens": len(eligible),
            "snapshot_head_block": snapshot,
            "exact_frozen_source_membership": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    allowed_events = TRADE_EVENT_TYPES[source_id]
    events = []
    seen_events = set()
    for raw in event_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token not in eligible:
            continue
        if str(row.get("event_type") or "") not in allowed_events:
            continue
        event = _event_key(row)
        if event[0] > snapshot:
            raise ValueError(
                f"{source_id} curve trade is after snapshot"
            )
        identity = (
            token,
            event[0],
            event[1],
            event[2],
            event[3],
        )
        if identity in seen_events:
            raise ValueError(
                f"{source_id} curve trade repeats: {identity}"
            )
        seen_events.add(identity)
        row["token"] = token
        events.append(row)
    events.sort(
        key=lambda row: (
            *_event_key(row),
            row["token"],
        )
    )
    raw_manifest = write_jsonl_snapshot(
        events,
        output=raw_output,
        provenance={
            "version": PHASE3_CURVE_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "market_registry_sha256": registry_manifest["sha256"],
            "snapshot_head_block": snapshot,
            "historical_event_scan_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    required_hashes = {
        str(row["transaction_hash"]).lower()
        for row in events
    }
    identities = {}
    for raw in transaction_rows:
        row = dict(raw)
        tx_hash = str(row.get("transaction_hash") or "").lower()
        if tx_hash not in required_hashes:
            continue
        if tx_hash in identities:
            raise ValueError(
                f"{source_id} transaction identity repeats: {tx_hash}"
            )
        block = row.get("block_number")
        if block is not None and int(block) > snapshot:
            raise ValueError(
                f"{source_id} transaction identity is after snapshot"
            )
        identities[tx_hash] = row
    if set(identities) != required_hashes:
        missing = sorted(required_hashes - set(identities))
        raise ValueError(
            f"{source_id} transaction identity coverage incomplete: "
            f"{missing[:10]}"
        )
    identity_rows = [
        identities[tx_hash]
        for tx_hash in sorted(identities)
    ]
    wallet_manifest = write_jsonl_snapshot(
        identity_rows,
        output=wallet_identity_output,
        provenance={
            "version": PHASE3_CURVE_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "wallet_identity_kind": "transaction_from",
            "required_transactions": len(required_hashes),
            "wallet_identity_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    if source_id == "flap":
        canonical = adapt_flap_trades_to_phase3(
            events,
            identity_rows,
        )
    elif source_id in {
        "hood_fun_current",
        "hood_fun_previous",
    }:
        canonical = adapt_hood_fun_trades_to_phase3(
            events,
            identity_rows,
            source_id=source_id,
        )
    else:
        canonical = adapt_trench_trades_to_phase3(
            events,
            registry,
            identity_rows,
        )

    canonical_manifest = write_jsonl_snapshot(
        canonical,
        output=canonical_output,
        provenance={
            "version": PHASE3_CURVE_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "market_registry_sha256": registry_manifest["sha256"],
            "raw_trade_tape_sha256": raw_manifest["sha256"],
            "wallet_identity_sha256": wallet_manifest["sha256"],
            "wallet_identity_kind": "transaction_from",
            "historical_event_scan_complete": True,
            "canonical_trade_adapter_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    coverage = build_phase3_trade_source_coverage(
        source_id,
        canonical,
        eligible_tokens=eligible,
        snapshot_head_block=snapshot,
        market_registry_sha256=registry_manifest["sha256"],
        raw_trade_tape_sha256=raw_manifest["sha256"],
        raw_trade_rows=int(raw_manifest["records"]),
        wallet_identity_sha256=wallet_manifest["sha256"],
        wallet_identity_kind="transaction_from",
        historical_event_scan_complete=True,
        wallet_identity_complete=True,
        canonical_trade_adapter_complete=True,
    )
    if coverage["canonical_trade_rows_sha256"] != (
        canonical_manifest["sha256"]
    ):
        raise ValueError(
            f"{source_id} canonical coverage SHA disagrees with manifest"
        )
    coverage_manifest = write_jsonl_snapshot(
        [coverage],
        output=coverage_output,
        provenance={
            "version": PHASE3_CURVE_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "market_registry_sha256": registry_manifest["sha256"],
            "raw_trade_tape_sha256": raw_manifest["sha256"],
            "wallet_identity_sha256": wallet_manifest["sha256"],
            "canonical_trade_rows_sha256": canonical_manifest["sha256"],
            "trade_coverage_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )
    return {
        "version": PHASE3_CURVE_TRADE_COVERAGE_VERSION,
        "source_id": source_id,
        "snapshot_head_block": snapshot,
        "eligible_tokens": len(eligible),
        "registry_rows": int(registry_manifest["records"]),
        "market_registry_sha256": registry_manifest["sha256"],
        "raw_trade_rows": int(raw_manifest["records"]),
        "raw_trade_tape_sha256": raw_manifest["sha256"],
        "wallet_identity_rows": int(wallet_manifest["records"]),
        "wallet_identity_sha256": wallet_manifest["sha256"],
        "wallet_identity_kind": "transaction_from",
        "canonical_trade_rows": int(canonical_manifest["records"]),
        "canonical_trade_rows_sha256": canonical_manifest["sha256"],
        "coverage_rows_sha256": coverage_manifest["sha256"],
        "historical_event_scan_complete": True,
        "wallet_identity_complete": True,
        "canonical_trade_adapter_complete": True,
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_curve_trade_coverage_ready": True,
    }
