import json
from pathlib import Path

from hlp.data.phase2_dataset import (
    PHASE2_CHECKPOINT_NAME,
    PHASE2_DATASET_HANDOFF_VERSION,
    PHASE2_DATASET_VERSION,
    build_phase2_dataset_handoff,
    materialize_phase2_dataset,
)


SHA = "ab" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20


def universe_summary():
    return {
        "version": "phase2-universe-v1",
        "snapshot_head_block": 100,
        "eligible_tokens": 2,
        "coverage_complete": True,
        "phase2_universe_frozen": True,
        "eligible_universe_sha256": SHA,
    }


def universe_handoff():
    return {
        "version": "phase2-universe-freeze-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "eligible_tokens": 2,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_frozen": True,
    }


def outcome_handoff():
    return {
        "version": "phase2-outcome-handoff-v1",
        "snapshot_head_block": 100,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "outcome_rows_sha256": SHA,
        "tokens": 2,
        "confirmed_dump_tokens": 1,
        "comeback_5x_tokens": 1,
        "post_dump_base_semantics": "retrospective_trough",
        "live_signal_semantics": "confirmation_event",
        "max_post_dump_multiple_retained": True,
        "candidate_selected": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
    }


def test_phase2_dataset_joins_universe_and_outcomes_exactly_once(tmp_path: Path):
    universe = [
        {
            "token": TOKEN_A,
            "universe_status": "eligible",
            "source_ids": ["pons_v1"],
        },
        {
            "token": TOKEN_B,
            "universe_status": "eligible",
            "source_ids": ["noxa"],
        },
    ]
    outcomes = [
        {
            "version": "phase2-outcome-label-v1",
            "token": TOKEN_A,
            "dump_status": "confirmed",
            "outcome_eligible": True,
            "comeback_5x": True,
            "max_post_dump_multiple": "12",
        },
        {
            "version": "phase2-outcome-label-v1",
            "token": TOKEN_B,
            "dump_status": "no_material_drawdown",
            "outcome_eligible": False,
            "comeback_5x": None,
            "max_post_dump_multiple": None,
        },
    ]

    output = tmp_path / "dataset.jsonl"
    manifest, summary = materialize_phase2_dataset(
        universe,
        outcomes,
        universe_summary=universe_summary(),
        universe_handoff=universe_handoff(),
        outcome_handoff=outcome_handoff(),
        output=output,
    )

    rows = [
        json.loads(line)
        for line in output.read_text().splitlines()
    ]
    assert manifest["records"] == 2
    assert rows[0]["version"] == PHASE2_DATASET_VERSION
    assert rows[0]["phase3_features_attached"] is False
    assert summary["checkpoint_name"] == PHASE2_CHECKPOINT_NAME
    assert summary["confirmed_dump_tokens"] == 1
    assert summary["comeback_5x_tokens"] == 1
    assert summary["phase2_dataset_ready"] is True


def test_phase2_dataset_handoff_is_feature_free_checkpoint():
    summary = {
        "version": PHASE2_DATASET_VERSION,
        "checkpoint_name": PHASE2_CHECKPOINT_NAME,
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "outcome_rows_sha256": SHA,
        "dataset_rows_sha256": SHA,
        "tokens": 2,
        "confirmed_dump_tokens": 1,
        "comeback_5x_tokens": 1,
        "max_post_dump_multiple_retained": True,
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
        "phase2_dataset_ready": True,
    }
    handoff = build_phase2_dataset_handoff(
        summary,
        dataset_summary_sha256=SHA,
        universe_handoff_sha256=SHA,
        outcome_handoff_sha256=SHA,
    )

    assert handoff["version"] == PHASE2_DATASET_HANDOFF_VERSION
    assert handoff["checkpoint_name"] == "hlp-v1-phase2-universe-labels"
    assert handoff["phase2_dataset_ready"] is True
    assert handoff["phase3_features_attached"] is False
