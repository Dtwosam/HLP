import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_trade_size_flow_features import (
    PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION,
    PHASE3_TRADE_SIZE_FLOW_HANDOFF_VERSION,
    build_phase3_trade_size_flow_handoff,
    materialize_phase3_trade_size_flow_features,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
A = "0x" + "aa" * 20
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


def trade_tape(rows=4, complete=True):
    return {
        "version": "phase3-canonical-trade-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "canonical_trade_rows_sha256": SHA,
        "trade_rows": rows,
        "trade_coverage_complete": complete,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
    }


def transfer_tape(rows=1, complete=True):
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
        "feature_cutoff_block": 3,
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
        "transaction_hash": "0x" + f"{1000 + block:064x}",
        "transaction_index": 0,
        "log_index": 0,
        "canonical_phase3_transfer": True,
        "outcome_derived": False,
    }


def trade(block, side, amount):
    return {
        "version": "phase3-canonical-trade-v1",
        "token": TOKEN,
        "source_id": "unit",
        "side": side,
        "initiator": A,
        "block_number": block,
        "transaction_index": 0,
        "log_index": 0,
        "token_amount_raw": amount,
        "quote_amount_raw": amount * 2,
        "canonical_phase3_trade": True,
        "outcome_derived": False,
    }


def test_size_flow_normalizes_trade_amounts_by_cutoff_supply(tmp_path: Path):
    trades = [
        trade(1, "buy", 10),
        trade(2, "buy", 20),
        trade(3, "sell", 15),
        trade(4, "sell", 90),
    ]
    transfers = [
        transfer(1, ZERO, A, 100),
    ]
    output = tmp_path / "flow.jsonl"
    manifest, summary = materialize_phase3_trade_size_flow_features(
        [subject()],
        trades,
        transfers,
        entry_handoff=entry(),
        trade_tape_handoff=trade_tape(),
        transfer_handoff=transfer_tape(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    values = row["feature_values"]

    assert row["version"] == PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION
    assert values["flow.buy_token_supply_multiple_so_far"] == "0.3"
    assert values["flow.sell_token_supply_multiple_so_far"] == "0.15"
    assert values["flow.net_token_supply_multiple_so_far"] == "0.15"
    assert values["flow.gross_token_supply_multiple_so_far"] == "0.45"
    assert values["flow.mean_buy_size_supply_fraction"] == "0.15"
    assert values["flow.mean_sell_size_supply_fraction"] == "0.15"
    assert values["flow.max_buy_size_supply_fraction"] == "0.2"
    assert values["flow.max_sell_size_supply_fraction"] == "0.15"
    assert values["flow.sell_to_buy_token_amount_ratio"] == "0.5"
    assert row["data_quality"][
        "raw_quote_amounts_not_compared_across_assets"
    ] is True
    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_trade_rows_ignored"] == 1


def test_size_flow_records_side_missingness(tmp_path: Path):
    trades = [trade(1, "buy", 10)]
    transfers = [transfer(1, ZERO, A, 100)]
    output = tmp_path / "missing.jsonl"
    _, summary = materialize_phase3_trade_size_flow_features(
        [subject()],
        trades,
        transfers,
        entry_handoff=entry(),
        trade_tape_handoff=trade_tape(rows=1),
        transfer_handoff=transfer_tape(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    assert row["feature_values"][
        "flow.sell_token_supply_multiple_so_far"
    ] == "0"
    assert row["feature_values"][
        "flow.mean_sell_size_supply_fraction"
    ] is None
    assert len(row["missing_feature_ids"]) == 2
    assert summary["missing_feature_values"] == 2


def test_size_flow_requires_both_complete_tapes(tmp_path: Path):
    with pytest.raises(ValueError, match="requires complete"):
        materialize_phase3_trade_size_flow_features(
            [subject()],
            [],
            [],
            entry_handoff=entry(),
            trade_tape_handoff=trade_tape(rows=0, complete=False),
            transfer_handoff=transfer_tape(rows=0),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "bad.jsonl",
        )


def test_size_flow_handoff_binds_both_tapes():
    summary = {
        "version": PHASE3_TRADE_SIZE_FLOW_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "trade_size_flow",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "canonical_trade_rows_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 9,
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
    handoff = build_phase3_trade_size_flow_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_trade_handoff_sha256=SHA,
        canonical_transfer_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_TRADE_SIZE_FLOW_HANDOFF_VERSION
    assert handoff["trade_coverage_complete"] is True
    assert handoff["transfer_coverage_complete"] is True
