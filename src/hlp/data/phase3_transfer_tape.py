"""Fail-closed Phase-3 canonical ERC-20 transfer tape."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_feature_entry import PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
from hlp.data.phase3_holder_features import (
    PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION,
    PHASE3_CANONICAL_TRANSFER_VERSION,
    ZERO_ADDRESS,
    validate_phase3_canonical_transfer_row,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_TRANSFER_TOKEN_COVERAGE_VERSION = (
    "phase3-transfer-token-coverage-v1"
)
PHASE3_CANONICAL_TRANSFER_TAPE_VERSION = (
    "phase3-canonical-transfer-tape-v1"
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
        raise ValueError("Phase-3 transfer event position is invalid")
    return block, tx, log


def _row_dict(raw: object) -> dict:
    if is_dataclass(raw):
        return asdict(raw)
    if isinstance(raw, Mapping):
        return dict(raw)
    raise TypeError(
        f"unsupported Phase-3 transfer row: {type(raw)!r}"
    )


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


def adapt_erc20_transfers_to_phase3(
    rows: Iterable[object],
) -> list[dict]:
    """Normalize decoded ERC-20 transfers into the Phase-3 canonical schema."""

    output = []
    seen = set()
    for raw in rows:
        row = _row_dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        tx_hash = str(row.get("transaction_hash") or "").lower()
        log_index = int(row.get("log_index", -1))
        identity = (token, tx_hash, log_index)
        if identity in seen:
            raise ValueError(
                f"Phase-3 transfer repeats token event: {identity}"
            )
        seen.add(identity)
        canonical = {
            "version": PHASE3_CANONICAL_TRANSFER_VERSION,
            "token": token,
            "from_address": normalize_address(
                str(row.get("from_address") or "")
            ),
            "to_address": normalize_address(
                str(row.get("to_address") or "")
            ),
            "value_raw": int(row.get("value_raw", -1)),
            "block_number": int(row.get("block_number", -1)),
            "transaction_hash": tx_hash,
            "transaction_index": row.get("transaction_index"),
            "log_index": log_index,
            "canonical_phase3_transfer": True,
            "outcome_derived": False,
        }
        output.append(
            validate_phase3_canonical_transfer_row(canonical)
        )
    output.sort(
        key=lambda row: (
            *_event_key(row),
            row["token"],
            row["transaction_hash"],
        )
    )
    return output


def build_phase3_transfer_token_coverage(
    token: str,
    canonical_transfer_rows: Iterable[Mapping[str, object]],
    *,
    snapshot_head_block: int,
    search_from_block: int,
    first_code_block: int,
    deployment_boundary_verified: bool,
    raw_transfer_tape_sha256: str,
    historical_event_scan_complete: bool,
) -> dict:
    """Bind one token's complete transfer tape from initial mint to snapshot."""

    token = normalize_address(token)
    snapshot = int(snapshot_head_block)
    start = int(search_from_block)
    first_code = int(first_code_block)
    if snapshot <= 0 or start < 0 or start > snapshot:
        raise ValueError("Phase-3 transfer coverage range is invalid")
    if first_code < 0 or first_code > snapshot or start > first_code:
        raise ValueError(
            "Phase-3 transfer coverage does not include deployment boundary"
        )
    if deployment_boundary_verified is not True:
        raise ValueError(
            "Phase-3 transfer coverage deployment boundary is unverified"
        )

    rows = []
    previous = None
    first_positive = None
    supply = 0
    for raw in canonical_transfer_rows:
        row = validate_phase3_canonical_transfer_row(raw)
        if row["token"] != token:
            raise ValueError(
                f"Phase-3 transfer coverage token drift: {token}"
            )
        event = _event_key(row)
        if event[0] < start or event[0] > snapshot:
            raise ValueError(
                f"Phase-3 transfer row outside coverage range: {token}"
            )
        key = (*event, row["transaction_hash"])
        if previous is not None and key <= previous:
            raise ValueError(
                f"Phase-3 transfer rows are not ordered: {token}"
            )
        previous = key
        if int(row["value_raw"]) > 0 and first_positive is None:
            first_positive = row
        if row["from_address"] == ZERO_ADDRESS:
            supply += int(row["value_raw"])
        if row["to_address"] == ZERO_ADDRESS:
            supply -= int(row["value_raw"])
        if supply < 0:
            raise ValueError(
                f"Phase-3 transfer coverage supply became negative: {token}"
            )
        rows.append(row)

    if not rows:
        raise ValueError(
            f"Phase-3 transfer coverage has no rows: {token}"
        )
    if first_positive is None or (
        first_positive["from_address"] != ZERO_ADDRESS
    ):
        raise ValueError(
            f"Phase-3 transfer coverage lacks initial mint: {token}"
        )
    if supply <= 0:
        raise ValueError(
            f"Phase-3 transfer coverage ends with non-positive supply: {token}"
        )

    count, digest = _jsonl_sha(rows)
    complete = historical_event_scan_complete is True
    return {
        "version": PHASE3_TRANSFER_TOKEN_COVERAGE_VERSION,
        "token": token,
        "snapshot_head_block": snapshot,
        "search_from_block": start,
        "first_code_block": first_code,
        "deployment_boundary_verified": True,
        "search_to_block": snapshot,
        "initial_mint_block": int(first_positive["block_number"]),
        "initial_mint_transaction_index": (
            first_positive.get("transaction_index")
        ),
        "initial_mint_log_index": int(first_positive["log_index"]),
        "continuous": complete,
        "missing_ranges": [],
        "raw_transfer_tape_sha256": _sha256(
            raw_transfer_tape_sha256,
            label=f"{token} raw transfer tape",
        ),
        "canonical_transfer_rows": count,
        "canonical_transfer_rows_sha256": digest,
        "historical_event_scan_complete": complete,
        "initial_mint_coverage_complete": True,
        "positive_supply_at_snapshot": True,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "transfer_coverage_complete": complete,
    }


