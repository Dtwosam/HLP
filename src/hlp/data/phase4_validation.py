"""Unseen chronological validation for frozen Phase-4 hypotheses."""

from __future__ import annotations

import hashlib
import random
from bisect import bisect_left, bisect_right
from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase4_chronological_split import (
    PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION,
)
from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
    PHASE4_DISCOVERY_ENTRY_VERSION,
)
from hlp.data.phase4_hypothesis_freeze import (
    PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION,
    PHASE4_HYPOTHESIS_FREEZE_VERSION,
)


PHASE4_VALIDATION_REPORT_VERSION = "phase4-validation-report-v1"
PHASE4_VALIDATION_HANDOFF_VERSION = "phase4-validation-handoff-v1"


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


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Phase-4 validation mean has no values")
    with localcontext() as context:
        context.prec = 80
        return sum(values, Decimal(0)) / Decimal(len(values))


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Phase-4 validation median has no values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    with localcontext() as context:
        context.prec = 80
        return (
            ordered[middle - 1] + ordered[middle]
        ) / Decimal(2)


def _cliffs_delta(
    winners: list[Decimal],
    failures: list[Decimal],
) -> Decimal:
    if not winners or not failures:
        raise ValueError(
            "Phase-4 validation Cliff's delta needs both cohorts"
        )
    ordered_failures = sorted(failures)
    dominance = 0
    for value in winners:
        lower = bisect_left(ordered_failures, value)
        upper = bisect_right(ordered_failures, value)
        dominance += lower
        dominance -= len(ordered_failures) - upper
    with localcontext() as context:
        context.prec = 80
        return Decimal(dominance) / Decimal(
            len(winners) * len(failures)
        )


def _rate_difference(
    winners: list[Decimal],
    failures: list[Decimal],
) -> Decimal:
    with localcontext() as context:
        context.prec = 80
        return _mean(winners) - _mean(failures)


def _effect(
    metric: str,
    winner_values: list[Decimal],
    failure_values: list[Decimal],
) -> Decimal:
    if metric == "cliffs_delta_winner_vs_failure":
        return _cliffs_delta(winner_values, failure_values)
    if metric == "mean_difference_winner_minus_failure":
        with localcontext() as context:
            context.prec = 80
            return _mean(winner_values) - _mean(failure_values)
    if metric == "median_difference_winner_minus_failure":
        with localcontext() as context:
            context.prec = 80
            return _median(winner_values) - _median(failure_values)
    if metric in {
        "missing_rate_difference_winner_minus_failure",
        "true_rate_difference_winner_minus_failure",
        "category_rate_difference_winner_minus_failure",
    }:
        return _rate_difference(winner_values, failure_values)
    raise ValueError(
        f"Phase-4 validation effect metric is unsupported: {metric}"
    )


def _measurements(
    rows: list[dict],
    hypothesis: Mapping[str, object],
) -> tuple[list[Decimal], list[bool]]:
    feature_id = str(hypothesis["feature_id"])
    metric = str(hypothesis["effect_metric"])
    category_value = hypothesis.get("category_value")
    values: list[Decimal] = []
    labels: list[bool] = []

    for row in rows:
        feature_values = row.get("feature_values")
        if not isinstance(feature_values, Mapping):
            raise ValueError(
                f"Phase-4 validation feature values missing: "
                f"{row['token']}"
            )
        if feature_id not in feature_values:
            raise ValueError(
                f"Phase-4 validation feature absent: {feature_id}"
            )
        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(
                f"Phase-4 validation target invalid: {row['token']}"
            )

        value = feature_values[feature_id]
        if metric == "missing_rate_difference_winner_minus_failure":
            values.append(Decimal(int(value is None)))
            labels.append(target)
            continue
        if value is None:
            continue

        if metric == "true_rate_difference_winner_minus_failure":
            if not isinstance(value, bool):
                raise ValueError(
                    f"Phase-4 validation boolean feature drift: "
                    f"{feature_id}"
                )
            values.append(Decimal(int(value)))
        elif metric == "category_rate_difference_winner_minus_failure":
            values.append(
                Decimal(int(str(value) == str(category_value)))
            )
        else:
            if isinstance(value, bool):
                raise ValueError(
                    f"Phase-4 validation numeric feature is boolean: "
                    f"{feature_id}"
                )
            values.append(
                _decimal(
                    value,
                    label=f"Phase-4 validation {feature_id}",
                )
            )
        labels.append(target)

    return values, labels


