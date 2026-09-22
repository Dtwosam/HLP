"""Discovery-only nonlinear numeric feature diagnostics for Phase 4."""

from __future__ import annotations

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


PHASE4_NONLINEAR_REPORT_VERSION = "phase4-nonlinear-report-v1"
PHASE4_NONLINEAR_HANDOFF_VERSION = "phase4-nonlinear-handoff-v1"
DEFAULT_BIN_COUNT = 4


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


def _quantile_cut_points(
    values: list[Decimal],
    *,
    bin_count: int,
) -> list[Decimal]:
    if not values:
        return []
    ordered = sorted(values)
    points = []
    total = len(ordered)
    for boundary in range(1, bin_count):
        index = (total * boundary + bin_count - 1) // bin_count - 1
        index = max(0, min(index, total - 1))
        points.append(ordered[index])
    unique = []
    for point in points:
        if not unique or point != unique[-1]:
            unique.append(point)
    return unique


def _bin_index(value: Decimal, cut_points: list[Decimal]) -> int:
    for index, point in enumerate(cut_points):
        if value <= point:
            return index
    return len(cut_points)


def _shape(rates: list[Decimal]) -> str:
    if len(rates) <= 1:
        return "insufficient_bins"
    increases = [
        rates[index] < rates[index + 1]
        for index in range(len(rates) - 1)
    ]
    decreases = [
        rates[index] > rates[index + 1]
        for index in range(len(rates) - 1)
    ]
    if not any(increases) and not any(decreases):
        return "flat"
    if all(
        rates[index] <= rates[index + 1]
        for index in range(len(rates) - 1)
    ):
        return "increasing"
    if all(
        rates[index] >= rates[index + 1]
        for index in range(len(rates) - 1)
    ):
        return "decreasing"
    return "non_monotonic"


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
        raise ValueError("Phase-4 nonlinear split version changed")
    if split.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 nonlinear checkpoint changed")
    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 nonlinear split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 nonlinear final test is not separated")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if split.get(flag) is not False:
            raise ValueError(f"Phase-4 nonlinear split violates {flag}")
    if _sha256(
        split.get("feature_registry_sha256"),
        label="Phase-4 nonlinear registry",
    ) != registry_sha256:
        raise ValueError("Phase-4 nonlinear registry drift")
    return split


