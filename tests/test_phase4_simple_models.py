from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND
from hlp.data.phase3_feature_registry import (
    PHASE3_FEATURE_REGISTRY_VERSION,
    validate_phase3_feature_registry,
)
from hlp.data.phase4_simple_models import (
    PHASE4_SIMPLE_MODEL_HANDOFF_VERSION,
    PHASE4_SIMPLE_MODEL_REPORT_VERSION,
    build_phase4_simple_model_handoff,
    build_phase4_simple_model_report,
)


SHA = "ab" * 32
VALIDATION_SHA = "cd" * 32


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
        "validation_split_rows_sha256": VALIDATION_SHA,
        "discovery_split_rows": 8,
        "validation_split_rows": 4,
        "phase4_split_frozen": True,
        "final_test_separated": True,
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "feature_values_mutated": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def row(index, numeric, flag, winner):
    values = {
        "unit.numeric": str(numeric),
        "unit.flag": flag,
        "unit.category": "x",
    }
    return {
        "version": "phase4-discovery-entry-v1",
        "token": "0x" + f"{index:040x}",
        "target_comeback_5x": winner,
        "feature_values": values,
        "missing_feature_ids": [],
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
    }


def discovery_rows():
    return [
        row(1, 1, False, False),
        row(2, 2, False, False),
        row(3, 3, True, False),
        row(4, 4, True, False),
        row(5, 5, False, False),
        row(6, 6, True, True),
        row(7, 7, True, True),
        row(8, 8, True, True),
    ]


def validation_rows():
    return [
        row(11, 100, False, False),
        row(12, 101, True, True),
        row(13, 102, False, False),
        row(14, 103, True, True),
    ]


def test_simple_models_fit_preprocessing_only_on_discovery():
    report = build_phase4_simple_model_report(
        discovery_rows(),
        validation_rows(),
        registry(),
        chronological_split_handoff=split_handoff(),
        discovery_rows_sha256=SHA,
        validation_rows_sha256=VALIDATION_SHA,
    )

    assert report["version"] == PHASE4_SIMPLE_MODEL_REPORT_VERSION
    assert report["discovery_rows"] == 8
    assert report["validation_rows"] == 4
    assert report["eligible_features"] == 2
    assert report["excluded_feature_count"] == 1
    assert report["predictor_count"] == 4

    rules = {
        row["feature_id"]: row
        for row in report["preprocessing_rules"]
    }
    assert rules["unit.numeric"]["threshold"] == "4.5"
    assert rules["unit.numeric"]["active_rule"] == (
        "value_greater_than_or_equal_to_discovery_median"
    )
    assert report["preprocessing_fit_on_discovery_only"] is True
    assert report["models_fit_on_discovery_only"] is True
    assert report["validation_rows_consumed"] is True
    assert report["final_test_rows_consumed"] is False

    for key in (
        "logistic_validation_metrics",
        "tree_validation_metrics",
    ):
        metrics = report[key]
        assert metrics["rows"] == 4
        assert 0 <= float(metrics["brier_score"]) <= 1
        assert 0 <= float(metrics["average_precision"]) <= 1
        assert 0 <= float(metrics["roc_auc"]) <= 1

    assert report["production_model_selected"] is False
    assert report["signal_threshold_selected"] is False
    assert report["signal_promoted"] is False


def test_simple_model_handoff_never_selects_production_model():
    report = build_phase4_simple_model_report(
        discovery_rows(),
        validation_rows(),
        registry(),
        chronological_split_handoff=split_handoff(),
        discovery_rows_sha256=SHA,
        validation_rows_sha256=VALIDATION_SHA,
    )
    handoff = build_phase4_simple_model_handoff(
        report,
        report_sha256=SHA,
        chronological_split_handoff_sha256=SHA,
        feature_registry_file_sha256=SHA,
    )

    assert handoff["version"] == PHASE4_SIMPLE_MODEL_HANDOFF_VERSION
    assert handoff["validation_rows_consumed"] is True
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["transparent_simple_models_examined"] is True
    assert handoff["automatic_model_feature_selection_used"] is True
    assert handoff["production_model_selected"] is False
    assert handoff["signal_threshold_selected"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
