"""Fail-closed Doppler Phase-2 source coverage validation."""

from __future__ import annotations

from typing import Mapping


DOPPLER_COVERAGE_VERSION = "phase2-doppler-source-coverage-v1"


def _count(value: object, *, field: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if result < 0:
        raise ValueError(f"{field} cannot be negative")
    return result


def _sha(value: object, *, field: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(
            f"{field} must be a SHA-256 hex digest"
        ) from exc
    return text


def validate_doppler_coverage_report(
    report: Mapping[str, object],
    *,
    required_start_block: int,
    snapshot_head_block: int,
) -> dict:
    """Validate one complete Doppler Airlock/V4 lifecycle report."""
    if str(report.get("version") or "") != DOPPLER_COVERAGE_VERSION:
        raise ValueError("Doppler coverage version changed")
    if str(report.get("source_id") or "") != "doppler":
        raise ValueError("Doppler coverage source changed")
    if str(report.get("source_readiness") or "") != "adapter_ready":
        raise ValueError("Doppler coverage readiness changed")
    if str(report.get("coverage_status") or "") != "complete":
        raise ValueError("Doppler coverage is not complete")

    required = _count(
        report.get("required_start_block"),
        field="required_start_block",
    )
    first = _count(report.get("first_block"), field="first_block")
    last = _count(report.get("last_block"), field="last_block")
    snapshot = _count(
        report.get("snapshot_head_block"),
        field="snapshot_head_block",
    )
    if required != int(required_start_block) or first != required:
        raise ValueError("Doppler coverage start changed")
    if snapshot != int(snapshot_head_block) or last != snapshot:
        raise ValueError("Doppler coverage does not reach snapshot")
    if report.get("continuous") is not True:
        raise ValueError("Doppler coverage is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("Doppler coverage has missing ranges")
    if report.get("same_transaction_initialize_complete") is not True:
        raise ValueError(
            "Doppler same-transaction Initialize proof is incomplete"
        )

    tokens = _count(
        report.get("tokens_discovered"),
        field="tokens_discovered",
    )
    initializes = _count(
        report.get("initialize_points"),
        field="initialize_points",
    )
    tokens_with_points = _count(
        report.get("tokens_with_price_points"),
        field="tokens_with_price_points",
    )
    points = _count(
        report.get("price_points"),
        field="price_points",
    )
    priced = _count(
        report.get("priced_points"),
        field="priced_points",
    )
    eligible = _count(
        report.get("tokens_crossed_100k"),
        field="tokens_crossed_100k",
    )
    if tokens <= 0:
        raise ValueError("Doppler coverage has no discovered tokens")
    if initializes != tokens:
        raise ValueError(
            "Doppler does not have exactly one Initialize point per token"
        )
    if tokens_with_points != tokens:
        raise ValueError(
            "Doppler price history does not cover every token"
        )
    if priced != points:
        raise ValueError("Doppler coverage has unpriced points")
    if points < initializes:
        raise ValueError("Doppler price points omit Initialize population")
    if eligible > tokens:
        raise ValueError("Doppler eligibility exceeds token population")

    hashes = {}
    for field in (
        "registry_sha256",
        "launch_state_sha256",
        "v4_initialize_sha256",
        "shared_v4_swap_sha256",
        "shared_supply_delta_sha256",
        "filtered_supply_sha256",
        "quote_decimals_sha256",
        "quote_feed_specs_sha256",
        "market_points_sha256",
        "token_summary_sha256",
        "provenance_sha256",
    ):
        hashes[field] = _sha(report.get(field), field=field)

    if report.get("blocking_reason") is not None:
        raise ValueError(
            "complete Doppler coverage cannot retain blocking_reason"
        )

    return {
        **dict(report),
        "version": DOPPLER_COVERAGE_VERSION,
        "source_id": "doppler",
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": required,
        "first_block": first,
        "last_block": last,
        "snapshot_head_block": snapshot,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "initialize_points": initializes,
        "tokens_with_price_points": tokens_with_points,
        "price_points": points,
        "priced_points": priced,
        "tokens_crossed_100k": eligible,
        **hashes,
        "blocking_reason": None,
    }
