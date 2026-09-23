from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND
from hlp.data.phase3_feature_registry import (
    PHASE3_FEATURE_REGISTRY_VERSION,
    validate_phase3_feature_registry,
)
from hlp.data.phase4_magnitude_strata import (
    PHASE4_MAGNITUDE_STRATA_HANDOFF_VERSION,
    PHASE4_MAGNITUDE_STRATA_REPORT_VERSION,
    build_phase4_magnitude_strata_handoff,
    build_phase4_magnitude_strata_report,
)


SHA = "ab" * 32


def definition(feature_id, dtype):
    return {
        "registry_version": PHASE3_FEATURE_REGISTRY_VERSION,
        "feature_id": feature_id,
        "family": "unit",
        "dtype": dtype,
        "formula": f"unit formula for {feature_id}",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "cutoff_inclusive": True,
        "data_dependency": "unit-test",
        "missingness_policy": "null_with_flag",
        "future_state_allowed": False,
        "outcome_dependency_allowed": False,
    }


def registry():
    return [
        definition("unit.numeric", "decimal_string"),
        definition("unit.flag", "boolean"),
        definition("unit.category", "string"),
    ]


def split_handoff():
    report = validate_phase3_feature_registry(registry())
    return {
        "version": "phase4-chronological-split-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": report["registry_sha256"],
        "discovery_split_rows_sha256": SHA,
        "discovery_split_rows": 8,
        "phase4_split_frozen": True,
        "final_test_separated": True,
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "feature_values_mutated": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def row(index, multiple, numeric, flag, category):
    values = {
        "unit.numeric": numeric,
        "unit.flag": flag,
        "unit.category": category,
    }
    return {
        "version": "phase4-discovery-entry-v1",
        "token": "0x" + f"{index:040x}",
        "target_comeback_5x": float(multiple) >= 5,
        "target_max_post_dump_multiple": str(multiple),
        "feature_values": values,
        "missing_feature_ids": [
            feature_id
            for feature_id, value in values.items()
            if value is None
        ],
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
    }


def discovery_rows():
    return [
        row(1, "2", "1", False, "a"),
        row(2, "4", "2", False, "a"),
        row(3, "6", "3", False, "b"),
        row(4, "8", "4", True, "b"),
        row(5, "12", "8", True, "b"),
        row(6, "15", "9", True, "c"),
        row(7, "22", "12", True, "c"),
        row(8, "30", "14", True, "c"),
    ]


def test_magnitude_strata_compare_ordinary_5x_with_10x_and_20x():
    report = build_phase4_magnitude_strata_report(
        discovery_rows(),
        registry(),
        chronological_split_handoff=split_handoff(),
    )

    assert report["version"] == PHASE4_MAGNITUDE_STRATA_REPORT_VERSION
    assert report["strata_counts"] == {
        "failure_lt5x": 2,
        "ordinary_5x_lt10x": 2,
        "runner_10x_lt20x": 2,
        "runner_20x_plus": 2,
    }
    by_id = {
        row["feature_id"]: row
        for row in report["feature_reports"]
    }
    numeric = by_id["unit.numeric"]
    assert numeric["strata"]["ordinary_5x_lt10x"][
        "distribution"
    ]["median"] == "3.5"
    assert numeric["runner_comparisons"][
        "runner_10x_plus_vs_ordinary_5x_lt10x"
    ]["cliffs_delta_left_vs_ordinary"] == "1"
    assert numeric["runner_comparisons"][
        "runner_20x_plus_vs_ordinary_5x_lt10x"
    ]["cliffs_delta_left_vs_ordinary"] == "1"

    flag = by_id["unit.flag"]
    assert flag["runner_comparisons"][
        "runner_10x_plus_vs_ordinary_5x_lt10x"
    ]["true_rate_difference"] == "0.5"

    assert report["ordinary_5x_vs_10x_plus_compared"] is True
    assert report["ordinary_5x_vs_20x_plus_compared"] is True
    assert report["validation_rows_consumed"] is False
    assert report["final_test_rows_consumed"] is False
    assert report["candidate_features_ranked"] is False
    assert report["signal_promoted"] is False


def test_magnitude_handoff_stays_discovery_only():
    report = build_phase4_magnitude_strata_report(
        discovery_rows(),
        registry(),
        chronological_split_handoff=split_handoff(),
    )
    handoff = build_phase4_magnitude_strata_handoff(
        report,
        report_sha256=SHA,
        chronological_split_handoff_sha256=SHA,
        feature_registry_file_sha256=SHA,
    )

    assert handoff["version"] == PHASE4_MAGNITUDE_STRATA_HANDOFF_VERSION
    assert handoff["validation_rows_consumed"] is False
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["candidate_features_ranked"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
