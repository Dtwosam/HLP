import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_retention_features import (
    PHASE3_RETENTION_FEATURE_HANDOFF_VERSION,
    PHASE3_RETENTION_FEATURE_VERSION,
    build_phase3_retention_feature_handoff,
    materialize_phase3_retention_features,
)
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
    PHASE3_CANONICAL_TRADE_VERSION,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
A = "0x" + "aa" * 20
B = "0x" + "bb" * 20
C = "0x" + "cc" * 20


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


def tape(rows=6, complete=True):
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


def test_retention_features_are_causal_and_track_returning_traders(
    tmp_path: Path,
):
    rows = [
        trade(1, "buy", A),
        trade(2, "buy", A),
        trade(3, "sell", B),
        trade(4, "sell", A),
        trade(5, "buy", C),
        trade(6, "buy", C),
    ]
    output = tmp_path / "retention.jsonl"
    manifest, summary = materialize_phase3_retention_features(
        [subject()],
        rows,
        entry_handoff=entry(),
        trade_tape_handoff=tape(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    values = row["feature_values"]

    assert row["version"] == PHASE3_RETENTION_FEATURE_VERSION
    assert values["retention.multi_trade_traders_so_far"] == 1
    assert values["retention.multi_trade_trader_share_so_far"].startswith(
        "0.333333333333"
    )
    assert values["retention.two_sided_traders_so_far"] == 1
    assert values["retention.two_sided_trader_share_so_far"].startswith(
        "0.333333333333"
    )
    assert values["retention.repeat_trades_so_far"] == 2
    assert values["retention.repeat_trade_share_so_far"] == "0.4"
    assert values["retention.latest_trader_prior_trades"] == 0
    assert values["retention.latest_trader_is_returning"] is False
    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_trade_rows_ignored"] == 1
    assert summary["future_trade_rows_used"] is False


def test_retention_records_missingness_when_no_trades(tmp_path: Path):
    output = tmp_path / "empty.jsonl"
    _, summary = materialize_phase3_retention_features(
        [subject()],
        [],
        entry_handoff=entry(),
        trade_tape_handoff=tape(rows=0),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    values = row["feature_values"]

    assert values["retention.multi_trade_traders_so_far"] == 0
    assert values["retention.two_sided_traders_so_far"] == 0
    assert values["retention.repeat_trades_so_far"] == 0
    assert values["retention.multi_trade_trader_share_so_far"] is None
    assert values["retention.repeat_trade_share_so_far"] is None
    assert values["retention.latest_trader_prior_trades"] is None
    assert values["retention.latest_trader_is_returning"] is None
    assert len(row["missing_feature_ids"]) == 5
    assert summary["subjects_without_trades"] == 1


def test_retention_requires_complete_trade_coverage(tmp_path: Path):
    with pytest.raises(ValueError, match="requires complete"):
        materialize_phase3_retention_features(
            [subject()],
            [],
            entry_handoff=entry(),
            trade_tape_handoff=tape(rows=0, complete=False),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "bad.jsonl",
        )


def test_retention_handoff_is_outcome_blind():
    summary = {
        "version": PHASE3_RETENTION_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "participant_retention",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "canonical_trade_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 8,
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_retention_features_ready": True,
    }
    handoff = build_phase3_retention_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_trade_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_RETENTION_FEATURE_HANDOFF_VERSION
    assert handoff["trade_coverage_complete"] is True
    assert handoff["future_trade_rows_used"] is False
