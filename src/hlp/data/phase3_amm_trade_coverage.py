"""Reusable Phase-3 V3/V4 AMM trade coverage materializer."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_trade_adapters import (
    adapt_v3_swaps_to_phase3,
    adapt_v4_swaps_to_phase3,
)
from hlp.data.phase3_trade_source_plan import (
    V3_SOURCES,
    V4_SOURCES,
)
from hlp.data.phase3_trade_tape import (
    build_phase3_trade_source_coverage,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_AMM_TRADE_COVERAGE_VERSION = (
    "phase3-amm-trade-coverage-v1"
)


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int, str]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    tx_hash = str(row.get("transaction_hash") or "").lower()
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 AMM event position is invalid")
    return block, tx, log, tx_hash


def _market_key(source_id: str) -> str:
    if source_id in V3_SOURCES:
        return "pool"
    if source_id in V4_SOURCES:
        return "pool_id"
    raise ValueError(f"unsupported Phase-3 AMM source: {source_id}")


def materialize_phase3_amm_trade_coverage(
    *,
    source_id: str,
    eligible_tokens: Iterable[str],
    market_rows: Iterable[Mapping[str, object]],
    raw_swap_rows: Iterable[Mapping[str, object]],
    transaction_rows: Iterable[Mapping[str, object]],
    snapshot_head_block: int,
    raw_scan_complete: bool,
    raw_output: Path,
    market_output: Path,
    wallet_identity_output: Path,
    canonical_output: Path,
    coverage_output: Path,
) -> dict:
    """Build one complete AMM source artifact from exact raw evidence."""

    key_field = _market_key(source_id)
    snapshot = int(snapshot_head_block)
    if snapshot <= 0:
        raise ValueError("Phase-3 AMM snapshot is invalid")
    if raw_scan_complete is not True:
        raise ValueError("Phase-3 AMM raw historical scan is incomplete")

    eligible = {
        normalize_address(str(token))
        for token in eligible_tokens
    }
    if not eligible:
        raise ValueError(f"{source_id} Phase-3 AMM eligible set is empty")

    markets = []
    market_ids = set()
    market_tokens = set()
    for raw in market_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token not in eligible:
            continue
        market_id = str(row.get(key_field) or "").lower()
        if not market_id:
            raise ValueError(
                f"{source_id} Phase-3 AMM market id is empty"
            )
        if market_id in market_ids:
            raise ValueError(
                f"{source_id} Phase-3 AMM market repeats: {market_id}"
            )
        if token in market_tokens:
            raise ValueError(
                f"{source_id} Phase-3 AMM token has multiple markets: "
                f"{token}"
            )
        quote = normalize_address(str(row.get("quote_token") or ""))
        if quote == token:
            raise ValueError(
                f"{source_id} Phase-3 AMM token/quote identity invalid"
            )
        row["token"] = token
        row["quote_token"] = quote
        row[key_field] = market_id
        market_ids.add(market_id)
        market_tokens.add(token)
        markets.append(row)
    if market_tokens != eligible:
        raise ValueError(
            f"{source_id} Phase-3 AMM market membership drift: "
            f"missing={sorted(eligible - market_tokens)[:10]} "
            f"extra={sorted(market_tokens - eligible)[:10]}"
        )
    markets.sort(
        key=lambda row: (
            str(row[key_field]),
            str(row["token"]),
        )
    )
    market_manifest = write_jsonl_snapshot(
        markets,
        output=market_output,
        provenance={
            "version": PHASE3_AMM_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "market_key": key_field,
            "eligible_tokens": len(eligible),
            "snapshot_head_block": snapshot,
            "exact_frozen_source_membership": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    swaps = []
    seen_events = set()
    previous = None
    for raw in raw_swap_rows:
        row = dict(raw)
        market_id = str(row.get(key_field) or "").lower()
        if market_id not in market_ids:
            continue
        event = _event_key(row)
        if event[0] > snapshot:
            raise ValueError(
                f"{source_id} Phase-3 AMM swap after snapshot"
            )
        if previous is not None and event < previous:
            raise ValueError(
                f"{source_id} Phase-3 AMM raw swaps are not chronological"
            )
        previous = event
        identity = (
            market_id,
            event[0],
            event[1],
            event[2],
            event[3],
        )
        if identity in seen_events:
            raise ValueError(
                f"{source_id} Phase-3 AMM raw swap repeats: {identity}"
            )
        seen_events.add(identity)
        row[key_field] = market_id
        swaps.append(row)
    swaps.sort(
        key=lambda row: (
            *_event_key(row),
            str(row[key_field]),
        )
    )
    raw_manifest = write_jsonl_snapshot(
        swaps,
        output=raw_output,
        provenance={
            "version": PHASE3_AMM_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "snapshot_head_block": snapshot,
            "market_registry_sha256": market_manifest["sha256"],
            "historical_event_scan_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    required_hashes = {
        str(row["transaction_hash"]).lower()
        for row in swaps
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
            "version": PHASE3_AMM_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "wallet_identity_kind": "transaction_from",
            "required_transactions": len(required_hashes),
            "wallet_identity_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    if source_id in V3_SOURCES:
        canonical = adapt_v3_swaps_to_phase3(
            swaps,
            markets,
            identity_rows,
            source_id=source_id,
        )
    else:
        canonical = adapt_v4_swaps_to_phase3(
            swaps,
            markets,
            identity_rows,
            source_id=source_id,
        )
    canonical_manifest = write_jsonl_snapshot(
        canonical,
        output=canonical_output,
        provenance={
            "version": PHASE3_AMM_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "market_registry_sha256": market_manifest["sha256"],
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
        market_registry_sha256=market_manifest["sha256"],
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
            "version": PHASE3_AMM_TRADE_COVERAGE_VERSION,
            "source_id": source_id,
            "market_registry_sha256": market_manifest["sha256"],
            "raw_trade_tape_sha256": raw_manifest["sha256"],
            "wallet_identity_sha256": wallet_manifest["sha256"],
            "canonical_trade_rows_sha256": canonical_manifest["sha256"],
            "trade_coverage_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )
    return {
        "version": PHASE3_AMM_TRADE_COVERAGE_VERSION,
        "source_id": source_id,
        "snapshot_head_block": snapshot,
        "eligible_tokens": len(eligible),
        "market_rows": int(market_manifest["records"]),
        "market_registry_sha256": market_manifest["sha256"],
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
        "phase3_amm_trade_coverage_ready": True,
    }
