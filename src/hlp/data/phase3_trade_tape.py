"""Fail-closed Phase-3 canonical trade-tape coverage and assembly."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_sources import build_phase2_source_inventory
from hlp.data.phase3_feature_entry import (
    PHASE3_FEATURE_ENTRY_HANDOFF_VERSION,
)
from hlp.data.phase3_trade_source_plan import (
    build_phase3_trade_source_plan,
)
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
    PHASE3_CANONICAL_TRADE_VERSION,
    validate_phase3_canonical_trade_row,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_TRADE_SOURCE_COVERAGE_VERSION = (
    "phase3-trade-source-coverage-v1"
)
PHASE3_CANONICAL_TRADE_TAPE_VERSION = (
    "phase3-canonical-trade-tape-v1"
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


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 canonical trade event position is invalid")
    return block, tx, log


def _jsonl_sha(rows: Iterable[Mapping[str, object]]) -> tuple[int, str]:
    count = 0
    digest = hashlib.sha256()
    for raw in rows:
        line = (
            json.dumps(
                dict(raw),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        digest.update(line)
        count += 1
    return count, digest.hexdigest()


def _token_set_sha(tokens: Iterable[str]) -> str:
    normalized = sorted({
        normalize_address(str(token))
        for token in tokens
    })
    payload = (
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def build_phase3_trade_source_coverage(
    source_id: str,
    canonical_trade_rows: Iterable[Mapping[str, object]],
    *,
    eligible_tokens: Iterable[str],
    snapshot_head_block: int,
    market_registry_sha256: str,
    raw_trade_tape_sha256: str,
    raw_trade_rows: int,
    wallet_identity_sha256: str,
    wallet_identity_kind: str,
    historical_event_scan_complete: bool,
    wallet_identity_complete: bool,
    canonical_trade_adapter_complete: bool,
) -> dict:
    """Bind one source's canonical trades to complete historical evidence."""

    inventory = {
        str(row["source_id"]): dict(row)
        for row in build_phase2_source_inventory()
    }
    source = inventory.get(str(source_id))
    plan = {
        str(row["source_id"]): dict(row)
        for row in build_phase3_trade_source_plan()
    }
    source_plan = plan.get(str(source_id))
    if source is None or source_plan is None:
        raise ValueError(
            f"unknown Phase-3 trade coverage source: {source_id}"
        )
    snapshot = int(snapshot_head_block)
    if snapshot <= 0:
        raise ValueError("Phase-3 trade coverage snapshot is invalid")
    raw_count = int(raw_trade_rows)
    if raw_count < 0:
        raise ValueError("Phase-3 raw trade row count is invalid")
    identity_kind = str(wallet_identity_kind or "")
    expected_identity_kind = str(
        source_plan.get("wallet_identity_kind") or ""
    )
    if identity_kind != expected_identity_kind:
        raise ValueError(
            f"{source_id} Phase-3 wallet identity kind drift: "
            f"{identity_kind} != {expected_identity_kind}"
        )

    eligible = sorted({
        normalize_address(str(token))
        for token in eligible_tokens
    })
    eligible_set = set(eligible)
    rows = []
    previous = None
    for raw in canonical_trade_rows:
        row = validate_phase3_canonical_trade_row(raw)
        if str(row["source_id"]) != str(source_id):
            raise ValueError(
                f"Phase-3 trade coverage source drift: {source_id}"
            )
        token = row["token"]
        if token not in eligible_set:
            raise ValueError(
                f"{source_id} canonical trade token is outside frozen "
                f"source membership: {token}"
            )
        event = _event_key(row)
        if event[0] > snapshot:
            raise ValueError(
                f"{source_id} canonical trade is after snapshot: {token}"
            )
        key = (*event, token, str(row.get("transaction_hash") or ""))
        if previous is not None and key <= previous:
            raise ValueError(
                f"{source_id} canonical trades are not strictly ordered"
            )
        previous = key
        rows.append(row)

    canonical_rows, canonical_sha = _jsonl_sha(rows)
    complete = (
        historical_event_scan_complete is True
        and wallet_identity_complete is True
        and canonical_trade_adapter_complete is True
    )
    return {
        "version": PHASE3_TRADE_SOURCE_COVERAGE_VERSION,
        "source_id": str(source_id),
        "source_kind": str(source["source_kind"]),
        "snapshot_head_block": snapshot,
        "eligible_tokens": len(eligible),
        "eligible_tokens_sha256": _token_set_sha(eligible),
        "market_registry_sha256": _sha256(
            market_registry_sha256,
            label=f"{source_id} Phase-3 market registry",
        ),
        "raw_trade_tape_sha256": _sha256(
            raw_trade_tape_sha256,
            label=f"{source_id} Phase-3 raw trade tape",
        ),
        "raw_trade_rows": raw_count,
        "wallet_identity_sha256": _sha256(
            wallet_identity_sha256,
            label=f"{source_id} wallet identity",
        ),
        "wallet_identity_kind": identity_kind,
        "canonical_trade_rows": canonical_rows,
        "canonical_trade_rows_sha256": canonical_sha,
        "historical_event_scan_complete": (
            historical_event_scan_complete is True
        ),
        "wallet_identity_complete": (
            wallet_identity_complete is True
        ),
        "canonical_trade_adapter_complete": (
            canonical_trade_adapter_complete is True
        ),
        "trade_coverage_complete": complete,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
    }