def materialize_phase3_canonical_transfer_tape(
    universe_rows: Iterable[Mapping[str, object]],
    token_transfer_rows: Mapping[
        str, Iterable[Mapping[str, object]]
    ],
    token_coverage_rows: Iterable[Mapping[str, object]],
    *,
    feature_entry_handoff: Mapping[str, object],
    output: Path,
) -> tuple[dict, dict]:
    """Assemble exact-universe transfer tapes only after every token is complete."""

    entry = dict(feature_entry_handoff)
    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 transfer entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 transfer entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 transfer entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 transfer entry allows future state")
    snapshot = int(entry.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Phase-3 transfer snapshot is invalid")

    universe = set()
    for raw in universe_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in universe:
            raise ValueError(
                f"Phase-3 transfer universe repeats token: {token}"
            )
        if row.get("universe_status") != "eligible":
            raise ValueError(
                f"Phase-3 transfer universe contains non-eligible token: "
                f"{token}"
            )
        universe.add(token)
    if len(universe) != int(entry.get("universe_tokens", -1)):
        raise ValueError("Phase-3 transfer universe count drift")

    supplied = {
        normalize_address(str(token))
        for token in token_transfer_rows
    }
    if supplied != universe:
        raise ValueError(
            "Phase-3 transfer token-tape contract mismatch: "
            f"missing={sorted(universe - supplied)[:20]} "
            f"extra={sorted(supplied - universe)[:20]}"
        )

    coverage = {}
    for raw in token_coverage_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE3_TRANSFER_TOKEN_COVERAGE_VERSION
        ):
            raise ValueError("Phase-3 transfer coverage version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token not in universe or token in coverage:
            raise ValueError(
                f"Phase-3 transfer coverage token invalid/repeated: {token}"
            )
        if int(row.get("snapshot_head_block", -1)) != snapshot:
            raise ValueError(
                f"Phase-3 transfer coverage snapshot drift: {token}"
            )
        if int(row.get("search_to_block", -1)) != snapshot:
            raise ValueError(
                f"Phase-3 transfer coverage end drift: {token}"
            )
        first_code = int(row.get("first_code_block", -1))
        start = int(row.get("search_from_block", -1))
        if (
            first_code < 0
            or first_code > snapshot
            or start < 0
            or start > first_code
        ):
            raise ValueError(
                f"Phase-3 transfer deployment coverage drift: {token}"
            )
        mint_block = int(row.get("initial_mint_block", -1))
        raw_mint_tx = row.get("initial_mint_transaction_index")
        mint_tx = -1 if raw_mint_tx is None else int(raw_mint_tx)
        mint_log = int(row.get("initial_mint_log_index", -1))
        if (
            mint_block < first_code
            or mint_block > snapshot
            or mint_tx < -1
            or mint_log < 0
        ):
            raise ValueError(
                f"Phase-3 transfer initial-mint boundary drift: {token}"
            )
        if row.get("deployment_boundary_verified") is not True:
            raise ValueError(
                f"Phase-3 transfer deployment boundary unverified: {token}"
            )
        if row.get("continuous") is not True:
            raise ValueError(
                f"Phase-3 transfer coverage is not continuous: {token}"
            )
        missing = row.get("missing_ranges")
        if not isinstance(missing, list) or missing:
            raise ValueError(
                f"Phase-3 transfer coverage has missing ranges: {token}"
            )
        for flag in (
            "historical_event_scan_complete",
            "initial_mint_coverage_complete",
            "positive_supply_at_snapshot",
            "transfer_coverage_complete",
        ):
            if row.get(flag) is not True:
                raise ValueError(
                    f"Phase-3 transfer coverage incomplete for {token}: "
                    f"{flag}"
                )
        if row.get("outcome_rows_consumed") is not False:
            raise ValueError(
                f"Phase-3 transfer coverage consumed outcomes: {token}"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 transfer coverage allows future state: {token}"
            )
        coverage[token] = row

    if set(coverage) != universe:
        raise ValueError(
            "Phase-3 transfer coverage token set mismatch"
        )

    merged = []
    per_token_rows = {}
    for token in sorted(universe):
        rows = [
            validate_phase3_canonical_transfer_row(raw)
            for raw in token_transfer_rows[token]
        ]
        count, digest = _jsonl_sha(rows)
        evidence = coverage[token]
        if count != int(evidence.get("canonical_transfer_rows", -1)):
            raise ValueError(
                f"Phase-3 transfer row count drift: {token}"
            )
        if digest != _sha256(
            evidence.get("canonical_transfer_rows_sha256"),
            label=f"{token} canonical transfer rows",
        ):
            raise ValueError(
                f"Phase-3 transfer row SHA drift: {token}"
            )
        previous = None
        for row in rows:
            if row["token"] != token:
                raise ValueError(
                    f"Phase-3 transfer token-tape drift: {token}"
                )
            event = _event_key(row)
            key = (*event, row["transaction_hash"])
            if previous is not None and key <= previous:
                raise ValueError(
                    f"Phase-3 transfer token tape not ordered: {token}"
                )
            previous = key
            merged.append(row)
        per_token_rows[token] = count

    merged.sort(
        key=lambda row: (
            *_event_key(row),
            row["token"],
            row["transaction_hash"],
        )
    )
    manifest = write_jsonl_snapshot(
        merged,
        output=output,
        provenance={
            "version": PHASE3_CANONICAL_TRANSFER_TAPE_VERSION,
            "snapshot_head_block": snapshot,
            "eligible_universe_sha256": entry[
                "eligible_universe_sha256"
            ],
            "universe_tokens": len(universe),
            "transfer_coverage_complete": True,
            "initial_mint_coverage_complete": True,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )

    _, coverage_sha = _jsonl_sha(
        coverage[token]
        for token in sorted(coverage)
    )
    summary = {
        "version": PHASE3_CANONICAL_TRANSFER_TAPE_VERSION,
        "snapshot_head_block": snapshot,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "universe_tokens": len(universe),
        "covered_tokens": len(coverage),
        "per_token_transfer_rows": per_token_rows,
        "token_coverage_sha256": coverage_sha,
        "transfer_rows": int(manifest["records"]),
        "canonical_transfer_rows_sha256": manifest["sha256"],
        "historical_event_scan_complete": True,
        "initial_mint_coverage_complete": True,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_transfer_tape_ready": True,
    }
    return manifest, summary


def build_phase3_canonical_transfer_handoff(
    tape_summary: Mapping[str, object],
    *,
    tape_summary_sha256: str,
    feature_entry_handoff_sha256: str,
) -> dict:
    summary = dict(tape_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_CANONICAL_TRANSFER_TAPE_VERSION
    ):
        raise ValueError("Phase-3 canonical transfer handoff version changed")
    for flag in (
        "historical_event_scan_complete",
        "initial_mint_coverage_complete",
        "transfer_coverage_complete",
        "phase3_canonical_transfer_tape_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 canonical transfer handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 canonical transfer handoff violates {flag}"
            )
    return {
        "version": PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 canonical transfer universe",
        ),
        "canonical_transfer_rows_sha256": _sha256(
            summary.get("canonical_transfer_rows_sha256"),
            label="Phase-3 canonical transfer rows",
        ),
        "token_coverage_sha256": _sha256(
            summary.get("token_coverage_sha256"),
            label="Phase-3 transfer token coverage",
        ),
        "tape_summary_sha256": _sha256(
            tape_summary_sha256,
            label="Phase-3 canonical transfer summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 feature-entry handoff",
        ),
        "universe_tokens": int(summary["universe_tokens"]),
        "transfer_rows": int(summary["transfer_rows"]),
        "historical_event_scan_complete": True,
        "initial_mint_coverage_complete": True,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_transfer_tape_ready": True,
    }
