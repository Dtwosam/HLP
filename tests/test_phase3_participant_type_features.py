import hashlib
import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_participant_type_features import (
    PHASE3_PARTICIPANT_CODE_STATE_VERSION,
    PHASE3_PARTICIPANT_TYPE_FEATURE_HANDOFF_VERSION,
    PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION,
    build_phase3_participant_code_query_plan,
    build_phase3_participant_type_feature_handoff,
    materialize_phase3_participant_type_features,
)
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
    PHASE3_CANONICAL_TRADE_VERSION,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
WALLET_A = "0x" + "aa" * 20
WALLET_B = "0x" + "bb" * 20
WALLET_C = "0x" + "cc" * 20


def entry_handoff():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def tape_handoff(rows=5, complete=True):
    return {
        "version": PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "canonical_trade_rows_sha256": SHA,
        "trade_rows": rows,
        "trade_coverage_complete": complete,
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


def trade(block, side, wallet):
    return {
        "version": PHASE3_CANONICAL_TRADE_VERSION,
        "token": TOKEN,
        "source_id": "unit",
        "side": side,
        "initiator": wallet,
        "block_number": block,
        "transaction_index": 0,
        "log_index": 0,
        "canonical_phase3_trade": True,
        "outcome_derived": False,
    }


def code_row(address, code_hex):
    raw = bytes.fromhex(code_hex)
    return {
        "version": PHASE3_PARTICIPANT_CODE_STATE_VERSION,
        "address": address,
        "block_number": 4,
        "code_present": bool(raw),
        "code_size_bytes": len(raw),
        "code_sha256": hashlib.sha256(raw).hexdigest(),
        "archive_state_read": True,
        "future_state_allowed": False,
    }


def trade_rows():
    return [
        trade(1, "buy", WALLET_A),
        trade(2, "buy", WALLET_B),
        trade(3, "sell", WALLET_A),
        trade(5, "buy", WALLET_C),
        trade(6, "sell", WALLET_A),
    ]


def test_participant_code_plan_uses_start_of_cutoff_block():
    rows, summary = build_phase3_participant_code_query_plan(
        [subject()],
        trade_rows(),
        entry_handoff=entry_handoff(),
        trade_tape_handoff=tape_handoff(),
    )

    assert rows == [
        {"block_number": 4, "address": WALLET_A},
        {"block_number": 4, "address": WALLET_B},
        {"block_number": 4, "address": WALLET_C},
    ]
    assert summary["participant_code_queries"] == 3
    assert summary["query_block_semantics"] == (
        "start_of_confirmation_block"
    )
    assert summary["same_block_future_state_allowed"] is False


def test_participant_type_features_are_causal(tmp_path: Path):
    output = tmp_path / "participant-type.jsonl"
    manifest, summary = materialize_phase3_participant_type_features(
        [subject()],
        trade_rows(),
        [
            code_row(WALLET_A, "6000"),
            code_row(WALLET_B, ""),
            code_row(WALLET_C, "60"),
        ],
        entry_handoff=entry_handoff(),
        trade_tape_handoff=tape_handoff(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )

    row = json.loads(output.read_text())
    values = row["feature_values"]
    assert row["version"] == PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION
    assert values["participant_type.unique_code_accounts_so_far"] == 2
    assert values["participant_type.unique_no_code_accounts_so_far"] == 1
    assert values[
        "participant_type.code_account_share_of_unique_traders"
    ].startswith("0.666666")
    assert values[
        "participant_type.code_account_trade_share_so_far"
    ] == "0.75"
    assert values[
        "participant_type.code_account_buy_trade_share_so_far"
    ].startswith("0.666666")
    assert values[
        "participant_type.code_account_sell_trade_share_so_far"
    ] == "1"
    assert values[
        "participant_type.latest_initiator_has_code_before_cutoff_block"
    ] is True
    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_trade_rows_ignored"] == 1
    assert summary["participant_code_rows"] == 3
    assert summary["same_block_future_state_used"] is False


def test_participant_type_features_record_missingness_without_trades(
    tmp_path: Path,
):
    output = tmp_path / "empty.jsonl"
    _, summary = materialize_phase3_participant_type_features(
        [subject()],
        [],
        [],
        entry_handoff=entry_handoff(),
        trade_tape_handoff=tape_handoff(rows=0),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )

    row = json.loads(output.read_text())
    values = row["feature_values"]
    assert values["participant_type.unique_code_accounts_so_far"] == 0
    assert values[
        "participant_type.code_account_trade_share_so_far"
    ] is None
    assert (
        "participant_type.code_account_trade_share_so_far"
        in row["missing_feature_ids"]
    )
    assert summary["subjects_without_trades"] == 1


def test_participant_type_rejects_end_of_cutoff_block_code_state(tmp_path):
    wrong = code_row(WALLET_A, "60")
    wrong["block_number"] = 5
    with pytest.raises(ValueError, match="coverage mismatch"):
        materialize_phase3_participant_type_features(
            [subject()],
            [trade(1, "buy", WALLET_A)],
            [wrong],
            entry_handoff=entry_handoff(),
            trade_tape_handoff=tape_handoff(rows=1),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "wrong.jsonl",
        )


def test_participant_type_handoff_binds_code_state_and_no_future_state():
    summary = {
        "version": PHASE3_PARTICIPANT_TYPE_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "participant_type",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "canonical_trade_rows_sha256": SHA,
        "participant_code_rows_sha256": SHA,
        "participant_code_rows": 3,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 7,
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
    handoff = build_phase3_participant_type_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_trade_handoff_sha256=SHA,
    )
    assert (
        handoff["version"]
        == PHASE3_PARTICIPANT_TYPE_FEATURE_HANDOFF_VERSION
    )
    assert handoff["participant_code_rows_sha256"] == SHA
    assert handoff["historical_code_state_complete"] is True
    assert handoff["same_block_future_state_used"] is False
