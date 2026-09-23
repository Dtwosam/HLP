import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_entry import (
    PHASE3_FEATURE_ENTRY_HANDOFF_VERSION,
    PHASE3_FEATURE_SNAPSHOT_KIND,
    PHASE3_FEATURE_SUBJECT_FIELDS,
    PHASE3_FEATURE_SUBJECT_VERSION,
    build_phase3_feature_entry_handoff,
    materialize_phase3_feature_subjects,
)


SHA = "ab" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20


def checkpoint():
    return {
        "version": "phase2-universe-outcome-dataset-handoff-v1",
        "checkpoint_name": "hlp-v1-phase2-universe-labels",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "tokens": 2,
        "confirmed_dump_tokens": 1,
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
        "phase2_dataset_ready": True,
    }


def detector_handoff():
    return {
        "version": "phase2-dump-detector-freeze-handoff-v1",
        "snapshot_head_block": 100,
        "universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "selected_candidate_id": "chosen",
        "selected_candidate_spec": {
            "candidate_id": "chosen",
            "family": "peak_drawdown_rebound",
        },
        "tokens": 2,
        "confirmed_tokens": 1,
        "candidate_selected": True,
        "detector_freeze_ready": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": False,
    }


def universe_rows():
    return [
        {"token": TOKEN_A, "universe_status": "eligible"},
        {"token": TOKEN_B, "universe_status": "eligible"},
    ]


def detector_rows():
    return [
        {
            "version": "phase2-dump-detector-freeze-v1",
            "token": TOKEN_A,
            "detector_id": "chosen",
            "detector_family": "peak_drawdown_rebound",
            "candidate_status": "confirmed",
            "confirmation_block": 50,
            "confirmation_transaction_index": 3,
            "confirmation_log_index": 1,
            "point_in_time_confirmed": True,
            "detector_frozen": True,
            "trough_block": 49,
            "trough_market_cap_proxy_usd": "100",
            "confirmation_market_cap_proxy_usd": "130",
        },
        {
            "version": "phase2-dump-detector-freeze-v1",
            "token": TOKEN_B,
            "detector_id": "chosen",
            "detector_family": "peak_drawdown_rebound",
            "candidate_status": "no_material_drawdown",
            "point_in_time_confirmed": False,
            "detector_frozen": True,
        },
    ]


def test_phase3_entry_exposes_only_confirmed_cutoff_contract(tmp_path: Path):
    output = tmp_path / "subjects.jsonl"
    manifest, summary = materialize_phase3_feature_subjects(
        universe_rows(),
        detector_rows(),
        phase2_dataset_handoff=checkpoint(),
        detector_handoff=detector_handoff(),
        output=output,
    )

    row = json.loads(output.read_text())
    assert set(row) == PHASE3_FEATURE_SUBJECT_FIELDS
    assert row["version"] == PHASE3_FEATURE_SUBJECT_VERSION
    assert row["snapshot_kind"] == PHASE3_FEATURE_SNAPSHOT_KIND
    assert row["feature_cutoff_block"] == 50
    assert row["feature_cutoff_transaction_index"] == 3
    assert row["feature_cutoff_log_index"] == 1
    assert row["feature_cutoff_inclusive"] is True
    assert "trough_block" not in row
    assert "comeback_5x" not in row
    assert "max_post_dump_multiple" not in row
    assert manifest["records"] == 1
    assert summary["feature_subjects"] == 1
    assert summary["outcome_rows_consumed"] is False
    assert summary["outcome_fields_exposed"] is False
    assert summary["future_state_allowed"] is False


def test_phase3_entry_rejects_outcome_contaminated_detector_handoff(tmp_path):
    contaminated = detector_handoff()
    contaminated["outcome_labels_computed"] = True

    with pytest.raises(ValueError, match="contains outcome labels"):
        materialize_phase3_feature_subjects(
            universe_rows(),
            detector_rows(),
            phase2_dataset_handoff=checkpoint(),
            detector_handoff=contaminated,
            output=tmp_path / "bad.jsonl",
        )


def test_phase3_feature_entry_handoff_remains_feature_and_label_free():
    summary = {
        "version": PHASE3_FEATURE_SUBJECT_VERSION,
        "snapshot_head_block": 100,
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_cutoff_inclusive": True,
        "phase2_checkpoint_name": "hlp-v1-phase2-universe-labels",
        "eligible_universe_sha256": SHA,
        "normalized_price_path_sha256": SHA,
        "selected_detector_id": "chosen",
        "universe_tokens": 2,
        "feature_subjects": 1,
        "feature_subjects_sha256": SHA,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": True,
    }

    handoff = build_phase3_feature_entry_handoff(
        summary,
        entry_summary_sha256=SHA,
        phase2_dataset_handoff_sha256=SHA,
        detector_freeze_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    assert handoff["outcome_rows_consumed"] is False
    assert handoff["outcome_fields_exposed"] is False
    assert handoff["future_state_allowed"] is False
    assert handoff["phase3_feature_values_computed"] is False
    assert handoff["phase3_feature_entry_ready"] is True