def _split_values(
    values: list[Decimal],
    labels: list[bool],
) -> tuple[list[Decimal], list[Decimal]]:
    winners = [
        value
        for value, label in zip(values, labels)
        if label
    ]
    failures = [
        value
        for value, label in zip(values, labels)
        if not label
    ]
    if not winners or not failures:
        raise ValueError(
            "Phase-4 validation hypothesis lacks both observed cohorts"
        )
    return winners, failures


def _permutation_p_value(
    values: list[Decimal],
    labels: list[bool],
    *,
    metric: str,
    trials: int,
    seed_material: str,
) -> Decimal:
    winners, failures = _split_values(values, labels)
    observed = abs(_effect(metric, winners, failures))
    winner_count = sum(labels)
    if winner_count <= 0 or winner_count >= len(labels):
        raise ValueError(
            "Phase-4 validation permutation needs both cohorts"
        )

    seed = int(
        hashlib.sha256(seed_material.encode()).hexdigest(),
        16,
    )
    rng = random.Random(seed)
    template = [True] * winner_count + [False] * (
        len(labels) - winner_count
    )
    extreme = 0
    for _ in range(trials):
        shuffled = list(template)
        rng.shuffle(shuffled)
        perm_winners, perm_failures = _split_values(
            values,
            shuffled,
        )
        permuted = abs(
            _effect(metric, perm_winners, perm_failures)
        )
        if permuted >= observed:
            extreme += 1
    with localcontext() as context:
        context.prec = 80
        return Decimal(extreme + 1) / Decimal(trials + 1)


def _benjamini_hochberg(
    p_values: Mapping[str, Decimal],
) -> dict[str, Decimal]:
    if not p_values:
        return {}
    ordered = sorted(
        p_values.items(),
        key=lambda item: (item[1], item[0]),
    )
    total = len(ordered)
    adjusted: dict[str, Decimal] = {}
    next_value = Decimal(1)
    for reverse_index in range(total - 1, -1, -1):
        hypothesis_id, p_value = ordered[reverse_index]
        rank = reverse_index + 1
        with localcontext() as context:
            context.prec = 80
            candidate = min(
                Decimal(1),
                p_value * Decimal(total) / Decimal(rank),
            )
        next_value = min(next_value, candidate)
        adjusted[hypothesis_id] = next_value
    return adjusted


