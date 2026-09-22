"""Population/base-rate diagnostics for guarded Phase-4 discovery."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
    PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION,
    PHASE4_DISCOVERY_ENTRY_VERSION,
)


PHASE4_BASE_RATE_REPORT_VERSION = "phase4-base-rate-report-v1"
PHASE4_BASE_RATE_HANDOFF_VERSION = "phase4-base-rate-handoff-v1"
DEFAULT_MILESTONES = (2, 3, 5, 10)


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
        raise ValueError(f"{label} is not a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{label} is not finite")
    return result


def _decimal_text(value: Decimal) -> str:
    with localcontext() as context:
        context.prec = 80
        if value == 0:
            return "0"
        return format(value.normalize(context=context), "f")


def _share(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        raise ValueError("Phase-4 base-rate denominator is not positive")
    with localcontext() as context:
        context.prec = 80
        value = Decimal(numerator) / Decimal(denominator)
    return _decimal_text(value)


def _median(values: list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Phase-4 base-rate distribution is empty")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    with localcontext() as context:
        context.prec = 80
        return (
            ordered[middle - 1] + ordered[middle]
        ) / Decimal(2)


def build_phase4_base_rate_report(
    discovery_rows: Iterable[Mapping[str, object]],
    *,
    discovery_entry_handoff: Mapping[str, object],
    milestones: Iterable[int] = DEFAULT_MILESTONES,
) -> dict:
    """Report outcome prevalence before testing any feature relationship."""

    handoff = dict(discovery_entry_handoff)
    if (
        str(handoff.get("version") or "")
        != PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 base-rate discovery handoff version changed")
    if handoff.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 base-rate checkpoint name changed")
    if handoff.get("phase4_discovery_entry_ready") is not True:
        raise ValueError("Phase-4 base-rate discovery entry is not ready")
    if handoff.get("phase4_discovery_only") is not True:
        raise ValueError("Phase-4 base-rate input is not discovery-only")
    if handoff.get("labels_joined_after_feature_freeze") is not True:
        raise ValueError("Phase-4 base-rate labels predate feature freeze")
    if handoff.get("feature_values_mutated") is not False:
        raise ValueError("Phase-4 base-rate input mutated frozen features")
    if handoff.get("phase4_discovery_checkpoint_claimed") is not False:
        raise ValueError("Phase-4 base-rate input already claimed discovery")

    milestone_values = tuple(sorted({int(value) for value in milestones}))
    if not milestone_values or any(value <= 1 for value in milestone_values):
        raise ValueError("Phase-4 base-rate milestones are invalid")
    if 5 not in milestone_values:
        raise ValueError("Phase-4 base-rate report must retain 5x")

    seen = set()
    multiples: list[Decimal] = []
    positives = 0
    right_censored = 0
    reached = {value: 0 for value in milestone_values}

    for raw in discovery_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 base-rate row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 base-rate repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 base-rate labels were joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 base-rate row mutated frozen features: {token}"
            )
        if row.get("phase4_discovery_only") is not True:
            raise ValueError(
                f"Phase-4 base-rate row is not discovery-only: {token}"
            )
        outcome = row.get("outcome")
        if not isinstance(outcome, Mapping):
            raise ValueError(f"Phase-4 base-rate outcome missing: {token}")
        if outcome.get("outcome_eligible") is not True:
            raise ValueError(
                f"Phase-4 base-rate contains ineligible outcome: {token}"
            )
        if outcome.get("dump_status") != "confirmed":
            raise ValueError(
                f"Phase-4 base-rate contains unconfirmed dump: {token}"
            )

        target = row.get("target_comeback_5x")
        if not isinstance(target, bool):
            raise ValueError(f"Phase-4 base-rate 5x target invalid: {token}")
        multiple = _decimal(
            row.get("target_max_post_dump_multiple"),
            label=f"{token} Phase-4 max multiple",
        )
        if multiple < 0:
            raise ValueError(
                f"Phase-4 base-rate max multiple is negative: {token}"
            )
        if target != (multiple >= Decimal("5")):
            raise ValueError(
                f"Phase-4 base-rate target/magnitude disagree: {token}"
            )
        if str(outcome.get("max_post_dump_multiple")) != str(
            row.get("target_max_post_dump_multiple")
        ):
            raise ValueError(
                f"Phase-4 base-rate target/outcome magnitude drift: {token}"
            )

        positives += int(target)
        multiples.append(multiple)
        censored = outcome.get("right_censored_at_snapshot")
        if not isinstance(censored, bool):
            raise ValueError(
                f"Phase-4 base-rate censoring flag invalid: {token}"
            )
        right_censored += int(censored)

        for milestone in milestone_values:
            key = f"reached_{milestone}x"
            value = outcome.get(key)
            if not isinstance(value, bool):
                raise ValueError(
                    f"Phase-4 base-rate milestone flag invalid: {token} {key}"
                )
            expected = multiple >= Decimal(milestone)
            if value != expected:
                raise ValueError(
                    f"Phase-4 base-rate milestone/magnitude disagree: "
                    f"{token} {key}"
                )
            reached[milestone] += int(value)

    subjects = len(seen)
    if subjects <= 0:
        raise ValueError("Phase-4 base-rate has no discovery subjects")
    if subjects != int(handoff.get("discovery_subjects", -1)):
        raise ValueError("Phase-4 base-rate discovery subject count drift")
    if positives != int(handoff.get("comeback_5x_tokens", -1)):
        raise ValueError("Phase-4 base-rate positive count drift")
    base_rate = _share(positives, subjects)
    if base_rate != str(handoff.get("comeback_5x_base_rate") or ""):
        raise ValueError("Phase-4 base-rate handoff prevalence drift")

    with localcontext() as context:
        context.prec = 80
        total_multiple = sum(multiples, Decimal(0))
        mean_multiple = total_multiple / Decimal(subjects)
    milestone_report = {
        str(milestone): {
            "reached_tokens": reached[milestone],
            "not_reached_tokens": subjects - reached[milestone],
            "reach_rate": _share(reached[milestone], subjects),
        }
        for milestone in milestone_values
    }
    ge_20 = sum(value >= Decimal("20") for value in multiples)

    return {
        "version": PHASE4_BASE_RATE_REPORT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            handoff.get("feature_registry_sha256"),
            label="Phase-4 base-rate feature registry",
        ),
        "discovery_rows_sha256": _sha256(
            handoff.get("discovery_rows_sha256"),
            label="Phase-4 base-rate discovery rows",
        ),
        "discovery_subjects": subjects,
        "comeback_5x_tokens": positives,
        "non_comeback_5x_tokens": subjects - positives,
        "comeback_5x_base_rate": base_rate,
        "milestones": milestone_report,
        "max_post_dump_multiple_distribution": {
            "minimum": _decimal_text(min(multiples)),
            "median": _decimal_text(_median(multiples)),
            "mean": _decimal_text(mean_multiple),
            "maximum": _decimal_text(max(multiples)),
            "ge_20x_tokens": ge_20,
            "ge_20x_rate": _share(ge_20, subjects),
        },
        "right_censored_at_snapshot_tokens": right_censored,
        "right_censored_at_snapshot_rate": _share(
            right_censored,
            subjects,
        ),
        "winner_failure_frequencies_reported": True,
        "continuous_outcome_distribution_reported": True,
        "feature_relationships_tested": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_base_rate_report_ready": True,
    }


def build_phase4_base_rate_handoff(
    report: Mapping[str, object],
    *,
    report_sha256: str,
    discovery_entry_handoff_sha256: str,
) -> dict:
    """Bind the base-rate report without promoting any feature relationship."""

    row = dict(report)
    if (
        str(row.get("version") or "")
        != PHASE4_BASE_RATE_REPORT_VERSION
    ):
        raise ValueError("Phase-4 base-rate handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 base-rate checkpoint changed")
    for flag in (
        "winner_failure_frequencies_reported",
        "continuous_outcome_distribution_reported",
        "phase4_base_rate_report_ready",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 base-rate handoff lacks {flag}")
    for flag in (
        "feature_relationships_tested",
        "signal_promoted",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 base-rate handoff violates {flag}")

    return {
        "version": PHASE4_BASE_RATE_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 base-rate registry",
        ),
        "discovery_rows_sha256": _sha256(
            row.get("discovery_rows_sha256"),
            label="Phase-4 base-rate discovery rows",
        ),
        "base_rate_report_sha256": _sha256(
            report_sha256,
            label="Phase-4 base-rate report",
        ),
        "discovery_entry_handoff_sha256": _sha256(
            discovery_entry_handoff_sha256,
            label="Phase-4 discovery-entry handoff",
        ),
        "discovery_subjects": int(row["discovery_subjects"]),
        "comeback_5x_tokens": int(row["comeback_5x_tokens"]),
        "comeback_5x_base_rate": str(row["comeback_5x_base_rate"]),
        "winner_failure_frequencies_reported": True,
        "continuous_outcome_distribution_reported": True,
        "feature_relationships_tested": False,
        "signal_promoted": False,
        "phase4_discovery_checkpoint_claimed": False,
        "phase4_base_rate_report_ready": True,
    }
