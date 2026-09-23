import pytest

from hlp.data.phase4_hypothesis_freeze import (
    PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION,
    PHASE4_HYPOTHESIS_FREEZE_VERSION,
    build_phase4_hypothesis_freeze,
    build_phase4_hypothesis_freeze_handoff,
)


SHA = "ab" * 32
SPLIT_SHA = "12" * 32


def split_handoff():
    return {
        "version": "phase4-chronological-split-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": SHA,
        "discovery_rows_sha256": SHA,
        "phase4_split_frozen": True,
        "final_test_separated": True,
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "feature_values_mutated": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def univariate_handoff():
    return {
        "version": "phase4-univariate-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": SHA,
        "univariate_report_sha256": SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "features_tested": 3,
        "phase4_univariate_report_ready": True,
        "univariate_relationships_tested": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "unseen_slice_validation_complete": False,
        "multiple_testing_control_applied": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def univariate_report():
    return {
        "version": "phase4-univariate-report-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": SHA,
        "feature_reports": [
            {
                "feature_id": "unit.numeric",
                "family": "unit",
                "comparison_kind": "numeric",
                "cliffs_delta_winner_vs_failure": "0.6",
                "mean_difference_winner_minus_failure": "4",
                "median_difference_winner_minus_failure": "3",
                "missing_rate_difference_winner_minus_failure": "0",
            },
            {
                "feature_id": "unit.flag",
                "family": "unit",
                "comparison_kind": "boolean",
                "true_rate_difference_winner_minus_failure": "-0.25",
                "missing_rate_difference_winner_minus_failure": "0",
            },
            {
                "feature_id": "unit.category",
                "family": "unit",
                "comparison_kind": "categorical",
                "missing_rate_difference_winner_minus_failure": "0",
                "categories": [
                    {
                        "value": "alpha",
                        "winner_rate_among_observed": "0.75",
                        "failure_rate_among_observed": "0.25",
                    },
                    {
                        "value": "beta",
                        "winner_rate_among_observed": "0.25",
                        "failure_rate_among_observed": "0.75",
                    },
                ],
            },
        ],
    }


def plan():
    return {
        "version": "phase4-hypothesis-plan-v1",
        "multiple_testing_method": "benjamini_hochberg",
        "false_discovery_rate_alpha": "0.05",
        "permutation_trials": 2000,
        "hypotheses": [
            {
                "hypothesis_id": "H-001",
                "feature_id": "unit.numeric",
                "effect_metric": "cliffs_delta_winner_vs_failure",
                "expected_direction": "positive",
                "minimum_absolute_effect": "0.3",
                "rationale": "Numeric separation is worth unseen validation.",
            },
            {
                "hypothesis_id": "H-002",
                "feature_id": "unit.category",
                "effect_metric": (
                    "category_rate_difference_winner_minus_failure"
                ),
                "category_value": "alpha",
                "expected_direction": "positive",
                "minimum_absolute_effect": "0.2",
                "rationale": "Category alpha differs in discovery.",
            },
        ],
    }


def test_hypothesis_freeze_is_manual_and_logs_unselected_features():
    report = build_phase4_hypothesis_freeze(
        univariate_report(),
        univariate_handoff=univariate_handoff(),
        chronological_split_handoff=split_handoff(),
        chronological_split_handoff_sha256=SPLIT_SHA,
        hypothesis_plan=plan(),
    )

    assert report["version"] == PHASE4_HYPOTHESIS_FREEZE_VERSION
    assert report["features_considered"] == 3
    assert report["selected_features"] == 2
    assert report["validation_hypotheses"] == 2
    assert report["selection_manual"] is True
    assert report["automatic_feature_ranking_used"] is False
    assert report["validation_rows_consumed"] is False
    assert report["final_test_rows_consumed"] is False
    assert report["permutation_trials"] == 2000
    assert report["permutation_test_two_sided"] is True
    assert report["multiple_testing_plan_frozen"] is True
    assert report["multiple_testing_control_applied"] is False

    frozen = {
        row["hypothesis_id"]: row
        for row in report["normalized_hypothesis_plan"]["hypotheses"]
    }
    assert frozen["H-001"]["discovery_effect"] == "0.6"
    assert frozen["H-002"]["discovery_effect"] == "0.5"

    dispositions = {
        row["feature_id"]: row["disposition"]
        for row in report["feature_dispositions"]
    }
    assert dispositions["unit.numeric"] == "selected_for_validation"
    assert dispositions["unit.category"] == "selected_for_validation"
    assert dispositions["unit.flag"] == "not_selected_for_validation"


def test_hypothesis_freeze_rejects_unknown_feature():
    bad = plan()
    bad["hypotheses"][0]["feature_id"] = "unit.unknown"

    with pytest.raises(ValueError, match="unknown feature"):
        build_phase4_hypothesis_freeze(
            univariate_report(),
            univariate_handoff=univariate_handoff(),
            chronological_split_handoff=split_handoff(),
            chronological_split_handoff_sha256=SPLIT_SHA,
            hypothesis_plan=bad,
        )


def test_hypothesis_freeze_rejects_invalid_metric_for_dtype():
    bad = plan()
    bad["hypotheses"][0]["effect_metric"] = (
        "true_rate_difference_winner_minus_failure"
    )

    with pytest.raises(ValueError, match="invalid for numeric"):
        build_phase4_hypothesis_freeze(
            univariate_report(),
            univariate_handoff=univariate_handoff(),
            chronological_split_handoff=split_handoff(),
            chronological_split_handoff_sha256=SPLIT_SHA,
            hypothesis_plan=bad,
        )


def test_hypothesis_freeze_rejects_opened_validation_rows():
    handoff = univariate_handoff()
    handoff["validation_rows_consumed"] = True

    with pytest.raises(ValueError, match="validation_rows_consumed"):
        build_phase4_hypothesis_freeze(
            univariate_report(),
            univariate_handoff=handoff,
            chronological_split_handoff=split_handoff(),
            chronological_split_handoff_sha256=SPLIT_SHA,
            hypothesis_plan=plan(),
        )


def test_hypothesis_freeze_handoff_never_claims_discovery():
    report = build_phase4_hypothesis_freeze(
        univariate_report(),
        univariate_handoff=univariate_handoff(),
        chronological_split_handoff=split_handoff(),
        chronological_split_handoff_sha256=SPLIT_SHA,
        hypothesis_plan=plan(),
    )
    handoff = build_phase4_hypothesis_freeze_handoff(
        report,
        report_sha256=SHA,
        univariate_handoff_sha256=SHA,
    )

    assert (
        handoff["version"]
        == PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION
    )
    assert handoff["selection_manual"] is True
    assert handoff["automatic_feature_ranking_used"] is False
    assert handoff["validation_rows_consumed"] is False
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["permutation_trials"] == 2000
    assert handoff["permutation_test_two_sided"] is True
    assert handoff["multiple_testing_plan_frozen"] is True
    assert handoff["multiple_testing_control_applied"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is False



def test_hypothesis_freeze_rejects_unfrozen_permutation_budget():
    bad = plan()
    bad["permutation_trials"] = 99

    with pytest.raises(ValueError, match="permutation trials"):
        build_phase4_hypothesis_freeze(
            univariate_report(),
            univariate_handoff=univariate_handoff(),
            chronological_split_handoff=split_handoff(),
            chronological_split_handoff_sha256=SPLIT_SHA,
            hypothesis_plan=bad,
        )
