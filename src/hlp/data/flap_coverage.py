"""Fail-closed Flap Phase-2 coverage-segment validation."""

from __future__ import annotations

from typing import Mapping


FLAP_CURVE_COVERAGE_VERSION = "phase2-flap-curve-coverage-v1"


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


def validate_flap_curve_coverage_report(
    report: Mapping[str, object],
    *,
    required_start_block: int,
    snapshot_head_block: int,
) -> dict:
    """Validate complete bonding-curve reconstruction without closing source coverage."""
    if str(report.get("version") or "") != FLAP_CURVE_COVERAGE_VERSION:
        raise ValueError("Flap curve coverage version changed")
    if str(report.get("source_id") or "") != "flap":
        raise ValueError("Flap curve coverage source changed")
    if str(report.get("coverage_segment") or "") != "bonding_curve":
        raise ValueError("Flap curve coverage segment changed")
    if report.get("source_coverage_complete") is not False:
        raise ValueError("Flap curve segment cannot close source coverage")

    required = _nonnegative(
        report.get("required_start_block"),
        field="required_start_block",
    )
    snapshot = _nonnegative(
        report.get("snapshot_head_block"),
        field="snapshot_head_block",
    )
    if required != int(required_start_block):
        raise ValueError("Flap curve coverage required start changed")
    if snapshot != int(snapshot_head_block):
        raise ValueError("Flap curve coverage snapshot changed")
    if report.get("continuous_event_scan") is not True:
        raise ValueError("Flap curve event scan is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("Flap curve coverage has missing ranges")

    tokens = _nonnegative(
        report.get("tokens_discovered"),
        field="tokens_discovered",
    )
    traded = _nonnegative(
        report.get("tokens_with_curve_trades"),
        field="tokens_with_curve_trades",
    )
    graduated = _nonnegative(
        report.get("graduated_tokens"),
        field="graduated_tokens",
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
    if traded > tokens:
        raise ValueError("Flap curve traded-token count exceeds launches")
    if graduated > tokens:
        raise ValueError("Flap graduated-token count exceeds launches")
    if priced != points:
        raise ValueError("Flap curve coverage has unpriced points")
    if crossed > traded:
        raise ValueError("Flap curve eligibility count exceeds traded tokens")

    hashes = {}
    for field in (
        "event_tape_sha256",
        "registry_sha256",
        "quote_feed_specs_sha256",
        "curve_points_sha256",
        "curve_summary_sha256",
    ):
        hashes[field] = _sha256(report.get(field), field=field)

    blocking = str(report.get("blocking_reason") or "")
    if graduated and blocking != "post_graduation_dex_lifecycle_not_yet_merged":
        raise ValueError("Flap graduated curve report lacks DEX-lifecycle blocker")

    return {
        "version": FLAP_CURVE_COVERAGE_VERSION,
        "source_id": "flap",
        "coverage_segment": "bonding_curve",
        "required_start_block": required,
        "snapshot_head_block": snapshot,
        "continuous_event_scan": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "tokens_with_curve_trades": traded,
        "graduated_tokens": graduated,
        "curve_price_points": points,
        "curve_priced_points": priced,
        "curve_tokens_crossed_100k": crossed,
        **hashes,
        "blocking_reason": (
            blocking if blocking else None
        ),
        "source_coverage_complete": False,
    }



FLAP_SOURCE_COVERAGE_VERSION = "phase2-flap-source-coverage-v1"


def validate_flap_source_coverage_report(
    report: Mapping[str, object],
    *,
    required_start_block: int,
    snapshot_head_block: int,
) -> dict:
    """Validate a full curve-plus-post-graduation Flap coverage report."""
    if str(report.get("version") or "") != FLAP_SOURCE_COVERAGE_VERSION:
        raise ValueError("Flap source coverage version changed")
    if str(report.get("source_id") or "") != "flap":
        raise ValueError("Flap source coverage source changed")
    if str(report.get("source_readiness") or "") != "adapter_ready":
        raise ValueError("Flap source coverage readiness changed")
    if str(report.get("coverage_status") or "") != "complete":
        raise ValueError("Flap source coverage is not complete")

    required = _nonnegative(
        report.get("required_start_block"),
        field="required_start_block",
    )
    first = _nonnegative(report.get("first_block"), field="first_block")
    last = _nonnegative(report.get("last_block"), field="last_block")
    snapshot = _nonnegative(
        report.get("snapshot_head_block"),
        field="snapshot_head_block",
    )
    if required != int(required_start_block) or first != required:
        raise ValueError("Flap source coverage start changed")
    if snapshot != int(snapshot_head_block) or last != snapshot:
        raise ValueError("Flap source coverage does not reach snapshot")
    if report.get("continuous") is not True:
        raise ValueError("Flap source coverage is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("Flap source coverage has missing ranges")

    tokens = _nonnegative(
        report.get("tokens_discovered"),
        field="tokens_discovered",
    )
    lifecycle_tokens = _nonnegative(
        report.get("lifecycle_tokens_with_points"),
        field="lifecycle_tokens_with_points",
    )
    graduated = _nonnegative(
        report.get("graduated_tokens"),
        field="graduated_tokens",
    )
    snapshots = _nonnegative(
        report.get("graduation_snapshots"),
        field="graduation_snapshots",
    )
    curve_points = _nonnegative(
        report.get("curve_price_points"),
        field="curve_price_points",
    )
    v3_points = _nonnegative(
        report.get("v3_price_points"),
        field="v3_price_points",
    )
    points = _nonnegative(
        report.get("price_points"),
        field="price_points",
    )
    priced = _nonnegative(
        report.get("priced_points"),
        field="priced_points",
    )
    if tokens <= 0:
        raise ValueError("Flap source coverage has no launches")
    if lifecycle_tokens != tokens:
        raise ValueError(
            "Flap source coverage does not price every launch"
        )
    if snapshots != graduated:
        raise ValueError(
            "Flap source coverage graduation snapshot count changed"
        )
    if curve_points + v3_points != points:
        raise ValueError("Flap source coverage point accounting drift")
    if priced != points:
        raise ValueError("Flap source coverage has unpriced points")
    if report.get("blocking_reason") is not None:
        raise ValueError(
            "complete Flap source coverage cannot retain blocking_reason"
        )

    hashes = {}
    for field in (
        "provenance_sha256",
        "event_tape_sha256",
        "registry_sha256",
        "curve_report_sha256",
        "curve_points_sha256",
        "graduation_registry_sha256",
        "v3_points_sha256",
        "final_summary_sha256",
    ):
        hashes[field] = _sha256(report.get(field), field=field)

    return {
        "version": FLAP_SOURCE_COVERAGE_VERSION,
        "source_id": "flap",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": required,
        "first_block": first,
        "last_block": last,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "lifecycle_tokens_with_points": lifecycle_tokens,
        "graduated_tokens": graduated,
        "graduation_snapshots": snapshots,
        "curve_price_points": curve_points,
        "v3_price_points": v3_points,
        "price_points": points,
        "priced_points": priced,
        "observed_volume_usd": report.get("observed_volume_usd"),
        **hashes,
        "blocking_reason": None,
        "snapshot_head_block": snapshot,
    }
