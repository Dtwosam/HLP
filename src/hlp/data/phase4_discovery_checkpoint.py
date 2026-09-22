"""Fail-closed Phase-4 discovery checkpoint and hypothesis ledger."""

from __future__ import annotations

from typing import Mapping

from hlp.data.phase4_base_rate import PHASE4_BASE_RATE_HANDOFF_VERSION
from hlp.data.phase4_chronological_split import (
    PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION,
)
from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
)
from hlp.data.phase4_hypothesis_freeze import (
    PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION,
    PHASE4_HYPOTHESIS_FREEZE_VERSION,
)
from hlp.data.phase4_interaction import PHASE4_INTERACTION_HANDOFF_VERSION
from hlp.data.phase4_magnitude_strata import (
    PHASE4_MAGNITUDE_STRATA_HANDOFF_VERSION,
)
from hlp.data.phase4_nonlinear import PHASE4_NONLINEAR_HANDOFF_VERSION
from hlp.data.phase4_simple_models import (
    PHASE4_SIMPLE_MODEL_HANDOFF_VERSION,
)
from hlp.data.phase4_stability import PHASE4_STABILITY_HANDOFF_VERSION
from hlp.data.phase4_univariate import PHASE4_UNIVARIATE_HANDOFF_VERSION
from hlp.data.phase4_validation import (
    PHASE4_VALIDATION_HANDOFF_VERSION,
    PHASE4_VALIDATION_REPORT_VERSION,
)


PHASE4_DISCOVERY_LEDGER_VERSION = "phase4-discovery-ledger-v1"
PHASE4_DISCOVERY_HANDOFF_VERSION = "phase4-discovery-handoff-v1"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _require_checkpoint(value: Mapping[str, object], *, label: str) -> None:
    if value.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError(f"Phase-4 discovery {label} checkpoint changed")


