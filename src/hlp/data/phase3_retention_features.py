"""Causal Phase-3 participant-retention features from canonical trades."""

from __future__ import annotations

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


PHASE3_RETENTION_FEATURE_VERSION = "phase3-retention-features-v1"
PHASE3_RETENTION_FEATURE_HANDOFF_VERSION = (
    "phase3-retention-features-handoff-v1"
)

RETENTION_FEATURE_IDS = (
    "retention.multi_trade_traders_so_far",
    "retention.multi_trade_trader_share_so_far",
    "retention.two_sided_traders_so_far",
    "retention.two_sided_trader_share_so_far",
    "retention.repeat_trades_so_far",
    "retention.repeat_trade_share_so_far",
    "retention.latest_trader_prior_trades",
    "retention.latest_trader_is_returning",
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
        raise ValueError("Phase-3 retention trade event position is invalid")
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 retention cutoff is invalid")
    return block, tx, log


def _share(numerator: int, denominator: int) -> str | None:
    if denominator <= 0:
        return None
    if numerator < 0 or numerator > denominator:
        raise ValueError("Phase-3 retention share inputs are invalid")
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def materialize_phase3_retention_features(
    subject_rows: Iterable[Mapping[str, object]],
    trade_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    trade_tape_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Compute repeat-participation state using no trades after each cutoff."""

    entry = dict(entry_handoff)
    tape = dict(trade_tape_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 retention entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 retention entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 retention entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 retention entry allows future state")

    if (
        str(tape.get("version") or "")
        != PHASE3_CANONICAL_TRADE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 retention trade-tape version changed")
    if tape.get("trade_coverage_complete") is not True:
        raise ValueError(
            "Phase-3 retention requires complete canonical trade coverage"
        )
    if tape.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 retention trade tape consumed outcomes")
    if tape.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 retention trade tape allows future state")
    if int(tape.get("snapshot_head_block", -1)) != int(
        entry.get("snapshot_head_block", -2)
    ):
        raise ValueError("Phase-3 retention entry/tape snapshot drift")
    if _sha256(
        tape.get("eligible_universe_sha256"),
        label="Phase-3 retention trade universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 retention entry universe",
    ):
        raise ValueError("Phase-3 retention entry/tape universe drift")

    registry_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "participant_retention"
    }
    if registry_ids != set(RETENTION_FEATURE_IDS):
        raise ValueError("Phase-3 retention feature registry changed")
    if registry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 retention registry allows future state")
    if registry.get("outcome_dependency_allowed") is not False:
        raise ValueError("Phase-3 retention registry depends on outcomes")

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 retention subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 retention subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 retention snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 retention cutoff is not inclusive")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 retention repeats subject: {token}"
            )
        subjects[token] = {
            "cutoff": _cutoff(row),
            "counts": defaultdict(int),
            "buyers": set(),
            "sellers": set(),
            "total": 0,
            "latest_prior_trades": None,
            "post_cutoff_rows_ignored": 0,
        }

    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 retention subject count drift")

    previous_global = None
    total_rows = 0
    for raw in trade_rows:
        row = validate_phase3_canonical_trade_row(raw)
        token = row["token"]
        event = _event_key(row)
        global_key = (*event, token, row["source_id"])
        if previous_global is not None and global_key <= previous_global:
            raise ValueError(
                "Phase-3 retention trade tape is not strictly chronological"
            )
        previous_global = global_key
        if event[0] > int(entry["snapshot_head_block"]):
            raise ValueError(
                "Phase-3 retention trade is after frozen snapshot"
            )
        total_rows += 1

        state = subjects.get(token)
        if state is None:
            continue
        if event > state["cutoff"]:
            state["post_cutoff_rows_ignored"] += 1
            continue

        initiator = row["initiator"]
        prior = int(state["counts"][initiator])
        state["latest_prior_trades"] = prior
        state["counts"][initiator] = prior + 1
        state["total"] += 1
        if row["side"] == "buy":
            state["buyers"].add(initiator)
        else:
            state["sellers"].add(initiator)

    if total_rows != int(tape.get("trade_rows", -1)):
        raise ValueError("Phase-3 retention trade row count changed")

    output_rows = []
    ignored_future = 0
    missing_total = 0
    subjects_without_trades = 0
    for token in sorted(subjects):
        state = subjects[token]
        total = int(state["total"])
        unique = len(state["counts"])
        if total < unique:
            raise ValueError(
                f"Phase-3 retention trade/participant drift: {token}"
            )
        multi = sum(
            int(count >= 2)
            for count in state["counts"].values()
        )
        two_sided = len(state["buyers"] & state["sellers"])
        repeat_trades = total - unique
        latest_prior = state["latest_prior_trades"]
        values = {
            "retention.multi_trade_traders_so_far": multi,
            "retention.multi_trade_trader_share_so_far": _share(
                multi,
                unique,
            ),
            "retention.two_sided_traders_so_far": two_sided,
            "retention.two_sided_trader_share_so_far": _share(
                two_sided,
                unique,
            ),
            "retention.repeat_trades_so_far": repeat_trades,
            "retention.repeat_trade_share_so_far": _share(
                repeat_trades,
                total,
            ),
            "retention.latest_trader_prior_trades": (
                None if latest_prior is None else int(latest_prior)
            ),
            "retention.latest_trader_is_returning": (
                None if latest_prior is None else int(latest_prior) > 0
            ),
        }
        if set(values) != set(RETENTION_FEATURE_IDS):
            raise ValueError("Phase-3 retention feature set changed")
        missing = sorted(
            feature_id
            for feature_id, value in values.items()
            if value is None
        )
        if total == 0:
            subjects_without_trades += 1
        missing_total += len(missing)
        ignored_future += int(state["post_cutoff_rows_ignored"])
        output_rows.append({
            "version": PHASE3_RETENTION_FEATURE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": state["cutoff"][0],
            "feature_cutoff_transaction_index": (
                None
                if state["cutoff"][1] == -1
                else state["cutoff"][1]
            ),
            "feature_cutoff_log_index": state["cutoff"][2],
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry["registry_sha256"],
            "feature_values": values,
            "missing_feature_ids": missing,
            "data_quality": {
                "canonical_trade_coverage_complete": True,
                "trades_observed_before_cutoff": total > 0,
                "future_trade_rows_used": False,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_RETENTION_FEATURE_VERSION,
            "feature_family": "participant_retention",
            "feature_registry_sha256": registry["registry_sha256"],
            "canonical_trade_rows_sha256": tape[
                "canonical_trade_rows_sha256"
            ],
            "trade_coverage_complete": True,
            "outcome_rows_consumed": False,
            "future_trade_rows_used": False,
        },
    )
    summary = {
        "version": PHASE3_RETENTION_FEATURE_VERSION,
        "snapshot_head_block": int(entry["snapshot_head_block"]),
        "feature_family": "participant_retention",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(RETENTION_FEATURE_IDS),
        "features_per_subject": len(RETENTION_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_trade_rows_validated": total_rows,
        "canonical_trade_rows_sha256": str(
            tape["canonical_trade_rows_sha256"]
        ),
        "trade_coverage_complete": True,
        "subjects_without_trades": subjects_without_trades,
        "missing_feature_values": missing_total,
        "post_cutoff_subject_trade_rows_ignored": ignored_future,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_retention_features_ready": True,
    }
    return manifest, summary


def build_phase3_retention_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_trade_handoff_sha256: str,
) -> dict:
    """Bind retention features to exact subjects and canonical trade identity."""

    summary = dict(feature_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_RETENTION_FEATURE_VERSION
    ):
        raise ValueError("Phase-3 retention handoff version changed")
    if summary.get("feature_family") != "participant_retention":
        raise ValueError("Phase-3 retention feature family changed")
    if summary.get("trade_coverage_complete") is not True:
        raise ValueError("Phase-3 retention trade coverage is incomplete")
    for flag in (
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_retention_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 retention handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_trade_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 retention handoff violates {flag}"
            )

    return {
        "version": PHASE3_RETENTION_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "participant_retention",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 retention registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 retention rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 retention summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 retention entry",
        ),
        "canonical_trade_handoff_sha256": _sha256(
            canonical_trade_handoff_sha256,
            label="Phase-3 retention canonical trade handoff",
        ),
        "canonical_trade_rows_sha256": _sha256(
            summary.get("canonical_trade_rows_sha256"),
            label="Phase-3 retention canonical trade rows",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 retention universe",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_retention_features_ready": True,
    }
