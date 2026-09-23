import copy

import pytest

from hlp.data.phase4_discovery_checkpoint import (
    PHASE4_DISCOVERY_HANDOFF_VERSION,
    PHASE4_DISCOVERY_LEDGER_VERSION,
    build_phase4_discovery_handoff,
    build_phase4_discovery_ledger,
)


SHA = "ab" * 32
SPLIT_SHA = "11" * 32
BASE_SHA = "22" * 32
UNIVARIATE_SHA = "33" * 32
FREEZE_SHA = "44" * 32
VALIDATION_SHA = "55" * 32
MAGNITUDE_SHA = "56" * 32
NONLINEAR_SHA = "57" * 32
INTERACTION_SHA = "58" * 32
SIMPLE_MODEL_SHA = "59" * 32
STABILITY_SHA = "5a" * 32
PLAN_SHA = "66" * 32
DISCOVERY_ROWS_SHA = "77" * 32
DISCOVERY_SPLIT_SHA = "88" * 32
VALIDATION_ROWS_SHA = "99" * 32


def split_handoff():
    return {
        "version": "phase4-chronological-split-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "feature_registry_file_sha256": SHA,
        "discovery_rows_sha256": DISCOVERY_ROWS_SHA,
        "discovery_subjects": 20,
        "discovery_split_rows_sha256": DISCOVERY_SPLIT_SHA,
        "validation_split_rows_sha256": VALIDATION_ROWS_SHA,
        "discovery_split_rows": 12,
        "validation_split_rows": 6,
        "phase4_split_frozen": True,
        "final_test_separated": True,
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "feature_values_mutated": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def base_handoff():
    return {
        "version": "phase4-base-rate-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_rows_sha256": DISCOVERY_ROWS_SHA,
        "discovery_subjects": 20,
        "comeback_5x_tokens": 5,
        "comeback_5x_base_rate": "0.25",
        "winner_failure_frequencies_reported": True,
        "continuous_outcome_distribution_reported": True,
        "feature_relationships_tested": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def univariate_handoff():
    return {
        "version": "phase4-univariate-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "source_discovery_rows_sha256": DISCOVERY_ROWS_SHA,
        "discovery_split_rows_sha256": DISCOVERY_SPLIT_SHA,
        "source_discovery_subjects": 20,
        "analysis_subjects": 12,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "base_rate_handoff_sha256": BASE_SHA,
        "winner_failure_frequencies_reported": True,
        "missingness_compared_by_outcome": True,
        "univariate_relationships_tested": True,
        "phase4_univariate_report_ready": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "unseen_slice_validation_complete": False,
        "multiple_testing_control_applied": False,
        "phase4_discovery_checkpoint_claimed": False,
    }


def freeze_handoff():
    return {
        "version": "phase4-hypothesis-freeze-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "univariate_handoff_sha256": UNIVARIATE_SHA,
        "hypothesis_plan_sha256": PLAN_SHA,
        "features_considered": 3,
        "validation_hypotheses": 2,
        "selection_manual": True,
        "automatic_feature_ranking_used": False,
        "all_feature_dispositions_logged": True,
        "validation_hypotheses_frozen": True,
        "multiple_testing_plan_frozen": True,
        "multiple_testing_control_applied": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_hypothesis_freeze_ready": True,
    }


def validation_handoff():
    return {
        "version": "phase4-validation-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "validation_rows_sha256": VALIDATION_ROWS_SHA,
        "hypothesis_plan_sha256": PLAN_SHA,
        "hypothesis_freeze_handoff_sha256": FREEZE_SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "validation_rows": 6,
        "validation_winner_rows": 2,
        "validation_failure_rows": 4,
        "hypotheses_tested": 2,
        "hypotheses_survived": 1,
        "surviving_hypothesis_ids": ["H-001"],
        "all_frozen_hypotheses_tested": True,
        "validation_rows_consumed": True,
        "final_test_rows_consumed": False,
        "unseen_slice_validation_complete": True,
        "multiple_testing_control_applied": True,
        "automatic_feature_ranking_used": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_validation_report_ready": True,
    }


def magnitude_handoff():
    return {
        "version": "phase4-magnitude-strata-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "feature_registry_file_sha256": SHA,
        "discovery_split_rows_sha256": DISCOVERY_SPLIT_SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "analysis_subjects": 12,
        "features_analyzed": 3,
        "families_analyzed": 1,
        "ordinary_5x_vs_10x_plus_compared": True,
        "ordinary_5x_vs_20x_plus_compared": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_magnitude_strata_report_ready": True,
    }


def nonlinear_handoff():
    return {
        "version": "phase4-nonlinear-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "feature_registry_file_sha256": SHA,
        "discovery_split_rows_sha256": DISCOVERY_SPLIT_SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "analysis_subjects": 12,
        "numeric_features_analyzed": 2,
        "non_numeric_features_excluded": 1,
        "nonlinear_relationships_examined": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_thresholds_promoted": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_nonlinear_report_ready": True,
    }


def interaction_handoff():
    return {
        "version": "phase4-interaction-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "feature_registry_file_sha256": SHA,
        "discovery_split_rows_sha256": DISCOVERY_SPLIT_SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "analysis_subjects": 12,
        "eligible_features": 2,
        "excluded_feature_count": 1,
        "pair_count": 1,
        "same_family_pairs": 0,
        "cross_family_pairs": 1,
        "effect_available_pairs": 1,
        "pairwise_interactions_examined": True,
        "interaction_pairs_ranked": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_interaction_report_ready": True,
    }


def simple_model_handoff():
    return {
        "version": "phase4-simple-model-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "feature_registry_file_sha256": SHA,
        "discovery_split_rows_sha256": DISCOVERY_SPLIT_SHA,
        "validation_rows_sha256": VALIDATION_ROWS_SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "discovery_rows": 12,
        "validation_rows": 6,
        "eligible_features": 2,
        "excluded_feature_count": 1,
        "predictor_count": 4,
        "preprocessing_fit_on_discovery_only": True,
        "models_fit_on_discovery_only": True,
        "validation_rows_consumed": True,
        "final_test_rows_consumed": False,
        "transparent_simple_models_examined": True,
        "automatic_model_feature_selection_used": True,
        "production_model_selected": False,
        "signal_threshold_selected": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_simple_model_report_ready": True,
    }


def stability_handoff():
    return {
        "version": "phase4-stability-handoff-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "feature_registry_sha256": SHA,
        "discovery_split_rows_sha256": DISCOVERY_SPLIT_SHA,
        "hypothesis_plan_sha256": PLAN_SHA,
        "hypothesis_freeze_handoff_sha256": FREEZE_SHA,
        "chronological_split_handoff_sha256": SPLIT_SHA,
        "analysis_subjects": 12,
        "hypotheses_examined": 2,
        "resamples_per_hypothesis": 32,
        "sample_fraction": "0.8",
        "chronological_fold_count": 4,
        "repeated_sampling_stability_examined": True,
        "chronological_stability_examined": True,
        "stability_pass_fail_threshold_applied": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_stability_report_ready": True,
    }


def frozen_hypothesis(hypothesis_id, feature_id):
    return {
        "hypothesis_id": hypothesis_id,
        "feature_id": feature_id,
        "family": "unit",
        "comparison_kind": "numeric",
        "effect_metric": "cliffs_delta_winner_vs_failure",
        "category_value": None,
        "expected_direction": "positive",
        "minimum_absolute_effect": "0.3",
        "discovery_effect": "0.6",
        "rationale": "Unit hypothesis.",
        "validation_rule": (
            "same_direction_and_absolute_effect_at_least_threshold"
        ),
    }


def freeze_report():
    hypotheses = [
        frozen_hypothesis("H-001", "unit.a"),
        frozen_hypothesis("H-002", "unit.b"),
    ]
    return {
        "version": "phase4-hypothesis-freeze-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "hypothesis_plan_sha256": PLAN_SHA,
        "normalized_hypothesis_plan": {
            "version": "phase4-hypothesis-plan-v1",
            "hypotheses": hypotheses,
        },
        "feature_dispositions": [
            {
                "feature_id": "unit.a",
                "disposition": "selected_for_validation",
            },
            {
                "feature_id": "unit.b",
                "disposition": "selected_for_validation",
            },
            {
                "feature_id": "unit.c",
                "disposition": "not_selected_for_validation",
            },
        ],
    }


def result(
    hypothesis_id,
    feature_id,
    *,
    survived,
    direction=True,
    threshold=True,
    significant=True,
):
    return {
        "hypothesis_id": hypothesis_id,
        "feature_id": feature_id,
        "effect_metric": "cliffs_delta_winner_vs_failure",
        "category_value": None,
        "expected_direction": "positive",
        "validation_effect": "0.5",
        "permutation_p_value": "0.01",
        "benjamini_hochberg_q_value": "0.02",
        "direction_consistent": direction,
        "effect_threshold_met": threshold,
        "fdr_significant": significant,
        "survived_validation": survived,
    }


def validation_report():
    return {
        "version": "phase4-validation-report-v1",
        "phase4_checkpoint_name": "hlp-v1-phase4-discovery",
        "hypothesis_plan_sha256": PLAN_SHA,
        "hypotheses_tested": 2,
        "hypotheses_survived": 1,
        "hypothesis_results": [
            result("H-001", "unit.a", survived=True),
            result(
                "H-002",
                "unit.b",
                survived=False,
                threshold=False,
                significant=False,
            ),
        ],
    }


def build(
    *,
    freeze_report_value=None,
    validation_report_value=None,
    validation_handoff_value=None,
):
    return build_phase4_discovery_ledger(
        freeze_report()
        if freeze_report_value is None
        else freeze_report_value,
        validation_report()
        if validation_report_value is None
        else validation_report_value,
        chronological_split_handoff=split_handoff(),
        chronological_split_handoff_sha256=SPLIT_SHA,
        base_rate_handoff=base_handoff(),
        base_rate_handoff_sha256=BASE_SHA,
        univariate_handoff=univariate_handoff(),
        univariate_handoff_sha256=UNIVARIATE_SHA,
        hypothesis_freeze_handoff=freeze_handoff(),
        hypothesis_freeze_handoff_sha256=FREEZE_SHA,
        validation_handoff=(
            validation_handoff()
            if validation_handoff_value is None
            else validation_handoff_value
        ),
        magnitude_strata_handoff=magnitude_handoff(),
        magnitude_strata_handoff_sha256=MAGNITUDE_SHA,
        nonlinear_handoff=nonlinear_handoff(),
        nonlinear_handoff_sha256=NONLINEAR_SHA,
        interaction_handoff=interaction_handoff(),
        interaction_handoff_sha256=INTERACTION_SHA,
        simple_model_handoff=simple_model_handoff(),
        simple_model_handoff_sha256=SIMPLE_MODEL_SHA,
        stability_handoff=stability_handoff(),
        stability_handoff_sha256=STABILITY_SHA,
    )


def test_discovery_ledger_logs_validated_rejected_and_unselected():
    ledger = build()

    assert ledger["version"] == PHASE4_DISCOVERY_LEDGER_VERSION
    assert ledger["hypotheses_tested"] == 2
    assert ledger["hypotheses_validated"] == 1
    assert ledger["hypotheses_rejected"] == 1
    assert ledger["validated_hypothesis_ids"] == ["H-001"]
    assert ledger["rejected_hypothesis_ids"] == ["H-002"]

    by_hypothesis = {
        row["hypothesis_id"]: row
        for row in ledger["hypothesis_ledger"]
    }
    assert by_hypothesis["H-001"]["final_disposition"] == (
        "validated_relationship"
    )
    assert by_hypothesis["H-001"]["rejection_reasons"] == []
    assert by_hypothesis["H-002"]["final_disposition"] == (
        "rejected_unseen_validation"
    )
    assert by_hypothesis["H-002"]["rejection_reasons"] == [
        "minimum_effect_not_reproduced",
        "fdr_not_significant",
    ]

    by_feature = {
        row["feature_id"]: row
        for row in ledger["feature_ledger"]
    }
    assert by_feature["unit.a"]["final_disposition"] == (
        "has_validated_relationship"
    )
    assert by_feature["unit.b"]["final_disposition"] == (
        "selected_but_rejected_in_validation"
    )
    assert by_feature["unit.c"]["final_disposition"] == (
        "not_selected_for_validation"
    )
    assert ledger["all_hypothesis_dispositions_logged"] is True
    assert ledger["rejected_hypotheses_logged"] is True
    assert ledger["magnitude_strata_examined"] is True
    assert ledger["nonlinear_relationships_examined"] is True
    assert ledger["pairwise_interactions_examined"] is True
    assert ledger["transparent_simple_models_examined"] is True
    assert ledger["repeated_sampling_stability_examined"] is True
    assert ledger["chronological_stability_examined"] is True
    assert ledger["sequence_analysis_performed"] is False
    assert ledger["cluster_analysis_performed"] is False
    assert ledger["final_test_rows_consumed"] is False
    assert ledger["signal_promoted"] is False
    assert ledger["phase4_discovery_checkpoint_claimed"] is True


def test_discovery_checkpoint_can_close_with_zero_survivors():
    report = validation_report()
    report["hypotheses_survived"] = 0
    report["hypothesis_results"] = [
        result(
            "H-001",
            "unit.a",
            survived=False,
            direction=False,
        ),
        result(
            "H-002",
            "unit.b",
            survived=False,
            significant=False,
        ),
    ]
    handoff = validation_handoff()
    handoff["hypotheses_survived"] = 0
    handoff["surviving_hypothesis_ids"] = []

    ledger = build(
        validation_report_value=report,
        validation_handoff_value=handoff,
    )

    assert ledger["hypotheses_validated"] == 0
    assert ledger["hypotheses_rejected"] == 2
    assert ledger["validated_relationships_present"] is False
    assert ledger["phase4_discovery_checkpoint_claimed"] is True


def test_discovery_ledger_rejects_missing_validation_result():
    report = validation_report()
    report["hypothesis_results"] = report["hypothesis_results"][:1]

    with pytest.raises(ValueError, match="membership drift"):
        build(validation_report_value=report)


def test_discovery_ledger_rejects_final_test_consumption():
    handoff = validation_handoff()
    handoff["final_test_rows_consumed"] = True

    with pytest.raises(ValueError, match="final_test_rows_consumed"):
        build(validation_handoff_value=handoff)


def test_discovery_handoff_claims_phase4_but_not_a_signal():
    ledger = build()
    handoff = build_phase4_discovery_handoff(
        ledger,
        ledger_sha256=SHA,
        chronological_split_handoff_sha256=SPLIT_SHA,
        base_rate_handoff_sha256=BASE_SHA,
        univariate_handoff_sha256=UNIVARIATE_SHA,
        hypothesis_freeze_handoff_sha256=FREEZE_SHA,
        validation_handoff_sha256=VALIDATION_SHA,
        magnitude_strata_handoff_sha256=MAGNITUDE_SHA,
        nonlinear_handoff_sha256=NONLINEAR_SHA,
        interaction_handoff_sha256=INTERACTION_SHA,
        simple_model_handoff_sha256=SIMPLE_MODEL_SHA,
        stability_handoff_sha256=STABILITY_SHA,
    )

    assert handoff["version"] == PHASE4_DISCOVERY_HANDOFF_VERSION
    assert handoff["checkpoint_name"] == "hlp-v1-phase4-discovery"
    assert handoff["rejected_hypotheses_logged"] is True
    assert handoff["magnitude_strata_examined"] is True
    assert handoff["nonlinear_relationships_examined"] is True
    assert handoff["pairwise_interactions_examined"] is True
    assert handoff["transparent_simple_models_examined"] is True
    assert handoff["repeated_sampling_stability_examined"] is True
    assert handoff["sequence_analysis_performed"] is False
    assert handoff["cluster_analysis_performed"] is False
    assert handoff["final_test_rows_consumed"] is False
    assert handoff["signal_promoted"] is False
    assert handoff["phase5_model_started"] is False
    assert handoff["phase4_discovery_checkpoint_claimed"] is True



def test_discovery_ledger_rejects_base_rate_population_drift():
    base = base_handoff()
    base["discovery_rows_sha256"] = SHA

    with pytest.raises(ValueError, match="base-rate population drift"):
        build_phase4_discovery_ledger(
            freeze_report(),
            validation_report(),
            chronological_split_handoff=split_handoff(),
            chronological_split_handoff_sha256=SPLIT_SHA,
            base_rate_handoff=base,
            base_rate_handoff_sha256=BASE_SHA,
            univariate_handoff=univariate_handoff(),
            univariate_handoff_sha256=UNIVARIATE_SHA,
            hypothesis_freeze_handoff=freeze_handoff(),
            hypothesis_freeze_handoff_sha256=FREEZE_SHA,
            validation_handoff=validation_handoff(),
            magnitude_strata_handoff=magnitude_handoff(),
            magnitude_strata_handoff_sha256=MAGNITUDE_SHA,
            nonlinear_handoff=nonlinear_handoff(),
            nonlinear_handoff_sha256=NONLINEAR_SHA,
            interaction_handoff=interaction_handoff(),
            interaction_handoff_sha256=INTERACTION_SHA,
            simple_model_handoff=simple_model_handoff(),
            simple_model_handoff_sha256=SIMPLE_MODEL_SHA,
            stability_handoff=stability_handoff(),
            stability_handoff_sha256=STABILITY_SHA,
        )



def test_discovery_ledger_rejects_experiment_suite_population_drift():
    magnitude = magnitude_handoff()
    magnitude["analysis_subjects"] = 11

    with pytest.raises(ValueError, match="magnitude-strata subject-count drift"):
        build_phase4_discovery_ledger(
            freeze_report(),
            validation_report(),
            chronological_split_handoff=split_handoff(),
            chronological_split_handoff_sha256=SPLIT_SHA,
            base_rate_handoff=base_handoff(),
            base_rate_handoff_sha256=BASE_SHA,
            univariate_handoff=univariate_handoff(),
            univariate_handoff_sha256=UNIVARIATE_SHA,
            hypothesis_freeze_handoff=freeze_handoff(),
            hypothesis_freeze_handoff_sha256=FREEZE_SHA,
            validation_handoff=validation_handoff(),
            magnitude_strata_handoff=magnitude,
            magnitude_strata_handoff_sha256=MAGNITUDE_SHA,
            nonlinear_handoff=nonlinear_handoff(),
            nonlinear_handoff_sha256=NONLINEAR_SHA,
            interaction_handoff=interaction_handoff(),
            interaction_handoff_sha256=INTERACTION_SHA,
            simple_model_handoff=simple_model_handoff(),
            simple_model_handoff_sha256=SIMPLE_MODEL_SHA,
            stability_handoff=stability_handoff(),
            stability_handoff_sha256=STABILITY_SHA,
        )
