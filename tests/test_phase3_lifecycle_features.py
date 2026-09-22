import hashlib
import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import build_phase3_feature_registry
from hlp.data.phase3_lifecycle_features import (
    PHASE3_LIFECYCLE_FEATURE_HANDOFF_VERSION,
    PHASE3_LIFECYCLE_FEATURE_VERSION,
    build_phase3_lifecycle_feature_handoff,
    materialize_phase3_lifecycle_features,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20


def coverage_row():
    return {
        "version": "phase3-transfer-token-coverage-v1",
        "token": TOKEN,
        "snapshot_head_block": 100,
        "search_from_block": 5,
        "first_code_block": 10,
        "deployment_boundary_verified": True,
        "search_to_block": 100,
        "initial_mint_block": 12,
        "initial_mint_transaction_index": 0,
        "initial_mint_log_index": 1,
        "continuous": True,
        "missing_ranges": [],
        "raw_transfer_tape_sha256": SHA,
        "canonical_transfer_rows": 1,
        "canonical_transfer_rows_sha256": SHA,
        "historical_event_scan_complete": True,
        "initial_mint_coverage_complete": True,
        "positive_supply_at_snapshot": True,
        "outcome_rows_consumed": False,
        "future_state_allowed": False,
        "transfer_coverage_complete": True,
    }


def coverage_sha(row):
    payload = (
        json.dumps(row, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def entry():
    return {
        "version": "phase3-feature-entry-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_entry_ready": True,
    }


def transfer(row):
    return {
        "version": "phase3-canonical-transfer-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "canonical_transfer_rows_sha256": SHA,
        "token_coverage_sha256": coverage_sha(row),
        "universe_tokens": 1,
        "transfer_rows": 1,
        "historical_event_scan_complete": True,
        "initial_mint_coverage_complete": True,
        "transfer_coverage_complete": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_canonical_transfer_tape_ready": True,
    }


def subject(block=50, tx=0, log=0):
    return {
        "version": "phase3-feature-subject-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": block,
        "feature_cutoff_transaction_index": tx,
        "feature_cutoff_log_index": log,
        "feature_cutoff_inclusive": True,
        "selected_detector_id": "chosen",
        "detector_family": "peak_drawdown_rebound",
    }


def test_lifecycle_features_use_verified_deployment_and_mint(tmp_path: Path):
    row = coverage_row()
    output = tmp_path / "lifecycle.jsonl"
    manifest, summary = materialize_phase3_lifecycle_features(
        [subject()],
        [row],
        entry_handoff=entry(),
        transfer_handoff=transfer(row),
        feature_registry=build_phase3_feature_registry(),
        output=output,
    )
    feature = json.loads(output.read_text())
    values = feature["feature_values"]

    assert feature["version"] == PHASE3_LIFECYCLE_FEATURE_VERSION
    assert values["lifecycle.blocks_deployment_to_cutoff"] == 40
    assert values["lifecycle.blocks_initial_mint_to_cutoff"] == 38
    assert values["lifecycle.blocks_deployment_to_initial_mint"] == 2
    assert values["lifecycle.initial_mint_in_deployment_block"] is False
    assert feature["data_quality"]["future_state_used"] is False
    assert manifest["records"] == 1
    assert summary["features_per_subject"] == 4


def test_lifecycle_rejects_mint_after_cutoff(tmp_path: Path):
    row = coverage_row()
    row["initial_mint_block"] = 60
    row["initial_mint_transaction_index"] = 0
    row["initial_mint_log_index"] = 0
    with pytest.raises(ValueError, match="initial mint is after cutoff"):
        materialize_phase3_lifecycle_features(
            [subject()],
            [row],
            entry_handoff=entry(),
            transfer_handoff=transfer(row),
            feature_registry=build_phase3_feature_registry(),
            output=tmp_path / "bad.jsonl",
        )


def test_lifecycle_handoff_binds_transfer_coverage():
    row = coverage_row()
    summary = {
        "version": PHASE3_LIFECYCLE_FEATURE_VERSION,
        "snapshot_head_block": 100,
        "feature_family": "lifecycle_age",
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "token_coverage_sha256": SHA,
        "eligible_universe_sha256": SHA,
        "feature_subjects": 1,
        "features_per_subject": 4,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_lifecycle_features_ready": True,
    }
    handoff = build_phase3_lifecycle_feature_handoff(
        summary,
        feature_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
        canonical_transfer_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_LIFECYCLE_FEATURE_HANDOFF_VERSION
    assert handoff["phase3_lifecycle_features_ready"] is True
