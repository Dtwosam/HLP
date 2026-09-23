"""Causal Phase-3 ERC-20 holder and concentration features."""

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
from hlp.data.snapshot import write_jsonl_snapshot


ZERO_ADDRESS = "0x" + "00" * 20

PHASE3_CANONICAL_TRANSFER_VERSION = "phase3-canonical-transfer-v1"
PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION = (
    "phase3-canonical-transfer-handoff-v1"
)
PHASE3_HOLDER_FEATURE_VERSION = "phase3-holder-features-v1"
PHASE3_HOLDER_FEATURE_HANDOFF_VERSION = (
    "phase3-holder-features-handoff-v1"
)

HOLDER_FEATURE_IDS = (
    "holder.holder_count",
    "holder.top1_balance_share",
    "holder.top5_balance_share",
    "holder.top10_balance_share",
    "holder.balance_hhi",
    "holder.balance_gini",
    "holder.transfer_events_so_far",
    "holder.unique_transfer_participants_so_far",
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
        raise ValueError("Phase-3 canonical transfer position is invalid")
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    return (
        int(row["feature_cutoff_block"]),
        (
            -1
            if row.get("feature_cutoff_transaction_index") is None
            else int(row["feature_cutoff_transaction_index"])
        ),
        int(row["feature_cutoff_log_index"]),
    )


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _share(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0 or numerator < 0:
        raise ValueError("Phase-3 holder share inputs are invalid")
    with localcontext() as context:
        context.prec = 80
        return Decimal(numerator) / Decimal(denominator)


def _concentration(balances: list[int]) -> dict[str, str]:
    if not balances or any(value <= 0 for value in balances):
        raise ValueError("Phase-3 holder concentration has no balances")
    values = sorted(balances, reverse=True)
    supply = sum(values)
    with localcontext() as context:
        context.prec = 80
        shares = [
            Decimal(value) / Decimal(supply)
            for value in values
        ]
        hhi = sum(
            (share * share for share in shares),
            Decimal("0"),
        )

        ascending = list(reversed(values))
        n = len(ascending)
        weighted = sum(
            Decimal(index) * Decimal(value)
            for index, value in enumerate(ascending, start=1)
        )
        gini = (
            (Decimal(2) * weighted)
            / (Decimal(n) * Decimal(supply))
            - Decimal(n + 1) / Decimal(n)
        )
        if gini < 0 and abs(gini) < Decimal("1e-60"):
            gini = Decimal("0")

    return {
        "holder.top1_balance_share": _decimal_text(
            _share(sum(values[:1]), supply)
        ),
        "holder.top5_balance_share": _decimal_text(
            _share(sum(values[:5]), supply)
        ),
        "holder.top10_balance_share": _decimal_text(
            _share(sum(values[:10]), supply)
        ),
        "holder.balance_hhi": _decimal_text(hhi),
        "holder.balance_gini": _decimal_text(gini),
    }


def validate_phase3_canonical_transfer_row(
    raw: Mapping[str, object],
) -> dict:
    row = dict(raw)
    if (
        str(row.get("version") or "")
        != PHASE3_CANONICAL_TRANSFER_VERSION
    ):
        raise ValueError("Phase-3 canonical transfer version changed")
    if row.get("canonical_phase3_transfer") is not True:
        raise ValueError("Phase-3 transfer row is not canonical")
    if row.get("outcome_derived") is not False:
        raise ValueError("Phase-3 canonical transfer is outcome-derived")
    token = normalize_address(str(row.get("token") or ""))
    from_address = normalize_address(
        str(row.get("from_address") or "")
    )
    to_address = normalize_address(
        str(row.get("to_address") or "")
    )
    value = int(row.get("value_raw", -1))
    if value < 0:
        raise ValueError("Phase-3 transfer value cannot be negative")
    event = _event_key(row)
    tx_hash = str(row.get("transaction_hash") or "").lower()
    if not tx_hash.startswith("0x") or len(tx_hash) != 66:
        raise ValueError("Phase-3 transfer transaction hash is invalid")
    return {
        **row,
        "token": token,
        "from_address": from_address,
        "to_address": to_address,
        "value_raw": value,
        "transaction_hash": tx_hash,
        "block_number": event[0],
        "transaction_index": None if event[1] == -1 else event[1],
        "log_index": event[2],
    }


def materialize_phase3_holder_features(
    subject_rows: Iterable[Mapping[str, object]],
    transfer_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    transfer_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Replay complete ERC-20 transfers only through each feature cutoff."""

    entry = dict(entry_handoff)
    tape = dict(transfer_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 holder entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 holder entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 holder entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 holder entry allows future state")

    if (
        str(tape.get("version") or "")
        != PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 transfer handoff version changed")
    for flag in (
        "historical_event_scan_complete",
        "initial_mint_coverage_complete",
        "transfer_coverage_complete",
    ):
        if tape.get(flag) is not True:
            raise ValueError(
                f"Phase-3 holder features require complete {flag}"
            )
    if tape.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 transfer tape consumed outcomes")
    if tape.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 transfer tape allows future state")
    if int(tape.get("snapshot_head_block", -1)) != int(
        entry.get("snapshot_head_block", -2)
    ):
        raise ValueError("Phase-3 holder entry/transfer snapshot drift")
    if _sha256(
        tape.get("eligible_universe_sha256"),
        label="Phase-3 holder transfer universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 holder entry universe",
    ):
        raise ValueError("Phase-3 holder entry/transfer universe drift")

    holder_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "holder_state"
    }
    if holder_ids != set(HOLDER_FEATURE_IDS):
        raise ValueError("Phase-3 holder feature registry changed")

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 holder subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 holder subject version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 holder subject repeats token: {token}"
            )
        cutoff = _cutoff(row)
        if cutoff[0] > int(entry["snapshot_head_block"]):
            raise ValueError(
                f"Phase-3 holder cutoff after snapshot: {token}"
            )
        subjects[token] = {
            "cutoff": cutoff,
            "balances": {},
            "supply": 0,
            "transfers": 0,
            "participants": set(),
            "first_mint_seen": False,
            "post_cutoff_rows_ignored": 0,
        }
    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 holder subject count drift")

    previous_global = None
    total_rows = 0
    for raw in transfer_rows:
        row = validate_phase3_canonical_transfer_row(raw)
        event = _event_key(row)
        token = row["token"]
        global_key = (
            *event,
            token,
            row["transaction_hash"],
        )
        if previous_global is not None and global_key <= previous_global:
            raise ValueError(
                "Phase-3 canonical transfer tape is not strictly chronological"
            )
        previous_global = global_key
        if event[0] > int(entry["snapshot_head_block"]):
            raise ValueError("Phase-3 transfer row is after frozen snapshot")
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
        state["transfers"] += 1
        if from_address != ZERO_ADDRESS:
            state["participants"].add(from_address)
        if to_address != ZERO_ADDRESS:
            state["participants"].add(to_address)

        if from_address == to_address:
            if from_address != ZERO_ADDRESS:
                current = balances.get(from_address, 0)
                if current < value:
                    raise ValueError(
                        "Phase-3 holder self-transfer exceeds known balance"
                    )
            continue

        if from_address == ZERO_ADDRESS:
            state["supply"] += value
            state["first_mint_seen"] = True
        else:
            current = balances.get(from_address, 0)
            if current < value:
                raise ValueError(
                    f"Phase-3 holder debit exceeds known balance: {token}"
                )
            next_balance = current - value
            if next_balance:
                balances[from_address] = next_balance
            else:
                balances.pop(from_address, None)

        if to_address == ZERO_ADDRESS:
            if state["supply"] < value:
                raise ValueError(
                    f"Phase-3 holder burn exceeds known supply: {token}"
                )
            state["supply"] -= value
        else:
            balances[to_address] = balances.get(to_address, 0) + value

    if total_rows != int(tape.get("transfer_rows", -1)):
        raise ValueError("Phase-3 canonical transfer row count changed")

    output_rows = []
    ignored_future = 0
    for token in sorted(subjects):
        state = subjects[token]
        if not state["first_mint_seen"]:
            raise ValueError(
                f"Phase-3 holder subject lacks initial mint: {token}"
            )
        if state["supply"] <= 0:
            raise ValueError(
                f"Phase-3 holder subject has non-positive supply: {token}"
            )
        balances = [
            int(value)
            for value in state["balances"].values()
            if int(value) > 0
        ]
        if sum(balances) != int(state["supply"]):
            raise ValueError(
                f"Phase-3 holder balances/supply drift: {token}"
            )
        concentration = _concentration(balances)
        values = {
            "holder.holder_count": len(balances),
            **concentration,
            "holder.transfer_events_so_far": int(state["transfers"]),
            "holder.unique_transfer_participants_so_far": len(
                state["participants"]
            ),
        }
        if set(values) != set(HOLDER_FEATURE_IDS):
            raise ValueError("Phase-3 holder feature output set changed")
        ignored_future += int(state["post_cutoff_rows_ignored"])
        output_rows.append({
            "version": PHASE3_HOLDER_FEATURE_VERSION,
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
                "historical_transfer_scan_complete": True,
                "initial_mint_covered": True,
                "balances_reconcile_to_accounted_supply": True,
                "future_transfer_rows_used": False,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_HOLDER_FEATURE_VERSION,
            "feature_family": "holder_state",
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
        "version": PHASE3_HOLDER_FEATURE_VERSION,
        "snapshot_head_block": int(entry["snapshot_head_block"]),
        "feature_family": "holder_state",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(HOLDER_FEATURE_IDS),
        "features_per_subject": len(HOLDER_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_transfer_rows_validated": total_rows,
        "canonical_transfer_rows_sha256": str(
            tape["canonical_transfer_rows_sha256"]
        ),
        "post_cutoff_subject_transfer_rows_ignored": ignored_future,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "transfer_coverage_complete": True,
        "initial_mint_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_holder_features_ready": True,
    }
    return manifest, summary


def build_phase3_holder_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_transfer_handoff_sha256: str,
) -> dict:
    summary = dict(feature_summary)
    if str(summary.get("version") or "") != PHASE3_HOLDER_FEATURE_VERSION:
        raise ValueError("Phase-3 holder feature handoff version changed")
    if summary.get("feature_family") != "holder_state":
        raise ValueError("Phase-3 holder feature family changed")
    for flag in (
        "transfer_coverage_complete",
        "initial_mint_coverage_complete",
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_holder_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 holder feature handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_transfer_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 holder feature handoff violates {flag}"
            )
    return {
        "version": PHASE3_HOLDER_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "holder_state",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 holder feature registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 holder feature rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 holder feature summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 holder feature entry",
        ),
        "canonical_transfer_handoff_sha256": _sha256(
            canonical_transfer_handoff_sha256,
            label="Phase-3 canonical transfer handoff",
        ),
        "canonical_transfer_rows_sha256": _sha256(
            summary.get("canonical_transfer_rows_sha256"),
            label="Phase-3 canonical transfer rows",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 holder feature universe",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "transfer_coverage_complete": True,
        "initial_mint_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_holder_features_ready": True,
    }
