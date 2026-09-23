import hashlib
import json
from decimal import Decimal

from hlp.config import ROBINHOOD_WETH
from hlp.data.phase2_pons_research_replay import (
    PONS_RESEARCH_REPLAY_VERSION,
    materialize_v1_research_points,
    materialize_v2_curve_research_points,
    materialize_v2_post_graduation_research_points,
)


TOKEN = "0x0000000000000000000000000000000000000011"
POOL = "0x" + "33" * 20
CURVE = "0x" + "22" * 20
POOL_ID = "0x" + "aa" * 32


def test_v1_research_replay_materializes_same_stream_used_by_summary(tmp_path):
    registry = [{
        "token": TOKEN,
        "pair_token": ROBINHOOD_WETH.lower(),
        "pool": POOL,
        "block_number": 10,
        "supply_raw": 100_000 * 10**18,
        "token_decimals": 18,
    }]
    swaps = [{
        "pool": POOL,
        "block_number": 20,
        "transaction_index": None,
        "log_index": 0,
        "sqrt_price_x96": 2**96,
    }]
    output = tmp_path / "v1.jsonl"

    summary, manifest = materialize_v1_research_points(
        registry,
        swaps,
        [],
        output=output,
        provenance={"source_evidence_sha256": "ab" * 32},
        initial_weth_usd=Decimal("2000"),
        weth_decimals=18,
        usdg_decimals=18,
    )

    raw = output.read_bytes()
    assert manifest["records"] == 1
    assert manifest["sha256"] == hashlib.sha256(raw).hexdigest()
    assert manifest["provenance"]["version"] == PONS_RESEARCH_REPLAY_VERSION
    assert manifest["provenance"]["phase"] == "pons_v1_v3"
    assert manifest["provenance"]["dump_threshold_frozen"] is False
    assert summary[0]["price_points"] == 1
    assert summary[0]["max_market_cap_proxy_usd"] == "200000000"


def _v2_registry():
    return [{
        "token": TOKEN,
        "curve": CURVE,
        "pair_token": ROBINHOOD_WETH.lower(),
        "block_number": 10,
        "transaction_hash": "0x" + "01" * 32,
        "transaction_index": 1,
        "log_index": 0,
        "supply_raw": 1000 * 10**18,
        "token_decimals": 18,
        "quote_decimals": 18,
        "phantom_quote": 10 * 10**18,
    }]


def test_v2_research_replay_keeps_curve_seed_and_v4_as_exact_segments(tmp_path):
    curve_output = tmp_path / "curve.jsonl"
    curve_summary, curve_manifest = materialize_v2_curve_research_points(
        _v2_registry(),
        [],
        [],
        output=curve_output,
        provenance={"source_evidence_sha256": "cd" * 32},
        initial_weth_usd=Decimal("2000"),
    )
    assert curve_manifest["records"] == 1
    assert curve_summary[0]["price_points"] == 1

    graduations = [{
        "token": TOKEN,
        "position_id": 1,
        "token_amount": 1000 * 10**18,
        "pair_token_amount": 1000 * 10**18,
        "block_number": 20,
        "transaction_hash": "0x" + "02" * 32,
        "transaction_index": 1,
        "log_index": 0,
    }]
    registrations = [{
        "pool_id": POOL_ID,
        "token": TOKEN,
        "quote_token": ROBINHOOD_WETH.lower(),
        "creator": "0x" + "44" * 20,
        "block_number": 20,
        "transaction_hash": "0x" + "03" * 32,
        "transaction_index": 2,
        "log_index": 0,
    }]
    v4_events = [{
        "pool_id": POOL_ID,
        "sqrt_price_x96": 2**96,
        "block_number": 21,
        "transaction_hash": "0x" + "04" * 32,
        "transaction_index": 1,
        "log_index": 0,
        "event_type": "v4_swap",
    }]
    seed_output = tmp_path / "seed.jsonl"
    v4_output = tmp_path / "v4.jsonl"

    seed_summary, v4_summary, seed_manifest, v4_manifest = (
        materialize_v2_post_graduation_research_points(
            _v2_registry(),
            graduations,
            registrations,
            v4_events,
            seed_anchor_points=[],
            v4_anchor_points=[],
            seed_output=seed_output,
            v4_output=v4_output,
            provenance={"source_evidence_sha256": "ef" * 32},
            initial_weth_usd=Decimal("2000"),
        )
    )

    assert seed_manifest["records"] == 1
    assert v4_manifest["records"] == 1
    assert seed_summary[0]["price_points"] == 1
    assert v4_summary[0]["price_points"] == 1
    assert json.loads(seed_output.read_text())["phase"] == "v4_seed"
    assert json.loads(v4_output.read_text())["phase"] == "v4"
