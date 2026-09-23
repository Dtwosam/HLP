"""Discovery-only repeated-sampling stability diagnostics for Phase 4."""

from __future__ import annotations

import hashlib
import math
import random
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
from hlp.data.phase4_validation import (
    _effect,
    _measurements,
    _split_values,
)


PHASE4_STABILITY_REPORT_VERSION = "phase4-stability-report-v1"
PHASE4_STABILITY_HANDOFF_VERSION = "phase4-stability-handoff-v1"
DEFAULT_RESAMPLES = 32
DEFAULT_SAMPLE_FRACTION = Decimal("0.8")
DEFAULT_CHRONOLOGICAL_FOLDS = 4


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


def _cutoff_key(row: Mapping[str, object]) -> tuple[int, int, int, str]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    token = normalize_address(str(row.get("token") or ""))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-4 stability cutoff is invalid")
    return block, tx, log, token


def _direction_matches(effect: Decimal, direction: str) -> bool:
    if direction == "positive":
        return effect > 0
    if direction == "negative":
        return effect < 0
    raise ValueError(
        f"Phase-4 stability direction is unsupported: {direction}"
    )


def _evaluate(
    rows: list[dict],
    hypothesis: Mapping[str, object],
) -> dict:
    try:
        values, labels = _measurements(rows, hypothesis)
        winners, failures = _split_values(values, labels)
        effect = _effect(
            str(hypothesis["effect_metric"]),
            winners,
            failures,
        )
    except ValueError as exc:
        return {
            "available": False,
            "reason": str(exc),
            "effect": None,
            "direction_consistent": None,
            "minimum_effect_met": None,
            "observed_measurements": 0,
            "winner_measurements": 0,
            "failure_measurements": 0,
        }

    direction = str(hypothesis["expected_direction"])
    minimum = _decimal(
        hypothesis["minimum_absolute_effect"],
        label="Phase-4 stability minimum effect",
    )
    return {
        "available": True,
        "reason": None,
        "effect": _text(effect),
        "direction_consistent": _direction_matches(
            effect,
            direction,
        ),
        "minimum_effect_met": abs(effect) >= minimum,
        "observed_measurements": len(values),
        "winner_measurements": len(winners),
        "failure_measurements": len(failures),
    }


