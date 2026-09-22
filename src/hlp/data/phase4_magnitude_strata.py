"""Outcome-magnitude strata diagnostics for Phase-4 discovery."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
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


PHASE4_MAGNITUDE_STRATA_REPORT_VERSION = (
    "phase4-magnitude-strata-report-v1"
)
PHASE4_MAGNITUDE_STRATA_HANDOFF_VERSION = (
    "phase4-magnitude-strata-handoff-v1"
)
STRATA = (
    "failure_lt5x",
    "ordinary_5x_lt10x",
    "runner_10x_lt20x",
    "runner_20x_plus",
)


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


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _numeric_summary(values: list[Decimal]) -> dict:
    if not values:
        return {
            "observed": 0,
            "minimum": None,
            "median": None,
            "mean": None,
            "maximum": None,
        }
    with localcontext() as context:
        context.prec = 80
        mean = sum(values, Decimal(0)) / Decimal(len(values))
    median = _median(values)
    return {
        "observed": len(values),
        "minimum": _text(min(values)),
        "median": None if median is None else _text(median),
        "mean": _text(mean),
        "maximum": _text(max(values)),
    }


def _cliffs_delta(
    left: list[Decimal],
    right: list[Decimal],
) -> str | None:
    if not left or not right:
        return None
    ordered_right = sorted(right)
    dominance = 0
    for value in left:
        lower = bisect_left(ordered_right, value)
        upper = bisect_right(ordered_right, value)
        dominance += lower
        dominance -= len(ordered_right) - upper
    with localcontext() as context:
        context.prec = 80
        return _text(
            Decimal(dominance) / Decimal(len(left) * len(right))
        )


def _stratum(multiple: Decimal) -> str:
    if multiple < Decimal("5"):
        return "failure_lt5x"
    if multiple < Decimal("10"):
        return "ordinary_5x_lt10x"
    if multiple < Decimal("20"):
        return "runner_10x_lt20x"
    return "runner_20x_plus"


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
        raise ValueError("Phase-4 magnitude split version changed")
    if split.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 magnitude checkpoint changed")
    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 magnitude split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 magnitude final test is not separated")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if split.get(flag) is not False:
            raise ValueError(f"Phase-4 magnitude split violates {flag}")
    if _sha256(
        split.get("feature_registry_sha256"),
        label="Phase-4 magnitude split registry",
    ) != registry_sha256:
        raise ValueError("Phase-4 magnitude registry drift")
    return split


def build_phase4_magnitude_strata_report(
    discovery_rows: Iterable[Mapping[str, object]],
    feature_registry: Iterable[Mapping[str, object]],
    *,
    chronological_split_handoff: Mapping[str, object],
) -> dict:
    """Compare frozen features across <5x, 5x, 10x and 20x+ strata."""

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
    states = {
        feature_id: {
            stratum: {"values": [], "missing": 0}
            for stratum in STRATA
        }
        for feature_id in feature_ids
    }
    strata_counts = {stratum: 0 for stratum in STRATA}
    seen = set()

    for raw in discovery_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 magnitude row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 magnitude repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 magnitude labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 magnitude feature row was mutated: {token}"
            )
        multiple = _decimal(
            row.get("target_max_post_dump_multiple"),
            label=f"{token} Phase-4 magnitude outcome",
        )
        if multiple < 0:
            raise ValueError(
                f"Phase-4 magnitude outcome is negative: {token}"
            )
        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(
                f"Phase-4 magnitude 5x target is invalid: {token}"
            )
        if target != (multiple >= Decimal("5")):
            raise ValueError(
                f"Phase-4 magnitude target/outcome disagree: {token}"
            )
        stratum = _stratum(multiple)
        strata_counts[stratum] += 1

        values = row.get("feature_values")
        if not isinstance(values, Mapping) or set(values) != set(feature_ids):
            raise ValueError(
                f"Phase-4 magnitude feature coverage drift: {token}"
            )
        missing_raw = row.get("missing_feature_ids")
        if not isinstance(missing_raw, list):
            raise ValueError(
                f"Phase-4 magnitude missingness is invalid: {token}"
            )
        missing = {str(value) for value in missing_raw}
        if missing != {
            feature_id
            for feature_id, value in values.items()
            if value is None
        }:
            raise ValueError(
                f"Phase-4 magnitude missing/null drift: {token}"
            )

        for feature_id in feature_ids:
            value = values[feature_id]
            state = states[feature_id][stratum]
            if value is None:
                state["missing"] += 1
                continue
            dtype = str(definitions[feature_id]["dtype"])
            if dtype == "decimal_string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"{feature_id} must remain a decimal string"
                    )
                normalized = _decimal(
                    value,
                    label=f"{token} {feature_id}",
                )
            elif dtype == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(
                        f"{feature_id} must remain an integer"
                    )
                normalized = Decimal(value)
            elif dtype == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(
                        f"{feature_id} must remain boolean"
                    )
                normalized = value
            elif dtype == "string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"{feature_id} must remain a string"
                    )
                normalized = value
            else:
                raise ValueError(
                    f"Phase-4 magnitude dtype unsupported: {dtype}"
                )
            state["values"].append(normalized)

    subjects = len(seen)
    if subjects != int(split.get("discovery_split_rows", -1)):
        raise ValueError("Phase-4 magnitude discovery-slice count drift")
    if subjects <= 0:
        raise ValueError("Phase-4 magnitude discovery slice is empty")

    feature_reports = []
    ordinary = "ordinary_5x_lt10x"
    for feature_id in feature_ids:
        definition = definitions[feature_id]
        dtype = str(definition["dtype"])
        strata_report = {}
        for stratum in STRATA:
            state = states[feature_id][stratum]
            total = strata_counts[stratum]
            common = {
                "total": total,
                "observed": len(state["values"]),
                "missing": int(state["missing"]),
                "missing_rate": _share(int(state["missing"]), total),
            }
            if dtype in {"decimal_string", "integer"}:
                strata_report[stratum] = {
                    **common,
                    "distribution": _numeric_summary(
                        list(state["values"])
                    ),
                }
            elif dtype == "boolean":
                true_count = sum(
                    bool(value) for value in state["values"]
                )
                strata_report[stratum] = {
                    **common,
                    "true": true_count,
                    "false": len(state["values"]) - true_count,
                    "true_rate_among_observed": _share(
                        true_count,
                        len(state["values"]),
                    ),
                }
            else:
                counts = {}
                for value in state["values"]:
                    counts[value] = counts.get(value, 0) + 1
                strata_report[stratum] = {
                    **common,
                    "categories": [
                        {
                            "value": value,
                            "count": int(counts[value]),
                            "rate_among_observed": _share(
                                int(counts[value]),
                                len(state["values"]),
                            ),
                        }
                        for value in sorted(counts)
                    ],
                }

        comparisons = {}
        for label, left_strata in (
            (
                "runner_10x_plus_vs_ordinary_5x_lt10x",
                ("runner_10x_lt20x", "runner_20x_plus"),
            ),
            (
                "runner_20x_plus_vs_ordinary_5x_lt10x",
                ("runner_20x_plus",),
            ),
        ):
            left_values = []
            left_missing = 0
            left_total = 0
            for stratum in left_strata:
                left_values.extend(states[feature_id][stratum]["values"])
                left_missing += int(states[feature_id][stratum]["missing"])
                left_total += strata_counts[stratum]
            right_values = list(states[feature_id][ordinary]["values"])
            right_missing = int(states[feature_id][ordinary]["missing"])
            right_total = strata_counts[ordinary]

            common = {
                "left_total": left_total,
                "right_total": right_total,
                "left_missing_rate": _share(
                    left_missing,
                    left_total,
                ),
                "right_missing_rate": _share(
                    right_missing,
                    right_total,
                ),
            }
            if dtype in {"decimal_string", "integer"}:
                comparisons[label] = {
                    **common,
                    "cliffs_delta_left_vs_ordinary": _cliffs_delta(
                        list(left_values),
                        list(right_values),
                    ),
                }
            elif dtype == "boolean":
                left_rate = _share(
                    sum(bool(value) for value in left_values),
                    len(left_values),
                )
                right_rate = _share(
                    sum(bool(value) for value in right_values),
                    len(right_values),
                )
                difference = None
                if left_rate is not None and right_rate is not None:
                    difference = _text(
                        Decimal(left_rate) - Decimal(right_rate)
                    )
                comparisons[label] = {
                    **common,
                    "left_true_rate": left_rate,
                    "ordinary_true_rate": right_rate,
                    "true_rate_difference": difference,
                }
            else:
                left_counts = {}
                right_counts = {}
                for value in left_values:
                    left_counts[value] = left_counts.get(value, 0) + 1
                for value in right_values:
                    right_counts[value] = (
                        right_counts.get(value, 0) + 1
                    )
                categories = []
                for value in sorted(set(left_counts) | set(right_counts)):
                    left_rate = _share(
                        int(left_counts.get(value, 0)),
                        len(left_values),
                    )
                    right_rate = _share(
                        int(right_counts.get(value, 0)),
                        len(right_values),
                    )
                    difference = None
                    if left_rate is not None and right_rate is not None:
                        difference = _text(
                            Decimal(left_rate) - Decimal(right_rate)
                        )
                    categories.append({
                        "value": value,
                        "left_rate": left_rate,
                        "ordinary_rate": right_rate,
                        "rate_difference": difference,
                    })
                comparisons[label] = {
                    **common,
                    "categories": categories,
                }

        feature_reports.append({
            "feature_id": feature_id,
            "family": str(definition["family"]),
            "dtype": dtype,
            "missingness_policy": str(
                definition["missingness_policy"]
            ),
            "strata": strata_report,
            "runner_comparisons": comparisons,
        })

    return {
        "version": PHASE4_MAGNITUDE_STRATA_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": registry_sha,
        "discovery_split_rows_sha256": _sha256(
            split.get("discovery_split_rows_sha256"),
            label="Phase-4 magnitude discovery rows",
        ),
        "analysis_subjects": subjects,
        "strata_counts": strata_counts,
        "features_analyzed": len(feature_reports),
        "families_analyzed": len(registry["families"]),
        "feature_reports": feature_reports,
        "ordinary_5x_vs_10x_plus_compared": True,
        "ordinary_5x_vs_20x_plus_compared": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_magnitude_strata_report_ready": True,
    }


def build_phase4_magnitude_strata_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    chronological_split_handoff_sha256: str,
    feature_registry_file_sha256: str,
) -> dict:
    """Bind magnitude-strata diagnostics without touching unseen slices."""

    row = dict(report)
    if (
        str(row.get("version") or "")
        != PHASE4_MAGNITUDE_STRATA_REPORT_VERSION
    ):
        raise ValueError("Phase-4 magnitude handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 magnitude checkpoint changed")
    for flag in (
        "ordinary_5x_vs_10x_plus_compared",
        "ordinary_5x_vs_20x_plus_compared",
        "phase4_magnitude_strata_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 magnitude handoff lacks {flag}")
    for flag in (
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "candidate_features_ranked",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 magnitude handoff violates {flag}")

    return {
        "version": PHASE4_MAGNITUDE_STRATA_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 magnitude registry",
        ),
        "feature_registry_file_sha256": _sha256(
            feature_registry_file_sha256,
            label="Phase-4 magnitude registry file",
        ),
        "discovery_split_rows_sha256": _sha256(
            row.get("discovery_split_rows_sha256"),
            label="Phase-4 magnitude discovery rows",
        ),
        "magnitude_strata_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 magnitude report",
        ),
        "chronological_split_handoff_sha256": _sha256(
            chronological_split_handoff_sha256,
            label="Phase-4 magnitude split handoff",
        ),
        "analysis_subjects": int(row["analysis_subjects"]),
        "features_analyzed": int(row["features_analyzed"]),
        "families_analyzed": int(row["families_analyzed"]),
        "strata_counts": dict(row["strata_counts"]),
        "ordinary_5x_vs_10x_plus_compared": True,
        "ordinary_5x_vs_20x_plus_compared": True,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_magnitude_strata_report_ready": True,
    }
