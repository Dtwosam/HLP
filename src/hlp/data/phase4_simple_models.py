"""Transparent discovery-fit simple models for Phase-4 exploration."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.phase4_chronological_split import (
    PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION,
)
from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
    PHASE4_DISCOVERY_ENTRY_VERSION,
)


PHASE4_SIMPLE_MODEL_REPORT_VERSION = "phase4-simple-model-report-v1"
PHASE4_SIMPLE_MODEL_HANDOFF_VERSION = "phase4-simple-model-handoff-v1"
LOGISTIC_ITERATIONS = 150
LOGISTIC_LEARNING_RATE = 0.1
LOGISTIC_L2 = 0.01
TREE_MAX_DEPTH = 2
TREE_MIN_LEAF = 2


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


def _text(value: float | Decimal) -> str:
    if isinstance(value, Decimal):
        with localcontext() as context:
            context.prec = 80
            if value == 0:
                return "0"
            return format(value.normalize(context=context), "f")
    if not math.isfinite(value):
        raise ValueError("Phase-4 model metric is not finite")
    if abs(value) < 1e-15:
        return "0"
    return format(value, ".15g")


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Phase-4 model median has no values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _validate_split(
    handoff: Mapping[str, object],
    *,
    registry_sha256: str,
    discovery_rows_sha256: str,
    validation_rows_sha256: str,
) -> dict:
    split = dict(handoff)
    if (
        str(split.get("version") or "")
        != PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 simple-model split version changed")
    if split.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 simple-model checkpoint changed")
    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 simple-model split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 simple-model final test is not separated")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if split.get(flag) is not False:
            raise ValueError(f"Phase-4 simple-model split violates {flag}")
    if _sha256(
        split.get("feature_registry_sha256"),
        label="Phase-4 simple-model registry",
    ) != registry_sha256:
        raise ValueError("Phase-4 simple-model registry drift")
    if _sha256(
        split.get("discovery_split_rows_sha256"),
        label="Phase-4 simple-model discovery split",
    ) != _sha256(
        discovery_rows_sha256,
        label="Phase-4 simple-model discovery rows",
    ):
        raise ValueError("Phase-4 simple-model discovery row SHA drift")
    if _sha256(
        split.get("validation_split_rows_sha256"),
        label="Phase-4 simple-model validation split",
    ) != _sha256(
        validation_rows_sha256,
        label="Phase-4 simple-model validation rows",
    ):
        raise ValueError("Phase-4 simple-model validation row SHA drift")
    return split


def _validate_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    feature_ids: list[str],
    definitions: Mapping[str, Mapping[str, object]],
    label: str,
) -> list[dict]:
    normalized = []
    seen = set()
    for raw in rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError(f"Phase-4 {label} row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 {label} repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 {label} labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 {label} feature row was mutated: {token}"
            )
        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(
                f"Phase-4 {label} target is invalid: {token}"
            )
        values = row.get("feature_values")
        if not isinstance(values, Mapping) or set(values) != set(feature_ids):
            raise ValueError(
                f"Phase-4 {label} feature coverage drift: {token}"
            )
        missing_raw = row.get("missing_feature_ids")
        if not isinstance(missing_raw, list):
            raise ValueError(
                f"Phase-4 {label} missingness is invalid: {token}"
            )
        missing = {str(value) for value in missing_raw}
        if missing != {
            feature_id
            for feature_id, value in values.items()
            if value is None
        }:
            raise ValueError(
                f"Phase-4 {label} missing/null drift: {token}"
            )

        normalized_values = {}
        for feature_id in feature_ids:
            value = values[feature_id]
            if value is None:
                normalized_values[feature_id] = None
                continue
            dtype = str(definitions[feature_id]["dtype"])
            if dtype == "decimal_string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"{feature_id} must remain a decimal string"
                    )
                normalized_values[feature_id] = _decimal(
                    value,
                    label=f"{token} {feature_id}",
                )
            elif dtype == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(
                        f"{feature_id} must remain an integer"
                    )
                normalized_values[feature_id] = Decimal(value)
            elif dtype == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(
                        f"{feature_id} must remain boolean"
                    )
                normalized_values[feature_id] = value
            elif dtype == "string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"{feature_id} must remain a string"
                    )
                normalized_values[feature_id] = value
            else:
                raise ValueError(
                    f"Phase-4 simple-model dtype unsupported: {dtype}"
                )
        normalized.append({
            "token": token,
            "target": bool(target),
            "values": normalized_values,
        })
    return normalized


def _fit_preprocessing(
    rows: list[dict],
    *,
    eligible: list[str],
    definitions: Mapping[str, Mapping[str, object]],
) -> tuple[dict, list[str]]:
    rules = {}
    predictors = []
    for feature_id in eligible:
        dtype = str(definitions[feature_id]["dtype"])
        active_name = f"{feature_id}__active"
        missing_name = f"{feature_id}__missing"
        predictors.extend((active_name, missing_name))
        if dtype == "boolean":
            rules[feature_id] = {
                "dtype": dtype,
                "active_rule": "value_is_true",
                "threshold": None,
                "active_predictor": active_name,
                "missing_predictor": missing_name,
            }
            continue
        observed = [
            row["values"][feature_id]
            for row in rows
            if row["values"][feature_id] is not None
        ]
        threshold = None if not observed else _median(observed)
        rules[feature_id] = {
            "dtype": dtype,
            "active_rule": (
                "unavailable_no_discovery_values"
                if threshold is None
                else "value_greater_than_or_equal_to_discovery_median"
            ),
            "threshold": (
                None if threshold is None else _text(threshold)
            ),
            "active_predictor": active_name,
            "missing_predictor": missing_name,
        }
    return rules, sorted(predictors)


def _encode(
    rows: list[dict],
    *,
    eligible: list[str],
    rules: Mapping[str, Mapping[str, object]],
    predictors: list[str],
) -> tuple[list[list[float]], list[int]]:
    matrices = []
    targets = []
    for row in rows:
        encoded = {predictor: 0.0 for predictor in predictors}
        for feature_id in eligible:
            value = row["values"][feature_id]
            rule = rules[feature_id]
            active_name = str(rule["active_predictor"])
            missing_name = str(rule["missing_predictor"])
            if value is None:
                encoded[missing_name] = 1.0
                continue
            if rule["dtype"] == "boolean":
                encoded[active_name] = 1.0 if bool(value) else 0.0
            else:
                threshold_text = rule["threshold"]
                if threshold_text is None:
                    encoded[missing_name] = 1.0
                else:
                    threshold = Decimal(str(threshold_text))
                    encoded[active_name] = (
                        1.0 if value >= threshold else 0.0
                    )
        matrices.append([encoded[name] for name in predictors])
        targets.append(1 if row["target"] else 0)
    return matrices, targets


def _sigmoid(value: float) -> float:
    if value >= 0:
        exp_value = math.exp(-value)
        return 1.0 / (1.0 + exp_value)
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def _fit_logistic(
    matrix: list[list[float]],
    targets: list[int],
    *,
    predictor_names: list[str],
) -> dict:
    total = len(targets)
    if total <= 0:
        raise ValueError("Phase-4 logistic training set is empty")
    positives = sum(targets)
    rate = min(max(positives / total, 1e-6), 1 - 1e-6)
    intercept = math.log(rate / (1.0 - rate))
    coefficients = [0.0 for _ in predictor_names]

    for _ in range(LOGISTIC_ITERATIONS):
        gradient_intercept = 0.0
        gradients = [0.0 for _ in coefficients]
        for features, target in zip(matrix, targets):
            score = intercept + sum(
                coefficient * value
                for coefficient, value in zip(coefficients, features)
            )
            error = _sigmoid(score) - target
            gradient_intercept += error
            for index, value in enumerate(features):
                gradients[index] += error * value
        gradient_intercept /= total
        intercept -= LOGISTIC_LEARNING_RATE * gradient_intercept
        for index in range(len(coefficients)):
            gradient = gradients[index] / total
            gradient += LOGISTIC_L2 * coefficients[index]
            coefficients[index] -= LOGISTIC_LEARNING_RATE * gradient

    return {
        "model": "l2_logistic_binary_features",
        "iterations": LOGISTIC_ITERATIONS,
        "learning_rate": _text(LOGISTIC_LEARNING_RATE),
        "l2_penalty": _text(LOGISTIC_L2),
        "intercept": _text(intercept),
        "coefficients": [
            {
                "predictor": name,
                "coefficient": _text(coefficient),
            }
            for name, coefficient in zip(
                predictor_names,
                coefficients,
            )
        ],
    }


def _predict_logistic(
    model: Mapping[str, object],
    matrix: list[list[float]],
    *,
    predictor_names: list[str],
) -> list[float]:
    coefficient_rows = model.get("coefficients")
    if not isinstance(coefficient_rows, list):
        raise ValueError("Phase-4 logistic coefficients are missing")
    coefficients = {
        str(row["predictor"]): float(row["coefficient"])
        for row in coefficient_rows
    }
    intercept = float(model["intercept"])
    return [
        _sigmoid(
            intercept
            + sum(
                coefficients[name] * value
                for name, value in zip(predictor_names, features)
            )
        )
        for features in matrix
    ]


def _gini(targets: list[int]) -> float:
    if not targets:
        return 0.0
    rate = sum(targets) / len(targets)
    return 1.0 - rate * rate - (1.0 - rate) * (1.0 - rate)


def _leaf_probability(targets: list[int]) -> float:
    return (sum(targets) + 1.0) / (len(targets) + 2.0)


def _build_tree(
    matrix: list[list[float]],
    targets: list[int],
    row_indices: list[int],
    *,
    predictor_names: list[str],
    depth: int,
    used: frozenset[int],
) -> dict:
    node_targets = [targets[index] for index in row_indices]
    node = {
        "rows": len(row_indices),
        "winner_rows": sum(node_targets),
        "probability": _text(_leaf_probability(node_targets)),
        "depth": depth,
    }
    if (
        depth >= TREE_MAX_DEPTH
        or not row_indices
        or sum(node_targets) in {0, len(node_targets)}
    ):
        return {**node, "leaf": True}

    candidates = []
    for feature_index, name in enumerate(predictor_names):
        if feature_index in used:
            continue
        left = [
            index
            for index in row_indices
            if matrix[index][feature_index] < 0.5
        ]
        right = [
            index
            for index in row_indices
            if matrix[index][feature_index] >= 0.5
        ]
        if len(left) < TREE_MIN_LEAF or len(right) < TREE_MIN_LEAF:
            continue
        score = (
            len(left) * _gini([targets[index] for index in left])
            + len(right) * _gini([targets[index] for index in right])
        ) / len(row_indices)
        candidates.append((score, name, feature_index, left, right))
    if not candidates:
        return {**node, "leaf": True}

    _, name, feature_index, left, right = min(
        candidates,
        key=lambda item: (item[0], item[1]),
    )
    next_used = used | frozenset({feature_index})
    return {
        **node,
        "leaf": False,
        "split_predictor": name,
        "left_if_zero": _build_tree(
            matrix,
            targets,
            left,
            predictor_names=predictor_names,
            depth=depth + 1,
            used=next_used,
        ),
        "right_if_one": _build_tree(
            matrix,
            targets,
            right,
            predictor_names=predictor_names,
            depth=depth + 1,
            used=next_used,
        ),
    }


def _predict_tree(
    tree: Mapping[str, object],
    matrix: list[list[float]],
    *,
    predictor_names: list[str],
) -> list[float]:
    index_by_name = {
        name: index for index, name in enumerate(predictor_names)
    }
    predictions = []
    for features in matrix:
        node = tree
        while node.get("leaf") is not True:
            name = str(node["split_predictor"])
            feature_index = index_by_name[name]
            node = (
                node["right_if_one"]
                if features[feature_index] >= 0.5
                else node["left_if_zero"]
            )
        predictions.append(float(node["probability"]))
    return predictions


def _roc_auc(probabilities: list[float], targets: list[int]) -> float | None:
    positives = sum(targets)
    negatives = len(targets) - positives
    if positives <= 0 or negatives <= 0:
        return None
    ordered = sorted(
        enumerate(probabilities),
        key=lambda item: (item[1], item[0]),
    )
    rank_sum = 0.0
    cursor = 0
    while cursor < len(ordered):
        end = cursor + 1
        while (
            end < len(ordered)
            and ordered[end][1] == ordered[cursor][1]
        ):
            end += 1
        average_rank = (cursor + 1 + end) / 2.0
        for index in range(cursor, end):
            original_index = ordered[index][0]
            if targets[original_index]:
                rank_sum += average_rank
        cursor = end
    return (
        rank_sum - positives * (positives + 1) / 2.0
    ) / (positives * negatives)


def _average_precision(
    probabilities: list[float],
    targets: list[int],
) -> float | None:
    positives = sum(targets)
    if positives <= 0:
        return None
    ordered = sorted(
        zip(probabilities, targets),
        key=lambda item: item[0],
        reverse=True,
    )
    total_seen = 0
    true_seen = 0
    previous_recall = 0.0
    area = 0.0
    cursor = 0
    while cursor < len(ordered):
        score = ordered[cursor][0]
        end = cursor
        group_true = 0
        while end < len(ordered) and ordered[end][0] == score:
            group_true += ordered[end][1]
            end += 1
        total_seen += end - cursor
        true_seen += group_true
        recall = true_seen / positives
        precision = true_seen / total_seen
        area += precision * (recall - previous_recall)
        previous_recall = recall
        cursor = end
    return area


def _metrics(
    probabilities: list[float],
    targets: list[int],
    *,
    frozen_base_rate: float,
) -> dict:
    if len(probabilities) != len(targets) or not targets:
        raise ValueError("Phase-4 model metrics input is invalid")
    epsilon = 1e-12
    brier = sum(
        (probability - target) ** 2
        for probability, target in zip(probabilities, targets)
    ) / len(targets)
    log_loss = -sum(
        target * math.log(min(max(probability, epsilon), 1 - epsilon))
        + (1 - target)
        * math.log(min(max(1 - probability, epsilon), 1 - epsilon))
        for probability, target in zip(probabilities, targets)
    ) / len(targets)
    base_probabilities = [frozen_base_rate for _ in targets]
    base_brier = sum(
        (probability - target) ** 2
        for probability, target in zip(base_probabilities, targets)
    ) / len(targets)
    base_log_loss = -sum(
        target * math.log(min(max(frozen_base_rate, epsilon), 1 - epsilon))
        + (1 - target)
        * math.log(min(max(1 - frozen_base_rate, epsilon), 1 - epsilon))
        for target in targets
    ) / len(targets)
    auc = _roc_auc(probabilities, targets)
    ap = _average_precision(probabilities, targets)
    return {
        "rows": len(targets),
        "winner_rows": sum(targets),
        "failure_rows": len(targets) - sum(targets),
        "observed_winner_rate": _text(sum(targets) / len(targets)),
        "brier_score": _text(brier),
        "log_loss": _text(log_loss),
        "roc_auc": None if auc is None else _text(auc),
        "average_precision": None if ap is None else _text(ap),
        "frozen_base_rate_brier_score": _text(base_brier),
        "frozen_base_rate_log_loss": _text(base_log_loss),
        "brier_improvement_vs_frozen_base_rate": _text(
            base_brier - brier
        ),
        "log_loss_improvement_vs_frozen_base_rate": _text(
            base_log_loss - log_loss
        ),
    }


def build_phase4_simple_model_report(
    discovery_rows: Iterable[Mapping[str, object]],
    validation_rows: Iterable[Mapping[str, object]],
    feature_registry: Iterable[Mapping[str, object]],
    *,
    chronological_split_handoff: Mapping[str, object],
    discovery_rows_sha256: str,
    validation_rows_sha256: str,
) -> dict:
    """Fit transparent baselines on discovery and evaluate on validation."""

    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)
    registry_sha = registry["registry_sha256"]
    split = _validate_split(
        chronological_split_handoff,
        registry_sha256=registry_sha,
        discovery_rows_sha256=discovery_rows_sha256,
        validation_rows_sha256=validation_rows_sha256,
    )
    definitions = {
        str(row["feature_id"]): row
        for row in registry_rows
    }
    feature_ids = sorted(definitions)
    eligible = [
        feature_id
        for feature_id in feature_ids
        if definitions[feature_id]["dtype"]
        in {"decimal_string", "integer", "boolean"}
    ]
    excluded = [
        {
            "feature_id": feature_id,
            "dtype": str(definitions[feature_id]["dtype"]),
            "reason": "categorical_string_not_encoded_in_simple_baseline",
        }
        for feature_id in feature_ids
        if feature_id not in eligible
    ]
    discovery = _validate_rows(
        discovery_rows,
        feature_ids=feature_ids,
        definitions=definitions,
        label="simple-model discovery",
    )
    validation = _validate_rows(
        validation_rows,
        feature_ids=feature_ids,
        definitions=definitions,
        label="simple-model validation",
    )
    if len(discovery) != int(split.get("discovery_split_rows", -1)):
        raise ValueError("Phase-4 simple-model discovery count drift")
    if len(validation) != int(split.get("validation_split_rows", -1)):
        raise ValueError("Phase-4 simple-model validation count drift")
    discovery_targets = [1 if row["target"] else 0 for row in discovery]
    validation_targets = [1 if row["target"] else 0 for row in validation]
    if not discovery_targets or sum(discovery_targets) in {
        0,
        len(discovery_targets),
    }:
        raise ValueError(
            "Phase-4 simple-model discovery needs both classes"
        )
    if not validation_targets or sum(validation_targets) in {
        0,
        len(validation_targets),
    }:
        raise ValueError(
            "Phase-4 simple-model validation needs both classes"
        )

    rules, predictors = _fit_preprocessing(
        discovery,
        eligible=eligible,
        definitions=definitions,
    )
    discovery_matrix, discovery_targets = _encode(
        discovery,
        eligible=eligible,
        rules=rules,
        predictors=predictors,
    )
    validation_matrix, validation_targets = _encode(
        validation,
        eligible=eligible,
        rules=rules,
        predictors=predictors,
    )
    discovery_base_rate = (
        sum(discovery_targets) / len(discovery_targets)
    )

    logistic = _fit_logistic(
        discovery_matrix,
        discovery_targets,
        predictor_names=predictors,
    )
    logistic_validation = _predict_logistic(
        logistic,
        validation_matrix,
        predictor_names=predictors,
    )
    tree = _build_tree(
        discovery_matrix,
        discovery_targets,
        list(range(len(discovery_targets))),
        predictor_names=predictors,
        depth=0,
        used=frozenset(),
    )
    tree_validation = _predict_tree(
        tree,
        validation_matrix,
        predictor_names=predictors,
    )

    preprocessing = [
        {
            "feature_id": feature_id,
            **dict(rules[feature_id]),
        }
        for feature_id in sorted(rules)
    ]
    return {
        "version": PHASE4_SIMPLE_MODEL_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": registry_sha,
        "discovery_split_rows_sha256": _sha256(
            discovery_rows_sha256,
            label="Phase-4 simple-model discovery rows",
        ),
        "validation_rows_sha256": _sha256(
            validation_rows_sha256,
            label="Phase-4 simple-model validation rows",
        ),
        "discovery_rows": len(discovery),
        "validation_rows": len(validation),
        "discovery_winner_rows": sum(discovery_targets),
        "validation_winner_rows": sum(validation_targets),
        "discovery_base_rate": _text(discovery_base_rate),
        "eligible_features": len(eligible),
        "excluded_features": excluded,
        "excluded_feature_count": len(excluded),
        "predictor_count": len(predictors),
        "preprocessing_rules": preprocessing,
        "logistic_model": logistic,
        "logistic_validation_metrics": _metrics(
            logistic_validation,
            validation_targets,
            frozen_base_rate=discovery_base_rate,
        ),
        "tree_model": {
            "model": "binary_tree",
            "max_depth": TREE_MAX_DEPTH,
            "min_leaf": TREE_MIN_LEAF,
            "tree": tree,
        },
        "tree_validation_metrics": _metrics(
            tree_validation,
            validation_targets,
            frozen_base_rate=discovery_base_rate,
        ),
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


def build_phase4_simple_model_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    chronological_split_handoff_sha256: str,
    feature_registry_file_sha256: str,
) -> dict:
    """Bind exploratory validation metrics without selecting a production model."""

    row = dict(report)
    if (
        str(row.get("version") or "")
        != PHASE4_SIMPLE_MODEL_REPORT_VERSION
    ):
        raise ValueError("Phase-4 simple-model handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 simple-model checkpoint changed")
    for flag in (
        "preprocessing_fit_on_discovery_only",
        "models_fit_on_discovery_only",
        "validation_rows_consumed",
        "transparent_simple_models_examined",
        "automatic_model_feature_selection_used",
        "phase4_simple_model_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 simple-model handoff lacks {flag}")
    for flag in (
        "final_test_rows_consumed",
        "production_model_selected",
        "signal_threshold_selected",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(
                f"Phase-4 simple-model handoff violates {flag}"
            )

    return {
        "version": PHASE4_SIMPLE_MODEL_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 simple-model registry",
        ),
        "feature_registry_file_sha256": _sha256(
            feature_registry_file_sha256,
            label="Phase-4 simple-model registry file",
        ),
        "discovery_split_rows_sha256": _sha256(
            row.get("discovery_split_rows_sha256"),
            label="Phase-4 simple-model discovery rows",
        ),
        "validation_rows_sha256": _sha256(
            row.get("validation_rows_sha256"),
            label="Phase-4 simple-model validation rows",
        ),
        "simple_model_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 simple-model report",
        ),
        "chronological_split_handoff_sha256": _sha256(
            chronological_split_handoff_sha256,
            label="Phase-4 simple-model split handoff",
        ),
        "discovery_rows": int(row["discovery_rows"]),
        "validation_rows": int(row["validation_rows"]),
        "eligible_features": int(row["eligible_features"]),
        "excluded_feature_count": int(row["excluded_feature_count"]),
        "predictor_count": int(row["predictor_count"]),
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
