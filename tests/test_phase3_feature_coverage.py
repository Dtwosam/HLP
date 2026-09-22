import json
from pathlib import Path

import pytest

from hlp.data.phase3_feature_coverage import (
    PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION,
    PHASE3_FEATURE_COVERAGE_VERSION,
    build_phase3_feature_coverage_handoff,
    materialize_phase3_feature_coverage,
)
from hlp.data.phase3_feature_registry import (
    build_phase3_feature_registry,
    validate_phase3_feature_registry,
)


SHA = "ab" * 32
TOKEN = "0x" + "11" * 20


def subject():
    return {
        "version": "phase3-feature-subject-v1",
        "token": TOKEN,
        "snapshot_kind": "first_major_dump_confirmation",
        "feature_cutoff_block": 50,
        "feature_cutoff_transaction_index": 1,
        "feature_cutoff_log_index": 2,
        "feature_cutoff_inclusive": True,
        "selected_detector_id": "chosen",
        "detector_family": "peak_drawdown_rebound",
    }


def family_row(family, registry_sha, missing=()):
    registry = build_phase3_feature_registry()
    ids = [
        row["feature_id"]
        for row in registry
        if row["family"] == family
    ]
    values = {
        feature_id: (
            None if feature_id in set(missing) else 0
        )
        for feature_id in ids
    }
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


def handoffs(registry_sha):
    return {
        "price_drawdown": {
            "version": "phase3-price-features-handoff-v1",
            "feature_family": "price_drawdown",
            "feature_registry_sha256": registry_sha,
            "feature_subjects": 1,
            "outcome_rows_consumed": False,
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
            "phase3_price_features_ready": True,
        },
        "trade_flow": {
            "version": "phase3-trade-features-handoff-v1",
            "feature_family": "trade_flow",
            "feature_registry_sha256": registry_sha,
            "feature_subjects": 1,
            "outcome_rows_consumed": False,
            "outcome_fields_exposed": False,
            "future_state_allowed": False,
            "phase3_trade_features_ready": True,
        },
    }


def test_feature_coverage_requires_equal_rows_at_exact_cutoff(tmp_path: Path):
    registry = build_phase3_feature_registry()
    registry_sha = validate_phase3_feature_registry(
        registry
    )["registry_sha256"]
    missing = ["trade.buy_trade_share_so_far"]
    output = tmp_path / "coverage.jsonl"
    manifest, summary = materialize_phase3_feature_coverage(
        [subject()],
        {
            "price_drawdown": [
                family_row("price_drawdown", registry_sha)
            ],
            "trade_flow": [
                family_row(
                    "trade_flow",
                    registry_sha,
                    missing=missing,
                )
            ],
        },
        handoffs(registry_sha),
        feature_registry=registry,
        required_families=["price_drawdown", "trade_flow"],
        output=output,
    )

    row = json.loads(output.read_text())
    assert row["version"] == PHASE3_FEATURE_COVERAGE_VERSION
    assert row["all_required_families_present"] is True
    assert row["missing_feature_ids_by_family"][
        "trade_flow"
    ] == missing
    assert manifest["records"] == 1
    assert summary["matched_subject_coverage_equal"] is True
    assert summary["subjects_with_any_missing_values"] == 1
    assert summary["feature_coverage_complete"] is True


def test_feature_coverage_rejects_cutoff_drift(tmp_path: Path):
    registry = build_phase3_feature_registry()
    registry_sha = validate_phase3_feature_registry(
        registry
    )["registry_sha256"]
    row = family_row("price_drawdown", registry_sha)
    row["feature_cutoff_block"] = 51

    with pytest.raises(ValueError, match="cutoff drift"):
        materialize_phase3_feature_coverage(
            [subject()],
            {"price_drawdown": [row]},
            {
                "price_drawdown": handoffs(registry_sha)[
                    "price_drawdown"
                ]
            },
            feature_registry=registry,
            required_families=["price_drawdown"],
            output=tmp_path / "bad.jsonl",
        )


def test_feature_coverage_handoff_keeps_missingness_not_outcomes():
    summary = {
        "version": PHASE3_FEATURE_COVERAGE_VERSION,
        "feature_registry_sha256": SHA,
        "required_families": ["price_drawdown"],
        "feature_subjects": 1,
        "coverage_rows_sha256": SHA,
        "matched_subject_coverage_equal": True,
        "missingness_recorded": True,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "feature_coverage_complete": True,
    }
    handoff = build_phase3_feature_coverage_handoff(
        summary,
        coverage_summary_sha256=SHA,
        feature_entry_handoff_sha256=SHA,
    )
    assert handoff["version"] == PHASE3_FEATURE_COVERAGE_HANDOFF_VERSION
    assert handoff["matched_subject_coverage_equal"] is True
    assert handoff["outcome_fields_exposed"] is False



def test_feature_coverage_contract_supports_regime_and_holder_families():
    from hlp.data.phase3_feature_coverage import FAMILY_HANDOFF_CONTRACTS

    assert set(FAMILY_HANDOFF_CONTRACTS) == {
        "chain_regime",
        "holder_state",
        "lifecycle_age",
        "participant_retention",
        "price_drawdown",
        "supply_redistribution",
        "trade_flow",
        "trade_size_flow",
        "venue_mechanics",
    }
    assert FAMILY_HANDOFF_CONTRACTS["chain_regime"][1] == (
        "phase3_chain_regime_features_ready"
    )
    assert FAMILY_HANDOFF_CONTRACTS["holder_state"][1] == (
        "phase3_holder_features_ready"
    )



def test_feature_coverage_contract_supports_venue_mechanics():
    from hlp.data.phase3_feature_coverage import FAMILY_HANDOFF_CONTRACTS

    assert FAMILY_HANDOFF_CONTRACTS["venue_mechanics"] == (
        "phase3-venue-mechanics-features-handoff-v1",
        "phase3_venue_features_ready",
    )



def test_feature_coverage_contract_supports_participant_retention():
    from hlp.data.phase3_feature_coverage import FAMILY_HANDOFF_CONTRACTS

    assert FAMILY_HANDOFF_CONTRACTS["participant_retention"] == (
        "phase3-retention-features-handoff-v1",
        "phase3_retention_features_ready",
    )



def test_feature_coverage_contract_supports_supply_redistribution():
    from hlp.data.phase3_feature_coverage import FAMILY_HANDOFF_CONTRACTS

    assert FAMILY_HANDOFF_CONTRACTS["supply_redistribution"] == (
        "phase3-supply-redistribution-features-handoff-v1",
        "phase3_redistribution_features_ready",
    )



def test_feature_coverage_contract_supports_trade_size_flow():
    from hlp.data.phase3_feature_coverage import FAMILY_HANDOFF_CONTRACTS

    assert FAMILY_HANDOFF_CONTRACTS["trade_size_flow"] == (
        "phase3-trade-size-flow-features-handoff-v1",
        "phase3_trade_size_flow_features_ready",
    )



def test_feature_coverage_contract_supports_lifecycle_age():
    from hlp.data.phase3_feature_coverage import FAMILY_HANDOFF_CONTRACTS

    assert FAMILY_HANDOFF_CONTRACTS["lifecycle_age"] == (
        "phase3-lifecycle-age-features-handoff-v1",
        "phase3_lifecycle_features_ready",
    )