def build_phase4_validation_report(
    validation_rows: Iterable[Mapping[str, object]],
    hypothesis_freeze_report: Mapping[str, object],
    *,
    hypothesis_freeze_handoff: Mapping[str, object],
    chronological_split_handoff: Mapping[str, object],
    chronological_split_handoff_sha256: str,
    validation_rows_sha256: str,
) -> dict:
    """Validate frozen discovery hypotheses on the unseen validation slice."""

    freeze_report = dict(hypothesis_freeze_report)
    freeze = dict(hypothesis_freeze_handoff)
    split = dict(chronological_split_handoff)
    validation_sha = _sha256(
        validation_rows_sha256,
        label="Phase-4 validation rows",
    )

    if (
        str(freeze_report.get("version") or "")
        != PHASE4_HYPOTHESIS_FREEZE_VERSION
    ):
        raise ValueError("Phase-4 validation freeze-report version changed")
    if (
        str(freeze.get("version") or "")
        != PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 validation freeze-handoff version changed")
    if (
        str(split.get("version") or "")
        != PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 validation split version changed")
    for value in (freeze_report, freeze, split):
        if value.get("phase4_checkpoint_name") != (
            PHASE4_DISCOVERY_CHECKPOINT_NAME
        ):
            raise ValueError("Phase-4 validation checkpoint changed")

    if freeze.get("phase4_hypothesis_freeze_ready") is not True:
        raise ValueError("Phase-4 hypothesis freeze is not ready")
    if freeze.get("validation_hypotheses_frozen") is not True:
        raise ValueError("Phase-4 validation hypotheses are not frozen")
    if freeze.get("multiple_testing_plan_frozen") is not True:
        raise ValueError("Phase-4 multiple-testing plan is not frozen")
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
                f"Phase-4 validation freeze violates {flag}"
            )

    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 validation split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 final-test slice is not separated")
    expected_split_sha = _sha256(
        chronological_split_handoff_sha256,
        label="Phase-4 validation split handoff",
    )
    if _sha256(
        freeze.get("chronological_split_handoff_sha256"),
        label="Phase-4 hypothesis-freeze split linkage",
    ) != expected_split_sha:
        raise ValueError(
            "Phase-4 validation hypothesis-freeze/split linkage drift"
        )
    if validation_sha != _sha256(
        split.get("validation_split_rows_sha256"),
        label="Phase-4 split validation rows",
    ):
        raise ValueError("Phase-4 validation row SHA drift")

    normalized_plan = freeze_report.get(
        "normalized_hypothesis_plan"
    )
    if not isinstance(normalized_plan, Mapping):
        raise ValueError("Phase-4 validation hypothesis plan is missing")
    if _sha256(
        freeze.get("hypothesis_plan_sha256"),
        label="Phase-4 validation hypothesis plan",
    ) != _sha256(
        freeze_report.get("hypothesis_plan_sha256"),
        label="Phase-4 validation freeze-report plan",
    ):
        raise ValueError("Phase-4 validation hypothesis-plan SHA drift")
    plan_hypotheses = normalized_plan.get("hypotheses")
    if not isinstance(plan_hypotheses, list):
        raise ValueError(
            "Phase-4 validation hypothesis rows are missing"
        )
    if len(plan_hypotheses) != int(
        freeze.get("validation_hypotheses", -1)
    ):
        raise ValueError(
            "Phase-4 validation hypothesis count drift"
        )
    method = str(freeze.get("multiple_testing_method") or "")
    if method != "benjamini_hochberg":
        raise ValueError(
            "Phase-4 validation multiple-testing method changed"
        )
    alpha = _decimal(
        freeze.get("false_discovery_rate_alpha"),
        label="Phase-4 validation FDR alpha",
    )
    trials = int(freeze.get("permutation_trials", -1))
    if trials < 1000:
        raise ValueError(
            "Phase-4 validation permutation budget is invalid"
        )
    if freeze.get("permutation_test_two_sided") is not True:
        raise ValueError(
            "Phase-4 validation permutation test semantics changed"
        )

    rows: list[dict] = []
    seen = set()
    winner_rows = 0
    failure_rows = 0
    for raw in validation_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 validation row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(
                f"Phase-4 validation repeats token: {token}"
            )
        seen.add(token)
        row["token"] = token
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 validation labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 validation feature values mutated: {token}"
            )
        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(
                f"Phase-4 validation target invalid: {token}"
            )
        winner_rows += int(target)
        failure_rows += int(not target)
        rows.append(row)

    expected_rows = int(split.get("validation_split_rows", -1))
    if len(rows) != expected_rows:
        raise ValueError("Phase-4 validation row count drift")
    if not rows or winner_rows <= 0 or failure_rows <= 0:
        raise ValueError(
            "Phase-4 validation requires winners and failures"
        )

    raw_results = []
    raw_p_values: dict[str, Decimal] = {}
    for raw_hypothesis in plan_hypotheses:
        if not isinstance(raw_hypothesis, Mapping):
            raise ValueError(
                "Phase-4 validation hypothesis row is invalid"
            )
        hypothesis = dict(raw_hypothesis)
        hypothesis_id = str(
            hypothesis.get("hypothesis_id") or ""
        )
        metric = str(hypothesis.get("effect_metric") or "")
        values, labels = _measurements(rows, hypothesis)
        winners, failures = _split_values(values, labels)
        effect = _effect(metric, winners, failures)
        seed_material = (
            validation_sha
            + str(freeze["hypothesis_plan_sha256"])
            + hypothesis_id
        )
        p_value = _permutation_p_value(
            values,
            labels,
            metric=metric,
            trials=trials,
            seed_material=seed_material,
        )
        raw_p_values[hypothesis_id] = p_value

        direction = str(
            hypothesis.get("expected_direction") or ""
        )
        direction_consistent = (
            effect > 0 if direction == "positive" else effect < 0
        )
        threshold = _decimal(
            hypothesis.get("minimum_absolute_effect"),
            label=f"{hypothesis_id} validation threshold",
        )
        raw_results.append({
            "hypothesis_id": hypothesis_id,
            "feature_id": str(hypothesis["feature_id"]),
            "family": str(hypothesis["family"]),
            "comparison_kind": str(
                hypothesis["comparison_kind"]
            ),
            "effect_metric": metric,
            "category_value": hypothesis.get("category_value"),
            "expected_direction": direction,
            "minimum_absolute_effect": _text(threshold),
            "discovery_effect": str(
                hypothesis["discovery_effect"]
            ),
            "validation_effect": _text(effect),
            "validation_observations": len(values),
            "validation_winner_observations": len(winners),
            "validation_failure_observations": len(failures),
            "direction_consistent": direction_consistent,
            "effect_threshold_met": abs(effect) >= threshold,
            "permutation_p_value": _text(p_value),
        })

    adjusted = _benjamini_hochberg(raw_p_values)
    results = []
    survived = []
    for result in raw_results:
        hypothesis_id = result["hypothesis_id"]
        q_value = adjusted[hypothesis_id]
        significant = q_value <= alpha
        survives = (
            result["direction_consistent"]
            and result["effect_threshold_met"]
            and significant
        )
        enriched = {
            **result,
            "benjamini_hochberg_q_value": _text(q_value),
            "fdr_significant": significant,
            "survived_validation": survives,
        }
        results.append(enriched)
        if survives:
            survived.append(hypothesis_id)

    return {
        "version": PHASE4_VALIDATION_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": str(
            freeze["feature_registry_sha256"]
        ),
        "discovery_split_rows_sha256": str(
            freeze["discovery_split_rows_sha256"]
        ),
        "validation_rows_sha256": validation_sha,
        "hypothesis_plan_sha256": str(
            freeze["hypothesis_plan_sha256"]
        ),
        "validation_rows": len(rows),
        "validation_winner_rows": winner_rows,
        "validation_failure_rows": failure_rows,
        "hypotheses_tested": len(results),
        "hypotheses_survived": len(survived),
        "surviving_hypothesis_ids": sorted(survived),
        "hypothesis_results": results,
        "multiple_testing_method": method,
        "false_discovery_rate_alpha": _text(alpha),
        "permutation_trials": trials,
        "permutation_seed_rule": str(
            freeze["permutation_seed_rule"]
        ),
        "permutation_test_two_sided": True,
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


