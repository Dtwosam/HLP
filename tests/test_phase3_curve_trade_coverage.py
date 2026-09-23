from pathlib import Path

from hlp.data.phase3_curve_trade_coverage import (
    materialize_phase3_curve_trade_coverage,
)


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
WALLET = "0x" + "33" * 20
TX = "0x" + "44" * 32


def identity():
    return {
        "transaction_hash": TX,
        "block_number": 10,
        "transaction_index": 1,
        "initiator": WALLET,
        "to": "0x" + "55" * 20,
        "value_raw": 0,
        "input_selector": "0x12345678",
        "transaction_type": 2,
    }


def outputs(tmp_path):
    return {
        "raw_output": tmp_path / "raw.jsonl",
        "registry_output": tmp_path / "registry.jsonl",
        "wallet_identity_output": tmp_path / "wallet.jsonl",
        "canonical_output": tmp_path / "canonical.jsonl",
        "coverage_output": tmp_path / "coverage.jsonl",
    }


def test_flap_curve_coverage_uses_native_trade_amounts(tmp_path: Path):
    summary = materialize_phase3_curve_trade_coverage(
        source_id="flap",
        eligible_tokens=[TOKEN],
        registry_rows=[{
            "token": TOKEN,
            "quote_token": QUOTE,
        }],
        event_rows=[{
            "token": TOKEN,
            "event_type": "token_bought",
            "actor": "0x" + "66" * 20,
            "quote_token": QUOTE,
            "amount_raw": 10,
            "quote_amount_raw": 20,
            "transaction_hash": TX,
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 2,
        }],
        transaction_rows=[identity()],
        snapshot_head_block=100,
        historical_event_scan_complete=True,
        **outputs(tmp_path),
    )
    assert summary["raw_trade_rows"] == 1
    assert summary["canonical_trade_rows"] == 1
    assert summary["trade_coverage_complete"] is True


def test_hood_curve_coverage_requires_generation(tmp_path: Path):
    summary = materialize_phase3_curve_trade_coverage(
        source_id="hood_fun_current",
        eligible_tokens=[TOKEN],
        registry_rows=[{
            "token": TOKEN,
            "generation": "current",
            "quote_token": "0x" + "00" * 20,
        }],
        event_rows=[{
            "token": TOKEN,
            "generation": "current",
            "event_type": "trade",
            "is_buy": True,
            "quote_token": "0x" + "00" * 20,
            "token_amount_raw": 10,
            "quote_amount_raw": 20,
            "transaction_hash": TX,
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 2,
        }],
        transaction_rows=[identity()],
        snapshot_head_block=100,
        historical_event_scan_complete=True,
        **outputs(tmp_path),
    )
    assert summary["canonical_trade_rows"] == 1
    assert summary["wallet_identity_kind"] == "transaction_from"


def test_trench_curve_coverage_uses_registry_quote(tmp_path: Path):
    summary = materialize_phase3_curve_trade_coverage(
        source_id="trench_today",
        eligible_tokens=[TOKEN],
        registry_rows=[{
            "token": TOKEN,
            "quote_token": QUOTE,
        }],
        event_rows=[{
            "token": TOKEN,
            "event_type": "token_purchase",
            "amount_raw": 10,
            "quote_amount_raw": 20,
            "transaction_hash": TX,
            "block_number": 10,
            "transaction_index": 1,
            "log_index": 2,
        }],
        transaction_rows=[identity()],
        snapshot_head_block=100,
        historical_event_scan_complete=True,
        **outputs(tmp_path),
    )
    assert summary["market_registry_sha256"]
    assert summary["canonical_trade_rows"] == 1
    assert summary["trade_coverage_complete"] is True
