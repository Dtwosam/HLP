import pytest

from hlp.data.phase4_validation import (
    PHASE4_VALIDATION_HANDOFF_VERSION,
    PHASE4_VALIDATION_REPORT_VERSION,
    build_phase4_validation_handoff,
    build_phase4_validation_report,
)


SHA = "ab" * 32
PLAN_SHA = "cd" * 32
SPLIT_SHA = "12" * 32
VALIDATION_SHA = "34" * 32


def split_handoff():
    return {
        "version": "phase4-chronological-split-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": SHA,
        "validation_split_rows_sha256": VALIDATION_SHA,
        "validation_split_rows": 10,
        "phase4_split_frozen": True,
        "final_test_separated": True,
    }


def frozen_hypothesis():
    return {
        "hypothesis_id": "H-001",
        "feature_id": "unit.numeric",
        "family": "unit",
        "comparison_kind": "numeric",
        "effect_metric": "cliffs_delta_winner_vs_failure",
        "category_value": None,
        "expected_direction": "positive",
        "minimum_absolute_effect": "0.5",
        "discovery_effect": "0.8",
        "rationale": "Strong discovery-only separation.",
        "validation_rule": (
            "same_direction_and_absolute_effect_at_least_threshold"
        ),
    }


def freeze_report():
    return {
        "version": "phase4-hypothesis-freeze-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "hypothesis_plan_sha256": PLAN_SHA,
        "normalized_hypothesis_plan": {
            "version": "phase4-hypothesis-plan-v1",
            "multiple_testing_method": "benjamini_hochberg",
            "false_discovery_rate_alpha": "0.05",
            "permutation_trials": 1000,
            "hypotheses": [frozen_hypothesis()],
        },
    }


def freeze_handoff():
    return {
        "version": "phase4-hypothesis-freeze-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "hypothesis_plan_sha256": PLAN_SHA,
        "validation_hypotheses": 1,
        "multiple_testing_method": "benjamini_hochberg",
        "false_discovery_rate_alpha": "0.05",
        "permutation_trials": 1000,
        "permutation_seed_rule": (
            "sha256(validation_rows_sha256+hypothesis_plan_sha256+"
            "hypothesis_id)"
        ),
        "permutation_test_two_sided": True,
        "validation_hypotheses_frozen": True,
        "multiple_testing_plan_frozen": True,
        "phase4_hypothesis_freeze_ready": True,
        "automatic_feature_ranking_used": False,
        "multiple_testing_control_applied": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def row(index, winner, value):
    return {
        "version": "phase4-discovery-entry-v1",
        "token": "0x" + f"{index:040x}",
        "feature_values": {"unit.numeric": str(value)},
        "missing_feature_ids": [],
        "target_comeback_5x": winner,
        "labels_joined_after_feature_freeze": True,
        "feature_values_mutated": False,
    }


def validation_rows():
    return [
        row(1, True, 10),
        row(2, True, 11),
        row(3, True, 12),
        row(4, True, 13),
        row(5, True, 14),
        row(6, False, 1),
        row(7, False, 2),
        row(8, False, 3),
        row(9, False, 4),
        row(10, False, 5),
    ]


def build():
    return build_phase4_validation_report(
        validation_rows(),
        freeze_report(),
        hypothesis_freeze_handoff=freeze_handoff(),
        chronological_split_handoff=split_handoff(),
        chronological_split_handoff_sha256=SPLIT_SHA,
        validation_rows_sha256=VALIDATION_SHA,
    )


def test_validation_applies_frozen_effect_and_multiple_testing_plan():
    report = build()

    assert report["version"] == PHASE4_VALIDATION_REPORT_VERSION
    assert report["validation_rows"] == 10
    assert report["validation_winner_rows"] == 5
    assert report["validation_failure_rows"] == 5
    assert report["hypotheses_tested"] == 1
    assert report["hypotheses_survived"] == 1
    assert report["surviving_hypothesis_ids"] == ["H-001"]

    result = report["hypothesis_results"][0]
    assert result["validation_effect"] == "1"
    assert result["direction_consistent"] is True
    assert result["effect_threshold_met"] is True
    assert result["fdr_significant"] is True
    assert result["survived_validation"] is True

    assert report["validation_rows_consumed"] is True
    assert report["final_test_rows_consumed"] is False
    assert report["unseen_slice_validation_complete"] is True
    assert report["multiple_testing_control_applied"] is True
    assert report["signal_promoted"] is False
    assert report["phase4_discovery_checkpoint_claimed"] is False


def test_validation_permutation_p_value_is_deterministic():
    first = build()["hypothesis_results"][0]
    second = build()["hypothesis_results"][0]

    assert first["permutation_p_value"] == second["permutation_p_value"]
    assert first["benjamini_hochberg_q_value"] == (
        second["benjamini_hochberg_q_value"]
    )


def test_validation_rejects_wrong_validation_slice_sha():
    with pytest.raises(ValueError, match="validation row SHA drift"):
        build_phase4_validation_report(
            validation_rows(),
            freeze_report(),
            hypothesis_freeze_handoff=freeze_handoff(),
            chronological_split_handoff=split_handoff(),
            chronological_split_handoff_sha256=SPLIT_SHA,
            validation_rows_sha256=SHA,
        )


def test_validation_handoff_never_opens_final_test_or_promotes_signal():
    report = build()
    handoff = build_phase4_validation_handoff(
        report,
        report_sha256=SHA,
        hypothesis_freeze_handoff_sha256=SHA,
        chronological_split_handoff_sha256=SPLIT_SHA,
    )

    assert handoff["version"] == PHASE4_VALIDATION_HANDOFF_VERSION
    assert handoff["validation_rows_consumed"] is True
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["unseen_slice_validation_complete"] is True
    assert handoff["multiple_testing_control_applied"] is True
    assert handoff["signal_promoted"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False
