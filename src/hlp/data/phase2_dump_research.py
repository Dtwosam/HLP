"""Research-only Phase-2 first-major-dump path geometry and candidates.

This module deliberately does not freeze a dump threshold or compute comeback
outcomes. It provides deterministic, price-path-only primitives that can be
used to compare candidate lifecycle detectors after the Phase-2 universe is
frozen.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION


PHASE2_DUMP_GEOMETRY_VERSION = "phase2-dump-geometry-v1"
PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION = "phase2-dump-candidate-research-v1"
PEAK_DRAWDOWN_REBOUND_FAMILY = "peak_drawdown_rebound"


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _decimal(value: object, *, label: str, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} is not numeric") from exc
    if not result.is_finite():
        raise ValueError(f"{label} is not finite")
    if positive and result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("block_number", -1))
    raw_transaction = row.get("transaction_index")
    transaction = -1 if raw_transaction is None else int(raw_transaction)
    log_index = int(row.get("log_index", -1))
    if block < 0 or transaction < -1 or log_index < 0:
        raise ValueError("dump research price row has invalid event position")
    return block, transaction, log_index


def _validate_frozen_universe(
    universe_rows: Iterable[Mapping[str, object]],
    universe_summary: Mapping[str, object],
) -> tuple[list[dict], int]:
    summary = dict(universe_summary)
    if str(summary.get("version") or "") != PHASE2_UNIVERSE_VERSION:
        raise ValueError("dump research requires the canonical Phase-2 universe version")
    if summary.get("phase2_universe_frozen") is not True:
        raise ValueError("dump research requires a frozen Phase-2 universe")
    if summary.get("coverage_complete") is not True:
        raise ValueError("dump research requires complete Phase-2 source coverage")
    snapshot = int(summary.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("dump research universe snapshot is invalid")

    rows = []
    seen: set[str] = set()
    for raw in universe_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"dump research universe repeats token: {token}")
        seen.add(token)
        if row.get("universe_status") != "eligible":
            raise ValueError(
                f"dump research universe contains non-eligible token: {token}"
            )
        row["token"] = token
        rows.append(row)

    if len(rows) != int(summary.get("eligible_tokens", -1)):
        raise ValueError("dump research universe token count disagrees with freeze")
    if not rows:
        raise ValueError("dump research universe is empty")
    rows.sort(key=lambda row: row["token"])
    return rows, snapshot


def build_phase2_dump_geometry(
    universe_rows: Iterable[Mapping[str, object]],
    price_rows: Iterable[Mapping[str, object]],
    *,
    universe_summary: Mapping[str, object],
    universe_sha256: str,
    price_path_provenance_sha256: str,
) -> tuple[list[dict], dict]:
    """Build causal trailing-peak/drawdown geometry without choosing a threshold."""

    universe, snapshot = _validate_frozen_universe(
        universe_rows,
        universe_summary,
    )
    universe_sha = _sha256(universe_sha256, label="Phase-2 universe")
    price_sha = _sha256(
        price_path_provenance_sha256,
        label="Phase-2 price-path provenance",
    )
    expected = {row["token"] for row in universe}

    grouped: dict[str, list[dict]] = {token: [] for token in expected}
    seen_events: set[tuple[str, int, int, int]] = set()
    for raw in price_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token not in expected:
            raise ValueError(
                f"dump research price path contains token outside frozen universe: "
                f"{token}"
            )
        event = _event_key(row)
        if event[0] > snapshot:
            raise ValueError(
                f"dump research price row is after universe snapshot: {token}"
            )
        identity = (token, *event)
        if identity in seen_events:
            raise ValueError(
                f"dump research price path repeats event position: {identity}"
            )
        seen_events.add(identity)
        market_cap = _decimal(
            row.get("market_cap_proxy_usd"),
            label=f"{token} market-cap proxy",
            positive=True,
        )
        grouped[token].append({
            "token": token,
            "block_number": event[0],
            "transaction_index": (
                None if event[1] == -1 else event[1]
            ),
            "log_index": event[2],
            "market_cap_proxy_usd": market_cap,
        })

    missing = sorted(token for token, rows in grouped.items() if not rows)
    if missing:
        raise ValueError(
            f"dump research price-path coverage missing frozen tokens: {missing}"
        )

    output: list[dict] = []
    token_point_counts: dict[str, int] = {}
    token_max_drawdown: dict[str, str] = {}
    for token in sorted(grouped):
        rows = sorted(
            grouped[token],
            key=lambda row: (
                *_event_key(row),
            ),
        )
        token_point_counts[token] = len(rows)
        peak: dict | None = None
        max_drawdown = Decimal("0")
        for row in rows:
            value = Decimal(row["market_cap_proxy_usd"])
            if peak is None or value > Decimal(peak["market_cap_proxy_usd"]):
                peak = row
            peak_value = Decimal(peak["market_cap_proxy_usd"])
            drawdown = (peak_value - value) / peak_value
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            output.append({
                "version": PHASE2_DUMP_GEOMETRY_VERSION,
                "token": token,
                "block_number": int(row["block_number"]),
                "transaction_index": row["transaction_index"],
                "log_index": int(row["log_index"]),
                "market_cap_proxy_usd": _decimal_text(value),
                "trailing_peak_market_cap_proxy_usd": _decimal_text(
                    peak_value
                ),
                "trailing_peak_block": int(peak["block_number"]),
                "trailing_peak_transaction_index": peak[
                    "transaction_index"
                ],
                "trailing_peak_log_index": int(peak["log_index"]),
                "drawdown_fraction": _decimal_text(drawdown),
                "is_new_trailing_peak": row is peak,
            })
        token_max_drawdown[token] = _decimal_text(max_drawdown)

    summary = {
        "version": PHASE2_DUMP_GEOMETRY_VERSION,
        "snapshot_head_block": snapshot,
        "universe_sha256": universe_sha,
        "price_path_provenance_sha256": price_sha,
        "tokens": len(grouped),
        "price_points": len(output),
        "token_price_points": dict(sorted(token_point_counts.items())),
        "token_max_drawdown_fraction": dict(sorted(token_max_drawdown.items())),
        "uses_price_path_only": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
    return output, summary


def _normalize_candidate_specs(
    candidate_specs: Iterable[Mapping[str, object]],
) -> list[dict]:
    normalized = []
    seen: set[str] = set()
    for raw in candidate_specs:
        spec = dict(raw)
        candidate_id = str(spec.get("candidate_id") or "").strip()
        if not candidate_id:
            raise ValueError("dump candidate id is empty")
        if candidate_id in seen:
            raise ValueError(f"dump candidate id repeats: {candidate_id}")
        seen.add(candidate_id)
        family = str(
            spec.get("family") or PEAK_DRAWDOWN_REBOUND_FAMILY
        )
        if family != PEAK_DRAWDOWN_REBOUND_FAMILY:
            raise ValueError(f"unsupported dump candidate family: {family}")
        drawdown = _decimal(
            spec.get("min_drawdown_fraction"),
            label=f"{candidate_id} minimum drawdown",
            positive=True,
        )
        if drawdown >= 1:
            raise ValueError(
                f"{candidate_id} minimum drawdown must be below 1"
            )
        rebound = _decimal(
            spec.get("confirmation_rebound_fraction"),
            label=f"{candidate_id} confirmation rebound",
            positive=True,
        )
        normalized.append({
            "candidate_id": candidate_id,
            "family": family,
            "min_drawdown_fraction": drawdown,
            "confirmation_rebound_fraction": rebound,
        })
    if not normalized:
        raise ValueError("dump research requires explicit candidate specs")
    normalized.sort(key=lambda row: row["candidate_id"])
    return normalized


def research_phase2_dump_candidates(
    geometry_rows: Iterable[Mapping[str, object]],
    candidate_specs: Iterable[Mapping[str, object]],
    *,
    geometry_summary: Mapping[str, object],
) -> tuple[list[dict], dict]:
    """Evaluate explicit dump candidates without selecting or freezing a winner."""

    summary = dict(geometry_summary)
    if str(summary.get("version") or "") != PHASE2_DUMP_GEOMETRY_VERSION:
        raise ValueError("dump candidate research requires canonical geometry")
    if summary.get("uses_price_path_only") is not True:
        raise ValueError("dump candidate research geometry is not price-path only")
    if summary.get("phase2_dump_detector_frozen") is not False:
        raise ValueError("dump candidate research received frozen detector state")
    if summary.get("outcome_labels_computed") is not False:
        raise ValueError("dump candidate research cannot consume outcome labels")

    specs = _normalize_candidate_specs(candidate_specs)
    grouped: dict[str, list[dict]] = {}
    for raw in geometry_rows:
        row = dict(raw)
        if str(row.get("version") or "") != PHASE2_DUMP_GEOMETRY_VERSION:
            raise ValueError("dump candidate geometry row version changed")
        token = normalize_address(str(row.get("token") or ""))
        row["token"] = token
        _event_key(row)
        _decimal(
            row.get("market_cap_proxy_usd"),
            label=f"{token} geometry market-cap proxy",
            positive=True,
        )
        _decimal(
            row.get("trailing_peak_market_cap_proxy_usd"),
            label=f"{token} geometry trailing peak",
            positive=True,
        )
        drawdown = _decimal(
            row.get("drawdown_fraction"),
            label=f"{token} geometry drawdown",
        )
        if drawdown < 0 or drawdown >= 1:
            raise ValueError(f"{token} geometry drawdown is invalid")
        grouped.setdefault(token, []).append(row)

    if len(grouped) != int(summary.get("tokens", -1)):
        raise ValueError("dump candidate geometry token count changed")
    if sum(len(rows) for rows in grouped.values()) != int(
        summary.get("price_points", -1)
    ):
        raise ValueError("dump candidate geometry price-point count changed")

    results = []
    counts: dict[str, Counter] = {
        spec["candidate_id"]: Counter() for spec in specs
    }
    for spec in specs:
        for token in sorted(grouped):
            rows = sorted(
                grouped[token],
                key=_event_key,
            )
            threshold_row = None
            peak_row = None
            trough_row = None
            confirmation_row = None
            for row in rows:
                drawdown = Decimal(str(row["drawdown_fraction"]))
                if threshold_row is None:
                    if drawdown < spec["min_drawdown_fraction"]:
                        continue
                    threshold_row = row
                    peak_key = (
                        int(row["trailing_peak_block"]),
                        (
                            -1
                            if row.get("trailing_peak_transaction_index")
                            is None
                            else int(row["trailing_peak_transaction_index"])
                        ),
                        int(row["trailing_peak_log_index"]),
                    )
                    peak_row = next(
                        candidate
                        for candidate in rows
                        if _event_key(candidate) == peak_key
                    )
                    trough_row = row
                    continue

                value = Decimal(str(row["market_cap_proxy_usd"]))
                trough_value = Decimal(
                    str(trough_row["market_cap_proxy_usd"])
                )
                if value < trough_value:
                    trough_row = row
                    continue
                confirmation_level = trough_value * (
                    Decimal("1")
                    + spec["confirmation_rebound_fraction"]
                )
                if value >= confirmation_level:
                    confirmation_row = row
                    break

            if threshold_row is None:
                status = "no_material_drawdown"
                result = {
                    "version": PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
                    "candidate_id": spec["candidate_id"],
                    "family": spec["family"],
                    "token": token,
                    "candidate_status": status,
                    "point_in_time_confirmed": False,
                    "research_candidate_only": True,
                }
            elif confirmation_row is None:
                status = "drawdown_unconfirmed"
                result = {
                    "version": PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
                    "candidate_id": spec["candidate_id"],
                    "family": spec["family"],
                    "token": token,
                    "candidate_status": status,
                    "threshold_cross_block": int(
                        threshold_row["block_number"]
                    ),
                    "trough_block": int(trough_row["block_number"]),
                    "point_in_time_confirmed": False,
                    "research_candidate_only": True,
                }
            else:
                peak_value = Decimal(
                    str(peak_row["market_cap_proxy_usd"])
                )
                trough_value = Decimal(
                    str(trough_row["market_cap_proxy_usd"])
                )
                confirmation_value = Decimal(
                    str(confirmation_row["market_cap_proxy_usd"])
                )
                observed_drawdown = (
                    peak_value - trough_value
                ) / peak_value
                observed_rebound = (
                    confirmation_value - trough_value
                ) / trough_value
                status = "confirmed"
                result = {
                    "version": PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
                    "candidate_id": spec["candidate_id"],
                    "family": spec["family"],
                    "token": token,
                    "candidate_status": status,
                    "peak_block": int(peak_row["block_number"]),
                    "peak_market_cap_proxy_usd": _decimal_text(peak_value),
                    "threshold_cross_block": int(
                        threshold_row["block_number"]
                    ),
                    "trough_block": int(trough_row["block_number"]),
                    "trough_market_cap_proxy_usd": _decimal_text(
                        trough_value
                    ),
                    "confirmation_block": int(
                        confirmation_row["block_number"]
                    ),
                    "confirmation_market_cap_proxy_usd": _decimal_text(
                        confirmation_value
                    ),
                    "observed_drawdown_fraction": _decimal_text(
                        observed_drawdown
                    ),
                    "observed_confirmation_rebound_fraction": _decimal_text(
                        observed_rebound
                    ),
                    "point_in_time_confirmed": True,
                    "research_candidate_only": True,
                }
            counts[spec["candidate_id"]][status] += 1
            results.append(result)

    results.sort(key=lambda row: (row["candidate_id"], row["token"]))
    normalized_specs = [
        {
            "candidate_id": spec["candidate_id"],
            "family": spec["family"],
            "min_drawdown_fraction": _decimal_text(
                spec["min_drawdown_fraction"]
            ),
            "confirmation_rebound_fraction": _decimal_text(
                spec["confirmation_rebound_fraction"]
            ),
        }
        for spec in specs
    ]
    research_summary = {
        "version": PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
        "geometry_version": PHASE2_DUMP_GEOMETRY_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "universe_sha256": str(summary["universe_sha256"]),
        "price_path_provenance_sha256": str(
            summary["price_path_provenance_sha256"]
        ),
        "tokens": len(grouped),
        "candidate_specs": normalized_specs,
        "candidate_status_counts": {
            candidate_id: dict(sorted(counter.items()))
            for candidate_id, counter in sorted(counts.items())
        },
        "uses_price_path_only": True,
        "point_in_time_confirmation": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
    return results, research_summary