def build_phase4_nonlinear_report(
    discovery_rows: Iterable[Mapping[str, object]],
    feature_registry: Iterable[Mapping[str, object]],
    *,
    chronological_split_handoff: Mapping[str, object],
    bin_count: int = DEFAULT_BIN_COUNT,
) -> dict:
    """Measure winner/failure frequency across deterministic numeric bins."""

    bins_requested = int(bin_count)
    if bins_requested < 3 or bins_requested > 10:
        raise ValueError("Phase-4 nonlinear bin count must be 3..10")

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
    numeric_ids = [
        feature_id
        for feature_id in feature_ids
        if definitions[feature_id]["dtype"]
        in {"decimal_string", "integer"}
    ]
    excluded = [
        {
            "feature_id": feature_id,
            "dtype": str(definitions[feature_id]["dtype"]),
            "reason": "non_numeric_dtype",
        }
        for feature_id in feature_ids
        if feature_id not in numeric_ids
    ]
    states = {
        feature_id: {
            "observations": [],
            "missing": 0,
        }
        for feature_id in numeric_ids
    }
    seen = set()
    winner_rows = 0
    failure_rows = 0

    for raw in discovery_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 nonlinear row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 nonlinear repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 nonlinear labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 nonlinear feature row was mutated: {token}"
            )
        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(
                f"Phase-4 nonlinear target is invalid: {token}"
            )
        winner_rows += int(target)
        failure_rows += int(not target)

        values = row.get("feature_values")
        if not isinstance(values, Mapping) or set(values) != set(feature_ids):
            raise ValueError(
                f"Phase-4 nonlinear feature coverage drift: {token}"
            )
        missing_raw = row.get("missing_feature_ids")
        if not isinstance(missing_raw, list):
            raise ValueError(
                f"Phase-4 nonlinear missingness is invalid: {token}"
            )
        missing = {str(value) for value in missing_raw}
        if missing != {
            feature_id
            for feature_id, value in values.items()
            if value is None
        }:
            raise ValueError(
                f"Phase-4 nonlinear missing/null drift: {token}"
            )

        for feature_id in numeric_ids:
            value = values[feature_id]
            state = states[feature_id]
            if value is None:
                state["missing"] += 1
                continue
            dtype = str(definitions[feature_id]["dtype"])
            if dtype == "decimal_string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"{feature_id} must remain a decimal string"
                    )
                number = _decimal(
                    value,
                    label=f"{token} {feature_id}",
                )
            else:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(
                        f"{feature_id} must remain an integer"
                    )
                number = Decimal(value)
            state["observations"].append((number, target))

    subjects = len(seen)
    if subjects != int(split.get("discovery_split_rows", -1)):
        raise ValueError("Phase-4 nonlinear discovery-slice count drift")
    if subjects <= 0 or winner_rows <= 0 or failure_rows <= 0:
        raise ValueError(
            "Phase-4 nonlinear requires winners and failures"
        )

    base_rate = Decimal(winner_rows) / Decimal(subjects)
    reports = []
    for feature_id in numeric_ids:
        state = states[feature_id]
        observations = list(state["observations"])
        values = [value for value, _ in observations]
        cut_points = _quantile_cut_points(
            values,
            bin_count=bins_requested,
        )
        bucket_count = len(cut_points) + 1
        buckets = [
            {
                "rows": 0,
                "winner_rows": 0,
                "failure_rows": 0,
                "minimum_value": None,
                "maximum_value": None,
            }
            for _ in range(bucket_count)
        ]
        for value, target in observations:
            index = _bin_index(value, cut_points)
            bucket = buckets[index]
            bucket["rows"] += 1
            bucket["winner_rows"] += int(target)
            bucket["failure_rows"] += int(not target)
            if (
                bucket["minimum_value"] is None
                or value < bucket["minimum_value"]
            ):
                bucket["minimum_value"] = value
            if (
                bucket["maximum_value"] is None
                or value > bucket["maximum_value"]
            ):
                bucket["maximum_value"] = value

        normalized_bins = []
        observed_rates = []
        for index, bucket in enumerate(buckets):
            rows = int(bucket["rows"])
            winner_rate = _share(
                int(bucket["winner_rows"]),
                rows,
            )
            lift = None
            if winner_rate is not None:
                with localcontext() as context:
                    context.prec = 80
                    lift = _text(
                        Decimal(winner_rate) - base_rate
                    )
                observed_rates.append(Decimal(winner_rate))
            normalized_bins.append({
                "bin_index": index,
                "lower_bound_exclusive": (
                    None
                    if index == 0
                    else _text(cut_points[index - 1])
                ),
                "upper_bound_inclusive": (
                    None
                    if index >= len(cut_points)
                    else _text(cut_points[index])
                ),
                "rows": rows,
                "winner_rows": int(bucket["winner_rows"]),
                "failure_rows": int(bucket["failure_rows"]),
                "winner_rate": winner_rate,
                "winner_rate_minus_base_rate": lift,
                "minimum_observed_value": (
                    None
                    if bucket["minimum_value"] is None
                    else _text(bucket["minimum_value"])
                ),
                "maximum_observed_value": (
                    None
                    if bucket["maximum_value"] is None
                    else _text(bucket["maximum_value"])
                ),
            })

        reports.append({
            "feature_id": feature_id,
            "family": str(definitions[feature_id]["family"]),
            "dtype": str(definitions[feature_id]["dtype"]),
            "observed_rows": len(observations),
            "missing_rows": int(state["missing"]),
            "missing_rate": _share(
                int(state["missing"]),
                subjects,
            ),
            "requested_bins": bins_requested,
            "effective_bins": bucket_count,
            "cut_points": [_text(value) for value in cut_points],
            "bins": normalized_bins,
            "shape": _shape(observed_rates),
            "nonlinear_structure_examined": True,
        })

    shape_counts = {}
    for report in reports:
        shape = str(report["shape"])
        shape_counts[shape] = shape_counts.get(shape, 0) + 1

    return {
        "version": PHASE4_NONLINEAR_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": registry_sha,
        "discovery_split_rows_sha256": _sha256(
            split.get("discovery_split_rows_sha256"),
            label="Phase-4 nonlinear discovery rows",
        ),
        "analysis_subjects": subjects,
        "winner_rows": winner_rows,
        "failure_rows": failure_rows,
        "winner_base_rate": _text(base_rate),
        "requested_bins": bins_requested,
        "numeric_features_analyzed": len(reports),
        "non_numeric_features_excluded": len(excluded),
        "excluded_features": excluded,
        "shape_counts": shape_counts,
        "feature_reports": reports,
        "nonlinear_relationships_examined": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_thresholds_promoted": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_nonlinear_report_ready": True,
    }


def build_phase4_nonlinear_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    chronological_split_handoff_sha256: str,
    feature_registry_file_sha256: str,
) -> dict:
    """Bind nonlinear discovery diagnostics without selecting thresholds."""

    row = dict(report)
    if str(row.get("version") or "") != PHASE4_NONLINEAR_REPORT_VERSION:
        raise ValueError("Phase-4 nonlinear handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 nonlinear checkpoint changed")
    for flag in (
        "nonlinear_relationships_examined",
        "phase4_nonlinear_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 nonlinear handoff lacks {flag}")
    for flag in (
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "candidate_thresholds_promoted",
        "candidate_features_ranked",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 nonlinear handoff violates {flag}")

    return {
        "version": PHASE4_NONLINEAR_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 nonlinear registry",
        ),
        "feature_registry_file_sha256": _sha256(
            feature_registry_file_sha256,
            label="Phase-4 nonlinear registry file",
        ),
        "discovery_split_rows_sha256": _sha256(
            row.get("discovery_split_rows_sha256"),
            label="Phase-4 nonlinear discovery rows",
        ),
        "nonlinear_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 nonlinear report",
        ),
        "chronological_split_handoff_sha256": _sha256(
            chronological_split_handoff_sha256,
            label="Phase-4 nonlinear split handoff",
        ),
        "analysis_subjects": int(row["analysis_subjects"]),
        "winner_rows": int(row["winner_rows"]),
        "failure_rows": int(row["failure_rows"]),
        "requested_bins": int(row["requested_bins"]),
        "numeric_features_analyzed": int(
            row["numeric_features_analyzed"]
        ),
        "non_numeric_features_excluded": int(
            row["non_numeric_features_excluded"]
        ),
        "shape_counts": dict(row["shape_counts"]),
        "nonlinear_relationships_examined": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_thresholds_promoted": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_nonlinear_report_ready": True,
    }
