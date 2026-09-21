"""Fail-closed trench.today Phase-2 curve coverage validation."""

from __future__ import annotations

from typing import Mapping


TRENCH_CURVE_COVERAGE_VERSION = "phase2-trench-curve-coverage-v1"


def _nonnegative(value: object, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative")
    return result


def _sha256(value: object, *, field: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{field} must be a SHA-256 hex digest") from exc
    return text


def validate_trench_curve_coverage_report(
    report: Mapping[str, object],
    *,
    required_start_block: int,
    snapshot_head_block: int,
) -> dict:
    """Validate complete curve reconstruction without closing source coverage."""
    if str(report.get("version") or "") != TRENCH_CURVE_COVERAGE_VERSION:
        raise ValueError("trench.today curve coverage version changed")
    if str(report.get("source_id") or "") != "trench_today":
        raise ValueError("trench.today curve coverage source changed")
    if str(report.get("coverage_segment") or "") != "bonding_curve":
        raise ValueError("trench.today curve coverage segment changed")
    if report.get("source_coverage_complete") is not False:
        raise ValueError(
            "trench.today curve segment cannot close source coverage"
        )

    required = _nonnegative(
        report.get("required_start_block"),
        field="required_start_block",
    )
    snapshot = _nonnegative(
        report.get("snapshot_head_block"),
        field="snapshot_head_block",
    )
    if required != int(required_start_block):
        raise ValueError("trench.today curve required start changed")
    if snapshot != int(snapshot_head_block):
        raise ValueError("trench.today curve snapshot changed")
    if report.get("continuous_event_scan") is not True:
        raise ValueError("trench.today curve event scan is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("trench.today curve coverage has missing ranges")

    tokens = _nonnegative(
        report.get("tokens_discovered"),
        field="tokens_discovered",
    )
    sync_tokens = _nonnegative(
        report.get("tokens_with_syncs"),
        field="tokens_with_syncs",
    )
    limited = _nonnegative(
        report.get("limit_reach_tokens"),
        field="limit_reach_tokens",
    )
    points = _nonnegative(
        report.get("curve_price_points"),
        field="curve_price_points",
    )
    priced = _nonnegative(
        report.get("curve_priced_points"),
        field="curve_priced_points",
    )
    crossed = _nonnegative(
        report.get("curve_tokens_crossed_100k"),
        field="curve_tokens_crossed_100k",
    )
    if sync_tokens > tokens:
        raise ValueError(
            "trench.today Sync-token count exceeds launch population"
        )
    if limited > tokens:
        raise ValueError(
            "trench.today LimitReach count exceeds launch population"
        )
    if priced != points:
        raise ValueError("trench.today curve coverage has unpriced points")
    if crossed > sync_tokens:
        raise ValueError(
            "trench.today curve eligibility exceeds Sync-token population"
        )

    hashes = {}
    for field in (
        "event_tape_sha256",
        "registry_sha256",
        "quote_decimals_sha256",
        "quote_feed_specs_sha256",
        "curve_points_sha256",
        "curve_summary_sha256",
    ):
        hashes[field] = _sha256(report.get(field), field=field)

    blocking = report.get("blocking_reason")
    if limited:
        if str(blocking or "") != "post_limit_dex_lifecycle_unresolved":
            raise ValueError(
                "trench.today LimitReach coverage lacks DEX-lifecycle blocker"
            )
    elif blocking is not None:
        raise ValueError(
            "trench.today curve coverage has unexpected blocking_reason"
        )

    return {
        "version": TRENCH_CURVE_COVERAGE_VERSION,
        "source_id": "trench_today",
        "coverage_segment": "bonding_curve",
        "required_start_block": required,
        "snapshot_head_block": snapshot,
        "continuous_event_scan": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "tokens_with_syncs": sync_tokens,
        "limit_reach_tokens": limited,
        "curve_price_points": points,
        "curve_priced_points": priced,
        "curve_tokens_crossed_100k": crossed,
        **hashes,
        "blocking_reason": (
            None if blocking is None else str(blocking)
        ),
        "source_coverage_complete": False,
    }
