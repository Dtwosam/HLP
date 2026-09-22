"""Deterministic winner/failure univariate diagnostics for Phase 4."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.phase4_base_rate import PHASE4_BASE_RATE_HANDOFF_VERSION
from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
    PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION,
    PHASE4_DISCOVERY_ENTRY_VERSION,
)


PHASE4_UNIVARIATE_REPORT_VERSION = "phase4-univariate-report-v1"
PHASE4_UNIVARIATE_HANDOFF_VERSION = "phase4-univariate-handoff-v1"


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
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _share(numerator: int, denominator: int) -> str | None:
    if denominator <= 0:
        return None
    with localcontext() as context:
        context.prec = 80
        return _text(Decimal(numerator) / Decimal(denominator))


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    with localcontext() as context:
        context.prec = 80
        return sum(values, Decimal(0)) / Decimal(len(values))


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _cliffs_delta(
    winners: list[Decimal],
    failures: list[Decimal],
) -> str | None:
    if not winners or not failures:
        return None
    ordered_failures = sorted(failures)
    dominance = 0
    for value in winners:
        lower = bisect_left(ordered_failures, value)
        upper = bisect_right(ordered_failures, value)
        dominance += lower
        dominance -= len(ordered_failures) - upper
    denominator = len(winners) * len(failures)
    with localcontext() as context:
        context.prec = 80
        return _text(Decimal(dominance) / Decimal(denominator))


def _numeric_summary(values: list[Decimal]) -> dict:
    mean = _mean(values)
    median = _median(values)
    return {
        "observed": len(values),
        "minimum": None if not values else _text(min(values)),
        "median": None if median is None else _text(median),
        "mean": None if mean is None else _text(mean),
        "maximum": None if not values else _text(max(values)),
    }


def _difference(
    left: Decimal | None,
    right: Decimal | None,
) -> str | None:
    if left is None or right is None:
        return None
    return _text(left - right)


def _validate_parent_handoffs(
    discovery_entry_handoff: Mapping[str, object],
    base_rate_handoff: Mapping[str, object],
    *,
    registry_sha256: str,
) -> tuple[dict, dict]:
    discovery = dict(discovery_entry_handoff)
    base = dict(base_rate_handoff)
    if (
        str(discovery.get("version") or "")
        != PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 univariate discovery-entry version changed")
    if discovery.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 univariate checkpoint name changed")
    if discovery.get("phase4_discovery_entry_ready") is not True:
        raise ValueError("Phase-4 univariate discovery entry is not ready")
    if discovery.get("labels_joined_after_feature_freeze") is not True:
        raise ValueError("Phase-4 univariate labels predate feature freeze")
    if discovery.get("feature_values_mutated") is not False:
        raise ValueError("Phase-4 univariate frozen features were mutated")
    if discovery.get("phase4_discovery_checkpoint_claimed") is not False:
        raise ValueError("Phase-4 univariate input already claimed discovery")
    if _sha256(
        discovery.get("feature_registry_sha256"),
        label="Phase-4 univariate discovery registry",
    ) != registry_sha256:
        raise ValueError("Phase-4 univariate registry SHA drift")

    if str(base.get("version") or "") != PHASE4_BASE_RATE_HANDOFF_VERSION:
        raise ValueError("Phase-4 univariate base-rate version changed")
    if base.get("phase4_base_rate_report_ready") is not True:
        raise ValueError("Phase-4 univariate base-rate report is not ready")
    if base.get("feature_relationships_tested") is not False:
        raise ValueError("Phase-4 base-rate unexpectedly tested features")
    if base.get("signal_promoted") is not False:
        raise ValueError("Phase-4 base-rate unexpectedly promoted a signal")
    if base.get("phase4_discovery_checkpoint_claimed") is not False:
        raise ValueError("Phase-4 base-rate claimed final discovery")
    if _sha256(
        base.get("feature_registry_sha256"),
        label="Phase-4 univariate base-rate registry",
    ) != registry_sha256:
        raise ValueError("Phase-4 univariate base-rate registry drift")
    if _sha256(
        base.get("discovery_rows_sha256"),
        label="Phase-4 univariate base-rate rows",
    ) != _sha256(
        discovery.get("discovery_rows_sha256"),
        label="Phase-4 univariate discovery rows",
    ):
        raise ValueError("Phase-4 univariate base-rate population drift")
    for key in (
        "discovery_subjects",
        "comeback_5x_tokens",
        "comeback_5x_base_rate",
    ):
        if str(base.get(key)) != str(discovery.get(key)):
            raise ValueError(
                f"Phase-4 univariate base-rate {key} drift"
            )
    return discovery, base


def build_phase4_univariate_report(
    discovery_rows: Iterable[Mapping[str, object]],
    feature_registry: Iterable[Mapping[str, object]],
    *,
    discovery_entry_handoff: Mapping[str, object],
    base_rate_handoff: Mapping[str, object],
) -> dict:
    """Compare every frozen feature across comeback and failure cohorts."""

    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)
    registry_sha = registry["registry_sha256"]
    discovery, _ = _validate_parent_handoffs(
        discovery_entry_handoff,
        base_rate_handoff,
        registry_sha256=registry_sha,
    )
    definitions = {
        str(row["feature_id"]): dict(row)
        for row in registry_rows
    }
    feature_ids = sorted(definitions)

    states = {
        feature_id: {
            "winner_values": [],
            "failure_values": [],
            "winner_missing": 0,
            "failure_missing": 0,
        }
        for feature_id in feature_ids
    }
    seen = set()
    winner_tokens = 0
    failure_tokens = 0

    for raw in discovery_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 univariate row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 univariate repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 univariate labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 univariate feature row was mutated: {token}"
            )
        if row.get("phase4_discovery_only") is not True:
            raise ValueError(
                f"Phase-4 univariate row is not discovery-only: {token}"
            )
        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(
                f"Phase-4 univariate target is invalid: {token}"
            )
        winner_tokens += int(target)
        failure_tokens += int(not target)

        values = row.get("feature_values")
        if not isinstance(values, Mapping) or set(values) != set(feature_ids):
            raise ValueError(
                f"Phase-4 univariate feature coverage drift: {token}"
            )
        missing_raw = row.get("missing_feature_ids")
        if not isinstance(missing_raw, list):
            raise ValueError(
                f"Phase-4 univariate missingness is invalid: {token}"
            )
        missing = {str(value) for value in missing_raw}
        if missing != {
            feature_id
            for feature_id, value in values.items()
            if value is None
        }:
            raise ValueError(
                f"Phase-4 univariate missing/null drift: {token}"
            )

        cohort = "winner" if target else "failure"
        for feature_id in feature_ids:
            definition = definitions[feature_id]
            dtype = str(definition["dtype"])
            value = values[feature_id]
            state = states[feature_id]
            if value is None:
                state[f"{cohort}_missing"] += 1
                continue

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
                    f"Phase-4 univariate dtype unsupported: {dtype}"
                )
            state[f"{cohort}_values"].append(normalized)

    subjects = len(seen)
    if subjects != int(discovery.get("discovery_subjects", -1)):
        raise ValueError("Phase-4 univariate subject count drift")
    if winner_tokens != int(discovery.get("comeback_5x_tokens", -1)):
        raise ValueError("Phase-4 univariate winner count drift")
    if failure_tokens != subjects - winner_tokens:
        raise ValueError("Phase-4 univariate failure count drift")
    if winner_tokens <= 0 or failure_tokens <= 0:
        raise ValueError(
            "Phase-4 univariate requires both winners and failures"
        )

    reports = []
    for feature_id in feature_ids:
        definition = definitions[feature_id]
        dtype = str(definition["dtype"])
        state = states[feature_id]
        winner_missing = int(state["winner_missing"])
        failure_missing = int(state["failure_missing"])
        common = {
            "feature_id": feature_id,
            "family": str(definition["family"]),
            "dtype": dtype,
            "missingness_policy": str(
                definition["missingness_policy"]
            ),
            "winner_total": winner_tokens,
            "failure_total": failure_tokens,
            "winner_observed": len(state["winner_values"]),
            "failure_observed": len(state["failure_values"]),
            "winner_missing": winner_missing,
            "failure_missing": failure_missing,
            "winner_missing_rate": _share(
                winner_missing,
                winner_tokens,
            ),
            "failure_missing_rate": _share(
                failure_missing,
                failure_tokens,
            ),
            "missing_rate_difference_winner_minus_failure": _difference(
                None
                if winner_tokens <= 0
                else Decimal(winner_missing) / Decimal(winner_tokens),
                None
                if failure_tokens <= 0
                else Decimal(failure_missing) / Decimal(failure_tokens),
            ),
        }

        if dtype in {"decimal_string", "integer"}:
            winners = list(state["winner_values"])
            failures = list(state["failure_values"])
            winner_mean = _mean(winners)
            failure_mean = _mean(failures)
            winner_median = _median(winners)
            failure_median = _median(failures)
            reports.append({
                **common,
                "comparison_kind": "numeric",
                "winner_distribution": _numeric_summary(winners),
                "failure_distribution": _numeric_summary(failures),
                "mean_difference_winner_minus_failure": _difference(
                    winner_mean,
                    failure_mean,
                ),
                "median_difference_winner_minus_failure": _difference(
                    winner_median,
                    failure_median,
                ),
                "cliffs_delta_winner_vs_failure": _cliffs_delta(
                    winners,
                    failures,
                ),
                "effect_available": bool(winners and failures),
            })
            continue

        if dtype == "boolean":
            winner_true = sum(bool(value) for value in state["winner_values"])
            failure_true = sum(
                bool(value) for value in state["failure_values"]
            )
            winner_observed = len(state["winner_values"])
            failure_observed = len(state["failure_values"])
            winner_rate = _share(winner_true, winner_observed)
            failure_rate = _share(failure_true, failure_observed)
            reports.append({
                **common,
                "comparison_kind": "boolean",
                "winner_true": winner_true,
                "winner_false": winner_observed - winner_true,
                "winner_true_rate": winner_rate,
                "failure_true": failure_true,
                "failure_false": failure_observed - failure_true,
                "failure_true_rate": failure_rate,
                "true_rate_difference_winner_minus_failure": (
                    None
                    if winner_rate is None or failure_rate is None
                    else _text(
                        Decimal(winner_rate) - Decimal(failure_rate)
                    )
                ),
                "effect_available": bool(
                    winner_observed and failure_observed
                ),
            })
            continue

        winner_counts = {}
        failure_counts = {}
        for value in state["winner_values"]:
            winner_counts[value] = winner_counts.get(value, 0) + 1
        for value in state["failure_values"]:
            failure_counts[value] = failure_counts.get(value, 0) + 1
        categories = []
        for value in sorted(set(winner_counts) | set(failure_counts)):
            winner_count = int(winner_counts.get(value, 0))
            failure_count = int(failure_counts.get(value, 0))
            categories.append({
                "value": value,
                "winner_count": winner_count,
                "winner_rate_among_observed": _share(
                    winner_count,
                    len(state["winner_values"]),
                ),
                "failure_count": failure_count,
                "failure_rate_among_observed": _share(
                    failure_count,
                    len(state["failure_values"]),
                ),
            })
        reports.append({
            **common,
            "comparison_kind": "categorical",
            "categories": categories,
            "category_count": len(categories),
            "effect_available": bool(
                state["winner_values"] and state["failure_values"]
            ),
        })

    return {
        "version": PHASE4_UNIVARIATE_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": registry_sha,
        "discovery_rows_sha256": _sha256(
            discovery.get("discovery_rows_sha256"),
            label="Phase-4 univariate discovery rows",
        ),
        "discovery_subjects": subjects,
        "winner_tokens": winner_tokens,
        "failure_tokens": failure_tokens,
        "features_tested": len(reports),
        "families_tested": len(registry["families"]),
        "feature_reports": reports,
        "winner_failure_frequencies_reported": True,
        "missingness_compared_by_outcome": True,
        "univariate_relationships_tested": True,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "unseen_slice_validation_complete": False,
        "multiple_testing_control_applied": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_univariate_report_ready": True,
    }


def build_phase4_univariate_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    discovery_entry_handoff_sha256: str,
    base_rate_handoff_sha256: str,
    feature_registry_file_sha256: str,
) -> dict:
    """Bind univariate diagnostics without ranking or promoting features."""

    row = dict(report)
    if (
        str(row.get("version") or "")
        != PHASE4_UNIVARIATE_REPORT_VERSION
    ):
        raise ValueError("Phase-4 univariate handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 univariate checkpoint changed")
    for flag in (
        "winner_failure_frequencies_reported",
        "missingness_compared_by_outcome",
        "univariate_relationships_tested",
        "phase4_univariate_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 univariate handoff lacks {flag}")
    for flag in (
        "candidate_features_ranked",
        "signal_promoted",
        "unseen_slice_validation_complete",
        "multiple_testing_control_applied",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 univariate handoff violates {flag}")

    return {
        "version": PHASE4_UNIVARIATE_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 univariate registry",
        ),
        "feature_registry_file_sha256": _sha256(
            feature_registry_file_sha256,
            label="Phase-4 univariate registry file",
        ),
        "discovery_rows_sha256": _sha256(
            row.get("discovery_rows_sha256"),
            label="Phase-4 univariate discovery rows",
        ),
        "univariate_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 univariate report",
        ),
        "discovery_entry_handoff_sha256": _sha256(
            discovery_entry_handoff_sha256,
            label="Phase-4 univariate discovery-entry handoff",
        ),
        "base_rate_handoff_sha256": _sha256(
            base_rate_handoff_sha256,
            label="Phase-4 univariate base-rate handoff",
        ),
        "discovery_subjects": int(row["discovery_subjects"]),
        "winner_tokens": int(row["winner_tokens"]),
        "failure_tokens": int(row["failure_tokens"]),
        "features_tested": int(row["features_tested"]),
        "families_tested": int(row["families_tested"]),
        "winner_failure_frequencies_reported": True,
        "missingness_compared_by_outcome": True,
        "univariate_relationships_tested": True,
        "candidate_features_ranked": False,
        "signal_promoted": False,
        "unseen_slice_validation_complete": False,
        "multiple_testing_control_applied": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_univariate_report_ready": True,
    }
