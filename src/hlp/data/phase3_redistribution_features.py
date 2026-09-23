"""Causal Phase-3 ERC-20 supply-redistribution features."""

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
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.phase3_holder_features import (
    PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION,
    ZERO_ADDRESS,
    validate_phase3_canonical_transfer_row,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_REDISTRIBUTION_FEATURE_VERSION = (
    "phase3-supply-redistribution-features-v1"
)
PHASE3_REDISTRIBUTION_FEATURE_HANDOFF_VERSION = (
    "phase3-supply-redistribution-features-handoff-v1"
)

REDISTRIBUTION_FEATURE_IDS = (
    "redistribution.transfer_events_so_far",
    "redistribution.unique_senders_so_far",
    "redistribution.unique_receivers_so_far",
    "redistribution.recipient_activation_events_so_far",
    "redistribution.sender_exit_events_so_far",
    "redistribution.net_holder_creation_events_so_far",
    "redistribution.gross_transfer_supply_multiple_so_far",
    "redistribution.transfer_value_hhi_so_far",
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
        raise ValueError(
            "Phase-3 redistribution transfer position is invalid"
        )
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 redistribution cutoff is invalid")
    return block, tx, log


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _ratio(numerator: int, denominator: int) -> str:
    if numerator < 0 or denominator <= 0:
        raise ValueError("Phase-3 redistribution ratio inputs invalid")
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
    return _decimal_text(value)


def _value_hhi(values: list[int]) -> str:
    if not values or any(value <= 0 for value in values):
        raise ValueError(
            "Phase-3 redistribution HHI requires positive transfers"
        )
    total = sum(values)
    with localcontext() as context:
        context.prec = 80
        hhi = sum(
            (
                (Decimal(value) / Decimal(total)) ** 2
                for value in values
            ),
            Decimal("0"),
        )
    return _decimal_text(hhi)


def materialize_phase3_redistribution_features(
    subject_rows: Iterable[Mapping[str, object]],
    transfer_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    transfer_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Replay complete transfers and measure real token redistribution."""

    entry = dict(entry_handoff)
    tape = dict(transfer_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 redistribution entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 redistribution entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 redistribution entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 redistribution entry allows future state")

    if (
        str(tape.get("version") or "")
        != PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 redistribution transfer version changed")
    for flag in (
        "historical_event_scan_complete",
        "initial_mint_coverage_complete",
        "transfer_coverage_complete",
    ):
        if tape.get(flag) is not True:
            raise ValueError(
                f"Phase-3 redistribution requires complete {flag}"
            )
    if tape.get("outcome_rows_consumed") is not False:
        raise ValueError(
            "Phase-3 redistribution transfer tape consumed outcomes"
        )
    if tape.get("future_state_allowed") is not False:
        raise ValueError(
            "Phase-3 redistribution transfer tape allows future state"
        )
    if int(tape.get("snapshot_head_block", -1)) != int(
        entry.get("snapshot_head_block", -2)
    ):
        raise ValueError(
            "Phase-3 redistribution entry/transfer snapshot drift"
        )
    if _sha256(
        tape.get("eligible_universe_sha256"),
        label="Phase-3 redistribution transfer universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 redistribution entry universe",
    ):
        raise ValueError(
            "Phase-3 redistribution entry/transfer universe drift"
        )

    family_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "supply_redistribution"
    }
    if family_ids != set(REDISTRIBUTION_FEATURE_IDS):
        raise ValueError(
            "Phase-3 redistribution feature registry changed"
        )

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError(
                "Phase-3 redistribution subject fields changed"
            )
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError(
                "Phase-3 redistribution subject version changed"
            )
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError(
                "Phase-3 redistribution snapshot kind changed"
            )
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError(
                "Phase-3 redistribution cutoff is not inclusive"
            )
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 redistribution repeats subject: {token}"
            )
        cutoff = _cutoff(row)
        if cutoff[0] > int(entry["snapshot_head_block"]):
            raise ValueError(
                f"Phase-3 redistribution cutoff after snapshot: {token}"
            )
        subjects[token] = {
            "cutoff": cutoff,
            "balances": {},
            "supply": 0,
            "first_mint_seen": False,
            "events": 0,
            "senders": set(),
            "receivers": set(),
            "activations": 0,
            "exits": 0,
            "values": [],
            "post_cutoff_rows_ignored": 0,
        }
    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError(
            "Phase-3 redistribution subject count drift"
        )

    previous_global = None
    total_rows = 0
    for raw in transfer_rows:
        row = validate_phase3_canonical_transfer_row(raw)
        event = _event_key(row)
        token = row["token"]
        global_key = (*event, token, row["transaction_hash"])
        if previous_global is not None and global_key <= previous_global:
            raise ValueError(
                "Phase-3 redistribution transfer tape is not chronological"
            )
        previous_global = global_key
        if event[0] > int(entry["snapshot_head_block"]):
            raise ValueError(
                "Phase-3 redistribution transfer after frozen snapshot"
            )
        total_rows += 1

        state = subjects.get(token)
        if state is None:
            continue
        if event > state["cutoff"]:
            state["post_cutoff_rows_ignored"] += 1
            continue

        from_address = row["from_address"]
        to_address = row["to_address"]
        value = int(row["value_raw"])
        balances = state["balances"]

        if from_address == to_address:
            if from_address != ZERO_ADDRESS:
                current = balances.get(from_address, 0)
                if current < value:
                    raise ValueError(
                        "Phase-3 redistribution self-transfer exceeds balance"
                    )
            continue

        receiver_was_zero = (
            to_address != ZERO_ADDRESS
            and balances.get(to_address, 0) == 0
        )

        if from_address == ZERO_ADDRESS:
            state["supply"] += value
            state["first_mint_seen"] = True
        else:
            current = balances.get(from_address, 0)
            if current < value:
                raise ValueError(
                    f"Phase-3 redistribution debit exceeds balance: {token}"
                )
            next_balance = current - value
            if next_balance:
                balances[from_address] = next_balance
            else:
                balances.pop(from_address, None)

        if to_address == ZERO_ADDRESS:
            if state["supply"] < value:
                raise ValueError(
                    f"Phase-3 redistribution burn exceeds supply: {token}"
                )
            state["supply"] -= value
        else:
            balances[to_address] = balances.get(to_address, 0) + value

        is_redistribution = (
            value > 0
            and from_address != ZERO_ADDRESS
            and to_address != ZERO_ADDRESS
        )
        if not is_redistribution:
            continue

        state["events"] += 1
        state["senders"].add(from_address)
        state["receivers"].add(to_address)
        state["values"].append(value)
        if receiver_was_zero:
            state["activations"] += 1
        if balances.get(from_address, 0) == 0:
            state["exits"] += 1

    if total_rows != int(tape.get("transfer_rows", -1)):
        raise ValueError(
            "Phase-3 redistribution canonical transfer count changed"
        )

    output_rows = []
    ignored_future = 0
    subjects_without_redistribution = 0
    missing_total = 0
    for token in sorted(subjects):
        state = subjects[token]
        if not state["first_mint_seen"]:
            raise ValueError(
                f"Phase-3 redistribution subject lacks initial mint: {token}"
            )
        if state["supply"] <= 0:
            raise ValueError(
                f"Phase-3 redistribution non-positive supply: {token}"
            )
        balances = [
            int(value)
            for value in state["balances"].values()
            if int(value) > 0
        ]
        if sum(balances) != int(state["supply"]):
            raise ValueError(
                f"Phase-3 redistribution balances/supply drift: {token}"
            )

        values = {
            "redistribution.transfer_events_so_far": int(
                state["events"]
            ),
            "redistribution.unique_senders_so_far": len(
                state["senders"]
            ),
            "redistribution.unique_receivers_so_far": len(
                state["receivers"]
            ),
            "redistribution.recipient_activation_events_so_far": int(
                state["activations"]
            ),
            "redistribution.sender_exit_events_so_far": int(
                state["exits"]
            ),
            "redistribution.net_holder_creation_events_so_far": (
                int(state["activations"]) - int(state["exits"])
            ),
            "redistribution.gross_transfer_supply_multiple_so_far": None,
            "redistribution.transfer_value_hhi_so_far": None,
        }
        missing = []
        if state["values"]:
            values[
                "redistribution.gross_transfer_supply_multiple_so_far"
            ] = _ratio(sum(state["values"]), int(state["supply"]))
            values[
                "redistribution.transfer_value_hhi_so_far"
            ] = _value_hhi(state["values"])
        else:
            subjects_without_redistribution += 1
            missing = [
                "redistribution.gross_transfer_supply_multiple_so_far",
                "redistribution.transfer_value_hhi_so_far",
            ]
        missing_total += len(missing)
        if set(values) != set(REDISTRIBUTION_FEATURE_IDS):
            raise ValueError(
                "Phase-3 redistribution feature output set changed"
            )
        ignored_future += int(state["post_cutoff_rows_ignored"])
        output_rows.append({
            "version": PHASE3_REDISTRIBUTION_FEATURE_VERSION,
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
            "missing_feature_ids": sorted(missing),
            "data_quality": {
                "historical_transfer_scan_complete": True,
                "initial_mint_covered": True,
                "balances_reconcile_to_accounted_supply": True,
                "mint_burn_self_zero_value_excluded": True,
                "future_transfer_rows_used": False,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_REDISTRIBUTION_FEATURE_VERSION,
            "feature_family": "supply_redistribution",
            "feature_registry_sha256": registry["registry_sha256"],
            "canonical_transfer_rows_sha256": tape[
                "canonical_transfer_rows_sha256"
            ],
            "transfer_coverage_complete": True,
            "outcome_rows_consumed": False,
            "future_transfer_rows_used": False,
        },
    )
    summary = {
        "version": PHASE3_REDISTRIBUTION_FEATURE_VERSION,
        "snapshot_head_block": int(entry["snapshot_head_block"]),
        "feature_family": "supply_redistribution",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(REDISTRIBUTION_FEATURE_IDS),
        "features_per_subject": len(REDISTRIBUTION_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_transfer_rows_validated": total_rows,
        "canonical_transfer_rows_sha256": str(
            tape["canonical_transfer_rows_sha256"]
        ),
        "transfer_coverage_complete": True,
        "subjects_without_redistribution": subjects_without_redistribution,
        "missing_feature_values": missing_total,
        "post_cutoff_subject_transfer_rows_ignored": ignored_future,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_redistribution_features_ready": True,
    }
    return manifest, summary


def build_phase3_redistribution_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_transfer_handoff_sha256: str,
) -> dict:
    """Bind redistribution features to exact subjects and transfer identity."""

    summary = dict(feature_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_REDISTRIBUTION_FEATURE_VERSION
    ):
        raise ValueError(
            "Phase-3 redistribution handoff version changed"
        )
    if summary.get("feature_family") != "supply_redistribution":
        raise ValueError(
            "Phase-3 redistribution feature family changed"
        )
    if summary.get("transfer_coverage_complete") is not True:
        raise ValueError(
            "Phase-3 redistribution transfer coverage incomplete"
        )
    for flag in (
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_redistribution_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 redistribution handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_transfer_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 redistribution handoff violates {flag}"
            )
    return {
        "version": PHASE3_REDISTRIBUTION_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "supply_redistribution",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 redistribution registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 redistribution rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 redistribution summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 redistribution entry",
        ),
        "canonical_transfer_handoff_sha256": _sha256(
            canonical_transfer_handoff_sha256,
            label="Phase-3 redistribution transfer handoff",
        ),
        "canonical_transfer_rows_sha256": _sha256(
            summary.get("canonical_transfer_rows_sha256"),
            label="Phase-3 redistribution transfer rows",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 redistribution universe",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_redistribution_features_ready": True,
    }
