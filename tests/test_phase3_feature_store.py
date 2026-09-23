import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import (
    build_phase3_feature_registry,
    validate_phase3_feature_registry,
)
from hlp.data.phase3_feature_store import (
    PHASE3_FEATURE_STORE_HANDOFF_VERSION,
    PHASE3_FEATURE_STORE_VERSION,
    build_phase3_feature_store_handoff,
    materialize_phase3_feature_store,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20


def registry_state():
    rows = build_phase3_feature_registry()
    report = validate_phase3_feature_registry(rows)
    return rows, report


def staging_handoff(report, families=None):
    families = report["families"] if families is None else families
    return {
        "version": "phase3-feature-staging-handoff-v1",
        "feature_registry_sha256": report["registry_sha256"],
        "feature_rows_sha256": SHA,
        "coverage_rows_sha256": SHA,
        "feature_coverage_handoff_sha256": SHA,
        "included_families": list(families),
        "feature_subjects": 1,
        "features_per_subject": report["features"],
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "staging_bundle_ready": True,
        "final_checkpoint_name": "hlp-v1-phase3-feature-store",
        "final_checkpoint_claimed": False,
    }


def coverage_handoff(report, families=None):
    families = report["families"] if families is None else families
    return {
        "version": "phase3-feature-coverage-handoff-v1",
        "feature_registry_sha256": report["registry_sha256"],
        "coverage_rows_sha256": SHA,
        "required_families": list(families),
        "feature_subjects": 1,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_coverage_complete": True,
    }


def staging_row(registry, report):
    values = {}
    missing = []
    quality = {}
    for definition in registry:
        feature_id = definition["feature_id"]
        dtype = definition["dtype"]
        policy = definition["missingness_policy"]
        if policy == "null_with_flag":
            values[feature_id] = None
            missing.append(feature_id)
        elif dtype == "decimal_string":
            values[feature_id] = "0"
        elif dtype == "integer":
            values[feature_id] = 0
        elif dtype == "boolean":
            values[feature_id] = False
        else:
            values[feature_id] = "unit"
        quality.setdefault(definition["family"], {"unit": True})
    return {
        "version": "phase3-feature-staging-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 50,
        "feature_cutoff_transaction_index": 1,
        "feature_cutoff_log_index": 2,
        "feature_cutoff_inclusive": True,
        "feature_registry_sha256": report["registry_sha256"],
        "included_families": report["families"],
        "feature_values": values,
        "missing_feature_ids": sorted(missing),
        "data_quality_by_family": quality,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
    }


def test_feature_store_claims_checkpoint_only_for_all_registry_features(
    tmp_path: Path,
):
    registry, report = registry_state()
    output = tmp_path / "store.jsonl"
    manifest, summary = materialize_phase3_feature_store(
        [staging_row(registry, report)],
        staging_handoff=staging_handoff(report),
        coverage_handoff=coverage_handoff(report),
        feature_coverage_handoff_sha256=SHA,
        feature_registry=registry,
        output=output,
    )
    row = json.loads(output.read_text())
    assert row["version"] == PHASE3_FEATURE_STORE_VERSION
    assert len(row["feature_values"]) == report["features"]
    assert row["included_families"] == report["families"]
    assert manifest["records"] == 1
    assert summary["features_per_subject"] == report["features"]
    assert summary["all_registered_families_included"] is True
    assert summary["all_registered_features_included"] is True
    assert summary["final_checkpoint_claimed"] is True


def test_feature_store_rejects_partial_family_staging(tmp_path: Path):
    registry, report = registry_state()
    partial = report["families"][:-1]
    with pytest.raises(ValueError, match="every registered family"):
        materialize_phase3_feature_store(
            [staging_row(registry, report)],
            staging_handoff=staging_handoff(report, partial),
            coverage_handoff=coverage_handoff(report, partial),
            feature_coverage_handoff_sha256=SHA,
            feature_registry=registry,
            output=tmp_path / "bad.jsonl",
        )


def test_feature_store_rejects_wrong_coverage_handoff_link(tmp_path: Path):
    registry, report = registry_state()
    stage = staging_handoff(report)
    stage["feature_coverage_handoff_sha256"] = "cd" * 32
    with pytest.raises(ValueError, match="linkage drift"):
        materialize_phase3_feature_store(
            [staging_row(registry, report)],
            staging_handoff=stage,
            coverage_handoff=coverage_handoff(report),
            feature_coverage_handoff_sha256=SHA,
            feature_registry=registry,
            output=tmp_path / "bad-link.jsonl",
        )


def test_feature_store_handoff_claims_named_checkpoint():
    registry, report = registry_state()
    summary = {
        "version": PHASE3_FEATURE_STORE_VERSION,
        "checkpoint_name": "hlp-v1-phase3-feature-store",
        "feature_registry_sha256": report["registry_sha256"],
        "feature_rows_sha256": SHA,
        "staging_rows_sha256": SHA,
        "coverage_rows_sha256": SHA,
        "included_families": report["families"],
        "feature_subjects": 1,
        "features_per_subject": report["features"],
        "missing_feature_values": 2,
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
    handoff = build_phase3_feature_store_handoff(
        summary,
        feature_store_summary_sha256=SHA,
        staging_handoff_sha256=SHA,
        feature_coverage_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_FEATURE_STORE_HANDOFF_VERSION
    assert handoff["checkpoint_name"] == "hlp-v1-phase3-feature-store"
    assert handoff["final_checkpoint_claimed"] is True
