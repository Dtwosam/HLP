"""Point-in-time contract-code participation features for Phase 3."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_feature_entry import (
    PHASE3_FEATURE_ENTRY_HANDOFF_VERSION,
    PHASE3_FEATURE_SNAPSHOT_KIND,
    PHASE3_FEATURE_SUBJECT_FIELDS,
    PHASE3_FEATURE_SUBJECT_VERSION,
)
from hlp.data.phase3_feature_registry import validate_phase3_feature_registry
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
    validate_phase3_canonical_trade_row,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_PARTICIPANT_CODE_STATE_VERSION = "phase3-participant-code-state-v1"
PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION = (
    "phase3-participant-type-features-v1"
)
PHASE3_PARTICIPANT_TYPE_FEATURE_HANDOFF_VERSION = (
    "phase3-participant-type-features-handoff-v1"
)

PARTICIPANT_TYPE_FEATURE_IDS = (
    "participant_type.unique_code_accounts_so_far",
    "participant_type.unique_no_code_accounts_so_far",
    "participant_type.code_account_share_of_unique_traders",
    "participant_type.code_account_trade_share_so_far",
    "participant_type.code_account_buy_trade_share_so_far",
    "participant_type.code_account_sell_trade_share_so_far",
    "participant_type.latest_initiator_has_code_before_cutoff_block",
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


def _event(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError(
            "Phase-3 participant-type trade position is invalid"
        )
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 participant-type cutoff is invalid")
    return block, tx, log


def _state_block(cutoff_block: int) -> int:
    return max(0, int(cutoff_block) - 1)


def _share(numerator: int, denominator: int) -> str | None:
    if denominator <= 0:
        return None
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _validate_entry_and_tape(
    entry_handoff: Mapping[str, object],
    trade_tape_handoff: Mapping[str, object],
) -> tuple[dict, dict, int]:
    entry = dict(entry_handoff)
    tape = dict(trade_tape_handoff)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 participant-type entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 participant-type entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 participant-type entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 participant-type entry allows future state")

    if (
        str(tape.get("version") or "")
        != PHASE3_CANONICAL_TRADE_HANDOFF_VERSION
    ):
        raise ValueError(
            "Phase-3 participant-type canonical trade handoff changed"
        )
    if tape.get("trade_coverage_complete") is not True:
        raise ValueError(
            "Phase-3 participant-type features require complete trade coverage"
        )
    if tape.get("outcome_rows_consumed") is not False:
        raise ValueError(
            "Phase-3 participant-type canonical trade tape consumed outcomes"
        )
    if tape.get("future_state_allowed") is not False:
        raise ValueError(
            "Phase-3 participant-type canonical trade tape allows future state"
        )

    snapshot = int(entry.get("snapshot_head_block", -1))
    if int(tape.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-3 participant-type entry/tape snapshot drift")
    if _sha256(
        tape.get("eligible_universe_sha256"),
        label="Phase-3 participant-type trade universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 participant-type entry universe",
    ):
        raise ValueError("Phase-3 participant-type universe drift")
    return entry, tape, snapshot


def _subject_map(
    subject_rows: Iterable[Mapping[str, object]],
    *,
    expected_subjects: int,
    snapshot_head_block: int,
) -> dict[str, dict]:
    subjects: dict[str, dict] = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError(
                "Phase-3 participant-type subject fields changed"
            )
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError(
                "Phase-3 participant-type subject version changed"
            )
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError(
                "Phase-3 participant-type snapshot kind changed"
            )
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError(
                "Phase-3 participant-type cutoff is not inclusive"
            )
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 participant-type repeats subject: {token}"
            )
        cutoff = _cutoff(row)
        if cutoff[0] > snapshot_head_block:
            raise ValueError(
                f"Phase-3 participant-type cutoff after snapshot: {token}"
            )
        subjects[token] = {
            "cutoff": cutoff,
            "state_block": _state_block(cutoff[0]),
            "total": 0,
            "buys": 0,
            "sells": 0,
            "counts": defaultdict(
                lambda: {"total": 0, "buy": 0, "sell": 0}
            ),
            "latest_initiator": None,
            "post_cutoff_rows_ignored": 0,
        }
    if len(subjects) != expected_subjects:
        raise ValueError("Phase-3 participant-type subject count drift")
    return subjects


def _scan_trades(
    subjects: Mapping[str, dict],
    trade_rows: Iterable[Mapping[str, object]],
    *,
    expected_trade_rows: int,
    snapshot_head_block: int,
) -> tuple[set[tuple[int, str]], int]:
    expected_queries: set[tuple[int, str]] = set()
    previous_global = None
    total_rows = 0

    for raw in trade_rows:
        row = validate_phase3_canonical_trade_row(raw)
        token = row["token"]
        event = _event(row)
        key = (*event, token, row["source_id"])
        if previous_global is not None and key <= previous_global:
            raise ValueError(
                "Phase-3 participant-type trade tape is not chronological"
            )
        previous_global = key
        if event[0] > snapshot_head_block:
            raise ValueError(
                "Phase-3 participant-type trade after frozen snapshot"
            )
        total_rows += 1

        state = subjects.get(token)
        if state is None:
            continue
        if event > state["cutoff"]:
            state["post_cutoff_rows_ignored"] += 1
            continue

        initiator = row["initiator"]
        side = row["side"]
        state["total"] += 1
        state[side + "s"] += 1
        state["counts"][initiator]["total"] += 1
        state["counts"][initiator][side] += 1
        state["latest_initiator"] = initiator
        expected_queries.add((state["state_block"], initiator))

    if total_rows != expected_trade_rows:
        raise ValueError(
            "Phase-3 participant-type canonical trade count changed"
        )
    return expected_queries, total_rows


def build_phase3_participant_code_query_plan(
    subject_rows: Iterable[Mapping[str, object]],
    trade_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    trade_tape_handoff: Mapping[str, object],
) -> tuple[list[dict], dict]:
    """Build exact historical eth_getCode queries without same-block lookahead."""

    entry, tape, snapshot = _validate_entry_and_tape(
        entry_handoff,
        trade_tape_handoff,
    )
    subjects = _subject_map(
        subject_rows,
        expected_subjects=int(entry.get("feature_subjects", -1)),
        snapshot_head_block=snapshot,
    )
    expected_queries, _ = _scan_trades(
        subjects,
        trade_rows,
        expected_trade_rows=int(tape.get("trade_rows", -1)),
        snapshot_head_block=snapshot,
    )
    rows = [
        {"block_number": block, "address": address}
        for block, address in sorted(expected_queries)
    ]
    return rows, {
        "version": "phase3-participant-code-query-plan-v1",
        "snapshot_head_block": snapshot,
        "feature_subjects": len(subjects),
        "participant_code_queries": len(rows),
        "query_block_semantics": "start_of_confirmation_block",
        "same_block_future_state_allowed": False,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
    }


def validate_phase3_participant_code_state_row(
    raw: Mapping[str, object],
) -> dict:
    row = dict(raw)
    if (
        str(row.get("version") or "")
        != PHASE3_PARTICIPANT_CODE_STATE_VERSION
    ):
        raise ValueError("Phase-3 participant code-state version changed")
    address = normalize_address(str(row.get("address") or ""))
    block = int(row.get("block_number", -1))
    if block < 0:
        raise ValueError("Phase-3 participant code-state block is invalid")
    code_present = row.get("code_present")
    if not isinstance(code_present, bool):
        raise ValueError(
            "Phase-3 participant code-state presence flag is invalid"
        )
    size = int(row.get("code_size_bytes", -1))
    if size < 0:
        raise ValueError("Phase-3 participant code-state size is invalid")
    if code_present != (size > 0):
        raise ValueError(
            "Phase-3 participant code-state size/presence disagree"
        )
    code_sha = _sha256(
        row.get("code_sha256"),
        label="Phase-3 participant code bytes",
    )
    if row.get("archive_state_read") is not True:
        raise ValueError(
            "Phase-3 participant code-state lacks archive evidence"
        )
    if row.get("future_state_allowed") is not False:
        raise ValueError(
            "Phase-3 participant code-state allows future state"
        )
    return {
        **row,
        "address": address,
        "block_number": block,
        "code_present": code_present,
        "code_size_bytes": size,
        "code_sha256": code_sha,
    }


def materialize_phase3_participant_type_features(
    subject_rows: Iterable[Mapping[str, object]],
    trade_rows: Iterable[Mapping[str, object]],
    code_state_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    trade_tape_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Measure code-bearing participant activity using only prior-block state."""

    entry, tape, snapshot = _validate_entry_and_tape(
        entry_handoff,
        trade_tape_handoff,
    )
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)
    family_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "participant_type"
    }
    if family_ids != set(PARTICIPANT_TYPE_FEATURE_IDS):
        raise ValueError(
            "Phase-3 participant-type feature registry changed"
        )
    if registry.get("future_state_allowed") is not False:
        raise ValueError(
            "Phase-3 participant-type registry allows future state"
        )
    if registry.get("outcome_dependency_allowed") is not False:
        raise ValueError(
            "Phase-3 participant-type registry depends on outcomes"
        )

    subjects = _subject_map(
        subject_rows,
        expected_subjects=int(entry.get("feature_subjects", -1)),
        snapshot_head_block=snapshot,
    )
    expected_queries, _ = _scan_trades(
        subjects,
        trade_rows,
        expected_trade_rows=int(tape.get("trade_rows", -1)),
        snapshot_head_block=snapshot,
    )

    code_by_query = {}
    code_digest = hashlib.sha256()
    previous = None
    for raw in code_state_rows:
        row = validate_phase3_participant_code_state_row(raw)
        key = (row["block_number"], row["address"])
        if previous is not None and key <= previous:
            raise ValueError(
                "Phase-3 participant code-state rows are not ordered"
            )
        previous = key
        if key in code_by_query:
            raise ValueError(
                "Phase-3 participant code-state query is repeated"
            )
        if row["block_number"] > snapshot:
            raise ValueError(
                "Phase-3 participant code-state is after frozen snapshot"
            )
        code_by_query[key] = row
        line = (
            json.dumps(
                row,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        code_digest.update(line)

    observed_queries = set(code_by_query)
    if observed_queries != expected_queries:
        raise ValueError(
            "Phase-3 participant code-state coverage mismatch: "
            f"missing={sorted(expected_queries - observed_queries)} "
            f"extra={sorted(observed_queries - expected_queries)}"
        )

    output_rows = []
    subjects_without_trades = 0
    ignored_future = 0
    for token in sorted(subjects):
        state = subjects[token]
        code_accounts = {
            address
            for address in state["counts"]
            if code_by_query[
                (state["state_block"], address)
            ]["code_present"]
        }
        no_code_accounts = set(state["counts"]) - code_accounts
        code_trades = sum(
            state["counts"][address]["total"]
            for address in code_accounts
        )
        code_buys = sum(
            state["counts"][address]["buy"]
            for address in code_accounts
        )
        code_sells = sum(
            state["counts"][address]["sell"]
            for address in code_accounts
        )
        trader_count = len(state["counts"])
        latest = state["latest_initiator"]
        latest_has_code = (
            None
            if latest is None
            else code_by_query[
                (state["state_block"], latest)
            ]["code_present"]
        )
        values = {
            "participant_type.unique_code_accounts_so_far": (
                len(code_accounts)
            ),
            "participant_type.unique_no_code_accounts_so_far": (
                len(no_code_accounts)
            ),
            "participant_type.code_account_share_of_unique_traders": (
                _share(len(code_accounts), trader_count)
            ),
            "participant_type.code_account_trade_share_so_far": (
                _share(code_trades, state["total"])
            ),
            "participant_type.code_account_buy_trade_share_so_far": (
                _share(code_buys, state["buys"])
            ),
            "participant_type.code_account_sell_trade_share_so_far": (
                _share(code_sells, state["sells"])
            ),
            (
                "participant_type."
                "latest_initiator_has_code_before_cutoff_block"
            ): latest_has_code,
        }
        missing = [
            feature_id
            for feature_id, value in values.items()
            if value is None
        ]
        if state["total"] == 0:
            subjects_without_trades += 1
        ignored_future += int(state["post_cutoff_rows_ignored"])
        cutoff = state["cutoff"]
        output_rows.append({
            "version": PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": cutoff[0],
            "feature_cutoff_transaction_index": (
                None if cutoff[1] == -1 else cutoff[1]
            ),
            "feature_cutoff_log_index": cutoff[2],
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry["registry_sha256"],
            "feature_values": values,
            "missing_feature_ids": sorted(missing),
            "data_quality": {
                "code_state_block": state["state_block"],
                "code_state_semantics": (
                    "eth_getCode_at_start_of_confirmation_block"
                ),
                "historical_code_state_complete": True,
                "same_block_future_state_used": False,
                "trades_observed_before_cutoff": state["total"] > 0,
                "future_trade_rows_used": False,
            },
        })

    code_rows_sha = code_digest.hexdigest()
    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION,
            "feature_family": "participant_type",
            "feature_registry_sha256": registry["registry_sha256"],
            "canonical_trade_rows_sha256": tape[
                "canonical_trade_rows_sha256"
            ],
            "participant_code_rows_sha256": code_rows_sha,
            "query_block_semantics": "start_of_confirmation_block",
            "same_block_future_state_allowed": False,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )
    summary = {
        "version": PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION,
        "snapshot_head_block": snapshot,
        "feature_family": "participant_type",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(PARTICIPANT_TYPE_FEATURE_IDS),
        "features_per_subject": len(PARTICIPANT_TYPE_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_trade_rows_sha256": str(
            tape["canonical_trade_rows_sha256"]
        ),
        "participant_code_rows": len(code_by_query),
        "participant_code_rows_sha256": code_rows_sha,
        "subjects_without_trades": subjects_without_trades,
        "post_cutoff_subject_trade_rows_ignored": ignored_future,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "query_block_semantics": "start_of_confirmation_block",
        "historical_code_state_complete": True,
        "same_block_future_state_used": False,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_participant_type_features_ready": True,
    }
    return manifest, summary


def build_phase3_participant_type_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_trade_handoff_sha256: str,
) -> dict:
    summary = dict(feature_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION
    ):
        raise ValueError(
            "Phase-3 participant-type handoff version changed"
        )
    if summary.get("feature_family") != "participant_type":
        raise ValueError(
            "Phase-3 participant-type feature family changed"
        )
    for flag in (
        "historical_code_state_complete",
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_participant_type_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 participant-type handoff lacks {flag}"
            )
    for flag in (
        "same_block_future_state_used",
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_trade_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 participant-type handoff violates {flag}"
            )
    if (
        str(summary.get("query_block_semantics") or "")
        != "start_of_confirmation_block"
    ):
        raise ValueError(
            "Phase-3 participant-type code-state semantics changed"
        )
    return {
        "version": PHASE3_PARTICIPANT_TYPE_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "participant_type",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 participant-type registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 participant-type rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 participant-type summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 participant-type entry",
        ),
        "canonical_trade_handoff_sha256": _sha256(
            canonical_trade_handoff_sha256,
            label="Phase-3 participant-type trade handoff",
        ),
        "canonical_trade_rows_sha256": _sha256(
            summary.get("canonical_trade_rows_sha256"),
            label="Phase-3 participant-type trade rows",
        ),
        "participant_code_rows_sha256": _sha256(
            summary.get("participant_code_rows_sha256"),
            label="Phase-3 participant code rows",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 participant-type universe",
        ),
        "participant_code_rows": int(summary["participant_code_rows"]),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "query_block_semantics": "start_of_confirmation_block",
        "historical_code_state_complete": True,
        "same_block_future_state_used": False,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_participant_type_features_ready": True,
    }
