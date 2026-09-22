import json
from pathlib import Path

import pytest

from hlp.data.phase2_sources import build_phase2_source_inventory
from hlp.data.phase3_trade_features import (
    PHASE3_CANONICAL_TRADE_HANDOFF_VERSION,
)
from hlp.data.phase3_trade_tape import (
    PHASE3_CANONICAL_TRADE_TAPE_VERSION,
    PHASE3_TRADE_SOURCE_COVERAGE_VERSION,
    build_phase3_canonical_trade_handoff,
    build_phase3_trade_source_coverage,
    materialize_phase3_canonical_trade_tape,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
WALLET = "0x" + "22" * 20
QUOTE = "0x" + "33" * 20
TX = "0x" + "44" * 32


def entry():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "universe_tokens": 1,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def trade(source_id, block=10):
    return {
        "version": "phase3-canonical-trade-v1",
        "token": TOKEN,
        "source_id": source_id,
        "venue": source_id,
        "phase": "v3",
        "side": "buy",
        "initiator": WALLET,
        "transaction_hash": TX,
        "block_number": block,
        "transaction_index": 1,
        "log_index": 2,
        "token_amount_raw": 100,
        "quote_amount_raw": 200,
        "quote_token": QUOTE,
        "canonical_phase3_trade": True,
        "outcome_derived": False,
    }


def coverage_for(source_id, rows, eligible_tokens):
    return build_phase3_trade_source_coverage(
        source_id,
        rows,
        eligible_tokens=eligible_tokens,
        snapshot_head_block=100,
        market_registry_sha256=SHA,
        raw_trade_tape_sha256=SHA,
        raw_trade_rows=len(rows),
        wallet_identity_sha256=SHA,
        wallet_identity_kind=(
            "cca_bid_owner"
            if source_id == "pools_trade_lbp"
            else (
                "source_normalized_initiator"
                if source_id in {"pons_v1", "pons_v2"}
                else "transaction_from"
            )
        ),
        historical_event_scan_complete=True,
        wallet_identity_complete=True,
        canonical_trade_adapter_complete=True,
    )


def complete_inputs(overlap=False):
    ids = [
        row["source_id"]
        for row in build_phase2_source_inventory()
    ]
    primary = "direct_uniswap_v3"
    secondary = "noxa"
    memberships = {
        source_id: []
        for source_id in ids
    }
    memberships[primary] = [TOKEN]
    if overlap:
        memberships[secondary] = [TOKEN]

    source_rows = {
        source_id: []
        for source_id in ids
    }
    source_rows[primary] = [trade(primary)]
    if overlap:
        source_rows[secondary] = [trade(secondary)]

    coverage = [
        coverage_for(
            source_id,
            source_rows[source_id],
            memberships[source_id],
        )
        for source_id in ids
    ]
    sources = [primary] + ([secondary] if overlap else [])
    universe = [{
        "token": TOKEN,
        "source_ids": sources,
        "universe_status": "eligible",
    }]
    return universe, source_rows, coverage


def test_canonical_trade_tape_requires_all_sources_and_collapses_overlap(
    tmp_path: Path,
):
    universe, source_rows, coverage = complete_inputs(overlap=True)
    output = tmp_path / "trades.jsonl"
    manifest, summary = materialize_phase3_canonical_trade_tape(
        universe,
        source_rows,
        coverage,
        feature_entry_handoff=entry(),
        output=output,
    )

    row = json.loads(output.read_text())
    assert manifest["records"] == 1
    assert row["source_ids"] == [
        "direct_uniswap_v3",
        "noxa",
    ]
    assert row["source_id"] == "direct_uniswap_v3"
    assert summary["inventory_sources"] == len(
        build_phase2_source_inventory()
    )
    assert summary["cross_source_duplicates_collapsed"] == 1
    assert summary["trade_coverage_complete"] is True
    assert summary["phase3_canonical_trade_tape_ready"] is True


def test_canonical_trade_tape_rejects_incomplete_source_coverage(tmp_path):
    universe, source_rows, coverage = complete_inputs()
    coverage[0] = {
        **coverage[0],
        "trade_coverage_complete": False,
    }
    with pytest.raises(ValueError, match="coverage is incomplete"):
        materialize_phase3_canonical_trade_tape(
            universe,
            source_rows,
            coverage,
            feature_entry_handoff=entry(),
            output=tmp_path / "bad.jsonl",
        )


def test_source_coverage_binds_exact_frozen_source_membership():
    row = coverage_for(
        "direct_uniswap_v3",
        [trade("direct_uniswap_v3")],
        [TOKEN],
    )
    assert row["version"] == PHASE3_TRADE_SOURCE_COVERAGE_VERSION
    assert row["eligible_tokens"] == 1
    assert row["trade_coverage_complete"] is True
    assert row["canonical_trade_rows"] == 1


def test_canonical_trade_handoff_matches_trade_feature_contract():
    summary = {
        "version": PHASE3_CANONICAL_TRADE_TAPE_VERSION,
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "source_coverage_sha256": SHA,
        "canonical_trade_rows_sha256": SHA,
        "inventory_sources": 14,
        "trade_rows": 1,
        "trade_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_trade_tape_ready": True,
    }
    handoff = build_phase3_canonical_trade_handoff(
        summary,
        tape_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_CANONICAL_TRADE_HANDOFF_VERSION
    assert handoff["trade_coverage_complete"] is True
    assert handoff["future_state_allowed"] is False



def test_source_coverage_accepts_cca_event_owner_identity():
    row = build_phase3_trade_source_coverage(
        "pools_trade_lbp",
        [],
        eligible_tokens=[],
        snapshot_head_block=100,
        market_registry_sha256=SHA,
        raw_trade_tape_sha256=SHA,
        raw_trade_rows=0,
        wallet_identity_sha256=SHA,
        wallet_identity_kind="cca_bid_owner",
        historical_event_scan_complete=True,
        wallet_identity_complete=True,
        canonical_trade_adapter_complete=True,
    )
    assert row["wallet_identity_kind"] == "cca_bid_owner"
    assert row["wallet_identity_complete"] is True
    assert row["trade_coverage_complete"] is True


def test_source_coverage_rejects_wrong_identity_kind():
    with pytest.raises(ValueError, match="identity kind drift"):
        build_phase3_trade_source_coverage(
            "pools_trade_lbp",
            [],
            eligible_tokens=[],
            snapshot_head_block=100,
            market_registry_sha256=SHA,
            raw_trade_tape_sha256=SHA,
            raw_trade_rows=0,
            wallet_identity_sha256=SHA,
            wallet_identity_kind="transaction_from",
            historical_event_scan_complete=True,
            wallet_identity_complete=True,
            canonical_trade_adapter_complete=True,
        )
