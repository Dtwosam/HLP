import json
from pathlib import Path

import pytest

from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
    PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION,
    PHASE4_DISCOVERY_ENTRY_VERSION,
    build_phase4_discovery_entry_handoff,
    materialize_phase4_discovery_entry,
)


SHA = "ab" * 32
P2_SHA = "12" * 32
ENTRY_SHA = "34" * 32
COVERAGE_SHA = "56" * 32
STORE_SHA = "78" * 32
REGISTRY_SHA = "90" * 32
TOKEN_A = "0x" + "11" * 20
TOKEN_B = "0x" + "22" * 20


def phase2_handoff():
    return {
        "version": "phase2-universe-outcome-dataset-handoff-v1",
        "checkpoint_name": "hlp-v1-phase2-universe-labels",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
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


def feature_entry_handoff():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "snapshot_kind": "first_major_dump_confirmation",
        "eligible_universe_sha256": SHA,
        "phase2_dataset_handoff_sha256": P2_SHA,
        "universe_tokens": 2,
        "feature_subjects": 1,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def coverage_handoff():
    return {
        "version": "phase3-feature-coverage-handoff-v1",
        "feature_registry_sha256": REGISTRY_SHA,
        "feature_entry_handoff_sha256": ENTRY_SHA,
        "feature_subjects": 1,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_coverage_complete": True,
    }


def feature_store_handoff():
    return {
        "version": "phase3-feature-store-handoff-v1",
        "checkpoint_name": "hlp-v1-phase3-feature-store",
        "feature_registry_sha256": REGISTRY_SHA,
        "feature_coverage_handoff_sha256": COVERAGE_SHA,
        "feature_subjects": 1,
        "features_per_subject": 2,
        "all_registered_families_included": True,
        "all_registered_features_included": True,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_store_ready": True,
        "final_checkpoint_claimed": True,
    }


def phase2_row(token, confirmed):
    if confirmed:
        outcome = {
            "version": "phase2-outcome-label-v1",
            "token": token,
            "detector_id": "chosen",
            "dump_status": "confirmed",
            "outcome_eligible": True,
            "outcome_status": "observed_through_snapshot",
            "live_signal_semantics": "confirmation_event",
            "confirmation_block": 50,
            "confirmation_transaction_index": 1,
            "confirmation_log_index": 2,
            "comeback_5x": True,
            "max_post_dump_multiple": "6",
        }
    else:
        outcome = {
            "version": "phase2-outcome-label-v1",
            "token": token,
            "detector_id": "chosen",
            "dump_status": "no_material_drawdown",
            "outcome_eligible": False,
            "outcome_status": "no_confirmed_first_major_dump",
            "comeback_5x": None,
            "max_post_dump_multiple": None,
        }
    return {
        "version": "phase2-universe-outcome-dataset-v1",
        "token": token,
        "snapshot_head_block": 100,
        "universe": {"token": token},
        "outcome": outcome,
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
    }


def feature_row(token=TOKEN_A):
    return {
        "version": "phase3-feature-store-v1",
        "token": token,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 50,
        "feature_cutoff_transaction_index": 1,
        "feature_cutoff_log_index": 2,
        "feature_cutoff_inclusive": True,
        "feature_registry_sha256": REGISTRY_SHA,
        "included_families": ["price_drawdown"],
        "feature_values": {
            "price.a": "1",
            "price.b": None,
        },
        "missing_feature_ids": ["price.b"],
        "data_quality_by_family": {
            "price_drawdown": {"unit": True},
        },
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
    }


def materialize(tmp_path: Path, feature_rows=None):
    return materialize_phase4_discovery_entry(
        [
            phase2_row(TOKEN_A, True),
            phase2_row(TOKEN_B, False),
        ],
        [feature_row()] if feature_rows is None else feature_rows,
        phase2_dataset_handoff=phase2_handoff(),
        feature_store_handoff=feature_store_handoff(),
        coverage_handoff=coverage_handoff(),
        feature_entry_handoff=feature_entry_handoff(),
        phase2_dataset_handoff_sha256=P2_SHA,
        feature_store_handoff_sha256=STORE_SHA,
        feature_coverage_handoff_sha256=COVERAGE_SHA,
        feature_entry_handoff_sha256=ENTRY_SHA,
        output=tmp_path / "discovery-entry.jsonl",
    )


def test_discovery_entry_joins_labels_only_after_feature_freeze(tmp_path):
    manifest, summary = materialize(tmp_path)

    row = json.loads((tmp_path / "discovery-entry.jsonl").read_text())
    assert row["version"] == PHASE4_DISCOVERY_ENTRY_VERSION
    assert row["token"] == TOKEN_A
    assert row["target_comeback_5x"] is True
    assert row["target_max_post_dump_multiple"] == "6"
    assert row["feature_values"]["price.a"] == "1"
    assert row["feature_values_mutated"] is False
    assert row["labels_joined_after_feature_freeze"] is True
    assert manifest["records"] == 1
    assert summary["discovery_subjects"] == 1
    assert summary["comeback_5x_tokens"] == 1
    assert summary["comeback_5x_base_rate"] == "1"
    assert summary["phase4_discovery_checkpoint_claimed"] is False


def test_discovery_entry_requires_exact_confirmation_cutoff(tmp_path):
    row = feature_row()
    row["feature_cutoff_block"] = 51

    with pytest.raises(ValueError, match="confirmation cutoff drift"):
        materialize(tmp_path, [row])


def test_discovery_entry_requires_exact_subject_membership(tmp_path):
    with pytest.raises(ValueError, match="subject membership drift"):
        materialize(tmp_path, [feature_row(TOKEN_B)])


def test_discovery_entry_rejects_broken_phase2_lineage(tmp_path):
    entry = feature_entry_handoff()
    entry["phase2_dataset_handoff_sha256"] = SHA

    with pytest.raises(ValueError, match="Phase-2 linkage drift"):
        materialize_phase4_discovery_entry(
            [phase2_row(TOKEN_A, True), phase2_row(TOKEN_B, False)],
            [feature_row()],
            phase2_dataset_handoff=phase2_handoff(),
            feature_store_handoff=feature_store_handoff(),
            coverage_handoff=coverage_handoff(),
            feature_entry_handoff=entry,
            phase2_dataset_handoff_sha256=P2_SHA,
            feature_store_handoff_sha256=STORE_SHA,
            feature_coverage_handoff_sha256=COVERAGE_SHA,
            feature_entry_handoff_sha256=ENTRY_SHA,
            output=tmp_path / "bad-lineage.jsonl",
        )


def test_discovery_entry_handoff_never_claims_phase4_checkpoint():
    summary = {
        "version": PHASE4_DISCOVERY_ENTRY_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "feature_registry_sha256": REGISTRY_SHA,
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 10,
        "comeback_5x_tokens": 2,
        "comeback_5x_base_rate": "0.2",
        "continuous_max_post_dump_multiple_retained": True,
        "exact_confirmation_cutoff_alignment": True,
        "matched_feature_coverage_equal": True,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_only": True,
        "phase4_discovery_entry_ready": True,
        "phase4_discovery_checkpoint_claimed": False,
    }
    handoff = build_phase4_discovery_entry_handoff(
        summary,
        discovery_summary_sha256=SHA,
        phase2_dataset_handoff_sha256=P2_SHA,
        feature_store_handoff_sha256=STORE_SHA,
        feature_coverage_handoff_sha256=COVERAGE_SHA,
        feature_entry_handoff_sha256=ENTRY_SHA,
    )
    assert handoff["version"] == PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION
    assert handoff["labels_joined_after_feature_freeze"] is True
    assert handoff["feature_values_mutated"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