def _chronological_folds(
    rows: list[dict],
    *,
    fold_count: int,
) -> list[list[dict]]:
    if fold_count < 2:
        raise ValueError("Phase-4 stability fold count must be >=2")
    total = len(rows)
    folds = [[] for _ in range(fold_count)]
    for index, row in enumerate(rows):
        fold_index = min((index * fold_count) // total, fold_count - 1)
        folds[fold_index].append(row)
    return folds


def _stratified_subsample(
    rows: list[dict],
    *,
    fraction: Decimal,
    seed_material: str,
) -> list[dict]:
    winners = [row for row in rows if row["target_comeback_5x"]]
    failures = [row for row in rows if not row["target_comeback_5x"]]
    if not winners or not failures:
        raise ValueError(
            "Phase-4 stability subsampling requires both cohorts"
        )
    rng = random.Random(
        int(hashlib.sha256(seed_material.encode()).hexdigest(), 16)
    )
    winner_rows = list(winners)
    failure_rows = list(failures)
    rng.shuffle(winner_rows)
    rng.shuffle(failure_rows)

    def size(total: int) -> int:
        return max(
            1,
            min(
                total,
                int(
                    math.ceil(
                        float(fraction) * total
                    )
                ),
            ),
        )

    sampled = (
        winner_rows[: size(len(winner_rows))]
        + failure_rows[: size(len(failure_rows))]
    )
    return sorted(sampled, key=_cutoff_key)


def _validate_inputs(
    *,
    freeze_report: Mapping[str, object],
    freeze_handoff: Mapping[str, object],
    split_handoff: Mapping[str, object],
    split_handoff_sha256: str,
    discovery_rows_sha256: str,
) -> tuple[dict, dict, dict]:
    report = dict(freeze_report)
    freeze = dict(freeze_handoff)
    split = dict(split_handoff)

    if (
        str(report.get("version") or "")
        != PHASE4_HYPOTHESIS_FREEZE_VERSION
    ):
        raise ValueError("Phase-4 stability freeze-report version changed")
    if (
        str(freeze.get("version") or "")
        != PHASE4_HYPOTHESIS_FREEZE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 stability freeze-handoff version changed")
    if (
        str(split.get("version") or "")
        != PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 stability split version changed")
    for value in (report, freeze, split):
        if value.get("phase4_checkpoint_name") != (
            PHASE4_DISCOVERY_CHECKPOINT_NAME
        ):
            raise ValueError("Phase-4 stability checkpoint changed")

    for flag in (
        "validation_hypotheses_frozen",
        "multiple_testing_plan_frozen",
        "phase4_hypothesis_freeze_ready",
    ):
        if freeze.get(flag) is not True:
            raise ValueError(f"Phase-4 stability freeze lacks {flag}")
    for flag in (
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if freeze.get(flag) is not False:
            raise ValueError(f"Phase-4 stability freeze violates {flag}")

    if split.get("phase4_split_frozen") is not True:
        raise ValueError("Phase-4 stability split is not frozen")
    if split.get("final_test_separated") is not True:
        raise ValueError("Phase-4 stability final test is not separated")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if split.get(flag) is not False:
            raise ValueError(f"Phase-4 stability split violates {flag}")

    expected_split_sha = _sha256(
        split_handoff_sha256,
        label="Phase-4 stability split handoff",
    )
    if _sha256(
        freeze.get("chronological_split_handoff_sha256"),
        label="Phase-4 stability freeze split link",
    ) != expected_split_sha:
        raise ValueError("Phase-4 stability freeze/split linkage drift")
    if _sha256(
        split.get("discovery_split_rows_sha256"),
        label="Phase-4 stability frozen discovery rows",
    ) != _sha256(
        discovery_rows_sha256,
        label="Phase-4 stability supplied discovery rows",
    ):
        raise ValueError("Phase-4 stability discovery row SHA drift")
    if _sha256(
        report.get("hypothesis_plan_sha256"),
        label="Phase-4 stability freeze-report plan",
    ) != _sha256(
        freeze.get("hypothesis_plan_sha256"),
        label="Phase-4 stability freeze-handoff plan",
    ):
        raise ValueError("Phase-4 stability hypothesis-plan drift")
    return report, freeze, split


def build_phase4_stability_report(
    discovery_rows: Iterable[Mapping[str, object]],
    hypothesis_freeze_report: Mapping[str, object],
    *,
    hypothesis_freeze_handoff: Mapping[str, object],
    chronological_split_handoff: Mapping[str, object],
    chronological_split_handoff_sha256: str,
    discovery_rows_sha256: str,
    resamples: int = DEFAULT_RESAMPLES,
    sample_fraction: Decimal = DEFAULT_SAMPLE_FRACTION,
    chronological_folds: int = DEFAULT_CHRONOLOGICAL_FOLDS,
) -> dict:
    """Re-measure frozen hypotheses across discovery-only repeated samples."""

    report, freeze, split = _validate_inputs(
        freeze_report=hypothesis_freeze_report,
        freeze_handoff=hypothesis_freeze_handoff,
        split_handoff=chronological_split_handoff,
        split_handoff_sha256=chronological_split_handoff_sha256,
        discovery_rows_sha256=discovery_rows_sha256,
    )
    sample_count = int(resamples)
    fold_count = int(chronological_folds)
    fraction = _decimal(
        sample_fraction,
        label="Phase-4 stability sample fraction",
    )
    if sample_count < 8 or sample_count > 256:
        raise ValueError(
            "Phase-4 stability resample count must be 8..256"
        )
    if fraction <= Decimal("0.5") or fraction > Decimal("1"):
        raise ValueError(
            "Phase-4 stability sample fraction must be >0.5 and <=1"
        )
    if fold_count < 2 or fold_count > 12:
        raise ValueError(
            "Phase-4 stability chronological folds must be 2..12"
        )

    rows = []
    seen = set()
    for raw in discovery_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 stability row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 stability repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 stability labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 stability feature row was mutated: {token}"
            )
        if not isinstance(row.get("target_comeback_5x"), bool):
            raise ValueError(
                f"Phase-4 stability target is invalid: {token}"
            )
        _cutoff_key(row)
        rows.append(row)
    rows.sort(key=_cutoff_key)

    if len(rows) != int(split.get("discovery_split_rows", -1)):
        raise ValueError("Phase-4 stability discovery count drift")
    if not rows:
        raise ValueError("Phase-4 stability discovery slice is empty")
    if not any(row["target_comeback_5x"] for row in rows):
        raise ValueError("Phase-4 stability has no winners")
    if all(row["target_comeback_5x"] for row in rows):
        raise ValueError("Phase-4 stability has no failures")

    plan = report.get("normalized_hypothesis_plan")
    if not isinstance(plan, Mapping):
        raise ValueError("Phase-4 stability normalized plan is missing")
    hypotheses = plan.get("hypotheses")
    if not isinstance(hypotheses, list):
        raise ValueError("Phase-4 stability hypotheses are missing")
    if len(hypotheses) != int(freeze.get("validation_hypotheses", -1)):
        raise ValueError("Phase-4 stability hypothesis count drift")

    folds = _chronological_folds(
        rows,
        fold_count=fold_count,
    )
    fold_summaries = [
        {
            "fold_index": index,
            "rows": len(fold),
            "minimum_cutoff": (
                None
                if not fold
                else {
                    "block": _cutoff_key(fold[0])[0],
                    "transaction_index": _cutoff_key(fold[0])[1],
                    "log_index": _cutoff_key(fold[0])[2],
                }
            ),
            "maximum_cutoff": (
                None
                if not fold
                else {
                    "block": _cutoff_key(fold[-1])[0],
                    "transaction_index": _cutoff_key(fold[-1])[1],
                    "log_index": _cutoff_key(fold[-1])[2],
                }
            ),
            "winner_rows": sum(
                int(row["target_comeback_5x"])
                for row in fold
            ),
            "failure_rows": sum(
                int(not row["target_comeback_5x"])
                for row in fold
            ),
        }
        for index, fold in enumerate(folds)
    ]

    hypothesis_reports = []
    for raw in hypotheses:
        if not isinstance(raw, Mapping):
            raise ValueError("Phase-4 stability hypothesis is invalid")
        hypothesis = dict(raw)
        hypothesis_id = str(hypothesis.get("hypothesis_id") or "")
        if not hypothesis_id:
            raise ValueError("Phase-4 stability hypothesis id is empty")

        full = _evaluate(rows, hypothesis)
        chronological_results = [
            {
                "fold_index": index,
                **_evaluate(fold, hypothesis),
            }
            for index, fold in enumerate(folds)
        ]
        chronological_available = [
            item for item in chronological_results
            if item["available"]
        ]
        chronological_direction_matches = sum(
            int(bool(item["direction_consistent"]))
            for item in chronological_available
        )
        chronological_threshold_matches = sum(
            int(bool(item["minimum_effect_met"]))
            for item in chronological_available
        )

        resample_results = []
        for replicate in range(sample_count):
            sampled = _stratified_subsample(
                rows,
                fraction=fraction,
                seed_material=(
                    f"{discovery_rows_sha256}:"
                    f"{hypothesis_id}:{replicate}"
                ),
            )
            measured = _evaluate(sampled, hypothesis)
            resample_results.append({
                "replicate": replicate,
                "rows": len(sampled),
                **measured,
            })
        resample_available = [
            item for item in resample_results if item["available"]
        ]
        resample_direction_matches = sum(
            int(bool(item["direction_consistent"]))
            for item in resample_available
        )
        resample_threshold_matches = sum(
            int(bool(item["minimum_effect_met"]))
            for item in resample_available
        )
        effects = [
            _decimal(
                item["effect"],
                label="Phase-4 stability resample effect",
            )
            for item in resample_available
        ]

        hypothesis_reports.append({
            "hypothesis_id": hypothesis_id,
            "feature_id": str(hypothesis["feature_id"]),
            "effect_metric": str(hypothesis["effect_metric"]),
            "category_value": hypothesis.get("category_value"),
            "expected_direction": str(
                hypothesis["expected_direction"]
            ),
            "minimum_absolute_effect": str(
                hypothesis["minimum_absolute_effect"]
            ),
            "full_discovery_measurement": full,
            "chronological_folds": chronological_results,
            "chronological_available_folds": len(
                chronological_available
            ),
            "chronological_direction_consistency_rate": _share(
                chronological_direction_matches,
                len(chronological_available),
            ),
            "chronological_minimum_effect_rate": _share(
                chronological_threshold_matches,
                len(chronological_available),
            ),
            "resamples": resample_results,
            "resample_available_count": len(resample_available),
            "resample_direction_consistency_rate": _share(
                resample_direction_matches,
                len(resample_available),
            ),
            "resample_minimum_effect_rate": _share(
                resample_threshold_matches,
                len(resample_available),
            ),
            "resample_minimum_effect": (
                None if not effects else _text(min(effects))
            ),
            "resample_maximum_effect": (
                None if not effects else _text(max(effects))
            ),
            "stability_pass_fail_threshold_applied": False,
        })

    return {
        "version": PHASE4_STABILITY_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": str(
            freeze["feature_registry_sha256"]
        ),
        "discovery_split_rows_sha256": _sha256(
            discovery_rows_sha256,
            label="Phase-4 stability discovery rows",
        ),
        "hypothesis_plan_sha256": str(
            freeze["hypothesis_plan_sha256"]
        ),
        "analysis_subjects": len(rows),
        "hypotheses_examined": len(hypothesis_reports),
        "resamples_per_hypothesis": sample_count,
        "sample_fraction": _text(fraction),
        "chronological_fold_count": fold_count,
        "chronological_fold_summaries": fold_summaries,
        "hypothesis_reports": hypothesis_reports,
        "repeated_sampling_stability_examined": True,
        "chronological_stability_examined": True,
        "stability_pass_fail_threshold_applied": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_stability_report_ready": True,
    }


def build_phase4_stability_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    hypothesis_freeze_handoff_sha256: str,
    chronological_split_handoff_sha256: str,
) -> dict:
    """Bind discovery-only stability evidence without promoting hypotheses."""

    row = dict(report)
    if str(row.get("version") or "") != PHASE4_STABILITY_REPORT_VERSION:
        raise ValueError("Phase-4 stability handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 stability checkpoint changed")
    for flag in (
        "repeated_sampling_stability_examined",
        "chronological_stability_examined",
        "phase4_stability_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 stability handoff lacks {flag}")
    for flag in (
        "stability_pass_fail_threshold_applied",
        "validation_rows_consumed",
        "final_test_rows_consumed",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 stability handoff violates {flag}")

    return {
        "version": PHASE4_STABILITY_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 stability registry",
        ),
        "discovery_split_rows_sha256": _sha256(
            row.get("discovery_split_rows_sha256"),
            label="Phase-4 stability discovery rows",
        ),
        "hypothesis_plan_sha256": _sha256(
            row.get("hypothesis_plan_sha256"),
            label="Phase-4 stability plan",
        ),
        "stability_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 stability report",
        ),
        "hypothesis_freeze_handoff_sha256": _sha256(
            hypothesis_freeze_handoff_sha256,
            label="Phase-4 stability freeze handoff",
        ),
        "chronological_split_handoff_sha256": _sha256(
            chronological_split_handoff_sha256,
            label="Phase-4 stability split handoff",
        ),
        "analysis_subjects": int(row["analysis_subjects"]),
        "hypotheses_examined": int(row["hypotheses_examined"]),
        "resamples_per_hypothesis": int(
            row["resamples_per_hypothesis"]
        ),
        "sample_fraction": str(row["sample_fraction"]),
        "chronological_fold_count": int(
            row["chronological_fold_count"]
        ),
        "repeated_sampling_stability_examined": True,
        "chronological_stability_examined": True,
        "stability_pass_fail_threshold_applied": False,
        "validation_rows_consumed": False,
        "final_test_rows_consumed": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_stability_report_ready": True,
    }
