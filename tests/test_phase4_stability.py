from hlp.data.phase4_stability import (
    PHASE4_STABILITY_HANDOFF_VERSION,
    PHASE4_STABILITY_REPORT_VERSION,
    build_phase4_stability_handoff,
    build_phase4_stability_report,
)


SHA = "ab" * 32
SPLIT_SHA = "12" * 32
PLAN_SHA = "34" * 32


def split_handoff():
    return {
        "version": "phase4-chronological-split-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": SHA,
        "discovery_split_rows": 12,
        "phase4_split_frozen": True,
        "final_test_separated": True,
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "feature_values_mutated": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def freeze_handoff():
    return {
        "version": "phase4-hypothesis-freeze-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "hypothesis_plan_sha256": PLAN_SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "validation_hypotheses": 1,
        "validation_hypotheses_frozen": True,
        "multiple_testing_plan_frozen": True,
        "phase4_hypothesis_freeze_ready": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def freeze_report():
    return {
        "version": "phase4-hypothesis-freeze-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "hypothesis_plan_sha256": PLAN_SHA,
        "normalized_hypothesis_plan": {
            "version": "phase4-hypothesis-plan-v1",
            "hypotheses": [
                {
                    "hypothesis_id": "H-001",
                    "feature_id": "unit.numeric",
                    "family": "unit",
                    "comparison_kind": "numeric",
                    "effect_metric": (
                        "cliffs_delta_winner_vs_failure"
                    ),
                    "category_value": None,
                    "expected_direction": "positive",
                    "minimum_absolute_effect": "0.3",
                    "discovery_effect": "1",
                    "rationale": "Unit test.",
                    "validation_rule": (
                        "same_direction_and_absolute_effect_at_least_threshold"
                    ),
                }
            ],
        },
    }


def row(index, value, winner):
    return {
        "version": "phase4-discovery-entry-v1",
        "token": "0x" + f"{index:040x}",
        "feature_cutoff_block": 100 + index,
        "feature_cutoff_transaction_index": 0,
        "feature_cutoff_log_index": 0,
        "feature_values": {"unit.numeric": str(value)},
        "missing_feature_ids": [],
        "target_comeback_5x": winner,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
    }


def rows():
    return [
        row(1, 1, False),
        row(2, 2, False),
        row(3, 3, False),
        row(4, 4, False),
        row(5, 5, False),
        row(6, 6, False),
        row(7, 10, True),
        row(8, 11, True),
        row(9, 12, True),
        row(10, 13, True),
        row(11, 14, True),
        row(12, 15, True),
    ]


def build():
    return build_phase4_stability_report(
        rows(),
        freeze_report(),
        hypothesis_freeze_handoff=freeze_handoff(),
        chronological_split_handoff=split_handoff(),
        chronological_split_handoff_sha256=SPLIT_SHA,
        discovery_rows_sha256=SHA,
        resamples=8,
        chronological_folds=3,
    )


def test_stability_is_deterministic_and_discovery_only():
    first = build()
    second = build()

    assert first == second
    assert first["version"] == PHASE4_STABILITY_REPORT_VERSION
    assert first["analysis_subjects"] == 12
    assert first["hypotheses_examined"] == 1
    assert first["resamples_per_hypothesis"] == 8
    assert first["chronological_fold_count"] == 3

    hypothesis = first["hypothesis_reports"][0]
    assert hypothesis["full_discovery_measurement"]["effect"] == "1"
    assert hypothesis["resample_available_count"] == 8
    assert hypothesis["resample_direction_consistency_rate"] == "1"
    assert hypothesis["resample_minimum_effect_rate"] == "1"
    assert hypothesis["stability_pass_fail_threshold_applied"] is False

    assert first["repeated_sampling_stability_examined"] is True
    assert first["chronological_stability_examined"] is True
    assert first["validation_rows_consumed"] is False
    assert first["final_test_rows_consumed"] is False
    assert first["signal_promoted"] is False


def test_stability_handoff_never_promotes_a_hypothesis():
    report = build()
    handoff = build_phase4_stability_handoff(
        report,
        report_sha256=SHA,
        hypothesis_freeze_handoff_sha256=SHA,
        chronological_split_handoff_sha256=SPLIT_SHA,
    )

    assert handoff["version"] == PHASE4_STABILITY_HANDOFF_VERSION
    assert handoff["repeated_sampling_stability_examined"] is True
    assert handoff["chronological_stability_examined"] is True
    assert handoff["stability_pass_fail_threshold_applied"] is False
    assert handoff["validation_rows_consumed"] is False
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
