import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_price_features import (
    PHASE3_PRICE_FEATURE_HANDOFF_VERSION,
    PHASE3_PRICE_FEATURE_VERSION,
    build_phase3_price_feature_handoff,
    materialize_phase3_price_features,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20


def entry_handoff():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_inclusive": True,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "selected_detector_id": "chosen",
        "feature_subjects": 1,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": True,
    }


def price_handoff(points=6):
    return {
        "version": "phase2-research-price-path-handoff-v1",
        "snapshot_head_block": 100,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "price_points": points,
        "research_price_path_ready": True,
        "outcome_labels_computed": False,
    }


def subject(tx=0, log=0):
    return {
        "version": "phase3-feature-subject-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 5,
        "feature_cutoff_transaction_index": tx,
        "feature_cutoff_log_index": log,
        "feature_cutoff_inclusive": True,
        "selected_detector_id": "chosen",
        "detector_family": "peak_drawdown_rebound",
    }


def price_row(block, value, tx=0, log=0):
    return {
        "version": "phase2-research-price-path-v1",
        "token": TOKEN,
        "block_number": block,
        "transaction_index": tx,
        "log_index": log,
        "market_cap_proxy_usd": str(value),
        "canonical_research_price_path": True,
    }


def test_price_features_stop_exactly_at_confirmation_cutoff(tmp_path: Path):
    rows = [
        price_row(1, 100),
        price_row(2, 200),
        price_row(3, 120),
        price_row(4, 80),
        price_row(5, 130),
        price_row(6, 1000),
    ]
    output = tmp_path / "price-features.jsonl"
    manifest, summary = materialize_phase3_price_features(
        [subject()],
        rows,
        entry_handoff=entry_handoff(),
        price_path_handoff=price_handoff(),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )

    row = json.loads(output.read_text())
    values = row["feature_values"]
    assert row["version"] == PHASE3_PRICE_FEATURE_VERSION
    assert values["price.market_cap_proxy_usd_at_cutoff"] == "130"
    assert values["price.trailing_peak_market_cap_proxy_usd"] == "200"
    assert values["price.drawdown_fraction_from_trailing_peak"] == "0.35"
    assert values["price.max_drawdown_fraction_so_far"] == "0.6"
    assert values["price.minimum_market_cap_proxy_usd_so_far"] == "80"
    assert values["price.expansion_multiple_from_first_observation"] == "1.3"
    assert values["price.recovery_multiple_from_minimum_so_far"] == "1.625"
    assert values["price.price_points_so_far"] == 5
    assert values["price.blocks_since_first_observation"] == 4
    assert values["price.blocks_since_trailing_peak"] == 3
    assert values["price.events_since_trailing_peak"] == 3
    assert row["missing_feature_ids"] == []
    assert row["data_quality"]["future_price_rows_used"] is False

    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_price_rows_ignored"] == 1
    assert summary["future_price_rows_used"] is False
    assert summary["outcome_rows_consumed"] is False


def test_price_features_respect_same_block_transaction_order(tmp_path: Path):
    rows = [
        price_row(4, 100, 0, 0),
        price_row(5, 130, 1, 0),
        price_row(5, 1000, 2, 0),
    ]
    output = tmp_path / "same-block.jsonl"
    _, summary = materialize_phase3_price_features(
        [subject(tx=1, log=0)],
        rows,
        entry_handoff=entry_handoff(),
        price_path_handoff=price_handoff(points=3),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )

    row = json.loads(output.read_text())
    assert row["feature_values"][
        "price.market_cap_proxy_usd_at_cutoff"
    ] == "130"
    assert summary["post_cutoff_subject_price_rows_ignored"] == 1


def test_price_features_require_exact_canonical_cutoff_point(tmp_path: Path):
    rows = [
        price_row(1, 100),
        price_row(4, 120),
        price_row(6, 1000),
    ]
    with pytest.raises(ValueError, match="lacks exact canonical point"):
        materialize_phase3_price_features(
            [subject()],
            rows,
            entry_handoff=entry_handoff(),
            price_path_handoff=price_handoff(points=3),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "missing-cutoff.jsonl",
        )


def test_price_feature_handoff_preserves_leakage_guards():
    summary = {
        "version": PHASE3_PRICE_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "price_drawdown",
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_inclusive": True,
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 11,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_price_features_ready": True,
    }
    handoff = build_phase3_price_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        price_path_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_PRICE_FEATURE_HANDOFF_VERSION
    assert handoff["future_price_rows_used"] is False
    assert handoff["outcome_rows_consumed"] is False
    assert handoff["phase3_price_features_ready"] is True
