"""Discovery-only pairwise feature interaction diagnostics for Phase 4."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from itertools import combinations
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


PHASE4_INTERACTION_REPORT_VERSION = "phase4-interaction-report-v1"
PHASE4_INTERACTION_HANDOFF_VERSION = "phase4-interaction-handoff-v1"


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


def _share(numerator: int, denominator: int) -> str | None:
    if denominator <= 0:
        return None
    with localcontext() as context:
        context.prec = 80
        return _text(Decimal(numerator) / Decimal(denominator))


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Phase-4 interaction median has no values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _validate_split(
    handoff: Mapping[str, object],
    *,
    registry_sha256: str,
) -> dict:
    split = dict(handoff)
    if (
        str(split.get("version") or "")
        != PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 interaction split version changed")
    if split.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 interaction checkpoint changed")
    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 interaction split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 interaction final test is not separated")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if split.get(flag) is not False:
            raise ValueError(f"Phase-4 interaction split violates {flag}")
    if _sha256(
        split.get("feature_registry_sha256"),
        label="Phase-4 interaction registry",
    ) != registry_sha256:
        raise ValueError("Phase-4 interaction registry drift")
    return split


def build_phase4_interaction_report(
    discovery_rows: Iterable[Mapping[str, object]],
    feature_registry: Iterable[Mapping[str, object]],
    *,
    chronological_split_handoff: Mapping[str, object],
) -> dict:
    """Measure pairwise binary interactions without selecting any pair."""

    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)
    registry_sha = registry["registry_sha256"]
    split = _validate_split(
        chronological_split_handoff,
        registry_sha256=registry_sha,
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
            "reason": "categorical_string_not_binary_encoded",
        }
        for feature_id in feature_ids
        if feature_id not in eligible
    ]

    rows = []
    numeric_values = {
        feature_id: []
        for feature_id in eligible
        if definitions[feature_id]["dtype"]
        in {"decimal_string", "integer"}
    }
    seen = set()
    winners = 0
    failures = 0
    for raw in discovery_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 interaction row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 interaction repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 interaction labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 interaction feature row was mutated: {token}"
            )
        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(
                f"Phase-4 interaction target is invalid: {token}"
            )
        winners += int(target)
        failures += int(not target)
        values = row.get("feature_values")
        if not isinstance(values, Mapping) or set(values) != set(feature_ids):
            raise ValueError(
                f"Phase-4 interaction feature coverage drift: {token}"
            )
        missing_raw = row.get("missing_feature_ids")
        if not isinstance(missing_raw, list):
            raise ValueError(
                f"Phase-4 interaction missingness is invalid: {token}"
            )
        missing = {str(value) for value in missing_raw}
        if missing != {
            feature_id
            for feature_id, value in values.items()
            if value is None
        }:
            raise ValueError(
                f"Phase-4 interaction missing/null drift: {token}"
            )

        normalized = {}
        for feature_id in eligible:
            value = values[feature_id]
            if value is None:
                normalized[feature_id] = None
                continue
            dtype = str(definitions[feature_id]["dtype"])
            if dtype == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(
                        f"{feature_id} must remain boolean"
                    )
                normalized[feature_id] = value
            elif dtype == "decimal_string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"{feature_id} must remain a decimal string"
                    )
                number = _decimal(
                    value,
                    label=f"{token} {feature_id}",
                )
                normalized[feature_id] = number
                numeric_values[feature_id].append(number)
            else:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(
                        f"{feature_id} must remain an integer"
                    )
                number = Decimal(value)
                normalized[feature_id] = number
                numeric_values[feature_id].append(number)
        rows.append((target, normalized))

    subjects = len(rows)
    if subjects != int(split.get("discovery_split_rows", -1)):
        raise ValueError("Phase-4 interaction discovery-slice count drift")
    if subjects <= 0 or winners <= 0 or failures <= 0:
        raise ValueError(
            "Phase-4 interaction requires winners and failures"
        )

    activation_rules = {}
    thresholds = {}
    for feature_id in eligible:
        dtype = str(definitions[feature_id]["dtype"])
        if dtype == "boolean":
            activation_rules[feature_id] = "value_is_true"
        else:
            values = numeric_values[feature_id]
            if not values:
                activation_rules[feature_id] = (
                    "unavailable_no_observed_values"
                )
                thresholds[feature_id] = None
            else:
                threshold = _median(values)
                activation_rules[feature_id] = (
                    "value_greater_than_or_equal_to_discovery_median"
                )
                thresholds[feature_id] = threshold

    encoded_rows = []
    for target, values in rows:
        encoded = {}
        for feature_id in eligible:
            value = values[feature_id]
            if value is None:
                encoded[feature_id] = None
                continue
            dtype = str(definitions[feature_id]["dtype"])
            if dtype == "boolean":
                encoded[feature_id] = bool(value)
            else:
                threshold = thresholds[feature_id]
                if threshold is None:
                    encoded[feature_id] = None
                else:
                    encoded[feature_id] = value >= threshold
        encoded_rows.append((target, encoded))

    base_rate = Decimal(winners) / Decimal(subjects)
    pair_reports = []
    same_family_pairs = 0
    cross_family_pairs = 0
    effect_available_pairs = 0
    for left_id, right_id in combinations(eligible, 2):
        cells = {
            "00": {"rows": 0, "winner_rows": 0},
            "01": {"rows": 0, "winner_rows": 0},
            "10": {"rows": 0, "winner_rows": 0},
            "11": {"rows": 0, "winner_rows": 0},
        }
        missing_rows = 0
        for target, encoded in encoded_rows:
            left = encoded[left_id]
            right = encoded[right_id]
            if left is None or right is None:
                missing_rows += 1
                continue
            key = f"{int(bool(left))}{int(bool(right))}"
            cells[key]["rows"] += 1
            cells[key]["winner_rows"] += int(target)

        normalized_cells = {}
        rates = {}
        for key in ("00", "01", "10", "11"):
            total = int(cells[key]["rows"])
            wins = int(cells[key]["winner_rows"])
            rate = _share(wins, total)
            normalized_cells[key] = {
                "rows": total,
                "winner_rows": wins,
                "failure_rows": total - wins,
                "winner_rate": rate,
            }
            rates[key] = None if rate is None else Decimal(rate)

        available = all(rates[key] is not None for key in rates)
        interaction_contrast = None
        if available:
            with localcontext() as context:
                context.prec = 80
                interaction_contrast = _text(
                    rates["11"]
                    - rates["10"]
                    - rates["01"]
                    + rates["00"]
                )
            effect_available_pairs += 1

        joint_lift = None
        if rates["11"] is not None:
            with localcontext() as context:
                context.prec = 80
                joint_lift = _text(rates["11"] - base_rate)

        left_family = str(definitions[left_id]["family"])
        right_family = str(definitions[right_id]["family"])
        if left_family == right_family:
            same_family_pairs += 1
        else:
            cross_family_pairs += 1
        pair_reports.append({
            "left_feature_id": left_id,
            "right_feature_id": right_id,
            "left_family": left_family,
            "right_family": right_family,
            "left_activation_rule": activation_rules[left_id],
            "right_activation_rule": activation_rules[right_id],
            "left_threshold": (
                None
                if thresholds.get(left_id) is None
                else _text(thresholds[left_id])
            ),
            "right_threshold": (
                None
                if thresholds.get(right_id) is None
                else _text(thresholds[right_id])
            ),
            "observed_pair_rows": subjects - missing_rows,
            "missing_pair_rows": missing_rows,
            "cells": normalized_cells,
            "interaction_contrast_difference_in_differences": (
                interaction_contrast
            ),
            "joint_active_winner_rate_minus_base_rate": joint_lift,
            "interaction_effect_available": available,
        })

    return {
        "version": PHASE4_INTERACTION_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": registry_sha,
        "discovery_split_rows_sha256": _sha256(
            split.get("discovery_split_rows_sha256"),
            label="Phase-4 interaction discovery rows",
        ),
        "analysis_subjects": subjects,
        "winner_rows": winners,
        "failure_rows": failures,
        "winner_base_rate": _text(base_rate),
        "eligible_features": len(eligible),
        "excluded_features": excluded,
        "excluded_feature_count": len(excluded),
        "pair_count": len(pair_reports),
        "same_family_pairs": same_family_pairs,
        "cross_family_pairs": cross_family_pairs,
        "effect_available_pairs": effect_available_pairs,
        "activation_rules": [
            {
                "feature_id": feature_id,
                "rule": activation_rules[feature_id],
                "threshold": (
                    None
                    if thresholds.get(feature_id) is None
                    else _text(thresholds[feature_id])
                ),
            }
            for feature_id in eligible
        ],
        "pair_reports": pair_reports,
        "pairwise_interactions_examined": True,
        "interaction_pairs_ranked": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_interaction_report_ready": True,
    }


def build_phase4_interaction_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    chronological_split_handoff_sha256: str,
    feature_registry_file_sha256: str,
) -> dict:
    """Bind pairwise discovery diagnostics without choosing interactions."""

    row = dict(report)
    if str(row.get("version") or "") != PHASE4_INTERACTION_REPORT_VERSION:
        raise ValueError("Phase-4 interaction handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 interaction checkpoint changed")
    for flag in (
        "pairwise_interactions_examined",
        "phase4_interaction_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 interaction handoff lacks {flag}")
    for flag in (
        "interaction_pairs_ranked",
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 interaction handoff violates {flag}")

    return {
        "version": PHASE4_INTERACTION_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 interaction registry",
        ),
        "feature_registry_file_sha256": _sha256(
            feature_registry_file_sha256,
            label="Phase-4 interaction registry file",
        ),
        "discovery_split_rows_sha256": _sha256(
            row.get("discovery_split_rows_sha256"),
            label="Phase-4 interaction discovery rows",
        ),
        "interaction_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 interaction report",
        ),
        "chronological_split_handoff_sha256": _sha256(
            chronological_split_handoff_sha256,
            label="Phase-4 interaction split handoff",
        ),
        "analysis_subjects": int(row["analysis_subjects"]),
        "eligible_features": int(row["eligible_features"]),
        "excluded_feature_count": int(row["excluded_feature_count"]),
        "pair_count": int(row["pair_count"]),
        "same_family_pairs": int(row["same_family_pairs"]),
        "cross_family_pairs": int(row["cross_family_pairs"]),
        "effect_available_pairs": int(row["effect_available_pairs"]),
        "pairwise_interactions_examined": True,
        "interaction_pairs_ranked": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_interaction_report_ready": True,
    }
