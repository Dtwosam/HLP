import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_registry import (
    build_phase3_feature_registry,
    validate_phase3_feature_registry,
)
from hlp.data.phase3_feature_staging import (
    PHASE3_FEATURE_STAGING_HANDOFF_VERSION,
    PHASE3_FEATURE_STAGING_VERSION,
    PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
    build_phase3_feature_staging_handoff,
    materialize_phase3_feature_staging,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20


def registry_and_sha():
    registry = build_phase3_feature_registry()
    return registry, validate_phase3_feature_registry(
        registry
    )["registry_sha256"]


def coverage_handoff(registry_sha):
    return {
        "version": "phase3-feature-coverage-handoff-v1",
        "feature_registry_sha256": registry_sha,
        "coverage_rows_sha256": SHA,
        "required_families": ["price_drawdown", "trade_flow"],
        "feature_subjects": 1,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_coverage_complete": True,
    }


def coverage_row(missing_trade=()):
    return {
        "version": "phase3-feature-coverage-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 50,
        "feature_cutoff_transaction_index": 1,
        "feature_cutoff_log_index": 2,
        "feature_cutoff_inclusive": True,
        "required_families": ["price_drawdown", "trade_flow"],
        "families_present": ["price_drawdown", "trade_flow"],
        "missing_feature_ids_by_family": {
            "price_drawdown": [],
            "trade_flow": sorted(missing_trade),
        },
        "all_required_families_present": True,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
    }


def family_row(family, registry, registry_sha, missing=()):
    defs = [
        row
        for row in registry
        if row["family"] == family
    ]
    missing = set(missing)
    values = {}
    for row in defs:
        feature_id = row["feature_id"]
        if feature_id in missing:
            values[feature_id] = None
        elif row["dtype"] == "decimal_string":
            values[feature_id] = "0.5"
        elif row["dtype"] == "integer":
            values[feature_id] = 2
        elif row["dtype"] == "boolean":
            values[feature_id] = True
        else:
            values[feature_id] = "x"
    return {
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 50,
        "feature_cutoff_transaction_index": 1,
        "feature_cutoff_log_index": 2,
        "feature_cutoff_inclusive": True,
        "feature_registry_sha256": registry_sha,
        "feature_values": values,
        "missing_feature_ids": sorted(missing),
        "data_quality": {"unit": True},
    }


def test_staging_flattens_equal_coverage_without_labels(tmp_path: Path):
    registry, registry_sha = registry_and_sha()
    missing = {"trade.buy_trade_share_so_far"}
    output = tmp_path / "staging.jsonl"
    manifest, summary = materialize_phase3_feature_staging(
        [coverage_row(missing)],
        {
            "price_drawdown": [
                family_row(
                    "price_drawdown",
                    registry,
                    registry_sha,
                )
            ],
            "trade_flow": [
                family_row(
                    "trade_flow",
                    registry,
                    registry_sha,
                    missing,
                )
            ],
        },
        coverage_handoff=coverage_handoff(registry_sha),
        feature_registry=registry,
        output=output,
    )

    row = json.loads(output.read_text())
    assert row["version"] == PHASE3_FEATURE_STAGING_VERSION
    assert len(row["feature_values"]) == 22
    assert row["missing_feature_ids"] == sorted(missing)
    assert row["outcome_fields_exposed"] is False
    assert row["future_state_allowed"] is False
    assert manifest["records"] == 1
    assert summary["features_per_subject"] == 22
    assert summary["outcome_rows_consumed"] is False
    assert summary["staging_bundle_ready"] is True
    assert summary["final_checkpoint_name"] == (
        PHASE3_FINAL_FEATURE_STORE_CHECKPOINT
    )
    assert summary["final_checkpoint_claimed"] is False


def test_staging_enforces_registry_dtype(tmp_path: Path):
    registry, registry_sha = registry_and_sha()
    price = family_row(
        "price_drawdown",
        registry,
        registry_sha,
    )
    price["feature_values"][
        "price.price_points_so_far"
    ] = "2"

    with pytest.raises(ValueError, match="must be an integer"):
        materialize_phase3_feature_staging(
            [coverage_row()],
            {
                "price_drawdown": [price],
                "trade_flow": [
                    family_row(
                        "trade_flow",
                        registry,
                        registry_sha,
                    )
                ],
            },
            coverage_handoff=coverage_handoff(registry_sha),
            feature_registry=registry,
            output=tmp_path / "bad.jsonl",
        )


def test_staging_rejects_null_for_error_if_missing_feature(tmp_path: Path):
    registry, registry_sha = registry_and_sha()
    price = family_row(
        "price_drawdown",
        registry,
        registry_sha,
        {"price.market_cap_proxy_usd_at_cutoff"},
    )
    coverage = coverage_row()
    coverage["missing_feature_ids_by_family"][
        "price_drawdown"
    ] = ["price.market_cap_proxy_usd_at_cutoff"]

    with pytest.raises(ValueError, match="cannot be null"):
        materialize_phase3_feature_staging(
            [coverage],
            {
                "price_drawdown": [price],
                "trade_flow": [
                    family_row(
                        "trade_flow",
                        registry,
                        registry_sha,
                    )
                ],
            },
            coverage_handoff=coverage_handoff(registry_sha),
            feature_registry=registry,
            output=tmp_path / "bad-null.jsonl",
        )


def test_staging_handoff_never_claims_final_feature_store():
    summary = {
        "version": PHASE3_FEATURE_STAGING_VERSION,
        "feature_registry_sha256": SHA,
        "feature_rows_sha256": SHA,
        "coverage_rows_sha256": SHA,
        "included_families": ["price_drawdown", "trade_flow"],
        "feature_subjects": 1,
        "features_per_subject": 22,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "staging_bundle_ready": True,
        "final_checkpoint_name": PHASE3_FINAL_FEATURE_STORE_CHECKPOINT,
        "final_checkpoint_claimed": False,
    }
    handoff = build_phase3_feature_staging_handoff(
        summary,
        staging_summary_sha256=SHA,
        feature_coverage_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_FEATURE_STAGING_HANDOFF_VERSION
    assert handoff["staging_bundle_ready"] is True
    assert handoff["final_checkpoint_claimed"] is False
