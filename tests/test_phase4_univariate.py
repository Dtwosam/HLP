import pytest

from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND
from hlp.data.phase3_feature_registry import (
    PHASE3_FEATURE_REGISTRY_VERSION,
    validate_phase3_feature_registry,
)
from hlp.data.phase4_univariate import (
    PHASE4_UNIVARIATE_HANDOFF_VERSION,
    PHASE4_UNIVARIATE_REPORT_VERSION,
    build_phase4_univariate_handoff,
    build_phase4_univariate_report,
)


SHA = "ab" * 32


def definition(feature_id, dtype, family="unit", missing="null_with_flag"):
    return {
        "registry_version": PHASE3_FEATURE_REGISTRY_VERSION,
        "feature_id": feature_id,
        "family": family,
        "dtype": dtype,
        "formula": f"unit formula for {feature_id}",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "cutoff_inclusive": True,
        "data_dependency": "unit-test",
        "missingness_policy": missing,
        "future_state_allowed": False,
        "outcome_dependency_allowed": False,
    }


def registry():
    return [
        definition("unit.numeric", "decimal_string"),
        definition("unit.count", "integer"),
        definition("unit.flag", "boolean"),
        definition("unit.category", "string"),
    ]


def handoffs():
    report = validate_phase3_feature_registry(registry())
    registry_sha = report["registry_sha256"]
    discovery = {
        "version": "phase4-discovery-entry-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": registry_sha,
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 4,
        "comeback_5x_tokens": 2,
        "comeback_5x_base_rate": "0.5",
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_entry_ready": True,
        "phase4_discovery_checkpoint_claimed": False,
    }
    base = {
        "version": "phase4-base-rate-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": registry_sha,
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 4,
        "comeback_5x_tokens": 2,
        "comeback_5x_base_rate": "0.5",
        "feature_relationships_tested": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_base_rate_report_ready": True,
    }
    return discovery, base


def row(suffix, winner, numeric, count, flag, category):
    missing = []
    values = {
        "unit.numeric": numeric,
        "unit.count": count,
        "unit.flag": flag,
        "unit.category": category,
    }
    for feature_id, value in values.items():
        if value is None:
            missing.append(feature_id)
    return {
        "version": "phase4-discovery-entry-v1",
        "token": "0x" + suffix * 20,
        "target_comeback_5x": winner,
        "feature_values": values,
        "missing_feature_ids": missing,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
        "phase4_discovery_only": True,
    }


def test_univariate_reports_winner_and_failure_distributions():
    discovery, base = handoffs()
    report = build_phase4_univariate_report(
        [
            row("11", True, "8", 1, True, "a"),
            row("22", True, "10", None, True, "b"),
            row("33", False, "2", 0, False, "a"),
            row("44", False, "4", 0, True, "a"),
        ],
        registry(),
        discovery_entry_handoff=discovery,
        base_rate_handoff=base,
    )

    assert report["version"] == PHASE4_UNIVARIATE_REPORT_VERSION
    assert report["winner_tokens"] == 2
    assert report["failure_tokens"] == 2
    assert report["features_tested"] == 4
    by_id = {
        row["feature_id"]: row
        for row in report["feature_reports"]
    }
    numeric = by_id["unit.numeric"]
    assert numeric["winner_distribution"]["mean"] == "9"
    assert numeric["failure_distribution"]["mean"] == "3"
    assert numeric["mean_difference_winner_minus_failure"] == "6"
    assert numeric["median_difference_winner_minus_failure"] == "6"
    assert numeric["cliffs_delta_winner_vs_failure"] == "1"

    count = by_id["unit.count"]
    assert count["winner_missing"] == 1
    assert count["failure_missing"] == 0
    assert count["winner_missing_rate"] == "0.5"
    assert count["missing_rate_difference_winner_minus_failure"] == "0.5"

    flag = by_id["unit.flag"]
    assert flag["winner_true_rate"] == "1"
    assert flag["failure_true_rate"] == "0.5"
    assert flag["true_rate_difference_winner_minus_failure"] == "0.5"

    category = by_id["unit.category"]
    categories = {
        item["value"]: item
        for item in category["categories"]
    }
    assert categories["a"]["winner_count"] == 1
    assert categories["a"]["failure_count"] == 2
    assert categories["b"]["winner_count"] == 1
    assert categories["b"]["failure_count"] == 0

    assert report["candidate_features_ranked"] is False
    assert report["signal_promoted"] is False
    assert report["unseen_slice_validation_complete"] is False
    assert report["phase4_discovery_checkpoint_claimed"] is False


def test_univariate_rejects_base_rate_population_drift():
    discovery, base = handoffs()
    base["discovery_subjects"] = 5

    with pytest.raises(ValueError, match="discovery_subjects drift"):
        build_phase4_univariate_report(
            [
                row("11", True, "8", 1, True, "a"),
                row("22", True, "10", 1, True, "b"),
                row("33", False, "2", 0, False, "a"),
                row("44", False, "4", 0, True, "a"),
            ],
            registry(),
            discovery_entry_handoff=discovery,
            base_rate_handoff=base,
        )


def test_univariate_handoff_never_ranks_or_promotes():
    discovery, _ = handoffs()
    report = {
        "version": PHASE4_UNIVARIATE_REPORT_VERSION,
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": discovery["feature_registry_sha256"],
        "discovery_rows_sha256": SHA,
        "discovery_subjects": 4,
        "winner_tokens": 2,
        "failure_tokens": 2,
        "features_tested": 4,
        "families_tested": 1,
        "winner_failure_frequencies_reported": True,
        "missingness_compared_by_outcome": True,
        "univariate_relationships_tested": True,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "unseen_slice_validation_complete": False,
        "multiple_testing_control_applied": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_univariate_report_ready": True,
    }
    handoff = build_phase4_univariate_handoff(
        report,
        report_sha256=SHA,
        discovery_entry_handoff_sha256=SHA,
        base_rate_handoff_sha256=SHA,
        feature_registry_file_sha256=SHA,
    )
    assert handoff["version"] == PHASE4_UNIVARIATE_HANDOFF_VERSION
    assert handoff["candidate_features_ranked"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["unseen_slice_validation_complete"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
