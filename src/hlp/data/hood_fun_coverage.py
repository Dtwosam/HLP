"""Validation for completed hood.fun Phase-2 coverage reports."""

from __future__ import annotations

from typing import Mapping

from hlp.config import (
    HOOD_FUN_CURRENT,
    HOOD_FUN_PREVIOUS,
    normalize_address,
)


HOOD_FUN_GENERATIONS = {
    "current": normalize_address(HOOD_FUN_CURRENT),
    "previous": normalize_address(HOOD_FUN_PREVIOUS),
}


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def validate_hood_fun_coverage_report(
    report: Mapping[str, object],
    *,
    generation: str,
    required_start_block: int,
    snapshot_head_block: int,
) -> dict:
    """Validate one complete hood.fun generation coverage report."""
    generation = str(generation)
    if generation not in HOOD_FUN_GENERATIONS:
        raise ValueError(f"unknown hood.fun generation: {generation!r}")
    source_id = f"hood_fun_{generation}"
    if str(report.get("source_id") or "") != source_id:
        raise ValueError("hood.fun coverage source_id changed")
    if str(report.get("source_readiness") or "") != "adapter_ready":
        raise ValueError("hood.fun coverage readiness changed")
    if str(report.get("coverage_status") or "") != "complete":
        raise ValueError("hood.fun coverage is not complete")

    required = int(report.get("required_start_block", -1))
    first = int(report.get("first_block", -1))
    last = int(report.get("last_block", -1))
    expected_start = int(required_start_block)
    expected_head = int(snapshot_head_block)
    if required != expected_start or first != expected_start:
        raise ValueError("hood.fun coverage start changed")
    if last != expected_head:
        raise ValueError("hood.fun coverage does not reach snapshot")
    if report.get("continuous") is not True:
        raise ValueError("hood.fun coverage is not continuous")
    missing = report.get("missing_ranges")
    if not isinstance(missing, list) or missing:
        raise ValueError("hood.fun coverage has missing ranges")

    tokens = int(report.get("tokens_discovered", -1))
    price_points = int(report.get("price_points", -1))
    priced_points = int(report.get("priced_points", -1))
    eligible = int(report.get("eligible_tokens", -1))
    if tokens < 0 or price_points < 0 or priced_points < 0:
        raise ValueError("hood.fun coverage counts are invalid")
    if priced_points != price_points:
        raise ValueError("hood.fun coverage has unpriced points")
    if eligible < 0 or eligible > tokens:
        raise ValueError("hood.fun eligible-token count is invalid")
    if tokens > 0 and price_points <= 0:
        raise ValueError(
            "hood.fun discovered tokens but has no price points"
        )

    provenance = _sha256(
        report.get("provenance_sha256"),
        label="hood.fun market-cap points",
    )
    event_sha = _sha256(
        report.get("event_tape_sha256"),
        label="hood.fun event tape",
    )
    sparse_sha = _sha256(
        report.get("sparse_anchor_sha256"),
        label="hood.fun sparse anchor",
    )
    summary_sha = _sha256(
        report.get("summary_sha256"),
        label="hood.fun summary",
    )

    windows = int(report.get("sparse_anchor_windows", -1))
    requests = int(report.get("rpc_requests", -1))
    if windows < 0 or requests < 0:
        raise ValueError("hood.fun sparse pricing accounting is invalid")
    route = str(report.get("rpc_route") or "")
    if not route:
        raise ValueError("hood.fun coverage RPC route is missing")

    reason = report.get("blocking_reason")
    if reason is not None:
        raise ValueError(
            "complete hood.fun coverage cannot retain blocking_reason"
        )

    return {
        "source_id": source_id,
        "generation": generation,
        "contract": HOOD_FUN_GENERATIONS[generation],
        "source_readiness": "adapter_ready",
        "coverage_status": "complete",
        "required_start_block": required,
        "first_block": first,
        "last_block": last,
        "continuous": True,
        "missing_ranges": [],
        "tokens_discovered": tokens,
        "price_points": price_points,
        "priced_points": priced_points,
        "observed_volume_usd": report.get("observed_volume_usd"),
        "provenance_sha256": provenance,
        "blocking_reason": None,
        "snapshot_head_block": expected_head,
        "event_tape_sha256": event_sha,
        "sparse_anchor_sha256": sparse_sha,
        "summary_sha256": summary_sha,
        "eligible_tokens": eligible,
        "sparse_anchor_windows": windows,
        "rpc_route": route,
        "rpc_requests": requests,
    }
