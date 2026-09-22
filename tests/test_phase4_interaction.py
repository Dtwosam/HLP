from hlp.data.phase3_feature_entry import PHASE3_FEATURE_SNAPSHOT_KIND
from hlp.data.phase3_feature_registry import (
    PHASE3_FEATURE_REGISTRY_VERSION,
    validate_phase3_feature_registry,
)
from hlp.data.phase4_interaction import (
    PHASE4_INTERACTION_HANDOFF_VERSION,
    PHASE4_INTERACTION_REPORT_VERSION,
    build_phase4_interaction_handoff,
    build_phase4_interaction_report,
)


SHA = "ab" * 32


def definition(feature_id, dtype, family="unit"):
    return {
        "registry_version": PHASE3_FEATURE_REGISTRY_VERSION,
        "feature_id": feature_id,
        "family": family,
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
        definition("unit.a", "boolean", "a"),
        definition("unit.b", "boolean", "b"),
        definition("unit.category", "string", "c"),
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


def row(index, a, b, winner):
    values = {
        "unit.a": a,
        "unit.b": b,
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


def rows():
    return [
        row(1, False, False, False),
        row(2, False, False, False),
        row(3, False, True, False),
        row(4, False, True, False),
        row(5, True, False, False),
        row(6, True, False, False),
        row(7, True, True, True),
        row(8, True, True, True),
    ]


def test_interaction_report_measures_difference_in_differences():
    report = build_phase4_interaction_report(
        rows(),
        registry(),
        chronological_split_handoff=split_handoff(),
    )

    assert report["version"] == PHASE4_INTERACTION_REPORT_VERSION
    assert report["eligible_features"] == 2
    assert report["excluded_feature_count"] == 1
    assert report["pair_count"] == 1
    pair = report["pair_reports"][0]
    assert pair["cells"]["00"]["winner_rate"] == "0"
    assert pair["cells"]["01"]["winner_rate"] == "0"
    assert pair["cells"]["10"]["winner_rate"] == "0"
    assert pair["cells"]["11"]["winner_rate"] == "1"
    assert pair[
        "interaction_contrast_difference_in_differences"
    ] == "1"
    assert pair["interaction_effect_available"] is True
    assert report["pairwise_interactions_examined"] is True
    assert report["interaction_pairs_ranked"] is False
    assert report["validation_rows_consumed"] is False
    assert report["final_test_rows_consumed"] is False


def test_interaction_handoff_never_promotes_pairs():
    report = build_phase4_interaction_report(
        rows(),
        registry(),
        chronological_split_handoff=split_handoff(),
    )
    handoff = build_phase4_interaction_handoff(
        report,
        report_sha256=SHA,
        chronological_split_handoff_sha256=SHA,
        feature_registry_file_sha256=SHA,
    )

    assert handoff["version"] == PHASE4_INTERACTION_HANDOFF_VERSION
    assert handoff["pairwise_interactions_examined"] is True
    assert handoff["interaction_pairs_ranked"] is False
    assert handoff["validation_rows_consumed"] is False
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