def _validate_parent_chain(
    *,
    chronological_split_handoff: Mapping[str, object],
    chronological_split_handoff_sha256: str,
    base_rate_handoff: Mapping[str, object],
    base_rate_handoff_sha256: str,
    univariate_handoff: Mapping[str, object],
    univariate_handoff_sha256: str,
    hypothesis_freeze_handoff: Mapping[str, object],
    hypothesis_freeze_handoff_sha256: str,
    validation_handoff: Mapping[str, object],
) -> tuple[dict, dict, dict, dict, dict]:
    split = dict(chronological_split_handoff)
    base = dict(base_rate_handoff)
    univariate = dict(univariate_handoff)
    freeze = dict(hypothesis_freeze_handoff)
    validation = dict(validation_handoff)

    if (
        str(split.get("version") or "")
        != PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 discovery split version changed")
    if str(base.get("version") or "") != PHASE4_BASE_RATE_HANDOFF_VERSION:
        raise ValueError("Phase-4 discovery base-rate version changed")
    if (
        str(univariate.get("version") or "")
        != PHASE4_UNIVARIATE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 discovery univariate version changed")
    if (
        str(freeze.get("version") or "")
        != PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 discovery hypothesis-freeze version changed")
    if (
        str(validation.get("version") or "")
        != PHASE4_VALIDATION_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 discovery validation version changed")

    for label, value in (
        ("split", split),
        ("base-rate", base),
        ("univariate", univariate),
        ("hypothesis-freeze", freeze),
        ("validation", validation),
    ):
        _require_checkpoint(value, label=label)

    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 discovery split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 discovery final test is not separated")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if split.get(flag) is not False:
            raise ValueError(f"Phase-4 discovery split violates {flag}")

    if base.get("winner_failure_frequencies_reported") is not True:
        raise ValueError("Phase-4 discovery lacks winner/failure base rates")
    if base.get("continuous_outcome_distribution_reported") is not True:
        raise ValueError("Phase-4 discovery lacks continuous outcomes")
    for flag in (
        "feature_relationships_tested",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if base.get(flag) is not False:
            raise ValueError(f"Phase-4 discovery base-rate violates {flag}")

    for flag in (
        "winner_failure_frequencies_reported",
        "missingness_compared_by_outcome",
        "univariate_relationships_tested",
        "phase4_univariate_report_ready",
    ):
        if univariate.get(flag) is not True:
            raise ValueError(f"Phase-4 discovery univariate lacks {flag}")
    for flag in (
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "candidate_features_ranked",
        "signal_promoted",
        "unseen_slice_validation_complete",
        "multiple_testing_control_applied",
        "phase4_discovery_checkpoint_claimed",
    ):
        if univariate.get(flag) is not False:
            raise ValueError(f"Phase-4 discovery univariate violates {flag}")

    for flag in (
        "selection_manual",
        "all_feature_dispositions_logged",
        "validation_hypotheses_frozen",
        "multiple_testing_plan_frozen",
        "phase4_hypothesis_freeze_ready",
    ):
        if freeze.get(flag) is not True:
            raise ValueError(
                f"Phase-4 discovery hypothesis freeze lacks {flag}"
            )
    for flag in (
        "automatic_feature_ranking_used",
        "multiple_testing_control_applied",
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if freeze.get(flag) is not False:
            raise ValueError(
                f"Phase-4 discovery hypothesis freeze violates {flag}"
            )

    for flag in (
        "all_frozen_hypotheses_tested",
        "validation_rows_consumed",
        "unseen_slice_validation_complete",
        "multiple_testing_control_applied",
        "phase4_validation_report_ready",
    ):
        if validation.get(flag) is not True:
            raise ValueError(f"Phase-4 discovery validation lacks {flag}")
    for flag in (
        "final_test_rows_consumed",
        "automatic_feature_ranking_used",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if validation.get(flag) is not False:
            raise ValueError(f"Phase-4 discovery validation violates {flag}")

    split_sha = _sha256(
        chronological_split_handoff_sha256,
        label="Phase-4 discovery split handoff",
    )
    base_sha = _sha256(
        base_rate_handoff_sha256,
        label="Phase-4 discovery base-rate handoff",
    )
    univariate_sha = _sha256(
        univariate_handoff_sha256,
        label="Phase-4 discovery univariate handoff",
    )
    freeze_sha = _sha256(
        hypothesis_freeze_handoff_sha256,
        label="Phase-4 discovery hypothesis-freeze handoff",
    )

    if _sha256(
        univariate.get("chronological_split_handoff_sha256"),
        label="Phase-4 discovery univariate split link",
    ) != split_sha:
        raise ValueError("Phase-4 discovery univariate/split linkage drift")
    if _sha256(
        univariate.get("base_rate_handoff_sha256"),
        label="Phase-4 discovery univariate base-rate link",
    ) != base_sha:
        raise ValueError("Phase-4 discovery univariate/base-rate linkage drift")
    if _sha256(
        freeze.get("chronological_split_handoff_sha256"),
        label="Phase-4 discovery freeze split link",
    ) != split_sha:
        raise ValueError("Phase-4 discovery freeze/split linkage drift")
    if _sha256(
        freeze.get("univariate_handoff_sha256"),
        label="Phase-4 discovery freeze univariate link",
    ) != univariate_sha:
        raise ValueError("Phase-4 discovery freeze/univariate linkage drift")
    if _sha256(
        validation.get("chronological_split_handoff_sha256"),
        label="Phase-4 discovery validation split link",
    ) != split_sha:
        raise ValueError("Phase-4 discovery validation/split linkage drift")
    if _sha256(
        validation.get("hypothesis_freeze_handoff_sha256"),
        label="Phase-4 discovery validation freeze link",
    ) != freeze_sha:
        raise ValueError("Phase-4 discovery validation/freeze linkage drift")

    registry_shas = {
        _sha256(
            value.get("feature_registry_sha256"),
            label=f"Phase-4 discovery {label} registry",
        )
        for label, value in (
            ("split", split),
            ("base-rate", base),
            ("univariate", univariate),
            ("hypothesis-freeze", freeze),
            ("validation", validation),
        )
    }
    if len(registry_shas) != 1:
        raise ValueError("Phase-4 discovery feature-registry lineage drift")

    if _sha256(
        base.get("discovery_rows_sha256"),
        label="Phase-4 discovery base-rate source rows",
    ) != _sha256(
        split.get("discovery_rows_sha256"),
        label="Phase-4 discovery split source rows",
    ):
        raise ValueError("Phase-4 discovery base-rate population drift")
    if int(base.get("discovery_subjects", -1)) != int(
        split.get("discovery_subjects", -2)
    ):
        raise ValueError(
            "Phase-4 discovery base-rate subject-count drift"
        )
    if _sha256(
        univariate.get("source_discovery_rows_sha256"),
        label="Phase-4 discovery univariate source rows",
    ) != _sha256(
        split.get("discovery_rows_sha256"),
        label="Phase-4 discovery split source rows",
    ):
        raise ValueError("Phase-4 discovery source-population drift")
    if _sha256(
        univariate.get("discovery_split_rows_sha256"),
        label="Phase-4 discovery univariate rows",
    ) != _sha256(
        split.get("discovery_split_rows_sha256"),
        label="Phase-4 discovery split rows",
    ):
        raise ValueError("Phase-4 discovery discovery-slice drift")
    if _sha256(
        validation.get("validation_rows_sha256"),
        label="Phase-4 discovery validation rows",
    ) != _sha256(
        split.get("validation_split_rows_sha256"),
        label="Phase-4 discovery split validation rows",
    ):
        raise ValueError("Phase-4 discovery validation-slice drift")
    if _sha256(
        validation.get("hypothesis_plan_sha256"),
        label="Phase-4 discovery validation plan",
    ) != _sha256(
        freeze.get("hypothesis_plan_sha256"),
        label="Phase-4 discovery frozen plan",
    ):
        raise ValueError("Phase-4 discovery hypothesis-plan drift")

    if int(validation.get("hypotheses_tested", -1)) != int(
        freeze.get("validation_hypotheses", -2)
    ):
        raise ValueError("Phase-4 discovery hypothesis-count drift")
    if sorted(validation.get("surviving_hypothesis_ids") or []) != sorted(
        set(validation.get("surviving_hypothesis_ids") or [])
    ):
        raise ValueError("Phase-4 discovery surviving hypothesis ids repeat")

    return split, base, univariate, freeze, validation



def _validate_experiment_suite(
    *,
    split: Mapping[str, object],
    split_handoff_sha256: str,
    freeze: Mapping[str, object],
    freeze_handoff_sha256: str,
    validation: Mapping[str, object],
    magnitude_strata_handoff: Mapping[str, object],
    magnitude_strata_handoff_sha256: str,
    nonlinear_handoff: Mapping[str, object],
    nonlinear_handoff_sha256: str,
    interaction_handoff: Mapping[str, object],
    interaction_handoff_sha256: str,
    simple_model_handoff: Mapping[str, object],
    simple_model_handoff_sha256: str,
    stability_handoff: Mapping[str, object],
    stability_handoff_sha256: str,
) -> dict:
    magnitude = dict(magnitude_strata_handoff)
    nonlinear = dict(nonlinear_handoff)
    interaction = dict(interaction_handoff)
    simple_model = dict(simple_model_handoff)
    stability = dict(stability_handoff)

    for label, value, version in (
        (
            "magnitude-strata",
            magnitude,
            PHASE4_MAGNITUDE_STRATA_HANDOFF_VERSION,
        ),
        ("nonlinear", nonlinear, PHASE4_NONLINEAR_HANDOFF_VERSION),
        ("interaction", interaction, PHASE4_INTERACTION_HANDOFF_VERSION),
        (
            "simple-model",
            simple_model,
            PHASE4_SIMPLE_MODEL_HANDOFF_VERSION,
        ),
        ("stability", stability, PHASE4_STABILITY_HANDOFF_VERSION),
    ):
        if str(value.get("version") or "") != version:
            raise ValueError(
                f"Phase-4 discovery {label} version changed"
            )
        _require_checkpoint(value, label=label)

    for flag in (
        "ordinary_5x_vs_10x_plus_compared",
        "ordinary_5x_vs_20x_plus_compared",
        "phase4_magnitude_strata_report_ready",
    ):
        if magnitude.get(flag) is not True:
            raise ValueError(
                f"Phase-4 discovery magnitude-strata lacks {flag}"
            )
    for flag in (
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "candidate_features_ranked",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if magnitude.get(flag) is not False:
            raise ValueError(
                f"Phase-4 discovery magnitude-strata violates {flag}"
            )

    for flag in (
        "nonlinear_relationships_examined",
        "phase4_nonlinear_report_ready",
    ):
        if nonlinear.get(flag) is not True:
            raise ValueError(
                f"Phase-4 discovery nonlinear lacks {flag}"
            )
    for flag in (
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "candidate_thresholds_promoted",
        "candidate_features_ranked",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if nonlinear.get(flag) is not False:
            raise ValueError(
                f"Phase-4 discovery nonlinear violates {flag}"
            )

    for flag in (
        "pairwise_interactions_examined",
        "phase4_interaction_report_ready",
    ):
        if interaction.get(flag) is not True:
            raise ValueError(
                f"Phase-4 discovery interaction lacks {flag}"
            )
    for flag in (
        "interaction_pairs_ranked",
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if interaction.get(flag) is not False:
            raise ValueError(
                f"Phase-4 discovery interaction violates {flag}"
            )

    for flag in (
        "preprocessing_fit_on_discovery_only",
        "models_fit_on_discovery_only",
        "validation_rows_consumed",
        "transparent_simple_models_examined",
        "phase4_simple_model_report_ready",
    ):
        if simple_model.get(flag) is not True:
            raise ValueError(
                f"Phase-4 discovery simple-model lacks {flag}"
            )
    for flag in (
        "final_test_rows_consumed",
        "production_model_selected",
        "signal_threshold_selected",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if simple_model.get(flag) is not False:
            raise ValueError(
                f"Phase-4 discovery simple-model violates {flag}"
            )

    for flag in (
        "repeated_sampling_stability_examined",
        "chronological_stability_examined",
        "phase4_stability_report_ready",
    ):
        if stability.get(flag) is not True:
            raise ValueError(
                f"Phase-4 discovery stability lacks {flag}"
            )
    for flag in (
        "stability_pass_fail_threshold_applied",
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if stability.get(flag) is not False:
            raise ValueError(
                f"Phase-4 discovery stability violates {flag}"
            )

    split_sha = _sha256(
        split_handoff_sha256,
        label="Phase-4 experiment-suite split handoff",
    )
    freeze_sha = _sha256(
        freeze_handoff_sha256,
        label="Phase-4 experiment-suite freeze handoff",
    )
    discovery_rows_sha = _sha256(
        split.get("discovery_split_rows_sha256"),
        label="Phase-4 experiment-suite discovery rows",
    )
    validation_rows_sha = _sha256(
        split.get("validation_split_rows_sha256"),
        label="Phase-4 experiment-suite validation rows",
    )
    registry_sha = _sha256(
        split.get("feature_registry_sha256"),
        label="Phase-4 experiment-suite registry",
    )
    registry_file_sha = _sha256(
        split.get("feature_registry_file_sha256"),
        label="Phase-4 experiment-suite registry file",
    )

    for label, value in (
        ("magnitude-strata", magnitude),
        ("nonlinear", nonlinear),
        ("interaction", interaction),
        ("simple-model", simple_model),
        ("stability", stability),
    ):
        if _sha256(
            value.get("chronological_split_handoff_sha256"),
            label=f"Phase-4 {label} split link",
        ) != split_sha:
            raise ValueError(
                f"Phase-4 discovery {label}/split linkage drift"
            )
        if _sha256(
            value.get("feature_registry_sha256"),
            label=f"Phase-4 {label} registry",
        ) != registry_sha:
            raise ValueError(
                f"Phase-4 discovery {label} registry drift"
            )
        if _sha256(
            value.get("discovery_split_rows_sha256"),
            label=f"Phase-4 {label} discovery rows",
        ) != discovery_rows_sha:
            raise ValueError(
                f"Phase-4 discovery {label} discovery-slice drift"
            )

    for label, value in (
        ("magnitude-strata", magnitude),
        ("nonlinear", nonlinear),
        ("interaction", interaction),
        ("simple-model", simple_model),
    ):
        if _sha256(
            value.get("feature_registry_file_sha256"),
            label=f"Phase-4 {label} registry file",
        ) != registry_file_sha:
            raise ValueError(
                f"Phase-4 discovery {label} registry-file drift"
            )

    if _sha256(
        simple_model.get("validation_rows_sha256"),
        label="Phase-4 simple-model validation rows",
    ) != validation_rows_sha:
        raise ValueError(
            "Phase-4 discovery simple-model validation-slice drift"
        )
    if _sha256(
        validation.get("validation_rows_sha256"),
        label="Phase-4 validation handoff rows",
    ) != validation_rows_sha:
        raise ValueError(
            "Phase-4 discovery validation handoff slice drift"
        )
    if _sha256(
        stability.get("hypothesis_freeze_handoff_sha256"),
        label="Phase-4 stability freeze link",
    ) != freeze_sha:
        raise ValueError(
            "Phase-4 discovery stability/freeze linkage drift"
        )
    if _sha256(
        stability.get("hypothesis_plan_sha256"),
        label="Phase-4 stability plan",
    ) != _sha256(
        freeze.get("hypothesis_plan_sha256"),
        label="Phase-4 frozen hypothesis plan",
    ):
        raise ValueError(
            "Phase-4 discovery stability hypothesis-plan drift"
        )

    discovery_subjects = int(split.get("discovery_split_rows", -1))
    validation_subjects = int(split.get("validation_split_rows", -1))
    for label, value, field in (
        ("magnitude-strata", magnitude, "analysis_subjects"),
        ("nonlinear", nonlinear, "analysis_subjects"),
        ("interaction", interaction, "analysis_subjects"),
        ("stability", stability, "analysis_subjects"),
        ("simple-model", simple_model, "discovery_rows"),
    ):
        if int(value.get(field, -2)) != discovery_subjects:
            raise ValueError(
                f"Phase-4 discovery {label} subject-count drift"
            )
    if int(simple_model.get("validation_rows", -1)) != validation_subjects:
        raise ValueError(
            "Phase-4 discovery simple-model validation-count drift"
        )

    features_considered = int(freeze.get("features_considered", -1))
    if int(magnitude.get("features_analyzed", -2)) != features_considered:
        raise ValueError(
            "Phase-4 discovery magnitude feature-count drift"
        )
    if (
        int(nonlinear.get("numeric_features_analyzed", -1))
        + int(nonlinear.get("non_numeric_features_excluded", -1))
        != features_considered
    ):
        raise ValueError(
            "Phase-4 discovery nonlinear feature-count drift"
        )
    if (
        int(interaction.get("eligible_features", -1))
        + int(interaction.get("excluded_feature_count", -1))
        != features_considered
    ):
        raise ValueError(
            "Phase-4 discovery interaction feature-count drift"
        )
    if (
        int(simple_model.get("eligible_features", -1))
        + int(simple_model.get("excluded_feature_count", -1))
        != features_considered
    ):
        raise ValueError(
            "Phase-4 discovery simple-model feature-count drift"
        )
    if int(stability.get("hypotheses_examined", -1)) != int(
        freeze.get("validation_hypotheses", -2)
    ):
        raise ValueError(
            "Phase-4 discovery stability hypothesis-count drift"
        )

    return {
        "magnitude_strata_handoff_sha256": _sha256(
            magnitude_strata_handoff_sha256,
            label="Phase-4 magnitude-strata handoff",
        ),
        "nonlinear_handoff_sha256": _sha256(
            nonlinear_handoff_sha256,
            label="Phase-4 nonlinear handoff",
        ),
        "interaction_handoff_sha256": _sha256(
            interaction_handoff_sha256,
            label="Phase-4 interaction handoff",
        ),
        "simple_model_handoff_sha256": _sha256(
            simple_model_handoff_sha256,
            label="Phase-4 simple-model handoff",
        ),
        "stability_handoff_sha256": _sha256(
            stability_handoff_sha256,
            label="Phase-4 stability handoff",
        ),
        "magnitude_strata_examined": True,
        "nonlinear_relationships_examined": True,
        "pairwise_interactions_examined": True,
        "transparent_simple_models_examined": True,
        "repeated_sampling_stability_examined": True,
        "chronological_stability_examined": True,
    }

def build_phase4_discovery_ledger(
    hypothesis_freeze_report: Mapping[str, object],
    validation_report: Mapping[str, object],
    *,
    chronological_split_handoff: Mapping[str, object],
    chronological_split_handoff_sha256: str,
    base_rate_handoff: Mapping[str, object],
    base_rate_handoff_sha256: str,
    univariate_handoff: Mapping[str, object],
    univariate_handoff_sha256: str,
    hypothesis_freeze_handoff: Mapping[str, object],
    hypothesis_freeze_handoff_sha256: str,
    validation_handoff: Mapping[str, object],
    magnitude_strata_handoff: Mapping[str, object],
    magnitude_strata_handoff_sha256: str,
    nonlinear_handoff: Mapping[str, object],
    nonlinear_handoff_sha256: str,
    interaction_handoff: Mapping[str, object],
    interaction_handoff_sha256: str,
    simple_model_handoff: Mapping[str, object],
    simple_model_handoff_sha256: str,
    stability_handoff: Mapping[str, object],
    stability_handoff_sha256: str,
) -> dict:
    """Close Phase 4 only after every frozen hypothesis has a disposition."""

    split, base, univariate, freeze, validation = _validate_parent_chain(
        chronological_split_handoff=chronological_split_handoff,
        chronological_split_handoff_sha256=(
            chronological_split_handoff_sha256
        ),
        base_rate_handoff=base_rate_handoff,
        base_rate_handoff_sha256=base_rate_handoff_sha256,
        univariate_handoff=univariate_handoff,
        univariate_handoff_sha256=univariate_handoff_sha256,
        hypothesis_freeze_handoff=hypothesis_freeze_handoff,
        hypothesis_freeze_handoff_sha256=(
            hypothesis_freeze_handoff_sha256
        ),
        validation_handoff=validation_handoff,
    )
    experiment_suite = _validate_experiment_suite(
        split=split,
        split_handoff_sha256=chronological_split_handoff_sha256,
        freeze=freeze,
        freeze_handoff_sha256=hypothesis_freeze_handoff_sha256,
        validation=validation,
        magnitude_strata_handoff=magnitude_strata_handoff,
        magnitude_strata_handoff_sha256=magnitude_strata_handoff_sha256,
        nonlinear_handoff=nonlinear_handoff,
        nonlinear_handoff_sha256=nonlinear_handoff_sha256,
        interaction_handoff=interaction_handoff,
        interaction_handoff_sha256=interaction_handoff_sha256,
        simple_model_handoff=simple_model_handoff,
        simple_model_handoff_sha256=simple_model_handoff_sha256,
        stability_handoff=stability_handoff,
        stability_handoff_sha256=stability_handoff_sha256,
    )

    freeze_report = dict(hypothesis_freeze_report)
    validation_report = dict(validation_report)
    if (
        str(freeze_report.get("version") or "")
        != PHASE4_HYPOTHESIS_FREEZE_VERSION
    ):
        raise ValueError("Phase-4 discovery freeze-report version changed")
    if (
        str(validation_report.get("version") or "")
        != PHASE4_VALIDATION_REPORT_VERSION
    ):
        raise ValueError("Phase-4 discovery validation-report version changed")
    _require_checkpoint(freeze_report, label="freeze-report")
    _require_checkpoint(validation_report, label="validation-report")

    if _sha256(
        freeze_report.get("hypothesis_plan_sha256"),
        label="Phase-4 discovery freeze-report plan",
    ) != _sha256(
        freeze.get("hypothesis_plan_sha256"),
        label="Phase-4 discovery freeze-handoff plan",
    ):
        raise ValueError("Phase-4 discovery freeze report/handoff plan drift")
    if _sha256(
        validation_report.get("hypothesis_plan_sha256"),
        label="Phase-4 discovery validation-report plan",
    ) != _sha256(
        validation.get("hypothesis_plan_sha256"),
        label="Phase-4 discovery validation-handoff plan",
    ):
        raise ValueError(
            "Phase-4 discovery validation report/handoff plan drift"
        )
    if int(validation_report.get("hypotheses_tested", -1)) != int(
        validation.get("hypotheses_tested", -2)
    ):
        raise ValueError("Phase-4 discovery validation report count drift")
    if int(validation_report.get("hypotheses_survived", -1)) != int(
        validation.get("hypotheses_survived", -2)
    ):
        raise ValueError("Phase-4 discovery survivor count drift")

    plan = freeze_report.get("normalized_hypothesis_plan")
    if not isinstance(plan, Mapping):
        raise ValueError("Phase-4 discovery normalized plan is missing")
    hypotheses = plan.get("hypotheses")
    if not isinstance(hypotheses, list):
        raise ValueError("Phase-4 discovery frozen hypotheses are missing")
    frozen_by_id = {}
    for raw in hypotheses:
        if not isinstance(raw, Mapping):
            raise ValueError("Phase-4 discovery frozen hypothesis is invalid")
        row = dict(raw)
        hypothesis_id = str(row.get("hypothesis_id") or "")
        if not hypothesis_id or hypothesis_id in frozen_by_id:
            raise ValueError(
                f"Phase-4 discovery frozen hypothesis id is invalid: "
                f"{hypothesis_id!r}"
            )
        frozen_by_id[hypothesis_id] = row

    results = validation_report.get("hypothesis_results")
    if not isinstance(results, list):
        raise ValueError("Phase-4 discovery validation results are missing")
    result_by_id = {}
    for raw in results:
        if not isinstance(raw, Mapping):
            raise ValueError("Phase-4 discovery validation result is invalid")
        row = dict(raw)
        hypothesis_id = str(row.get("hypothesis_id") or "")
        if not hypothesis_id or hypothesis_id in result_by_id:
            raise ValueError(
                f"Phase-4 discovery result id is invalid: {hypothesis_id!r}"
            )
        result_by_id[hypothesis_id] = row

    if set(frozen_by_id) != set(result_by_id):
        raise ValueError(
            "Phase-4 discovery frozen/result hypothesis membership drift"
        )
    if len(frozen_by_id) != int(validation.get("hypotheses_tested", -1)):
        raise ValueError("Phase-4 discovery tested-hypothesis count drift")

    hypothesis_ledger = []
    surviving = []
    rejected = []
    for hypothesis_id in sorted(frozen_by_id):
        frozen = frozen_by_id[hypothesis_id]
        result = result_by_id[hypothesis_id]
        for key in (
            "feature_id",
            "effect_metric",
            "expected_direction",
            "category_value",
        ):
            if result.get(key) != frozen.get(key):
                raise ValueError(
                    f"Phase-4 discovery hypothesis {key} drift: "
                    f"{hypothesis_id}"
                )
        survives = result.get("survived_validation")
        if not isinstance(survives, bool):
            raise ValueError(
                f"Phase-4 discovery survivor flag is invalid: "
                f"{hypothesis_id}"
            )

        reasons = []
        if not bool(result.get("direction_consistent")):
            reasons.append("direction_not_reproduced")
        if not bool(result.get("effect_threshold_met")):
            reasons.append("minimum_effect_not_reproduced")
        if not bool(result.get("fdr_significant")):
            reasons.append("fdr_not_significant")

        if survives:
            if reasons:
                raise ValueError(
                    f"Phase-4 discovery surviving hypothesis has "
                    f"rejection reasons: {hypothesis_id}"
                )
            disposition = "validated_relationship"
            surviving.append(hypothesis_id)
        else:
            if not reasons:
                raise ValueError(
                    f"Phase-4 discovery rejected hypothesis lacks reason: "
                    f"{hypothesis_id}"
                )
            disposition = "rejected_unseen_validation"
            rejected.append(hypothesis_id)

        hypothesis_ledger.append({
            "hypothesis_id": hypothesis_id,
            "feature_id": str(frozen["feature_id"]),
            "family": str(frozen.get("family") or ""),
            "effect_metric": str(frozen["effect_metric"]),
            "category_value": frozen.get("category_value"),
            "expected_direction": str(frozen["expected_direction"]),
            "minimum_absolute_effect": str(
                frozen["minimum_absolute_effect"]
            ),
            "discovery_effect": str(frozen["discovery_effect"]),
            "validation_effect": str(result["validation_effect"]),
            "permutation_p_value": str(result["permutation_p_value"]),
            "benjamini_hochberg_q_value": str(
                result["benjamini_hochberg_q_value"]
            ),
            "direction_consistent": bool(
                result["direction_consistent"]
            ),
            "effect_threshold_met": bool(
                result["effect_threshold_met"]
            ),
            "fdr_significant": bool(result["fdr_significant"]),
            "final_disposition": disposition,
            "rejection_reasons": reasons,
        })

    expected_surviving = sorted(
        str(value)
        for value in validation.get("surviving_hypothesis_ids") or []
    )
    if surviving != expected_surviving:
        raise ValueError("Phase-4 discovery surviving-id ledger drift")
    if len(surviving) != int(validation.get("hypotheses_survived", -1)):
        raise ValueError("Phase-4 discovery survivor ledger count drift")

    feature_dispositions = freeze_report.get("feature_dispositions")
    if not isinstance(feature_dispositions, list):
        raise ValueError("Phase-4 discovery feature dispositions are missing")
    hypotheses_by_feature = {}
    for row in hypothesis_ledger:
        hypotheses_by_feature.setdefault(row["feature_id"], []).append(row)

    feature_ledger = []
    seen_features = set()
    for raw in feature_dispositions:
        if not isinstance(raw, Mapping):
            raise ValueError("Phase-4 discovery feature disposition is invalid")
        feature_id = str(raw.get("feature_id") or "")
        if not feature_id or feature_id in seen_features:
            raise ValueError(
                f"Phase-4 discovery feature disposition id is invalid: "
                f"{feature_id!r}"
            )
        seen_features.add(feature_id)
        discovery_disposition = str(raw.get("disposition") or "")
        linked = hypotheses_by_feature.get(feature_id, [])
        if discovery_disposition == "not_selected_for_validation":
            if linked:
                raise ValueError(
                    f"Phase-4 discovery unselected feature has hypothesis: "
                    f"{feature_id}"
                )
            final_disposition = "not_selected_for_validation"
        elif discovery_disposition == "selected_for_validation":
            if not linked:
                raise ValueError(
                    f"Phase-4 discovery selected feature lacks hypothesis: "
                    f"{feature_id}"
                )
            if any(
                row["final_disposition"] == "validated_relationship"
                for row in linked
            ):
                final_disposition = "has_validated_relationship"
            else:
                final_disposition = "selected_but_rejected_in_validation"
        else:
            raise ValueError(
                f"Phase-4 discovery feature disposition changed: "
                f"{discovery_disposition!r}"
            )
        feature_ledger.append({
            "feature_id": feature_id,
            "discovery_disposition": discovery_disposition,
            "validation_hypothesis_ids": sorted(
                row["hypothesis_id"] for row in linked
            ),
            "final_disposition": final_disposition,
        })

    if len(feature_ledger) != int(freeze.get("features_considered", -1)):
        raise ValueError("Phase-4 discovery feature-ledger count drift")
    if len(hypothesis_ledger) != int(
        freeze.get("validation_hypotheses", -1)
    ):
        raise ValueError("Phase-4 discovery hypothesis-ledger count drift")

    return {
        "version": PHASE4_DISCOVERY_LEDGER_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": str(
            validation["feature_registry_sha256"]
        ),
        "source_discovery_subjects": int(
            univariate["source_discovery_subjects"]
        ),
        "discovery_analysis_subjects": int(
            univariate["analysis_subjects"]
        ),
        "validation_rows": int(validation["validation_rows"]),
        "validation_winner_rows": int(
            validation["validation_winner_rows"]
        ),
        "validation_failure_rows": int(
            validation["validation_failure_rows"]
        ),
        "base_rate_subjects": int(base["discovery_subjects"]),
        "base_rate_comeback_5x_tokens": int(base["comeback_5x_tokens"]),
        "base_rate_comeback_5x": str(base["comeback_5x_base_rate"]),
        "features_considered": len(feature_ledger),
        "hypotheses_tested": len(hypothesis_ledger),
        "hypotheses_validated": len(surviving),
        "hypotheses_rejected": len(rejected),
        "validated_hypothesis_ids": surviving,
        "rejected_hypothesis_ids": rejected,
        "feature_ledger": feature_ledger,
        "hypothesis_ledger": hypothesis_ledger,
        **experiment_suite,
        "sequence_analysis_performed": False,
        "sequence_analysis_disposition": (
            "not_applicable_point_in_time_feature_store_has_no_"
            "sequence_valued_inputs"
        ),
        "cluster_analysis_performed": False,
        "cluster_analysis_disposition": (
            "not_run_optional_where_useful_task_without_predefined_"
            "cluster_research_question"
        ),
        "optional_cluster_sequence_disposition_recorded": True,
        "winner_failure_frequencies_reported": True,
        "all_feature_dispositions_logged": True,
        "all_hypothesis_dispositions_logged": True,
        "rejected_hypotheses_logged": True,
        "unseen_slice_validation_complete": True,
        "multiple_testing_control_applied": True,
        "magnitude_strata_examined": True,
        "nonlinear_relationships_examined": True,
        "pairwise_interactions_examined": True,
        "transparent_simple_models_examined": True,
        "repeated_sampling_stability_examined": True,
        "chronological_stability_examined": True,
        "optional_cluster_sequence_disposition_recorded": True,
        "validated_relationships_present": bool(surviving),
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase5_model_started": False,
        "phase4_discovery_checkpoint_claimed": True,
        "phase4_discovery_complete": True,
    }


def build_phase4_discovery_handoff(
    ledger: Mapping[str, object],
    *,
    ledger_sha256: str,
    chronological_split_handoff_sha256: str,
    base_rate_handoff_sha256: str,
    univariate_handoff_sha256: str,
    hypothesis_freeze_handoff_sha256: str,
    validation_handoff_sha256: str,
) -> dict:
    """Publish the Phase-4 checkpoint without promoting a production signal."""

    row = dict(ledger)
    if (
        str(row.get("version") or "")
        != PHASE4_DISCOVERY_LEDGER_VERSION
    ):
        raise ValueError("Phase-4 discovery handoff version changed")
    _require_checkpoint(row, label="ledger")
    for flag in (
        "winner_failure_frequencies_reported",
        "all_feature_dispositions_logged",
        "all_hypothesis_dispositions_logged",
        "rejected_hypotheses_logged",
        "unseen_slice_validation_complete",
        "multiple_testing_control_applied",
        "phase4_discovery_checkpoint_claimed",
        "phase4_discovery_complete",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 discovery handoff lacks {flag}")
    for flag in (
        "final_test_rows_consumed",
        "signal_promoted",
        "phase5_model_started",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 discovery handoff violates {flag}")

    tested = int(row["hypotheses_tested"])
    validated = int(row["hypotheses_validated"])
    rejected = int(row["hypotheses_rejected"])
    if tested != validated + rejected:
        raise ValueError("Phase-4 discovery disposition totals drift")

    return {
        "version": PHASE4_DISCOVERY_HANDOFF_VERSION,
        "checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 discovery registry",
        ),
        "discovery_ledger_sha256": _sha256(
            ledger_sha256,
            label="Phase-4 discovery ledger",
        ),
        "chronological_split_handoff_sha256": _sha256(
            chronological_split_handoff_sha256,
            label="Phase-4 discovery split handoff",
        ),
        "base_rate_handoff_sha256": _sha256(
            base_rate_handoff_sha256,
            label="Phase-4 discovery base-rate handoff",
        ),
        "univariate_handoff_sha256": _sha256(
            univariate_handoff_sha256,
            label="Phase-4 discovery univariate handoff",
        ),
        "hypothesis_freeze_handoff_sha256": _sha256(
            hypothesis_freeze_handoff_sha256,
            label="Phase-4 discovery hypothesis-freeze handoff",
        ),
        "validation_handoff_sha256": _sha256(
            validation_handoff_sha256,
            label="Phase-4 discovery validation handoff",
        ),
        "base_rate_subjects": int(row["base_rate_subjects"]),
        "features_considered": int(row["features_considered"]),
        "hypotheses_tested": tested,
        "hypotheses_validated": validated,
        "hypotheses_rejected": rejected,
        "validated_hypothesis_ids": list(
            row["validated_hypothesis_ids"]
        ),
        "rejected_hypothesis_ids": list(
            row["rejected_hypothesis_ids"]
        ),
        "winner_failure_frequencies_reported": True,
        "all_feature_dispositions_logged": True,
        "all_hypothesis_dispositions_logged": True,
        "rejected_hypotheses_logged": True,
        "unseen_slice_validation_complete": True,
        "multiple_testing_control_applied": True,
        "validated_relationships_present": bool(
            row["validated_relationships_present"]
        ),
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase5_model_started": False,
        "phase4_discovery_checkpoint_claimed": True,
        "phase4_discovery_complete": True,
    }
