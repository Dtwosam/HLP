import json
from pathlib import Path

from hlp.data.phase3_pons_trade_coverage import (
    PHASE3_PONS_TRADE_COVERAGE_VERSION,
    materialize_phase3_pons_trade_coverage,
)
from hlp.data.snapshot import write_jsonl_snapshot


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
QUOTE = "0x" + "22" * 20
WALLET = "0x" + "33" * 20


def point(block, log, *, version="v1", phase="curve", event_type="curve_buy"):
    return {
        "token": TOKEN,
        "quote_token": QUOTE,
        "pons_version": version,
        "phase": phase,
        "event_type": event_type,
        "initiator": WALLET,
        "transaction_hash": "0x" + f"{block:064x}",
        "transaction_to": "0x" + "44" * 20,
        "input_selector": "0x12345678",
        "block_number": block,
        "block_timestamp": block * 2,
        "transaction_index": 0,
        "log_index": log,
        "token_amount": 10,
        "quote_amount": 20,
        "fee": 1,
        "tax": 0,
        "market_cap_proxy_usd": "100000",
        "drawdown_from_running_peak": "0",
        "seconds_since_first_priced_point": block,
    }


def report(source_id, records):
    return {
        "version": "phase2-pons-research-materialization-v1",
        "source_id": source_id,
        "eligible_tokens": 1,
        "materialized_records": records,
        "source_binding_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "snapshot_head_block": 100,
        "market_registry_sha256": SHA,
        "eligible_token_coverage_complete": True,
        "accepted_lifecycle_replay_equivalent": True,
        "full_inputs_validated": True,
        "research_component_ready": True,
        "outcome_labels_computed": False,
    }


def snapshot(tmp_path, name, rows):
    path = tmp_path / name
    write_jsonl_snapshot(
        rows,
        output=path,
        provenance={"unit": True},
    )
    return path, path.with_suffix(path.suffix + ".manifest.json")


def test_materializes_v1_canonical_trades_and_coverage(tmp_path: Path):
    points = snapshot(
        tmp_path,
        "v1.jsonl",
        [point(10, 1), point(11, 2)],
    )
    summary = materialize_phase3_pons_trade_coverage(
        source_id="pons_v1",
        research_report=report("pons_v1", 2),
        research_point_files=[points],
        raw_output=tmp_path / "raw.jsonl",
        canonical_output=tmp_path / "canonical.jsonl",
        wallet_identity_output=tmp_path / "wallet.jsonl",
        coverage_output=tmp_path / "coverage.jsonl",
    )
    coverage = json.loads((tmp_path / "coverage.jsonl").read_text())

    assert summary["version"] == PHASE3_PONS_TRADE_COVERAGE_VERSION
    assert summary["raw_trade_rows"] == 2
    assert summary["canonical_trade_rows"] == 2
    assert summary["wallet_identity_rows"] == 2
    assert summary["trade_coverage_complete"] is True
    assert coverage["source_id"] == "pons_v1"
    assert coverage["eligible_tokens"] == 1
    assert coverage["wallet_identity_kind"] == (
        "source_normalized_initiator"
    )
    assert coverage["trade_coverage_complete"] is True


def test_materializes_v2_across_curve_seed_and_v4(tmp_path: Path):
    curve = snapshot(
        tmp_path,
        "curve.jsonl",
        [point(10, 1, version="v2")],
    )
    seed = snapshot(
        tmp_path,
        "seed.jsonl",
        [{
            **point(
                12,
                0,
                version="v2",
                phase="v4_seed",
                event_type="v4_initialize",
            ),
        }],
    )
    v4 = snapshot(
        tmp_path,
        "v4.jsonl",
        [{
            **point(
                20,
                2,
                version="v2",
                phase="v4",
                event_type="v4_swap",
            ),
            "amount0": -10
            if int(TOKEN, 16) < int(QUOTE, 16)
            else 20,
            "amount1": 20
            if int(TOKEN, 16) < int(QUOTE, 16)
            else -10,
        }],
    )
    summary = materialize_phase3_pons_trade_coverage(
        source_id="pons_v2",
        research_report=report("pons_v2", 3),
        research_point_files=[curve, seed, v4],
        raw_output=tmp_path / "raw.jsonl",
        canonical_output=tmp_path / "canonical.jsonl",
        wallet_identity_output=tmp_path / "wallet.jsonl",
        coverage_output=tmp_path / "coverage.jsonl",
    )
    assert summary["research_point_rows"] == 3
    assert summary["raw_trade_rows"] == 2
    assert summary["canonical_trade_rows"] == 2
    assert summary["trade_coverage_complete"] is True
