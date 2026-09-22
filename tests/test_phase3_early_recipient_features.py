import json
from pathlib import Path

import pytest

from hlp.data.phase3_early_recipient_features import (
    EARLY_RECIPIENT_COHORT_LIMIT,
    PHASE3_EARLY_RECIPIENT_FEATURE_HANDOFF_VERSION,
    PHASE3_EARLY_RECIPIENT_FEATURE_VERSION,
    build_phase3_early_recipient_feature_handoff,
    materialize_phase3_early_recipient_features,
)
from hlp.data.phase3_feature_registry import build_phase3_feature_registry


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
A = "0x" + "aa" * 20
B = "0x" + "bb" * 20
C = "0x" + "cc" * 20
D = "0x" + "dd" * 20
ZERO = "0x" + "00" * 20


def entry():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def transfer_handoff(rows=5):
    return {
        "version": "phase3-canonical-transfer-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "token_coverage_sha256": SHA,
        "universe_tokens": 1,
        "transfer_rows": rows,
        "historical_event_scan_complete": True,
        "initial_mint_coverage_complete": True,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_transfer_tape_ready": True,
    }


def subject():
    return {
        "version": "phase3-feature-subject-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 4,
        "feature_cutoff_transaction_index": 0,
        "feature_cutoff_log_index": 0,
        "feature_cutoff_inclusive": True,
        "selected_detector_id": "chosen",
        "detector_family": "peak_drawdown_rebound",
    }


def transfer(block, from_address, to_address, value):
    return {
        "version": "phase3-canonical-transfer-v1",
        "token": TOKEN,
        "from_address": from_address,
        "to_address": to_address,
        "value_raw": value,
        "block_number": block,
        "transaction_hash": "0x" + f"{block:064x}",
        "transaction_index": 0,
        "log_index": 0,
        "canonical_phase3_transfer": True,
        "outcome_derived": False,
    }


def test_early_recipient_features_freeze_first_positive_recipients(
    tmp_path: Path,
):
    rows = [
        transfer(1, ZERO, A, 100),
        transfer(2, A, B, 40),
        transfer(3, B, C, 10),
        transfer(4, A, D, 60),
        transfer(5, D, C, 5),
    ]
    output = tmp_path / "early.jsonl"
    manifest, summary = materialize_phase3_early_recipient_features(
        [subject()],
        rows,
        entry_handoff=entry(),
        transfer_handoff=transfer_handoff(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    feature = json.loads(output.read_text())
    values = feature["feature_values"]

    assert feature["version"] == PHASE3_EARLY_RECIPIENT_FEATURE_VERSION
    assert values["early.cohort_size"] == 4
    assert values["early.cohort_nonzero_balance_count"] == 3
    assert values["early.cohort_retention_share"] == "0.75"
    assert values["early.cohort_current_supply_share"] == "1"
    assert values[
        "early.cohort_received_supply_multiple_so_far"
    ] == "2.1"
    assert values["early.cohort_sent_supply_multiple_so_far"] == "1.1"
    assert feature["data_quality"]["address_type_not_assumed"] is True
    assert feature["data_quality"]["creator_identity_not_assumed"] is True
    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_transfer_rows_ignored"] == 1


def test_early_recipient_cohort_is_capped_at_ten(tmp_path: Path):
    recipients = [
        "0x" + f"{index:040x}"
        for index in range(1, 13)
    ]
    rows = [transfer(1, ZERO, A, 1000)]
    sender = A
    for index, recipient in enumerate(recipients, start=2):
        rows.append(transfer(index, sender, recipient, 1))
    cutoff = subject()
    cutoff["feature_cutoff_block"] = 20
    output = tmp_path / "capped.jsonl"
    materialize_phase3_early_recipient_features(
        [cutoff],
        rows,
        entry_handoff=entry(),
        transfer_handoff=transfer_handoff(rows=len(rows)),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    feature = json.loads(output.read_text())
    assert feature["feature_values"]["early.cohort_size"] == (
        EARLY_RECIPIENT_COHORT_LIMIT
    )


def test_early_recipient_handoff_is_outcome_blind():
    summary = {
        "version": PHASE3_EARLY_RECIPIENT_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "early_recipient_activity",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "cohort_limit": EARLY_RECIPIENT_COHORT_LIMIT,
        "feature_subjects": 1,
        "features_per_subject": 6,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_early_recipient_features_ready": True,
    }
    handoff = build_phase3_early_recipient_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_transfer_handoff_sha256=SHA,
    )
    assert handoff["version"] == (
        PHASE3_EARLY_RECIPIENT_FEATURE_HANDOFF_VERSION
    )
    assert handoff["cohort_limit"] == 10
    assert handoff["future_transfer_rows_used"] is False
