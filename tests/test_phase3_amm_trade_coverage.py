from pathlib import Path

from hlp.data.phase3_amm_trade_coverage import (
    materialize_phase3_amm_trade_coverage,
)


TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
POOL = "0x" + "33" * 20
POOL_ID = "0x" + "44" * 32
TX = "0x" + "55" * 32
WALLET = "0x" + "66" * 20


def identity():
    return {
        "transaction_hash": TX,
        "block_number": 10,
        "transaction_index": 1,
        "initiator": WALLET,
        "to": "0x" + "77" * 20,
        "value_raw": 0,
        "input_selector": "0x12345678",
        "transaction_type": 2,
    }


def test_v3_amm_coverage_filters_exact_market_membership(tmp_path: Path):
    markets = [{
        "token": TOKEN,
        "quote_token": QUOTE,
        "pool": POOL,
    }]
    swaps = [{
        "pool": POOL,
        "amount0": -10
        if int(TOKEN, 16) < int(QUOTE, 16)
        else 20,
        "amount1": 20
        if int(TOKEN, 16) < int(QUOTE, 16)
        else -10,
        "transaction_hash": TX,
        "block_number": 10,
        "transaction_index": 1,
        "log_index": 2,
    }]
    summary = materialize_phase3_amm_trade_coverage(
        source_id="pools_fun",
        eligible_tokens=[TOKEN],
        market_rows=markets,
        raw_swap_rows=swaps,
        transaction_rows=[identity()],
        snapshot_head_block=100,
        raw_scan_complete=True,
        raw_output=tmp_path / "raw.jsonl",
        market_output=tmp_path / "markets.jsonl",
        wallet_identity_output=tmp_path / "wallet.jsonl",
        canonical_output=tmp_path / "canonical.jsonl",
        coverage_output=tmp_path / "coverage.jsonl",
    )
    assert summary["raw_trade_rows"] == 1
    assert summary["canonical_trade_rows"] == 1
    assert summary["wallet_identity_rows"] == 1
    assert summary["trade_coverage_complete"] is True


def test_v4_amm_coverage_uses_pool_id(tmp_path: Path):
    markets = [{
        "token": TOKEN,
        "quote_token": QUOTE,
        "pool_id": POOL_ID,
    }]
    swaps = [{
        "pool_id": POOL_ID,
        "amount0": -10
        if int(TOKEN, 16) < int(QUOTE, 16)
        else 20,
        "amount1": 20
        if int(TOKEN, 16) < int(QUOTE, 16)
        else -10,
        "transaction_hash": TX,
        "block_number": 10,
        "transaction_index": 1,
        "log_index": 2,
    }]
    summary = materialize_phase3_amm_trade_coverage(
        source_id="doppler",
        eligible_tokens=[TOKEN],
        market_rows=markets,
        raw_swap_rows=swaps,
        transaction_rows=[identity()],
        snapshot_head_block=100,
        raw_scan_complete=True,
        raw_output=tmp_path / "raw.jsonl",
        market_output=tmp_path / "markets.jsonl",
        wallet_identity_output=tmp_path / "wallet.jsonl",
        canonical_output=tmp_path / "canonical.jsonl",
        coverage_output=tmp_path / "coverage.jsonl",
    )
    assert summary["market_rows"] == 1
    assert summary["canonical_trade_rows"] == 1
    assert summary["wallet_identity_kind"] == "transaction_from"
