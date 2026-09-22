import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_venue_features import (
    PHASE3_VENUE_FEATURE_HANDOFF_VERSION,
    PHASE3_VENUE_FEATURE_VERSION,
    build_phase3_venue_feature_handoff,
    materialize_phase3_venue_features,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20
OTHER = "0x" + "22" * 20


def entry():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "feature_subjects": 1,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def price_handoff(rows):
    return {
        "version": "phase2-research-price-path-handoff-v1",
        "snapshot_head_block": 100,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "price_points": rows,
        "research_price_path_ready": True,
        "outcome_labels_computed": False,
    }


def subject():
    return {
        "version": "phase3-feature-subject-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 5,
        "feature_cutoff_transaction_index": 0,
        "feature_cutoff_log_index": 1,
        "feature_cutoff_inclusive": True,
        "selected_detector_id": "chosen",
        "detector_family": "peak_drawdown_rebound",
    }


def price(token, block, log, sources, components):
    return {
        "version": "phase2-research-price-path-v1",
        "token": token,
        "block_number": block,
        "transaction_index": 0,
        "log_index": log,
        "market_cap_proxy_usd": "100000",
        "source_ids": sources,
        "component_ids": components,
        "canonical_research_price_path": True,
    }


def test_venue_features_track_only_causal_identity_changes(tmp_path: Path):
    rows = [
        price(OTHER, 1, 0, ["noxa"], ["noxa"]),
        price(TOKEN, 2, 0, ["pons_v2"], ["pons_v2"]),
        price(TOKEN, 3, 0, ["pons_v2"], ["pons_v2"]),
        price(
            TOKEN,
            4,
            0,
            ["pons_v2", "direct_uniswap_v4"],
            ["pons_v2", "direct_canonical"],
        ),
        price(
            TOKEN,
            5,
            1,
            ["direct_uniswap_v4"],
            ["direct_canonical"],
        ),
        price(TOKEN, 6, 0, ["noxa"], ["noxa"]),
    ]
    output = tmp_path / "venue.jsonl"
    manifest, summary = materialize_phase3_venue_features(
        [subject()],
        rows,
        entry_handoff=entry(),
        price_path_handoff=price_handoff(len(rows)),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )

    row = json.loads(output.read_text())
    values = row["feature_values"]
    assert row["version"] == PHASE3_VENUE_FEATURE_VERSION
    assert values["venue.unique_source_ids_seen_so_far"] == 2
    assert values["venue.unique_component_ids_seen_so_far"] == 2
    assert values["venue.source_set_switches_so_far"] == 2
    assert values["venue.component_set_switches_so_far"] == 2
    assert values["venue.current_source_count"] == 1
    assert values["venue.current_component_count"] == 1
    assert values["venue.multi_source_events_so_far"] == 1
    assert values["venue.multi_component_events_so_far"] == 1
    assert values["venue.current_event_multi_source"] is False
    assert values["venue.current_event_multi_component"] is False
    assert manifest["records"] == 1
    assert summary["post_cutoff_subject_price_rows_ignored"] == 1
    assert summary["future_price_rows_used"] is False


def test_venue_features_require_exact_cutoff_event(tmp_path: Path):
    rows = [
        price(TOKEN, 2, 0, ["pons_v2"], ["pons_v2"]),
    ]
    with pytest.raises(ValueError, match="lacks exact cutoff"):
        materialize_phase3_venue_features(
            [subject()],
            rows,
            entry_handoff=entry(),
            price_path_handoff=price_handoff(1),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "bad.jsonl",
        )


def test_venue_feature_handoff_is_label_free():
    summary = {
        "version": PHASE3_VENUE_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "venue_mechanics",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 10,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_venue_features_ready": True,
    }
    handoff = build_phase3_venue_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        price_path_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_VENUE_FEATURE_HANDOFF_VERSION
    assert handoff["future_price_rows_used"] is False
    assert handoff["outcome_rows_consumed"] is False
