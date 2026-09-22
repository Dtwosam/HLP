from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND
from hlp.data.phase3_feature_registry import (
    PHASE3_FEATURE_REGISTRY_VERSION,
    validate_phase3_feature_registry,
)
from hlp.data.phase4_nonlinear import (
    PHASE4_NONLINEAR_HANDOFF_VERSION,
    PHASE4_NONLINEAR_REPORT_VERSION,
    build_phase4_nonlinear_handoff,
    build_phase4_nonlinear_report,
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
    ]


def split_handoff():
    registry_report = validate_phase3_feature_registry(registry())
    return {
        "version": "phase4-chronological-split-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": registry_report["registry_sha256"],
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


def row(index, value, winner):
    values = {
        "unit.numeric": str(value),
        "unit.flag": bool(index % 2),
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


def test_nonlinear_report_detects_non_monotonic_quartile_shape():
    rows = [
        row(1, 1, True),
        row(2, 2, True),
        row(3, 3, False),
        row(4, 4, False),
        row(5, 5, False),
        row(6, 6, False),
        row(7, 7, True),
        row(8, 8, True),
    ]
    report = build_phase4_nonlinear_report(
        rows,
        registry(),
        chronological_split_handoff=split_handoff(),
    )

    assert report["version"] == PHASE4_NONLINEAR_REPORT_VERSION
    assert report["winner_base_rate"] == "0.5"
    assert report["numeric_features_analyzed"] == 1
    assert report["non_numeric_features_excluded"] == 1
    feature = report["feature_reports"][0]
    assert feature["cut_points"] == ["2", "4", "6"]
    assert [bucket["winner_rate"] for bucket in feature["bins"]] == [
        "1",
        "0",
        "0",
        "1",
    ]
    assert feature["shape"] == "non_monotonic"
    assert report["shape_counts"]["non_monotonic"] == 1
    assert report["candidate_thresholds_promoted"] is False
    assert report["validation_rows_consumed"] is False
    assert report["final_test_rows_consumed"] is False


def test_nonlinear_handoff_never_promotes_thresholds():
    rows = [
        row(1, 1, False),
        row(2, 2, False),
        row(3, 3, False),
        row(4, 4, False),
        row(5, 5, True),
        row(6, 6, True),
        row(7, 7, True),
        row(8, 8, True),
    ]
    report = build_phase4_nonlinear_report(
        rows,
        registry(),
        chronological_split_handoff=split_handoff(),
    )
    handoff = build_phase4_nonlinear_handoff(
        report,
        report_sha256=SHA,
        chronological_split_handoff_sha256=SHA,
        feature_registry_file_sha256=SHA,
    )

    assert handoff["version"] == PHASE4_NONLINEAR_HANDOFF_VERSION
    assert handoff["nonlinear_relationships_examined"] is True
    assert handoff["candidate_thresholds_promoted"] is False
    assert handoff["validation_rows_consumed"] is False
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
