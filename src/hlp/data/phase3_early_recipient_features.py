"""Causal Phase-3 early-recipient cohort activity features."""

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
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_EARLY_RECIPIENT_FEATURE_VERSION = (
    "phase3-early-recipient-features-v1"
)
PHASE3_EARLY_RECIPIENT_FEATURE_HANDOFF_VERSION = (
    "phase3-early-recipient-features-handoff-v1"
)
EARLY_RECIPIENT_COHORT_LIMIT = 10

EARLY_RECIPIENT_FEATURE_IDS = (
    "early.cohort_size",
    "early.cohort_nonzero_balance_count",
    "early.cohort_retention_share",
    "early.cohort_current_supply_share",
    "early.cohort_received_supply_multiple_so_far",
    "early.cohort_sent_supply_multiple_so_far",
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
            "Phase-3 early-recipient transfer position is invalid"
        )
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 early-recipient cutoff is invalid")
    return block, tx, log


def _ratio(numerator: int, denominator: int) -> str:
    if numerator < 0 or denominator <= 0:
        raise ValueError(
            "Phase-3 early-recipient ratio inputs are invalid"
        )
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def materialize_phase3_early_recipient_features(
    subject_rows: Iterable[Mapping[str, object]],
    transfer_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    transfer_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Replay transfers and freeze the first-ten positive-recipient cohort."""

    entry = dict(entry_handoff)
    transfer = dict(transfer_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 early-recipient entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 early-recipient entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError(
            "Phase-3 early-recipient entry consumed outcomes"
        )
    if entry.get("future_state_allowed") is not False:
        raise ValueError(
            "Phase-3 early-recipient entry allows future state"
        )

    if (
        str(transfer.get("version") or "")
        != PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION
    ):
        raise ValueError(
            "Phase-3 early-recipient transfer handoff changed"
        )
    for flag in (
        "historical_event_scan_complete",
        "initial_mint_coverage_complete",
        "transfer_coverage_complete",
        "phase3_canonical_transfer_tape_ready",
    ):
        if transfer.get(flag) is not True:
            raise ValueError(
                f"Phase-3 early-recipient transfer handoff lacks {flag}"
            )
    if transfer.get("outcome_rows_consumed") is not False:
        raise ValueError(
            "Phase-3 early-recipient transfer handoff consumed outcomes"
        )
    if transfer.get("future_state_allowed") is not False:
        raise ValueError(
            "Phase-3 early-recipient transfer handoff allows future state"
        )

    snapshot = int(entry.get("snapshot_head_block", -1))
    if int(transfer.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError(
            "Phase-3 early-recipient entry/transfer snapshot drift"
        )
    if _sha256(
        transfer.get("eligible_universe_sha256"),
        label="Phase-3 early-recipient transfer universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 early-recipient entry universe",
    ):
        raise ValueError("Phase-3 early-recipient universe drift")

    family_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "early_recipient_activity"
    }
    if family_ids != set(EARLY_RECIPIENT_FEATURE_IDS):
        raise ValueError(
            "Phase-3 early-recipient feature registry changed"
        )

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError(
                "Phase-3 early-recipient subject fields changed"
            )
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError(
                "Phase-3 early-recipient subject version changed"
            )
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError(
                "Phase-3 early-recipient snapshot kind changed"
            )
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError(
                "Phase-3 early-recipient cutoff is not inclusive"
            )
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 early-recipient repeats subject: {token}"
            )
        cutoff = _cutoff(row)
        if cutoff[0] > snapshot:
            raise ValueError(
                f"Phase-3 early-recipient cutoff after snapshot: {token}"
            )
        subjects[token] = {
            "cutoff": cutoff,
            "balances": {},
            "supply": 0,
            "first_mint_seen": False,
            "cohort": [],
            "cohort_set": set(),
            "received": 0,
            "sent": 0,
            "post_cutoff_rows_ignored": 0,
        }
    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 early-recipient subject count drift")

    previous_global = None
    total_rows = 0
    for raw in transfer_rows:
        row = validate_phase3_canonical_transfer_row(raw)
        event = _event(row)
        token = row["token"]
        key = (*event, token, row["transaction_hash"])
        if previous_global is not None and key <= previous_global:
            raise ValueError(
                "Phase-3 early-recipient transfer tape is not chronological"
            )
        previous_global = key
        if event[0] > snapshot:
            raise ValueError(
                "Phase-3 early-recipient transfer after frozen snapshot"
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
                        "Phase-3 early-recipient self-transfer exceeds balance"
                    )
            continue

        if from_address == ZERO_ADDRESS:
            state["supply"] += value
            if value > 0:
                state["first_mint_seen"] = True
        else:
            current = balances.get(from_address, 0)
            if current < value:
                raise ValueError(
                    f"Phase-3 early-recipient debit exceeds balance: {token}"
                )
            next_balance = current - value
            if next_balance:
                balances[from_address] = next_balance
            else:
                balances.pop(from_address, None)

        if to_address == ZERO_ADDRESS:
            if state["supply"] < value:
                raise ValueError(
                    f"Phase-3 early-recipient burn exceeds supply: {token}"
                )
            state["supply"] -= value
        else:
            if (
                value > 0
                and to_address not in state["cohort_set"]
                and len(state["cohort"]) < EARLY_RECIPIENT_COHORT_LIMIT
            ):
                state["cohort"].append(to_address)
                state["cohort_set"].add(to_address)
            balances[to_address] = balances.get(to_address, 0) + value

        if value > 0:
            if from_address in state["cohort_set"]:
                state["sent"] += value
            if to_address in state["cohort_set"]:
                state["received"] += value

    if total_rows != int(transfer.get("transfer_rows", -1)):
        raise ValueError(
            "Phase-3 early-recipient canonical transfer count changed"
        )

    output_rows = []
    ignored_future = 0
    for token in sorted(subjects):
        state = subjects[token]
        if not state["first_mint_seen"]:
            raise ValueError(
                f"Phase-3 early-recipient subject lacks initial mint: {token}"
            )
        supply = int(state["supply"])
        if supply <= 0:
            raise ValueError(
                f"Phase-3 early-recipient supply non-positive: {token}"
            )
        if not state["cohort"]:
            raise ValueError(
                f"Phase-3 early-recipient cohort is empty: {token}"
            )
        balances = [
            int(value)
            for value in state["balances"].values()
            if int(value) > 0
        ]
        if sum(balances) != supply:
            raise ValueError(
                f"Phase-3 early-recipient balances/supply drift: {token}"
            )

        cohort_size = len(state["cohort"])
        cohort_balances = [
            int(state["balances"].get(address, 0))
            for address in state["cohort"]
        ]
        retained = sum(1 for value in cohort_balances if value > 0)
        current_balance = sum(cohort_balances)
        values = {
            "early.cohort_size": cohort_size,
            "early.cohort_nonzero_balance_count": retained,
            "early.cohort_retention_share": _ratio(
                retained, cohort_size
            ),
            "early.cohort_current_supply_share": _ratio(
                current_balance, supply
            ),
            "early.cohort_received_supply_multiple_so_far": _ratio(
                int(state["received"]), supply
            ),
            "early.cohort_sent_supply_multiple_so_far": _ratio(
                int(state["sent"]), supply
            ),
        }
        ignored_future += int(state["post_cutoff_rows_ignored"])
        output_rows.append({
            "version": PHASE3_EARLY_RECIPIENT_FEATURE_VERSION,
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
            "missing_feature_ids": [],
            "data_quality": {
                "cohort_limit": EARLY_RECIPIENT_COHORT_LIMIT,
                "complete_transfer_history_verified": True,
                "address_type_not_assumed": True,
                "creator_identity_not_assumed": True,
                "future_transfer_rows_used": False,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_EARLY_RECIPIENT_FEATURE_VERSION,
            "feature_family": "early_recipient_activity",
            "feature_registry_sha256": registry["registry_sha256"],
            "canonical_transfer_rows_sha256": transfer[
                "canonical_transfer_rows_sha256"
            ],
            "cohort_limit": EARLY_RECIPIENT_COHORT_LIMIT,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )
    summary = {
        "version": PHASE3_EARLY_RECIPIENT_FEATURE_VERSION,
        "snapshot_head_block": snapshot,
        "feature_family": "early_recipient_activity",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(EARLY_RECIPIENT_FEATURE_IDS),
        "features_per_subject": len(EARLY_RECIPIENT_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_transfer_rows_sha256": str(
            transfer["canonical_transfer_rows_sha256"]
        ),
        "cohort_limit": EARLY_RECIPIENT_COHORT_LIMIT,
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
        "phase3_early_recipient_features_ready": True,
    }
    return manifest, summary


def build_phase3_early_recipient_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_transfer_handoff_sha256: str,
) -> dict:
    summary = dict(feature_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_EARLY_RECIPIENT_FEATURE_VERSION
    ):
        raise ValueError(
            "Phase-3 early-recipient handoff version changed"
        )
    if summary.get("feature_family") != "early_recipient_activity":
        raise ValueError(
            "Phase-3 early-recipient feature family changed"
        )
    for flag in (
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_early_recipient_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 early-recipient handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_transfer_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 early-recipient handoff violates {flag}"
            )
    if int(summary.get("cohort_limit", -1)) != (
        EARLY_RECIPIENT_COHORT_LIMIT
    ):
        raise ValueError(
            "Phase-3 early-recipient cohort limit changed"
        )
    return {
        "version": PHASE3_EARLY_RECIPIENT_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "early_recipient_activity",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 early-recipient registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 early-recipient rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 early-recipient summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 early-recipient entry",
        ),
        "canonical_transfer_handoff_sha256": _sha256(
            canonical_transfer_handoff_sha256,
            label="Phase-3 early-recipient transfer handoff",
        ),
        "canonical_transfer_rows_sha256": _sha256(
            summary.get("canonical_transfer_rows_sha256"),
            label="Phase-3 early-recipient transfer rows",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 early-recipient universe",
        ),
        "cohort_limit": EARLY_RECIPIENT_COHORT_LIMIT,
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_early_recipient_features_ready": True,
    }
