"""Manual Phase-4 hypothesis freeze between discovery and validation."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation, localcontext
from typing import Mapping

from hlp.data.phase4_chronological_split import (
    PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION,
)
from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
)
from hlp.data.phase4_univariate import (
    PHASE4_UNIVARIATE_HANDOFF_VERSION,
    PHASE4_UNIVARIATE_REPORT_VERSION,
)


PHASE4_HYPOTHESIS_PLAN_VERSION = "phase4-hypothesis-plan-v1"
PHASE4_HYPOTHESIS_FREEZE_VERSION = "phase4-hypothesis-freeze-v1"
PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION = (
    "phase4-hypothesis-freeze-handoff-v1"
)
SUPPORTED_DIRECTIONS = frozenset({"positive", "negative"})
SUPPORTED_MULTIPLE_TESTING_METHODS = frozenset({
    "benjamini_hochberg",
})
COMMON_EFFECT_METRIC = "missing_rate_difference_winner_minus_failure"
NUMERIC_EFFECT_METRICS = frozenset({
    "cliffs_delta_winner_vs_failure",
    "mean_difference_winner_minus_failure",
    "median_difference_winner_minus_failure",
    COMMON_EFFECT_METRIC,
})
BOOLEAN_EFFECT_METRICS = frozenset({
    "true_rate_difference_winner_minus_failure",
    COMMON_EFFECT_METRIC,
})
CATEGORICAL_EFFECT_METRICS = frozenset({
    "category_rate_difference_winner_minus_failure",
    COMMON_EFFECT_METRIC,
})


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _decimal(value: object, *, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} is not numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{label} is not finite")
    return result


def _text(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 80
        if value == 0:
            return "0"
        return format(value.normalize(context=context), "f")


def _canonical_sha(value: object) -> str:
    payload = (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _category_effect(
    feature: Mapping[str, object],
    category_value: str,
) -> Decimal:
    categories = feature.get("categories")
    if not isinstance(categories, list):
        raise ValueError(
            "Phase-4 categorical hypothesis lacks category diagnostics"
        )
    for raw in categories:
        if not isinstance(raw, Mapping):
            continue
        if str(raw.get("value")) != category_value:
            continue
        winner_rate = raw.get("winner_rate_among_observed")
        failure_rate = raw.get("failure_rate_among_observed")
        if winner_rate is None or failure_rate is None:
            raise ValueError(
                "Phase-4 categorical hypothesis effect is unavailable"
            )
        with localcontext() as context:
            context.prec = 80
            return _decimal(
                winner_rate,
                label="Phase-4 category winner rate",
            ) - _decimal(
                failure_rate,
                label="Phase-4 category failure rate",
            )
    raise ValueError(
        f"Phase-4 categorical hypothesis category is absent: "
        f"{category_value!r}"
    )


def _effect(
    feature: Mapping[str, object],
    metric: str,
    category_value: str | None,
) -> Decimal:
    kind = str(feature.get("comparison_kind") or "")
    allowed = {
        "numeric": NUMERIC_EFFECT_METRICS,
        "boolean": BOOLEAN_EFFECT_METRICS,
        "categorical": CATEGORICAL_EFFECT_METRICS,
    }.get(kind)
    if allowed is None:
        raise ValueError(
            f"Phase-4 hypothesis comparison kind is unsupported: {kind}"
        )
    if metric not in allowed:
        raise ValueError(
            f"Phase-4 hypothesis metric {metric!r} is invalid for {kind}"
        )
    if metric == "category_rate_difference_winner_minus_failure":
        if kind != "categorical" or category_value is None:
            raise ValueError(
                "Phase-4 category hypothesis requires category_value"
            )
        return _category_effect(feature, category_value)

    value = feature.get(metric)
    if value is None:
        raise ValueError(
            f"Phase-4 hypothesis discovery effect is unavailable: {metric}"
        )
    return _decimal(
        value,
        label=f"Phase-4 hypothesis discovery effect {metric}",
    )


def build_phase4_hypothesis_freeze(
    univariate_report: Mapping[str, object],
    *,
    univariate_handoff: Mapping[str, object],
    chronological_split_handoff: Mapping[str, object],
    chronological_split_handoff_sha256: str,
    hypothesis_plan: Mapping[str, object],
) -> dict:
    """Freeze manual discovery hypotheses before validation is opened."""

    report = dict(univariate_report)
    univariate = dict(univariate_handoff)
    split = dict(chronological_split_handoff)
    plan = dict(hypothesis_plan)

    if (
        str(report.get("version") or "")
        != PHASE4_UNIVARIATE_REPORT_VERSION
    ):
        raise ValueError("Phase-4 hypothesis freeze report version changed")
    if (
        str(univariate.get("version") or "")
        != PHASE4_UNIVARIATE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 hypothesis freeze handoff version changed")
    if (
        str(split.get("version") or "")
        != PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 hypothesis freeze split version changed")
    for value in (report, univariate, split):
        if value.get("phase4_checkpoint_name") != (
            PHASE4_DISCOVERY_CHECKPOINT_NAME
        ):
            raise ValueError("Phase-4 hypothesis freeze checkpoint changed")

    if univariate.get("phase4_univariate_report_ready") is not True:
        raise ValueError("Phase-4 univariate report is not ready")
    if univariate.get("univariate_relationships_tested") is not True:
        raise ValueError("Phase-4 univariate relationships were not tested")
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
            raise ValueError(
                f"Phase-4 hypothesis freeze univariate violates {flag}"
            )

    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 chronological split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 final-test slice is not separated")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if split.get(flag) is not False:
            raise ValueError(
                f"Phase-4 hypothesis freeze split violates {flag}"
            )

    expected_split_sha = _sha256(
        chronological_split_handoff_sha256,
        label="Phase-4 hypothesis freeze split handoff",
    )
    if _sha256(
        univariate.get("chronological_split_handoff_sha256"),
        label="Phase-4 univariate split linkage",
    ) != expected_split_sha:
        raise ValueError(
            "Phase-4 hypothesis freeze univariate/split linkage drift"
        )
    if _sha256(
        report.get("feature_registry_sha256"),
        label="Phase-4 hypothesis report registry",
    ) != _sha256(
        univariate.get("feature_registry_sha256"),
        label="Phase-4 hypothesis handoff registry",
    ):
        raise ValueError("Phase-4 hypothesis registry drift")
    if _sha256(
        report.get("discovery_split_rows_sha256"),
        label="Phase-4 hypothesis report rows",
    ) != _sha256(
        split.get("discovery_split_rows_sha256"),
        label="Phase-4 hypothesis split rows",
    ):
        raise ValueError("Phase-4 hypothesis discovery-slice drift")

    feature_reports = report.get("feature_reports")
    if not isinstance(feature_reports, list):
        raise ValueError("Phase-4 hypothesis feature reports are missing")
    features = {}
    for raw in feature_reports:
        if not isinstance(raw, Mapping):
            raise ValueError("Phase-4 hypothesis feature report is invalid")
        feature = dict(raw)
        feature_id = str(feature.get("feature_id") or "")
        if not feature_id or feature_id in features:
            raise ValueError(
                f"Phase-4 hypothesis feature id is invalid: {feature_id!r}"
            )
        features[feature_id] = feature
    if len(features) != int(univariate.get("features_tested", -1)):
        raise ValueError("Phase-4 hypothesis feature count drift")

    if str(plan.get("version") or "") != PHASE4_HYPOTHESIS_PLAN_VERSION:
        raise ValueError("Phase-4 hypothesis plan version changed")
    method = str(plan.get("multiple_testing_method") or "")
    if method not in SUPPORTED_MULTIPLE_TESTING_METHODS:
        raise ValueError("Phase-4 multiple-testing method is unsupported")
    try:
        permutation_trials = int(plan.get("permutation_trials"))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Phase-4 permutation trial count is invalid"
        ) from exc
    if permutation_trials < 1000 or permutation_trials > 100000:
        raise ValueError(
            "Phase-4 permutation trials must be between 1000 and 100000"
        )
    alpha = _decimal(
        plan.get("false_discovery_rate_alpha"),
        label="Phase-4 false-discovery-rate alpha",
    )
    if alpha <= 0 or alpha >= 1:
        raise ValueError(
            "Phase-4 false-discovery-rate alpha must be between 0 and 1"
        )
    plan_rows = plan.get("hypotheses")
    if not isinstance(plan_rows, list):
        raise ValueError("Phase-4 hypothesis plan rows are missing")

    frozen = []
    hypothesis_ids = set()
    selected_features = set()
    for raw in plan_rows:
        if not isinstance(raw, Mapping):
            raise ValueError("Phase-4 hypothesis plan row is invalid")
        item = dict(raw)
        hypothesis_id = str(item.get("hypothesis_id") or "").strip()
        feature_id = str(item.get("feature_id") or "").strip()
        metric = str(item.get("effect_metric") or "").strip()
        direction = str(item.get("expected_direction") or "").strip()
        category_raw = item.get("category_value")
        category_value = (
            None if category_raw is None else str(category_raw)
        )
        rationale = str(item.get("rationale") or "").strip()

        if not hypothesis_id or hypothesis_id in hypothesis_ids:
            raise ValueError(
                f"Phase-4 hypothesis id is invalid: {hypothesis_id!r}"
            )
        hypothesis_ids.add(hypothesis_id)
        if feature_id not in features:
            raise ValueError(
                f"Phase-4 hypothesis references unknown feature: "
                f"{feature_id!r}"
            )
        if direction not in SUPPORTED_DIRECTIONS:
            raise ValueError(
                f"Phase-4 hypothesis direction is invalid: {direction!r}"
            )
        if not rationale:
            raise ValueError(
                f"Phase-4 hypothesis rationale is empty: {hypothesis_id}"
            )
        minimum = _decimal(
            item.get("minimum_absolute_effect"),
            label=f"{hypothesis_id} minimum absolute effect",
        )
        if minimum < 0:
            raise ValueError(
                f"Phase-4 hypothesis minimum effect is negative: "
                f"{hypothesis_id}"
            )
        observed = _effect(
            features[feature_id],
            metric,
            category_value,
        )
        selected_features.add(feature_id)
        frozen.append({
            "hypothesis_id": hypothesis_id,
            "feature_id": feature_id,
            "family": str(features[feature_id].get("family") or ""),
            "comparison_kind": str(
                features[feature_id].get("comparison_kind") or ""
            ),
            "effect_metric": metric,
            "category_value": category_value,
            "expected_direction": direction,
            "minimum_absolute_effect": _text(minimum),
            "discovery_effect": _text(observed),
            "rationale": rationale,
            "validation_rule": (
                "same_direction_and_absolute_effect_at_least_threshold"
            ),
        })

    normalized_plan = {
        "version": PHASE4_HYPOTHESIS_PLAN_VERSION,
        "multiple_testing_method": method,
        "false_discovery_rate_alpha": _text(alpha),
        "permutation_trials": permutation_trials,
        "hypotheses": frozen,
    }
    dispositions = [
        {
            "feature_id": feature_id,
            "disposition": (
                "selected_for_validation"
                if feature_id in selected_features
                else "not_selected_for_validation"
            ),
        }
        for feature_id in sorted(features)
    ]

    return {
        "version": PHASE4_HYPOTHESIS_FREEZE_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": str(
            univariate["feature_registry_sha256"]
        ),
        "discovery_split_rows_sha256": str(
            univariate["discovery_split_rows_sha256"]
        ),
        "chronological_split_handoff_sha256": expected_split_sha,
        "univariate_report_sha256": str(
            univariate["univariate_report_sha256"]
        ),
        "hypothesis_plan_sha256": _canonical_sha(normalized_plan),
        "normalized_hypothesis_plan": normalized_plan,
        "feature_dispositions": dispositions,
        "features_considered": len(features),
        "selected_features": len(selected_features),
        "validation_hypotheses": len(frozen),
        "multiple_testing_method": method,
        "false_discovery_rate_alpha": _text(alpha),
        "permutation_trials": permutation_trials,
        "permutation_seed_rule": (
            "sha256(validation_rows_sha256+hypothesis_plan_sha256+"
            "hypothesis_id)"
        ),
        "permutation_test_two_sided": True,
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


def build_phase4_hypothesis_freeze_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    univariate_handoff_sha256: str,
) -> dict:
    """Bind the manual hypothesis set without opening unseen rows."""

    row = dict(report)
    if (
        str(row.get("version") or "")
        != PHASE4_HYPOTHESIS_FREEZE_VERSION
    ):
        raise ValueError("Phase-4 hypothesis-freeze handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 hypothesis-freeze checkpoint changed")
    for flag in (
        "selection_manual",
        "all_feature_dispositions_logged",
        "validation_hypotheses_frozen",
        "multiple_testing_plan_frozen",
        "phase4_hypothesis_freeze_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(
                f"Phase-4 hypothesis-freeze handoff lacks {flag}"
            )
    for flag in (
        "automatic_feature_ranking_used",
        "multiple_testing_control_applied",
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(
                f"Phase-4 hypothesis-freeze handoff violates {flag}"
            )

    return {
        "version": PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 hypothesis-freeze registry",
        ),
        "discovery_split_rows_sha256": _sha256(
            row.get("discovery_split_rows_sha256"),
            label="Phase-4 hypothesis-freeze discovery rows",
        ),
        "chronological_split_handoff_sha256": _sha256(
            row.get("chronological_split_handoff_sha256"),
            label="Phase-4 hypothesis-freeze split handoff",
        ),
        "univariate_report_sha256": _sha256(
            row.get("univariate_report_sha256"),
            label="Phase-4 hypothesis-freeze univariate report",
        ),
        "hypothesis_plan_sha256": _sha256(
            row.get("hypothesis_plan_sha256"),
            label="Phase-4 hypothesis plan",
        ),
        "hypothesis_freeze_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 hypothesis-freeze report",
        ),
        "univariate_handoff_sha256": _sha256(
            univariate_handoff_sha256,
            label="Phase-4 univariate handoff",
        ),
        "features_considered": int(row["features_considered"]),
        "selected_features": int(row["selected_features"]),
        "validation_hypotheses": int(row["validation_hypotheses"]),
        "multiple_testing_method": str(
            row["multiple_testing_method"]
        ),
        "false_discovery_rate_alpha": str(
            row["false_discovery_rate_alpha"]
        ),
        "permutation_trials": int(row["permutation_trials"]),
        "permutation_seed_rule": str(row["permutation_seed_rule"]),
        "permutation_test_two_sided": True,
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
