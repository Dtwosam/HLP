"""Source-agnostic causal trade-flow features for Phase 3."""

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
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_CANONICAL_TRADE_VERSION = "phase3-canonical-trade-v1"
PHASE3_CANONICAL_TRADE_HANDOFF_VERSION = (
    "phase3-canonical-trade-handoff-v1"
)
PHASE3_TRADE_FEATURE_VERSION = "phase3-trade-features-v1"
PHASE3_TRADE_FEATURE_HANDOFF_VERSION = (
    "phase3-trade-features-handoff-v1"
)

TRADE_FEATURE_IDS = (
    "trade.total_trades_so_far",
    "trade.buy_trades_so_far",
    "trade.sell_trades_so_far",
    "trade.buy_trade_share_so_far",
    "trade.unique_traders_so_far",
    "trade.unique_buyers_so_far",
    "trade.unique_sellers_so_far",
    "trade.repeat_buyer_trade_share_so_far",
    "trade.repeat_seller_trade_share_so_far",
    "trade.current_side_is_buy",
    "trade.current_side_streak_trades",
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


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 trade feature cutoff is invalid")
    return block, tx, log


def _share(numerator: int, denominator: int) -> str | None:
    if denominator <= 0:
        return None
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def validate_phase3_canonical_trade_row(
    raw: Mapping[str, object],
) -> dict:
    """Normalize and validate one already source-adapted canonical trade row."""

    row = dict(raw)
    if (
        str(row.get("version") or "")
        != PHASE3_CANONICAL_TRADE_VERSION
    ):
        raise ValueError("Phase-3 canonical trade version changed")
    if row.get("canonical_phase3_trade") is not True:
        raise ValueError("Phase-3 trade row is not canonical")
    token = normalize_address(str(row.get("token") or ""))
    initiator = normalize_address(str(row.get("initiator") or ""))
    side = str(row.get("side") or "")
    if side not in {"buy", "sell"}:
        raise ValueError(f"Phase-3 canonical trade side is invalid: {side}")
    source_id = str(row.get("source_id") or "").strip()
    if not source_id:
        raise ValueError("Phase-3 canonical trade source id is empty")
    event = _event_key(row)
    if row.get("outcome_derived") is not False:
        raise ValueError("Phase-3 canonical trade row is outcome-derived")
    return {
        **row,
        "token": token,
        "initiator": initiator,
        "side": side,
        "source_id": source_id,
        "block_number": event[0],
        "transaction_index": None if event[1] == -1 else event[1],
        "log_index": event[2],
    }


def materialize_phase3_trade_features(
    subject_rows: Iterable[Mapping[str, object]],
    trade_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    trade_tape_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Compute causal flow/participant features from a complete canonical tape."""

    entry = dict(entry_handoff)
    tape = dict(trade_tape_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 trade features entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 trade features entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 trade feature entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 trade feature entry allows future state")

    if (
        str(tape.get("version") or "")
        != PHASE3_CANONICAL_TRADE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 canonical trade handoff version changed")
    if tape.get("trade_coverage_complete") is not True:
        raise ValueError(
            "Phase-3 trade features require complete canonical trade coverage"
        )
    if tape.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 canonical trade tape consumed outcomes")
    if tape.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 canonical trade tape allows future state")
    if int(tape.get("snapshot_head_block", -1)) != int(
        entry.get("snapshot_head_block", -2)
    ):
        raise ValueError("Phase-3 trade entry/tape snapshot drift")
    if _sha256(
        tape.get("eligible_universe_sha256"),
        label="Phase-3 canonical trade universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 trade feature universe",
    ):
        raise ValueError("Phase-3 trade entry/tape universe drift")

    trade_registry_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "trade_flow"
    }
    expected_ids = set(TRADE_FEATURE_IDS)
    if trade_registry_ids != expected_ids:
        raise ValueError(
            "Phase-3 trade feature registry changed: "
            f"missing={sorted(expected_ids - trade_registry_ids)} "
            f"extra={sorted(trade_registry_ids - expected_ids)}"
        )
    if registry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 trade registry allows future state")
    if registry.get("outcome_dependency_allowed") is not False:
        raise ValueError("Phase-3 trade registry depends on outcomes")

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 trade feature subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 trade feature subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 trade feature snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 trade cutoff is not inclusive")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 trade feature subject repeats token: {token}"
            )
        subjects[token] = {
            "cutoff": _cutoff(row),
            "state": {
                "total": 0,
                "buys": 0,
                "sells": 0,
                "traders": set(),
                "buyers": set(),
                "sellers": set(),
                "buyer_counts": defaultdict(int),
                "seller_counts": defaultdict(int),
                "last_side": None,
                "side_streak": 0,
            },
            "post_cutoff_rows_ignored": 0,
        }

    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 trade feature subject count changed")

    previous_global = None
    total_rows = 0
    for raw in trade_rows:
        row = validate_phase3_canonical_trade_row(raw)
        token = row["token"]
        event = _event_key(row)
        global_key = (*event, token, row["source_id"])
        if previous_global is not None and global_key <= previous_global:
            raise ValueError(
                "Phase-3 canonical trade tape is not strictly chronological"
            )
        previous_global = global_key
        if event[0] > int(entry["snapshot_head_block"]):
            raise ValueError("Phase-3 canonical trade is after frozen snapshot")
        total_rows += 1

        subject = subjects.get(token)
        if subject is None:
            continue
        if event > subject["cutoff"]:
            subject["post_cutoff_rows_ignored"] += 1
            continue

        state = subject["state"]
        initiator = row["initiator"]
        side = row["side"]
        state["total"] += 1
        state["traders"].add(initiator)
        if side == "buy":
            state["buys"] += 1
            state["buyers"].add(initiator)
            state["buyer_counts"][initiator] += 1
        else:
            state["sells"] += 1
            state["sellers"].add(initiator)
            state["seller_counts"][initiator] += 1
        if state["last_side"] == side:
            state["side_streak"] += 1
        else:
            state["last_side"] = side
            state["side_streak"] = 1

    if total_rows != int(tape.get("trade_rows", -1)):
        raise ValueError("Phase-3 canonical trade row count changed")

    output_rows = []
    missing_total = 0
    ignored_future = 0
    subjects_without_trades = 0
    for token in sorted(subjects):
        subject = subjects[token]
        state = subject["state"]
        total = int(state["total"])
        buys = int(state["buys"])
        sells = int(state["sells"])
        if total != buys + sells:
            raise ValueError("Phase-3 trade buy/sell counts do not reconcile")

        repeat_buy_trades = sum(
            max(0, count - 1)
            for count in state["buyer_counts"].values()
        )
        repeat_sell_trades = sum(
            max(0, count - 1)
            for count in state["seller_counts"].values()
        )
        values = {
            "trade.total_trades_so_far": total,
            "trade.buy_trades_so_far": buys,
            "trade.sell_trades_so_far": sells,
            "trade.buy_trade_share_so_far": _share(buys, total),
            "trade.unique_traders_so_far": len(state["traders"]),
            "trade.unique_buyers_so_far": len(state["buyers"]),
            "trade.unique_sellers_so_far": len(state["sellers"]),
            "trade.repeat_buyer_trade_share_so_far": _share(
                repeat_buy_trades,
                buys,
            ),
            "trade.repeat_seller_trade_share_so_far": _share(
                repeat_sell_trades,
                sells,
            ),
            "trade.current_side_is_buy": (
                None
                if state["last_side"] is None
                else state["last_side"] == "buy"
            ),
            "trade.current_side_streak_trades": (
                None
                if state["last_side"] is None
                else int(state["side_streak"])
            ),
        }
        if set(values) != expected_ids:
            raise ValueError("Phase-3 trade feature output set changed")
        missing = sorted(
            feature_id
            for feature_id, value in values.items()
            if value is None
        )
        if total == 0:
            subjects_without_trades += 1
        missing_total += len(missing)
        ignored_future += int(subject["post_cutoff_rows_ignored"])
        output_rows.append({
            "version": PHASE3_TRADE_FEATURE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": subject["cutoff"][0],
            "feature_cutoff_transaction_index": (
                None
                if subject["cutoff"][1] == -1
                else subject["cutoff"][1]
            ),
            "feature_cutoff_log_index": subject["cutoff"][2],
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
            "version": PHASE3_TRADE_FEATURE_VERSION,
            "feature_family": "trade_flow",
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
        "version": PHASE3_TRADE_FEATURE_VERSION,
        "snapshot_head_block": int(entry["snapshot_head_block"]),
        "feature_family": "trade_flow",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(TRADE_FEATURE_IDS),
        "features_per_subject": len(TRADE_FEATURE_IDS),
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
        "phase3_trade_features_ready": True,
    }
    return manifest, summary


def build_phase3_trade_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_trade_handoff_sha256: str,
) -> dict:
    """Bind trade features to exact subject and complete trade-tape identities."""

    summary = dict(feature_summary)
    if str(summary.get("version") or "") != PHASE3_TRADE_FEATURE_VERSION:
        raise ValueError("Phase-3 trade feature handoff version changed")
    if summary.get("feature_family") != "trade_flow":
        raise ValueError("Phase-3 trade feature family changed")
    if summary.get("trade_coverage_complete") is not True:
        raise ValueError("Phase-3 trade feature coverage is incomplete")
    if summary.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 trade feature handoff consumed outcomes")
    if summary.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 trade feature handoff exposes outcomes")
    if summary.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 trade feature handoff allows future state")
    if summary.get("future_trade_rows_used") is not False:
        raise ValueError("Phase-3 trade feature handoff used future rows")
    if summary.get("missingness_recorded") is not True:
        raise ValueError("Phase-3 trade feature missingness is not recorded")
    if summary.get("data_quality_recorded") is not True:
        raise ValueError("Phase-3 trade feature data quality is not recorded")
    if summary.get("phase3_trade_features_ready") is not True:
        raise ValueError("Phase-3 trade features are not ready")

    return {
        "version": PHASE3_TRADE_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "trade_flow",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 trade feature registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 trade feature rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 trade feature summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 trade feature entry",
        ),
        "canonical_trade_handoff_sha256": _sha256(
            canonical_trade_handoff_sha256,
            label="Phase-3 canonical trade handoff",
        ),
        "canonical_trade_rows_sha256": _sha256(
            summary.get("canonical_trade_rows_sha256"),
            label="Phase-3 canonical trade rows",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 trade feature universe",
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
        "phase3_trade_features_ready": True,
    }
