"""Causal Phase-3 token-size and net-flow features."""

from __future__ import annotations

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
from hlp.data.phase3_holder_features import (
    PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION,
    ZERO_ADDRESS,
    validate_phase3_canonical_transfer_row,
)
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
    validate_phase3_canonical_trade_row,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION = (
    "phase3-trade-size-flow-features-v1"
)
PHASE3_TRADE_SIZE_FLOW_HANDOFF_VERSION = (
    "phase3-trade-size-flow-features-handoff-v1"
)

TRADE_SIZE_FLOW_FEATURE_IDS = (
    "flow.buy_token_supply_multiple_so_far",
    "flow.sell_token_supply_multiple_so_far",
    "flow.net_token_supply_multiple_so_far",
    "flow.gross_token_supply_multiple_so_far",
    "flow.mean_buy_size_supply_fraction",
    "flow.mean_sell_size_supply_fraction",
    "flow.max_buy_size_supply_fraction",
    "flow.max_sell_size_supply_fraction",
    "flow.sell_to_buy_token_amount_ratio",
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
        raise ValueError("Phase-3 size-flow event position is invalid")
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 size-flow cutoff is invalid")
    return block, tx, log


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("Phase-3 size-flow denominator is non-positive")
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
    return _decimal_text(value)


def _mean_supply_fraction(values: list[int], supply: int) -> str:
    if not values or supply <= 0:
        raise ValueError("Phase-3 size-flow mean inputs are invalid")
    with localcontext() as context:
        context.prec = 80
        value = (
            Decimal(sum(values))
            / Decimal(len(values))
            / Decimal(supply)
        )
    return _decimal_text(value)


def materialize_phase3_trade_size_flow_features(
    subject_rows: Iterable[Mapping[str, object]],
    trade_rows: Iterable[Mapping[str, object]],
    transfer_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    trade_tape_handoff: Mapping[str, object],
    transfer_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Normalize canonical token trade size by causal cutoff supply."""

    entry = dict(entry_handoff)
    trade_tape = dict(trade_tape_handoff)
    transfer_tape = dict(transfer_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 size-flow entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 size-flow entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 size-flow entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 size-flow entry allows future state")

    if (
        str(trade_tape.get("version") or "")
        != PHASE3_CANONICAL_TRADE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 size-flow trade handoff changed")
    if trade_tape.get("trade_coverage_complete") is not True:
        raise ValueError(
            "Phase-3 size-flow requires complete canonical trade coverage"
        )
    if (
        str(transfer_tape.get("version") or "")
        != PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 size-flow transfer handoff changed")
    for flag in (
        "historical_event_scan_complete",
        "initial_mint_coverage_complete",
        "transfer_coverage_complete",
    ):
        if transfer_tape.get(flag) is not True:
            raise ValueError(
                f"Phase-3 size-flow requires complete {flag}"
            )

    snapshot = int(entry.get("snapshot_head_block", -1))
    for label, tape in (
        ("trade", trade_tape),
        ("transfer", transfer_tape),
    ):
        if int(tape.get("snapshot_head_block", -2)) != snapshot:
            raise ValueError(
                f"Phase-3 size-flow {label} snapshot drift"
            )
        if _sha256(
            tape.get("eligible_universe_sha256"),
            label=f"Phase-3 size-flow {label} universe",
        ) != _sha256(
            entry.get("eligible_universe_sha256"),
            label="Phase-3 size-flow entry universe",
        ):
            raise ValueError(
                f"Phase-3 size-flow {label} universe drift"
            )
        if tape.get("outcome_rows_consumed") is not False:
            raise ValueError(
                f"Phase-3 size-flow {label} tape consumed outcomes"
            )
        if tape.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 size-flow {label} tape allows future state"
            )

    family_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "trade_size_flow"
    }
    if family_ids != set(TRADE_SIZE_FLOW_FEATURE_IDS):
        raise ValueError("Phase-3 size-flow feature registry changed")

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 size-flow subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 size-flow subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 size-flow snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 size-flow cutoff is not inclusive")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 size-flow repeats subject: {token}"
            )
        cutoff = _cutoff(row)
        if cutoff[0] > snapshot:
            raise ValueError(
                f"Phase-3 size-flow cutoff after snapshot: {token}"
            )
        subjects[token] = {
            "cutoff": cutoff,
            "supply": 0,
            "first_mint_seen": False,
            "buys": [],
            "sells": [],
            "post_cutoff_trade_rows_ignored": 0,
            "post_cutoff_transfer_rows_ignored": 0,
        }
    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 size-flow subject count drift")

    previous_transfer = None
    transfer_count = 0
    for raw in transfer_rows:
        row = validate_phase3_canonical_transfer_row(raw)
        event = _event(row)
        token = row["token"]
        key = (*event, token, row["transaction_hash"])
        if previous_transfer is not None and key <= previous_transfer:
            raise ValueError(
                "Phase-3 size-flow transfer tape is not chronological"
            )
        previous_transfer = key
        if event[0] > snapshot:
            raise ValueError(
                "Phase-3 size-flow transfer is after frozen snapshot"
            )
        transfer_count += 1
        state = subjects.get(token)
        if state is None:
            continue
        if event > state["cutoff"]:
            state["post_cutoff_transfer_rows_ignored"] += 1
            continue
        value = int(row["value_raw"])
        if row["from_address"] == ZERO_ADDRESS:
            state["supply"] += value
            state["first_mint_seen"] = True
        if row["to_address"] == ZERO_ADDRESS:
            if state["supply"] < value:
                raise ValueError(
                    f"Phase-3 size-flow burn exceeds supply: {token}"
                )
            state["supply"] -= value

    if transfer_count != int(transfer_tape.get("transfer_rows", -1)):
        raise ValueError(
            "Phase-3 size-flow canonical transfer count changed"
        )

    previous_trade = None
    trade_count = 0
    for raw in trade_rows:
        row = validate_phase3_canonical_trade_row(raw)
        event = _event(row)
        token = row["token"]
        key = (*event, token, row["source_id"])
        if previous_trade is not None and key <= previous_trade:
            raise ValueError(
                "Phase-3 size-flow trade tape is not chronological"
            )
        previous_trade = key
        if event[0] > snapshot:
            raise ValueError(
                "Phase-3 size-flow trade is after frozen snapshot"
            )
        token_amount = int(row.get("token_amount_raw", -1))
        quote_amount = int(row.get("quote_amount_raw", -1))
        if token_amount <= 0 or quote_amount <= 0:
            raise ValueError(
                "Phase-3 size-flow canonical trade lacks positive amounts"
            )
        trade_count += 1
        state = subjects.get(token)
        if state is None:
            continue
        if event > state["cutoff"]:
            state["post_cutoff_trade_rows_ignored"] += 1
            continue
        state["buys" if row["side"] == "buy" else "sells"].append(
            token_amount
        )

    if trade_count != int(trade_tape.get("trade_rows", -1)):
        raise ValueError("Phase-3 size-flow canonical trade count changed")

    output_rows = []
    missing_total = 0
    ignored_trades = 0
    ignored_transfers = 0
    for token in sorted(subjects):
        state = subjects[token]
        supply = int(state["supply"])
        if not state["first_mint_seen"]:
            raise ValueError(
                f"Phase-3 size-flow subject lacks initial mint: {token}"
            )
        if supply <= 0:
            raise ValueError(
                f"Phase-3 size-flow subject supply is non-positive: {token}"
            )
        buys = list(state["buys"])
        sells = list(state["sells"])
        buy_total = sum(buys)
        sell_total = sum(sells)

        values = {
            "flow.buy_token_supply_multiple_so_far": _ratio(
                buy_total, supply
            ),
            "flow.sell_token_supply_multiple_so_far": _ratio(
                sell_total, supply
            ),
            "flow.net_token_supply_multiple_so_far": _ratio(
                buy_total - sell_total, supply
            ),
            "flow.gross_token_supply_multiple_so_far": _ratio(
                buy_total + sell_total, supply
            ),
            "flow.mean_buy_size_supply_fraction": None,
            "flow.mean_sell_size_supply_fraction": None,
            "flow.max_buy_size_supply_fraction": None,
            "flow.max_sell_size_supply_fraction": None,
            "flow.sell_to_buy_token_amount_ratio": None,
        }
        missing = []
        if buys:
            values["flow.mean_buy_size_supply_fraction"] = (
                _mean_supply_fraction(buys, supply)
            )
            values["flow.max_buy_size_supply_fraction"] = _ratio(
                max(buys), supply
            )
            values["flow.sell_to_buy_token_amount_ratio"] = _ratio(
                sell_total, buy_total
            )
        else:
            missing.extend([
                "flow.mean_buy_size_supply_fraction",
                "flow.max_buy_size_supply_fraction",
                "flow.sell_to_buy_token_amount_ratio",
            ])
        if sells:
            values["flow.mean_sell_size_supply_fraction"] = (
                _mean_supply_fraction(sells, supply)
            )
            values["flow.max_sell_size_supply_fraction"] = _ratio(
                max(sells), supply
            )
        else:
            missing.extend([
                "flow.mean_sell_size_supply_fraction",
                "flow.max_sell_size_supply_fraction",
            ])
        missing_total += len(missing)
        ignored_trades += int(
            state["post_cutoff_trade_rows_ignored"]
        )
        ignored_transfers += int(
            state["post_cutoff_transfer_rows_ignored"]
        )
        output_rows.append({
            "version": PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": state["cutoff"][0],
            "feature_cutoff_transaction_index": (
                None if state["cutoff"][1] == -1 else state["cutoff"][1]
            ),
            "feature_cutoff_log_index": state["cutoff"][2],
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry["registry_sha256"],
            "feature_values": values,
            "missing_feature_ids": sorted(missing),
            "data_quality": {
                "trade_coverage_complete": True,
                "transfer_coverage_complete": True,
                "initial_mint_covered": True,
                "raw_quote_amounts_not_compared_across_assets": True,
                "future_trade_rows_used": False,
                "future_transfer_rows_used": False,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION,
            "feature_family": "trade_size_flow",
            "feature_registry_sha256": registry["registry_sha256"],
            "canonical_trade_rows_sha256": trade_tape[
                "canonical_trade_rows_sha256"
            ],
            "canonical_transfer_rows_sha256": transfer_tape[
                "canonical_transfer_rows_sha256"
            ],
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )
    summary = {
        "version": PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION,
        "snapshot_head_block": snapshot,
        "feature_family": "trade_size_flow",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(TRADE_SIZE_FLOW_FEATURE_IDS),
        "features_per_subject": len(TRADE_SIZE_FLOW_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_trade_rows_sha256": str(
            trade_tape["canonical_trade_rows_sha256"]
        ),
        "canonical_transfer_rows_sha256": str(
            transfer_tape["canonical_transfer_rows_sha256"]
        ),
        "trade_coverage_complete": True,
        "transfer_coverage_complete": True,
        "missing_feature_values": missing_total,
        "post_cutoff_subject_trade_rows_ignored": ignored_trades,
        "post_cutoff_subject_transfer_rows_ignored": ignored_transfers,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_trade_size_flow_features_ready": True,
    }
    return manifest, summary


def build_phase3_trade_size_flow_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_trade_handoff_sha256: str,
    canonical_transfer_handoff_sha256: str,
) -> dict:
    summary = dict(feature_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION
    ):
        raise ValueError("Phase-3 size-flow handoff version changed")
    if summary.get("feature_family") != "trade_size_flow":
        raise ValueError("Phase-3 size-flow family changed")
    for flag in (
        "trade_coverage_complete",
        "transfer_coverage_complete",
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_trade_size_flow_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 size-flow handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_trade_rows_used",
        "future_transfer_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 size-flow handoff violates {flag}"
            )
    return {
        "version": PHASE3_TRADE_SIZE_FLOW_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "trade_size_flow",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 size-flow registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 size-flow rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 size-flow summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 size-flow entry",
        ),
        "canonical_trade_handoff_sha256": _sha256(
            canonical_trade_handoff_sha256,
            label="Phase-3 size-flow trade handoff",
        ),
        "canonical_transfer_handoff_sha256": _sha256(
            canonical_transfer_handoff_sha256,
            label="Phase-3 size-flow transfer handoff",
        ),
        "canonical_trade_rows_sha256": _sha256(
            summary.get("canonical_trade_rows_sha256"),
            label="Phase-3 size-flow trade rows",
        ),
        "canonical_transfer_rows_sha256": _sha256(
            summary.get("canonical_transfer_rows_sha256"),
            label="Phase-3 size-flow transfer rows",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 size-flow universe",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "trade_coverage_complete": True,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_trade_size_flow_features_ready": True,
    }