def _duplicate_economics(row: Mapping[str, object]) -> tuple:
    return (
        str(row.get("initiator") or "").lower(),
        str(row.get("side") or ""),
        int(row.get("token_amount_raw", -1)),
        int(row.get("quote_amount_raw", -1)),
        str(row.get("quote_token") or "").lower(),
        str(row.get("transaction_hash") or "").lower(),
    )


def materialize_phase3_canonical_trade_tape(
    universe_rows: Iterable[Mapping[str, object]],
    source_trade_rows: Mapping[
        str, Iterable[Mapping[str, object]]
    ],
    source_coverage_rows: Iterable[Mapping[str, object]],
    *,
    feature_entry_handoff: Mapping[str, object],
    output: Path,
) -> tuple[dict, dict]:
    """Merge only fully covered source trades for the frozen Phase-3 universe."""

    entry = dict(feature_entry_handoff)
    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 canonical trade entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 canonical trade entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 canonical trade entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 canonical trade entry allows future state")

    snapshot = int(entry.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Phase-3 canonical trade snapshot is invalid")

    inventory_ids = {
        str(row["source_id"])
        for row in build_phase2_source_inventory()
    }
    supplied_ids = {str(key) for key in source_trade_rows}
    if supplied_ids != inventory_ids:
        raise ValueError(
            "Phase-3 canonical trade source contract mismatch: "
            f"missing={sorted(inventory_ids - supplied_ids)} "
            f"extra={sorted(supplied_ids - inventory_ids)}"
        )

    source_tokens = {
        source_id: set()
        for source_id in inventory_ids
    }
    universe_tokens = set()
    for raw in universe_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in universe_tokens:
            raise ValueError(
                f"Phase-3 canonical trade universe repeats token: {token}"
            )
        if row.get("universe_status") != "eligible":
            raise ValueError(
                f"Phase-3 canonical trade universe contains non-eligible "
                f"token: {token}"
            )
        raw_sources = {
            str(source_id)
            for source_id in row.get("source_ids") or []
        }
        if not raw_sources:
            raise ValueError(
                f"Phase-3 canonical trade universe token lacks source: {token}"
            )
        unknown = raw_sources - inventory_ids
        if unknown:
            raise ValueError(
                f"Phase-3 canonical trade universe has unknown sources: "
                f"{sorted(unknown)}"
            )
        universe_tokens.add(token)
        for source_id in raw_sources:
            source_tokens[source_id].add(token)

    if len(universe_tokens) != int(entry.get("universe_tokens", -1)):
        raise ValueError("Phase-3 canonical trade universe count drift")

    coverage = {}
    for raw in source_coverage_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE3_TRADE_SOURCE_COVERAGE_VERSION
        ):
            raise ValueError("Phase-3 trade source coverage version changed")
        source_id = str(row.get("source_id") or "")
        if source_id not in inventory_ids:
            raise ValueError(
                f"Phase-3 trade coverage has unknown source: {source_id}"
            )
        if source_id in coverage:
            raise ValueError(
                f"Phase-3 trade coverage repeats source: {source_id}"
            )
        if int(row.get("snapshot_head_block", -1)) != snapshot:
            raise ValueError(
                f"{source_id} Phase-3 trade coverage snapshot drift"
            )
        source_plan = {
            str(item["source_id"]): dict(item)
            for item in build_phase3_trade_source_plan()
        }[source_id]
        if str(row.get("wallet_identity_kind") or "") != str(
            source_plan.get("wallet_identity_kind") or ""
        ):
            raise ValueError(
                f"{source_id} Phase-3 wallet identity provenance drift"
            )
        _sha256(
            row.get("wallet_identity_sha256"),
            label=f"{source_id} wallet identity evidence",
        )
        expected_tokens = source_tokens[source_id]
        if int(row.get("eligible_tokens", -1)) != len(expected_tokens):
            raise ValueError(
                f"{source_id} Phase-3 trade eligible-token count drift"
            )
        if _sha256(
            row.get("eligible_tokens_sha256"),
            label=f"{source_id} eligible-token set",
        ) != _token_set_sha(expected_tokens):
            raise ValueError(
                f"{source_id} Phase-3 trade eligible-token membership drift"
            )
        for flag in (
            "historical_event_scan_complete",
            "wallet_identity_complete",
            "canonical_trade_adapter_complete",
            "trade_coverage_complete",
        ):
            if row.get(flag) is not True:
                raise ValueError(
                    f"{source_id} Phase-3 trade coverage is incomplete: "
                    f"{flag}"
                )
        if row.get("outcome_rows_consumed") is not False:
            raise ValueError(
                f"{source_id} Phase-3 trade coverage consumed outcomes"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"{source_id} Phase-3 trade coverage allows future state"
            )
        coverage[source_id] = row

    if set(coverage) != inventory_ids:
        raise ValueError(
            "Phase-3 trade coverage source set mismatch: "
            f"missing={sorted(inventory_ids - set(coverage))} "
            f"extra={sorted(set(coverage) - inventory_ids)}"
        )

    by_event = {}
    source_row_counts = {}
    collapsed_duplicates = 0
    for source_id in sorted(inventory_ids):
        rows = [
            validate_phase3_canonical_trade_row(raw)
            for raw in source_trade_rows[source_id]
        ]
        source_row_counts[source_id] = len(rows)
        count, digest = _jsonl_sha(rows)
        evidence = coverage[source_id]
        if count != int(evidence.get("canonical_trade_rows", -1)):
            raise ValueError(
                f"{source_id} Phase-3 canonical trade count drift"
            )
        if digest != _sha256(
            evidence.get("canonical_trade_rows_sha256"),
            label=f"{source_id} canonical trade rows",
        ):
            raise ValueError(
                f"{source_id} Phase-3 canonical trade SHA drift"
            )

        previous = None
        for row in rows:
            if str(row["source_id"]) != source_id:
                raise ValueError(
                    f"{source_id} Phase-3 canonical trade source drift"
                )
            token = row["token"]
            if token not in source_tokens[source_id]:
                raise ValueError(
                    f"{source_id} Phase-3 canonical trade token outside "
                    f"source membership: {token}"
                )
            event = _event_key(row)
            if event[0] > snapshot:
                raise ValueError(
                    f"{source_id} Phase-3 canonical trade after snapshot"
                )
            source_key = (
                *event,
                token,
                str(row.get("transaction_hash") or "").lower(),
            )
            if previous is not None and source_key <= previous:
                raise ValueError(
                    f"{source_id} Phase-3 canonical trades are not ordered"
                )
            previous = source_key

            identity = (
                token,
                *event,
                str(row.get("transaction_hash") or "").lower(),
            )
            prior = by_event.get(identity)
            if prior is None:
                merged = dict(row)
                merged["source_ids"] = [source_id]
                by_event[identity] = merged
                continue
            if _duplicate_economics(prior) != _duplicate_economics(row):
                raise ValueError(
                    "Phase-3 cross-source duplicate trade disagrees: "
                    f"{identity}"
                )
            prior_sources = set(prior.get("source_ids") or [])
            prior_sources.add(source_id)
            prior["source_ids"] = sorted(prior_sources)
            prior["source_id"] = min(prior["source_ids"])
            collapsed_duplicates += 1

    merged_rows = list(by_event.values())
    merged_rows.sort(
        key=lambda row: (
            *_event_key(row),
            row["token"],
            row["source_id"],
            str(row.get("transaction_hash") or ""),
        )
    )
    manifest = write_jsonl_snapshot(
        merged_rows,
        output=output,
        provenance={
            "version": PHASE3_CANONICAL_TRADE_TAPE_VERSION,
            "snapshot_head_block": snapshot,
            "eligible_universe_sha256": entry[
                "eligible_universe_sha256"
            ],
            "inventory_sources": len(inventory_ids),
            "complete_trade_sources": len(coverage),
            "cross_source_duplicates_collapsed": collapsed_duplicates,
            "trade_coverage_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    coverage_rows_sorted = [
        coverage[source_id]
        for source_id in sorted(coverage)
    ]
    _, coverage_sha = _jsonl_sha(coverage_rows_sorted)
    summary = {
        "version": PHASE3_CANONICAL_TRADE_TAPE_VERSION,
        "snapshot_head_block": snapshot,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "inventory_sources": len(inventory_ids),
        "complete_source_ids": sorted(inventory_ids),
        "source_eligible_token_counts": {
            source_id: len(source_tokens[source_id])
            for source_id in sorted(source_tokens)
        },
        "source_canonical_trade_rows": dict(
            sorted(source_row_counts.items())
        ),
        "source_coverage_sha256": coverage_sha,
        "trade_rows_before_cross_source_dedup": sum(
            source_row_counts.values()
        ),
        "cross_source_duplicates_collapsed": collapsed_duplicates,
        "trade_rows": int(manifest["records"]),
        "canonical_trade_rows_sha256": manifest["sha256"],
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_trade_tape_ready": True,
    }
    return manifest, summary


def build_phase3_canonical_trade_handoff(
    tape_summary: Mapping[str, object],
    *,
    tape_summary_sha256: str,
    feature_entry_handoff_sha256: str,
) -> dict:
    """Publish complete canonical trade tape identity for feature materializers."""

    summary = dict(tape_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_CANONICAL_TRADE_TAPE_VERSION
    ):
        raise ValueError("Phase-3 canonical trade handoff version changed")
    if summary.get("trade_coverage_complete") is not True:
        raise ValueError("Phase-3 canonical trade coverage is incomplete")
    if summary.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 canonical trade handoff consumed outcomes")
    if summary.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 canonical trade handoff exposes outcomes")
    if summary.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 canonical trade handoff allows future state")
    if summary.get("phase3_canonical_trade_tape_ready") is not True:
        raise ValueError("Phase-3 canonical trade tape is not ready")

    return {
        "version": PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 canonical trade universe",
        ),
        "canonical_trade_rows_sha256": _sha256(
            summary.get("canonical_trade_rows_sha256"),
            label="Phase-3 canonical trade rows",
        ),
        "source_coverage_sha256": _sha256(
            summary.get("source_coverage_sha256"),
            label="Phase-3 trade source coverage",
        ),
        "tape_summary_sha256": _sha256(
            tape_summary_sha256,
            label="Phase-3 canonical trade summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 feature-entry handoff",
        ),
        "inventory_sources": int(summary["inventory_sources"]),
        "trade_rows": int(summary["trade_rows"]),
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_trade_tape_ready": True,
    }
