import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_redistribution_features import (
    PHASE3_REDISTRIBUTION_FEATURE_HANDOFF_VERSION,
    PHASE3_REDISTRIBUTION_FEATURE_VERSION,
    build_phase3_redistribution_feature_handoff,
    materialize_phase3_redistribution_features,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
A = "0x" + "aa" * 20
B = "0x" + "bb" * 20
C = "0x" + "cc" * 20
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


def tape(rows=5, complete=True):
    return {
        "version": "phase3-canonical-transfer-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "transfer_rows": rows,
        "historical_event_scan_complete": complete,
        "initial_mint_coverage_complete": complete,
        "transfer_coverage_complete": complete,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
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


def test_redistribution_tracks_real_holder_movement_only(tmp_path: Path):
    rows = [
        transfer(1, ZERO, A, 100),
        transfer(2, A, B, 40),
        transfer(3, B, C, 10),
        transfer(4, A, B, 60),
        transfer(5, B, C, 5),
    ]
    output = tmp_path / "redistribution.jsonl"
    manifest, summary = materialize_phase3_redistribution_features(
        [subject()],
        rows,
        entry_handoff=entry(),
        transfer_handoff=tape(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    values = row["feature_values"]

    assert row["version"] == PHASE3_REDISTRIBUTION_FEATURE_VERSION
    assert values["redistribution.transfer_events_so_far"] == 3
    assert values["redistribution.unique_senders_so_far"] == 2
    assert values["redistribution.unique_receivers_so_far"] == 2
    assert values[
        "redistribution.recipient_activation_events_so_far"
    ] == 2
    assert values["redistribution.sender_exit_events_so_far"] == 1
    assert values[
        "redistribution.net_holder_creation_events_so_far"
    ] == 1
    assert values[
        "redistribution.gross_transfer_supply_multiple_so_far"
    ] == "1.1"
    assert values[
        "redistribution.transfer_value_hhi_so_far"
    ].startswith("0.487603305785")
    assert row["data_quality"][
        "mint_burn_self_zero_value_excluded"
    ] is True
    assert manifest["records"] == 1
    assert summary[
        "post_cutoff_subject_transfer_rows_ignored"
    ] == 1
    assert summary["future_transfer_rows_used"] is False


def test_redistribution_records_missingness_without_real_transfers(
    tmp_path: Path,
):
    rows = [
        transfer(1, ZERO, A, 100),
        transfer(2, A, A, 20),
    ]
    output = tmp_path / "none.jsonl"
    _, summary = materialize_phase3_redistribution_features(
        [subject()],
        rows,
        entry_handoff=entry(),
        transfer_handoff=tape(rows=2),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    assert row["feature_values"][
        "redistribution.transfer_events_so_far"
    ] == 0
    assert row["feature_values"][
        "redistribution.gross_transfer_supply_multiple_so_far"
    ] is None
    assert len(row["missing_feature_ids"]) == 2
    assert summary["subjects_without_redistribution"] == 1


def test_redistribution_requires_complete_transfer_coverage(tmp_path: Path):
    with pytest.raises(ValueError, match="requires complete"):
        materialize_phase3_redistribution_features(
            [subject()],
            [],
            entry_handoff=entry(),
            transfer_handoff=tape(rows=0, complete=False),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "bad.jsonl",
        )


def test_redistribution_handoff_is_outcome_blind():
    summary = {
        "version": PHASE3_REDISTRIBUTION_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "supply_redistribution",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 8,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_transfer_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_redistribution_features_ready": True,
    }
    handoff = build_phase3_redistribution_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_transfer_handoff_sha256=SHA,
    )
    assert handoff["version"] == (
        PHASE3_REDISTRIBUTION_FEATURE_HANDOFF_VERSION
    )
    assert handoff["transfer_coverage_complete"] is True
    assert handoff["future_transfer_rows_used"] is False
