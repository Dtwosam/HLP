import json
from pathlib import Path

from hlp.data.phase3_chain_regime import (
    PHASE3_CHAIN_REGIME_FEATURE_VERSION,
    REGIME_WINDOW_BLOCKS,
    build_phase3_chain_regime_handoff,
    materialize_phase3_chain_regime_features,
)
from hlp.data.phase3_feature_registry import build_phase3_feature_registry


SHA = "ab" * 32
TARGET = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def entry():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 2000,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "feature_subjects": 1,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def price_handoff(rows):
    return {
        "version": "phase2-research-price-path-handoff-v1",
        "snapshot_head_block": 2000,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "price_points": rows,
        "research_price_path_ready": True,
        "outcome_labels_computed": False,
    }


def subject():
    return {
        "version": "phase3-feature-subject-v1",
        "token": TARGET,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 1500,
        "feature_cutoff_transaction_index": 1,
        "feature_cutoff_log_index": 0,
        "feature_cutoff_inclusive": True,
        "selected_detector_id": "chosen",
        "detector_family": "peak_drawdown_rebound",
    }


def price(token, block, value, tx=0):
    return {
        "version": "phase2-research-price-path-v1",
        "token": token,
        "block_number": block,
        "transaction_index": tx,
        "log_index": 0,
        "market_cap_proxy_usd": str(value),
        "canonical_research_price_path": True,
    }


def test_chain_regime_is_point_in_time_and_cross_sectional(tmp_path: Path):
    rows = [
        price(OTHER, 400, 50000),
        price(TARGET, 600, 120000),
        price(OTHER, 1000, 150000),
        price(TARGET, 1500, 80000, tx=1),
        price(OTHER, 1500, 900000, tx=2),
        price(TARGET, 1700, 1000000),
    ]
    output = tmp_path / "regime.jsonl"
    manifest, summary = materialize_phase3_chain_regime_features(
        [subject()],
        rows,
        entry_handoff=entry(),
        price_path_handoff=price_handoff(len(rows)),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    row = json.loads(output.read_text())
    values = row["feature_values"]
    assert row["version"] == PHASE3_CHAIN_REGIME_FEATURE_VERSION
    assert values["regime.observed_tokens_so_far"] == 2
    assert values["regime.tokens_above_100k_at_cutoff"] == 1
    assert values[
        "regime.median_latest_market_cap_proxy_usd"
    ] == "115000"
    assert values["regime.price_points_last_1000_blocks"] == 3
    assert values["regime.active_tokens_last_1000_blocks"] == 2
    assert row["data_quality"]["future_price_rows_used"] is False
    assert row["data_quality"]["regime_window_blocks"] == (
        REGIME_WINDOW_BLOCKS
    )
    assert manifest["records"] == 1
    assert summary["canonical_price_points_validated"] == 6
    assert summary["future_price_rows_used"] is False


def test_chain_regime_handoff_remains_label_free():
    summary = {
        "version": PHASE3_CHAIN_REGIME_FEATURE_VERSION,
        "snapshot_head_block": 2000,
        "feature_family": "chain_regime",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 5,
        "regime_window_blocks": 1000,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_chain_regime_features_ready": True,
    }
    handoff = build_phase3_chain_regime_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        price_path_handoff_sha256=SHA,
    )
    assert handoff["feature_family"] == "chain_regime"
    assert handoff["future_price_rows_used"] is False
    assert handoff["outcome_rows_consumed"] is False
