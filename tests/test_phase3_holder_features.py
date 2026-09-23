import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_holder_features import (
    PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION,
    PHASE3_CANONICAL_TRANSFER_VERSION,
    PHASE3_HOLDER_FEATURE_HANDOFF_VERSION,
    PHASE3_HOLDER_FEATURE_VERSION,
    build_phase3_holder_feature_handoff,
    materialize_phase3_holder_features,
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


def transfer_handoff(rows=5):
    return {
        "version": PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION,
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "transfer_rows": rows,
        "historical_event_scan_complete": True,
        "initial_mint_coverage_complete": True,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
    }


def subject():
    return {
        "version": "phase3-feature-subject-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 5,
        "feature_cutoff_transaction_index": 0,
        "feature_cutoff_log_index": 0,
        "feature_cutoff_inclusive": True,
        "selected_detector_id": "chosen",
        "detector_family": "peak_drawdown_rebound",
    }


def transfer(block, from_address, to_address, value):
    return {
        "version": PHASE3_CANONICAL_TRANSFER_VERSION,
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


def test_holder_features_replay_only_through_cutoff(tmp_path: Path):
    rows = [
        transfer(1, ZERO, A, 1000),
        transfer(2, A, B, 300),
        transfer(3, A, C, 200),
        transfer(5, B, C, 100),
        transfer(6, C, A, 400),
    ]
    output = tmp_path / "holder.jsonl"
    manifest, summary = materialize_phase3_holder_features(
        [subject()],
        rows,
        entry_handoff=entry(),
        transfer_handoff=transfer_handoff(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )

    row = json.loads(output.read_text())
    values = row["feature_values"]
    assert row["version"] == PHASE3_HOLDER_FEATURE_VERSION
    assert values["holder.holder_count"] == 3
    assert values["holder.top1_balance_share"] == "0.5"
    assert values["holder.top5_balance_share"] == "1"
    assert values["holder.top10_balance_share"] == "1"
    assert values["holder.balance_hhi"] == "0.38"
    assert values["holder.balance_gini"] == "0.2"
    assert values["holder.transfer_events_so_far"] == 4
    assert values["holder.unique_transfer_participants_so_far"] == 3
    assert row["data_quality"]["future_transfer_rows_used"] is False
    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_transfer_rows_ignored"] == 1


def test_holder_features_fail_when_initial_mint_is_missing(tmp_path: Path):
    with pytest.raises(ValueError, match="debit exceeds known balance"):
        materialize_phase3_holder_features(
            [subject()],
            [transfer(2, A, B, 10)],
            entry_handoff=entry(),
            transfer_handoff=transfer_handoff(rows=1),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "bad.jsonl",
        )


def test_holder_features_require_complete_transfer_coverage(tmp_path: Path):
    tape = transfer_handoff(rows=0)
    tape["transfer_coverage_complete"] = False
    with pytest.raises(ValueError, match="require complete"):
        materialize_phase3_holder_features(
            [subject()],
            [],
            entry_handoff=entry(),
            transfer_handoff=tape,
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "incomplete.jsonl",
        )


def test_holder_feature_handoff_preserves_leakage_guards():
    summary = {
        "version": PHASE3_HOLDER_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "holder_state",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 8,
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
    handoff = build_phase3_holder_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_transfer_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_HOLDER_FEATURE_HANDOFF_VERSION
    assert handoff["transfer_coverage_complete"] is True
    assert handoff["future_transfer_rows_used"] is False
