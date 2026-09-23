import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
    PHASE3_CANONICAL_TRADE_VERSION,
    PHASE3_TRADE_FEATURE_HANDOFF_VERSION,
    PHASE3_TRADE_FEATURE_VERSION,
    build_phase3_trade_feature_handoff,
    materialize_phase3_trade_features,
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


def test_trade_features_are_causal_and_ignore_post_cutoff_rows(tmp_path: Path):
    rows = [
        trade(1, "buy", WALLET_A),
        trade(2, "buy", WALLET_A),
        trade(3, "sell", WALLET_B),
        trade(5, "buy", WALLET_C),
        trade(6, "sell", WALLET_A),
    ]
    output = tmp_path / "trade-features.jsonl"
    manifest, summary = materialize_phase3_trade_features(
        [subject()],
        rows,
        entry_handoff=entry_handoff(),
        trade_tape_handoff=tape_handoff(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )

    row = json.loads(output.read_text())
    values = row["feature_values"]
    assert row["version"] == PHASE3_TRADE_FEATURE_VERSION
    assert values["trade.total_trades_so_far"] == 4
    assert values["trade.buy_trades_so_far"] == 3
    assert values["trade.sell_trades_so_far"] == 1
    assert values["trade.buy_trade_share_so_far"] == "0.75"
    assert values["trade.unique_traders_so_far"] == 3
    assert values["trade.unique_buyers_so_far"] == 2
    assert values["trade.unique_sellers_so_far"] == 1
    assert values["trade.repeat_buyer_trade_share_so_far"].startswith(
        "0.333333333333"
    )
    assert values["trade.repeat_seller_trade_share_so_far"] == "0"
    assert values["trade.current_side_is_buy"] is True
    assert values["trade.current_side_streak_trades"] == 1
    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_trade_rows_ignored"] == 1
    assert summary["future_trade_rows_used"] is False


def test_trade_features_refuse_incomplete_chain_wide_trade_coverage(tmp_path):
    with pytest.raises(ValueError, match="require complete"):
        materialize_phase3_trade_features(
            [subject()],
            [],
            entry_handoff=entry_handoff(),
            trade_tape_handoff=tape_handoff(rows=0, complete=False),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "incomplete.jsonl",
        )


def test_trade_features_record_missingness_when_no_prior_trades(tmp_path):
    output = tmp_path / "empty.jsonl"
    _, summary = materialize_phase3_trade_features(
        [subject()],
        [],
        entry_handoff=entry_handoff(),
        trade_tape_handoff=tape_handoff(rows=0),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    assert row["feature_values"]["trade.total_trades_so_far"] == 0
    assert row["feature_values"]["trade.buy_trade_share_so_far"] is None
    assert "trade.buy_trade_share_so_far" in row["missing_feature_ids"]
    assert row["data_quality"]["trades_observed_before_cutoff"] is False
    assert summary["subjects_without_trades"] == 1
    assert summary["missingness_recorded"] is True


def test_trade_feature_handoff_requires_complete_coverage_and_no_future_rows():
    summary = {
        "version": PHASE3_TRADE_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "trade_flow",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "canonical_trade_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 11,
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_trade_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_trade_features_ready": True,
    }
    handoff = build_phase3_trade_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_trade_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_TRADE_FEATURE_HANDOFF_VERSION
    assert handoff["trade_coverage_complete"] is True
    assert handoff["future_trade_rows_used"] is False