def build_phase4_validation_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    hypothesis_freeze_handoff_sha256: str,
    chronological_split_handoff_sha256: str,
) -> dict:
    """Bind unseen validation without touching the final-test slice."""

    row = dict(report)
    if (
        str(row.get("version") or "")
        != PHASE4_VALIDATION_REPORT_VERSION
    ):
        raise ValueError("Phase-4 validation handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 validation checkpoint changed")
    for flag in (
        "all_frozen_hypotheses_tested",
        "validation_rows_consumed",
        "unseen_slice_validation_complete",
        "multiple_testing_control_applied",
        "phase4_validation_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(
                f"Phase-4 validation handoff lacks {flag}"
            )
    for flag in (
        "final_test_rows_consumed",
        "automatic_feature_ranking_used",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(
                f"Phase-4 validation handoff violates {flag}"
            )

    return {
        "version": PHASE4_VALIDATION_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 validation registry",
        ),
        "discovery_split_rows_sha256": _sha256(
            row.get("discovery_split_rows_sha256"),
            label="Phase-4 validation discovery rows",
        ),
        "validation_rows_sha256": _sha256(
            row.get("validation_rows_sha256"),
            label="Phase-4 validation rows",
        ),
        "hypothesis_plan_sha256": _sha256(
            row.get("hypothesis_plan_sha256"),
            label="Phase-4 validation hypothesis plan",
        ),
        "validation_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 validation report",
        ),
        "hypothesis_freeze_handoff_sha256": _sha256(
            hypothesis_freeze_handoff_sha256,
            label="Phase-4 hypothesis-freeze handoff",
        ),
        "chronological_split_handoff_sha256": _sha256(
            chronological_split_handoff_sha256,
            label="Phase-4 validation split handoff",
        ),
        "validation_rows": int(row["validation_rows"]),
        "validation_winner_rows": int(
            row["validation_winner_rows"]
        ),
        "validation_failure_rows": int(
            row["validation_failure_rows"]
        ),
        "hypotheses_tested": int(row["hypotheses_tested"]),
        "hypotheses_survived": int(
            row["hypotheses_survived"]
        ),
        "surviving_hypothesis_ids": list(
            row["surviving_hypothesis_ids"]
        ),
        "multiple_testing_method": str(
            row["multiple_testing_method"]
        ),
        "false_discovery_rate_alpha": str(
            row["false_discovery_rate_alpha"]
        ),
        "permutation_trials": int(row["permutation_trials"]),
        "permutation_seed_rule": str(
            row["permutation_seed_rule"]
        ),
        "permutation_test_two_sided": True,
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
