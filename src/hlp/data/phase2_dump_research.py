"""Research-only Phase-2 first-major-dump path geometry and candidates.

This module deliberately does not freeze a dump threshold or compute comeback
outcomes. It provides deterministic, price-path-only primitives that can be
used to compare candidate lifecycle detectors after the Phase-2 universe is
frozen.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION
from hlp.data.snapshot import iter_jsonl_snapshot, write_jsonl_snapshot


PHASE2_DUMP_GEOMETRY_VERSION = "phase2-dump-geometry-v1"
PHASE2_DUMP_GEOMETRY_HANDOFF_VERSION = (
    "phase2-dump-geometry-handoff-v1"
)
PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION = "phase2-dump-candidate-research-v1"
PHASE2_DUMP_CANDIDATE_HANDOFF_VERSION = (
    "phase2-dump-candidate-handoff-v1"
)
PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION = (
    "phase2-dump-candidate-diagnostics-v1"
)
PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_HANDOFF_VERSION = (
    "phase2-dump-candidate-diagnostics-handoff-v1"
)
PHASE2_DUMP_DETECTOR_FREEZE_VERSION = (
    "phase2-dump-detector-freeze-v1"
)
PHASE2_DUMP_DETECTOR_FREEZE_HANDOFF_VERSION = (
    "phase2-dump-detector-freeze-handoff-v1"
)
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



def materialize_phase2_dump_geometry(
    universe_rows: Iterable[Mapping[str, object]],
    price_rows: Iterable[Mapping[str, object]],
    *,
    universe_summary: Mapping[str, object],
    universe_sha256: str,
    price_path_provenance_sha256: str,
    normalized_price_path_sha256: str,
    output: Path,
) -> tuple[dict, dict]:
    """Stream causal trailing-peak geometry in global price-event order."""

    universe, snapshot = _validate_frozen_universe(
        universe_rows,
        universe_summary,
    )
    universe_sha = _sha256(
        universe_sha256,
        label="Phase-2 universe",
    )
    price_provenance_sha = _sha256(
        price_path_provenance_sha256,
        label="Phase-2 price-path provenance",
    )
    price_path_sha = _sha256(
        normalized_price_path_sha256,
        label="Phase-2 normalized price path",
    )
    expected = {row["token"] for row in universe}

    states: dict[str, dict] = {}
    token_point_counts = {
        token: 0 for token in expected
    }
    token_max_drawdown = {
        token: Decimal("0") for token in expected
    }
    previous_global: tuple[int, int, int, str] | None = None
    previous_by_token: dict[str, tuple[int, int, int]] = {}

    def geometry_rows():
        nonlocal previous_global
        for raw in price_rows:
            row = dict(raw)
            token = normalize_address(str(row.get("token") or ""))
            if token not in expected:
                raise ValueError(
                    "dump research price path contains token outside frozen "
                    f"universe: {token}"
                )
            event = _event_key(row)
            if event[0] > snapshot:
                raise ValueError(
                    "dump research price row is after universe snapshot: "
                    f"{token}"
                )
            global_key = (*event, token)
            if (
                previous_global is not None
                and global_key < previous_global
            ):
                raise ValueError(
                    "dump research price path is not globally chronological"
                )
            previous_global = global_key

            previous = previous_by_token.get(token)
            if previous is not None and event <= previous:
                raise ValueError(
                    "dump research price path repeats or reverses token event "
                    f"position: {(token, *event)}"
                )
            previous_by_token[token] = event

            value = _decimal(
                row.get("market_cap_proxy_usd"),
                label=f"{token} market-cap proxy",
                positive=True,
            )
            state = states.get(token)
            is_peak = (
                state is None
                or value > state["peak_value"]
            )
            if is_peak:
                state = {
                    "peak_value": value,
                    "peak_block": event[0],
                    "peak_transaction_index": (
                        None if event[1] == -1 else event[1]
                    ),
                    "peak_log_index": event[2],
                }
                states[token] = state

            peak_value = state["peak_value"]
            drawdown = (peak_value - value) / peak_value
            if drawdown > token_max_drawdown[token]:
                token_max_drawdown[token] = drawdown
            token_point_counts[token] += 1

            yield {
                "version": PHASE2_DUMP_GEOMETRY_VERSION,
                "token": token,
                "block_number": event[0],
                "transaction_index": (
                    None if event[1] == -1 else event[1]
                ),
                "log_index": event[2],
                "market_cap_proxy_usd": _decimal_text(value),
                "trailing_peak_market_cap_proxy_usd": _decimal_text(
                    peak_value
                ),
                "trailing_peak_block": int(
                    state["peak_block"]
                ),
                "trailing_peak_transaction_index": state[
                    "peak_transaction_index"
                ],
                "trailing_peak_log_index": int(
                    state["peak_log_index"]
                ),
                "drawdown_fraction": _decimal_text(drawdown),
                "is_new_trailing_peak": is_peak,
            }

        missing = sorted(
            token
            for token, count in token_point_counts.items()
            if count <= 0
        )
        if missing:
            raise ValueError(
                "dump research price-path coverage missing frozen tokens: "
                f"{missing[:20]}"
            )

    tapped = iter_jsonl_snapshot(
        geometry_rows(),
        output=output,
        provenance={
            "version": PHASE2_DUMP_GEOMETRY_VERSION,
            "snapshot_head_block": snapshot,
            "universe_sha256": universe_sha,
            "price_path_provenance_sha256": price_provenance_sha,
            "normalized_price_path_sha256": price_path_sha,
            "uses_price_path_only": True,
            "streaming_order": "global_event_order",
            "dump_threshold_frozen": False,
            "phase2_dump_detector_frozen": False,
            "outcome_labels_computed": False,
        },
    )
    for _ in tapped:
        pass
    manifest_path = output.with_suffix(
        output.suffix + ".manifest.json"
    )
    if not manifest_path.is_file():
        raise ValueError(
            "dump geometry streaming snapshot did not finalize"
        )
    import json
    manifest = json.loads(manifest_path.read_text())
    summary = {
        "version": PHASE2_DUMP_GEOMETRY_VERSION,
        "snapshot_head_block": snapshot,
        "universe_sha256": universe_sha,
        "price_path_provenance_sha256": price_provenance_sha,
        "normalized_price_path_sha256": price_path_sha,
        "geometry_sha256": manifest["sha256"],
        "tokens": len(expected),
        "price_points": int(manifest["records"]),
        "token_price_points": dict(
            sorted(token_point_counts.items())
        ),
        "token_max_drawdown_fraction": {
            token: _decimal_text(value)
            for token, value in sorted(
                token_max_drawdown.items()
            )
        },
        "uses_price_path_only": True,
        "streaming_materialization": True,
        "streaming_order": "global_event_order",
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
    return manifest, summary


def build_phase2_dump_geometry_handoff(
    geometry_summary: Mapping[str, object],
    *,
    geometry_summary_sha256: str,
    price_path_handoff_sha256: str,
) -> dict:
    """Bind geometry research to the exact normalized price-path handoff."""

    summary = dict(geometry_summary)
    if (
        str(summary.get("version") or "")
        != PHASE2_DUMP_GEOMETRY_VERSION
    ):
        raise ValueError("dump geometry handoff version changed")
    if summary.get("uses_price_path_only") is not True:
        raise ValueError("dump geometry handoff is not price-path only")
    if summary.get("streaming_materialization") is not True:
        raise ValueError("dump geometry is not streaming-materialized")
    if summary.get("dump_threshold_frozen") is not False:
        raise ValueError("dump geometry cannot freeze a threshold")
    if summary.get("phase2_dump_detector_frozen") is not False:
        raise ValueError("dump geometry cannot freeze a detector")
    if summary.get("outcome_labels_computed") is not False:
        raise ValueError("dump geometry cannot contain outcome labels")

    return {
        "version": PHASE2_DUMP_GEOMETRY_HANDOFF_VERSION,
        "snapshot_head_block": int(
            summary["snapshot_head_block"]
        ),
        "universe_sha256": _sha256(
            summary.get("universe_sha256"),
            label="dump geometry universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="dump geometry normalized price path",
        ),
        "price_path_handoff_sha256": _sha256(
            price_path_handoff_sha256,
            label="dump geometry price-path handoff",
        ),
        "geometry_sha256": _sha256(
            summary.get("geometry_sha256"),
            label="dump geometry tape",
        ),
        "geometry_summary_sha256": _sha256(
            geometry_summary_sha256,
            label="dump geometry summary",
        ),
        "tokens": int(summary["tokens"]),
        "price_points": int(summary["price_points"]),
        "uses_price_path_only": True,
        "dump_geometry_ready": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }



def materialize_phase2_dump_candidate_research(
    geometry_rows: Iterable[Mapping[str, object]],
    candidate_specs: Iterable[Mapping[str, object]],
    *,
    geometry_summary: Mapping[str, object],
    output: Path,
) -> tuple[dict, dict]:
    """Evaluate explicit detector candidates in one causal streaming pass."""

    summary = dict(geometry_summary)
    if (
        str(summary.get("version") or "")
        != PHASE2_DUMP_GEOMETRY_VERSION
    ):
        raise ValueError(
            "dump candidate research requires canonical geometry"
        )
    if summary.get("uses_price_path_only") is not True:
        raise ValueError(
            "dump candidate research geometry is not price-path only"
        )
    if summary.get("phase2_dump_detector_frozen") is not False:
        raise ValueError(
            "dump candidate research received frozen detector state"
        )
    if summary.get("outcome_labels_computed") is not False:
        raise ValueError(
            "dump candidate research cannot consume outcome labels"
        )
    specs = _normalize_candidate_specs(candidate_specs)
    expected_tokens = {
        str(token)
        for token in (summary.get("token_price_points") or {})
    }
    if len(expected_tokens) != int(summary.get("tokens", -1)):
        raise ValueError(
            "dump candidate geometry token membership changed"
        )
    if not expected_tokens:
        raise ValueError("dump candidate geometry has no tokens")

    states = {
        spec["candidate_id"]: {
            token: {
                "threshold": None,
                "peak": None,
                "trough": None,
                "confirmation": None,
            }
            for token in expected_tokens
        }
        for spec in specs
    }
    seen_tokens: set[str] = set()
    token_counts = {
        token: 0 for token in expected_tokens
    }
    previous_global: tuple[int, int, int, str] | None = None
    total_points = 0

    for raw in geometry_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_DUMP_GEOMETRY_VERSION
        ):
            raise ValueError(
                "dump candidate geometry row version changed"
            )
        token = normalize_address(str(row.get("token") or ""))
        if token not in expected_tokens:
            raise ValueError(
                "dump candidate geometry contains unexpected token: "
                f"{token}"
            )
        row["token"] = token
        event = _event_key(row)
        global_key = (*event, token)
        if (
            previous_global is not None
            and global_key < previous_global
        ):
            raise ValueError(
                "dump candidate geometry is not globally chronological"
            )
        previous_global = global_key

        value = _decimal(
            row.get("market_cap_proxy_usd"),
            label=f"{token} geometry market-cap proxy",
            positive=True,
        )
        peak_value = _decimal(
            row.get("trailing_peak_market_cap_proxy_usd"),
            label=f"{token} geometry trailing peak",
            positive=True,
        )
        drawdown = _decimal(
            row.get("drawdown_fraction"),
            label=f"{token} geometry drawdown",
        )
        if drawdown < 0 or drawdown >= 1:
            raise ValueError(
                f"{token} geometry drawdown is invalid"
            )
        if value > peak_value:
            raise ValueError(
                f"{token} geometry value exceeds trailing peak"
            )

        total_points += 1
        token_counts[token] += 1
        seen_tokens.add(token)

        for spec in specs:
            state = states[spec["candidate_id"]][token]
            if state["confirmation"] is not None:
                continue
            if state["threshold"] is None:
                if drawdown < spec["min_drawdown_fraction"]:
                    continue
                state["threshold"] = {
                    "block_number": event[0],
                    "transaction_index": (
                        None if event[1] == -1 else event[1]
                    ),
                    "log_index": event[2],
                }
                state["peak"] = {
                    "block_number": int(
                        row["trailing_peak_block"]
                    ),
                    "transaction_index": row[
                        "trailing_peak_transaction_index"
                    ],
                    "log_index": int(
                        row["trailing_peak_log_index"]
                    ),
                    "market_cap_proxy_usd": peak_value,
                }
                state["trough"] = {
                    "block_number": event[0],
                    "transaction_index": (
                        None if event[1] == -1 else event[1]
                    ),
                    "log_index": event[2],
                    "market_cap_proxy_usd": value,
                }
                continue

            trough = state["trough"]
            trough_value = trough["market_cap_proxy_usd"]
            if value < trough_value:
                state["trough"] = {
                    "block_number": event[0],
                    "transaction_index": (
                        None if event[1] == -1 else event[1]
                    ),
                    "log_index": event[2],
                    "market_cap_proxy_usd": value,
                }
                continue
            confirmation_level = trough_value * (
                Decimal("1")
                + spec["confirmation_rebound_fraction"]
            )
            if value >= confirmation_level:
                state["confirmation"] = {
                    "block_number": event[0],
                    "transaction_index": (
                        None if event[1] == -1 else event[1]
                    ),
                    "log_index": event[2],
                    "market_cap_proxy_usd": value,
                }

    if total_points != int(summary.get("price_points", -1)):
        raise ValueError(
            "dump candidate geometry price-point count changed"
        )
    if seen_tokens != expected_tokens:
        raise ValueError(
            "dump candidate geometry token coverage changed"
        )
    expected_counts = {
        str(token): int(count)
        for token, count in (
            summary.get("token_price_points") or {}
        ).items()
    }
    if token_counts != expected_counts:
        raise ValueError(
            "dump candidate geometry per-token point counts changed"
        )

    results = []
    counts: dict[str, Counter] = {
        spec["candidate_id"]: Counter() for spec in specs
    }
    for spec in specs:
        candidate_id = spec["candidate_id"]
        for token in sorted(expected_tokens):
            state = states[candidate_id][token]
            threshold = state["threshold"]
            trough = state["trough"]
            confirmation = state["confirmation"]
            if threshold is None:
                status = "no_material_drawdown"
                result = {
                    "version": (
                        PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
                    ),
                    "candidate_id": candidate_id,
                    "family": spec["family"],
                    "token": token,
                    "candidate_status": status,
                    "point_in_time_confirmed": False,
                    "research_candidate_only": True,
                }
            elif confirmation is None:
                status = "drawdown_unconfirmed"
                result = {
                    "version": (
                        PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
                    ),
                    "candidate_id": candidate_id,
                    "family": spec["family"],
                    "token": token,
                    "candidate_status": status,
                    "threshold_cross_block": int(
                        threshold["block_number"]
                    ),
                    "threshold_cross_transaction_index": threshold[
                        "transaction_index"
                    ],
                    "threshold_cross_log_index": int(
                        threshold["log_index"]
                    ),
                    "trough_block": int(
                        trough["block_number"]
                    ),
                    "trough_transaction_index": trough[
                        "transaction_index"
                    ],
                    "trough_log_index": int(
                        trough["log_index"]
                    ),
                    "point_in_time_confirmed": False,
                    "research_candidate_only": True,
                }
            else:
                peak = state["peak"]
                peak_value = peak["market_cap_proxy_usd"]
                trough_value = trough["market_cap_proxy_usd"]
                confirmation_value = confirmation[
                    "market_cap_proxy_usd"
                ]
                observed_drawdown = (
                    peak_value - trough_value
                ) / peak_value
                observed_rebound = (
                    confirmation_value - trough_value
                ) / trough_value
                status = "confirmed"
                result = {
                    "version": (
                        PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
                    ),
                    "candidate_id": candidate_id,
                    "family": spec["family"],
                    "token": token,
                    "candidate_status": status,
                    "peak_block": int(peak["block_number"]),
                    "peak_transaction_index": peak[
                        "transaction_index"
                    ],
                    "peak_log_index": int(peak["log_index"]),
                    "peak_market_cap_proxy_usd": _decimal_text(
                        peak_value
                    ),
                    "threshold_cross_block": int(
                        threshold["block_number"]
                    ),
                    "threshold_cross_transaction_index": threshold[
                        "transaction_index"
                    ],
                    "threshold_cross_log_index": int(
                        threshold["log_index"]
                    ),
                    "trough_block": int(
                        trough["block_number"]
                    ),
                    "trough_transaction_index": trough[
                        "transaction_index"
                    ],
                    "trough_log_index": int(
                        trough["log_index"]
                    ),
                    "trough_market_cap_proxy_usd": _decimal_text(
                        trough_value
                    ),
                    "confirmation_block": int(
                        confirmation["block_number"]
                    ),
                    "confirmation_transaction_index": confirmation[
                        "transaction_index"
                    ],
                    "confirmation_log_index": int(
                        confirmation["log_index"]
                    ),
                    "confirmation_market_cap_proxy_usd": _decimal_text(
                        confirmation_value
                    ),
                    "observed_drawdown_fraction": _decimal_text(
                        observed_drawdown
                    ),
                    "observed_confirmation_rebound_fraction": (
                        _decimal_text(observed_rebound)
                    ),
                    "point_in_time_confirmed": True,
                    "research_candidate_only": True,
                }
            counts[candidate_id][status] += 1
            results.append(result)

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
    import hashlib
    import json
    specs_bytes = (
        json.dumps(
            normalized_specs,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    specs_sha = hashlib.sha256(specs_bytes).hexdigest()

    manifest = write_jsonl_snapshot(
        results,
        output=output,
        provenance={
            "version": PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
            "geometry_sha256": _sha256(
                summary.get("geometry_sha256"),
                label="dump candidate geometry",
            ),
            "candidate_specs_sha256": specs_sha,
            "uses_price_path_only": True,
            "point_in_time_confirmation": True,
            "candidate_selected": False,
            "dump_threshold_frozen": False,
            "phase2_dump_detector_frozen": False,
            "outcome_labels_computed": False,
        },
    )
    research_summary = {
        "version": PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION,
        "geometry_version": PHASE2_DUMP_GEOMETRY_VERSION,
        "snapshot_head_block": int(
            summary["snapshot_head_block"]
        ),
        "universe_sha256": str(summary["universe_sha256"]),
        "price_path_provenance_sha256": str(
            summary["price_path_provenance_sha256"]
        ),
        "normalized_price_path_sha256": str(
            summary["normalized_price_path_sha256"]
        ),
        "geometry_sha256": str(summary["geometry_sha256"]),
        "candidate_specs": normalized_specs,
        "candidate_specs_sha256": specs_sha,
        "tokens": len(expected_tokens),
        "candidate_rows": int(manifest["records"]),
        "candidate_rows_sha256": manifest["sha256"],
        "candidate_status_counts": {
            candidate_id: dict(sorted(counter.items()))
            for candidate_id, counter in sorted(counts.items())
        },
        "uses_price_path_only": True,
        "point_in_time_confirmation": True,
        "streaming_evaluation": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
    return manifest, research_summary


def build_phase2_dump_candidate_handoff(
    research_summary: Mapping[str, object],
    *,
    research_summary_sha256: str,
    geometry_handoff_sha256: str,
) -> dict:
    """Bind candidate-comparison evidence without selecting a detector."""

    summary = dict(research_summary)
    if (
        str(summary.get("version") or "")
        != PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
    ):
        raise ValueError("dump candidate handoff version changed")
    if summary.get("uses_price_path_only") is not True:
        raise ValueError(
            "dump candidate handoff is not price-path only"
        )
    if summary.get("point_in_time_confirmation") is not True:
        raise ValueError(
            "dump candidate handoff lacks point-in-time confirmation"
        )
    if summary.get("candidate_selected") is not False:
        raise ValueError(
            "dump candidate handoff cannot select a detector"
        )
    if summary.get("dump_threshold_frozen") is not False:
        raise ValueError(
            "dump candidate handoff cannot freeze a threshold"
        )
    if summary.get("phase2_dump_detector_frozen") is not False:
        raise ValueError(
            "dump candidate handoff cannot freeze a detector"
        )
    if summary.get("outcome_labels_computed") is not False:
        raise ValueError(
            "dump candidate handoff cannot contain outcome labels"
        )

    return {
        "version": PHASE2_DUMP_CANDIDATE_HANDOFF_VERSION,
        "snapshot_head_block": int(
            summary["snapshot_head_block"]
        ),
        "universe_sha256": _sha256(
            summary.get("universe_sha256"),
            label="dump candidate universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="dump candidate price path",
        ),
        "geometry_sha256": _sha256(
            summary.get("geometry_sha256"),
            label="dump candidate geometry",
        ),
        "geometry_handoff_sha256": _sha256(
            geometry_handoff_sha256,
            label="dump candidate geometry handoff",
        ),
        "candidate_specs_sha256": _sha256(
            summary.get("candidate_specs_sha256"),
            label="dump candidate specs",
        ),
        "candidate_rows_sha256": _sha256(
            summary.get("candidate_rows_sha256"),
            label="dump candidate rows",
        ),
        "research_summary_sha256": _sha256(
            research_summary_sha256,
            label="dump candidate summary",
        ),
        "tokens": int(summary["tokens"]),
        "candidate_rows": int(summary["candidate_rows"]),
        "uses_price_path_only": True,
        "candidate_research_ready": True,
        "candidate_selected": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }



def _median_decimal(values: list[Decimal]) -> str | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return _decimal_text(ordered[middle])
    return _decimal_text(
        (ordered[middle - 1] + ordered[middle]) / Decimal("2")
    )


def _median_int(values: list[int]) -> str | None:
    return _median_decimal([Decimal(value) for value in values])


def build_phase2_dump_candidate_diagnostics(
    candidate_rows: Iterable[Mapping[str, object]],
    *,
    research_summary: Mapping[str, object],
) -> tuple[list[dict], dict]:
    """Describe detector behavior without outcome labels or candidate selection."""

    summary = dict(research_summary)
    if (
        str(summary.get("version") or "")
        != PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
    ):
        raise ValueError(
            "dump candidate diagnostics require canonical candidate research"
        )
    if summary.get("uses_price_path_only") is not True:
        raise ValueError(
            "dump candidate diagnostics are not price-path only"
        )
    if summary.get("point_in_time_confirmation") is not True:
        raise ValueError(
            "dump candidate diagnostics require point-in-time confirmation"
        )
    if summary.get("candidate_selected") is not False:
        raise ValueError(
            "dump candidate diagnostics cannot consume selected detector"
        )
    if summary.get("phase2_dump_detector_frozen") is not False:
        raise ValueError(
            "dump candidate diagnostics cannot consume frozen detector"
        )
    if summary.get("outcome_labels_computed") is not False:
        raise ValueError(
            "dump candidate diagnostics cannot consume outcome labels"
        )

    specs = {
        str(row["candidate_id"]): dict(row)
        for row in summary.get("candidate_specs") or []
    }
    if not specs:
        raise ValueError(
            "dump candidate diagnostics have no candidate specs"
        )
    tokens = int(summary.get("tokens", -1))
    if tokens <= 0:
        raise ValueError(
            "dump candidate diagnostics token count is invalid"
        )

    grouped = {
        candidate_id: []
        for candidate_id in specs
    }
    seen: set[tuple[str, str]] = set()
    for raw in candidate_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
        ):
            raise ValueError(
                "dump candidate diagnostics row version changed"
            )
        candidate_id = str(row.get("candidate_id") or "")
        token = normalize_address(str(row.get("token") or ""))
        if candidate_id not in specs:
            raise ValueError(
                "dump candidate diagnostics contain unknown candidate: "
                f"{candidate_id}"
            )
        identity = (candidate_id, token)
        if identity in seen:
            raise ValueError(
                "dump candidate diagnostics repeat candidate/token: "
                f"{identity}"
            )
        seen.add(identity)
        status = str(row.get("candidate_status") or "")
        if status not in {
            "confirmed",
            "drawdown_unconfirmed",
            "no_material_drawdown",
        }:
            raise ValueError(
                f"dump candidate diagnostics status is invalid: {status}"
            )
        confirmed = status == "confirmed"
        if bool(row.get("point_in_time_confirmed")) != confirmed:
            raise ValueError(
                "dump candidate point-in-time confirmation flag drift"
            )
        if row.get("research_candidate_only") is not True:
            raise ValueError(
                "dump candidate row is not research-only"
            )
        row["token"] = token
        grouped[candidate_id].append(row)

    expected_rows = tokens * len(specs)
    if len(seen) != expected_rows:
        raise ValueError(
            "dump candidate diagnostics candidate/token coverage changed"
        )
    if int(summary.get("candidate_rows", -1)) != expected_rows:
        raise ValueError(
            "dump candidate diagnostics summary row count changed"
        )

    status_signatures = {}
    diagnostics = []
    for candidate_id in sorted(specs):
        rows = grouped[candidate_id]
        if len(rows) != tokens:
            raise ValueError(
                f"{candidate_id} candidate token coverage changed"
            )
        statuses = Counter(
            str(row["candidate_status"]) for row in rows
        )
        confirmed = [
            row
            for row in rows
            if row["candidate_status"] == "confirmed"
        ]
        threshold_to_trough = [
            int(row["trough_block"])
            - int(row["threshold_cross_block"])
            for row in confirmed
        ]
        trough_to_confirmation = [
            int(row["confirmation_block"])
            - int(row["trough_block"])
            for row in confirmed
        ]
        threshold_to_confirmation = [
            int(row["confirmation_block"])
            - int(row["threshold_cross_block"])
            for row in confirmed
        ]
        peak_to_confirmation = [
            int(row["confirmation_block"])
            - int(row["peak_block"])
            for row in confirmed
        ]
        for values, label in (
            (threshold_to_trough, "threshold-to-trough"),
            (trough_to_confirmation, "trough-to-confirmation"),
            (
                threshold_to_confirmation,
                "threshold-to-confirmation",
            ),
            (peak_to_confirmation, "peak-to-confirmation"),
        ):
            if any(value < 0 for value in values):
                raise ValueError(
                    f"{candidate_id} {label} block ordering is invalid"
                )

        drawdowns = [
            _decimal(
                row["observed_drawdown_fraction"],
                label=f"{candidate_id} observed drawdown",
            )
            for row in confirmed
        ]
        rebounds = [
            _decimal(
                row["observed_confirmation_rebound_fraction"],
                label=f"{candidate_id} observed rebound",
            )
            for row in confirmed
        ]
        signature = tuple(
            (
                row["token"],
                row["candidate_status"],
                row.get("confirmation_block"),
                row.get("confirmation_transaction_index"),
                row.get("confirmation_log_index"),
            )
            for row in sorted(rows, key=lambda value: value["token"])
        )
        status_signatures[candidate_id] = signature

        def bounds(values: list[Decimal]):
            if not values:
                return {
                    "min": None,
                    "median": None,
                    "max": None,
                }
            return {
                "min": _decimal_text(min(values)),
                "median": _median_decimal(values),
                "max": _decimal_text(max(values)),
            }

        def int_bounds(values: list[int]):
            if not values:
                return {
                    "min": None,
                    "median": None,
                    "max": None,
                }
            return {
                "min": min(values),
                "median": _median_int(values),
                "max": max(values),
            }

        diagnostics.append({
            "version": PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION,
            "candidate_id": candidate_id,
            "family": specs[candidate_id]["family"],
            "min_drawdown_fraction": specs[candidate_id][
                "min_drawdown_fraction"
            ],
            "confirmation_rebound_fraction": specs[candidate_id][
                "confirmation_rebound_fraction"
            ],
            "tokens": tokens,
            "status_counts": dict(sorted(statuses.items())),
            "confirmed_fraction": _decimal_text(
                Decimal(len(confirmed)) / Decimal(tokens)
            ),
            "threshold_to_trough_blocks": int_bounds(
                threshold_to_trough
            ),
            "trough_to_confirmation_blocks": int_bounds(
                trough_to_confirmation
            ),
            "threshold_to_confirmation_blocks": int_bounds(
                threshold_to_confirmation
            ),
            "peak_to_confirmation_blocks": int_bounds(
                peak_to_confirmation
            ),
            "observed_drawdown_fraction": bounds(drawdowns),
            "observed_confirmation_rebound_fraction": bounds(rebounds),
            "uses_outcome_labels": False,
            "candidate_selected": False,
            "detector_freeze_ready": False,
        })

    equivalent = []
    candidate_ids = sorted(status_signatures)
    for index, left in enumerate(candidate_ids):
        for right in candidate_ids[index + 1:]:
            if status_signatures[left] == status_signatures[right]:
                equivalent.append([left, right])

    diagnostic_summary = {
        "version": PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION,
        "candidate_research_version": (
            PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
        ),
        "snapshot_head_block": int(
            summary["snapshot_head_block"]
        ),
        "universe_sha256": str(summary["universe_sha256"]),
        "geometry_sha256": str(summary["geometry_sha256"]),
        "candidate_specs_sha256": str(
            summary["candidate_specs_sha256"]
        ),
        "candidate_rows_sha256": str(
            summary["candidate_rows_sha256"]
        ),
        "tokens": tokens,
        "candidates": len(specs),
        "equivalent_candidate_pairs": equivalent,
        "uses_price_path_only": True,
        "uses_outcome_labels": False,
        "point_in_time_confirmation": True,
        "candidate_selected": False,
        "detector_freeze_ready": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
    return diagnostics, diagnostic_summary



def build_phase2_dump_candidate_diagnostics_handoff(
    diagnostics_summary: Mapping[str, object],
    *,
    diagnostics_sha256: str,
    diagnostics_summary_sha256: str,
    candidate_research_handoff_sha256: str,
) -> dict:
    """Bind structural candidate diagnostics without approving a detector."""

    summary = dict(diagnostics_summary)
    if (
        str(summary.get("version") or "")
        != PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION
    ):
        raise ValueError(
            "dump candidate diagnostics handoff version changed"
        )
    if summary.get("uses_price_path_only") is not True:
        raise ValueError(
            "dump candidate diagnostics handoff is not price-path only"
        )
    if summary.get("uses_outcome_labels") is not False:
        raise ValueError(
            "dump candidate diagnostics handoff uses outcome labels"
        )
    if summary.get("point_in_time_confirmation") is not True:
        raise ValueError(
            "dump candidate diagnostics handoff is not point-in-time"
        )
    if summary.get("candidate_selected") is not False:
        raise ValueError(
            "dump candidate diagnostics handoff cannot select a detector"
        )
    if summary.get("detector_freeze_ready") is not False:
        raise ValueError(
            "dump candidate diagnostics cannot self-approve detector freeze"
        )
    if summary.get("phase2_dump_detector_frozen") is not False:
        raise ValueError(
            "dump candidate diagnostics handoff cannot freeze detector"
        )
    if summary.get("outcome_labels_computed") is not False:
        raise ValueError(
            "dump candidate diagnostics handoff cannot contain labels"
        )

    return {
        "version": (
            PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_HANDOFF_VERSION
        ),
        "snapshot_head_block": int(
            summary["snapshot_head_block"]
        ),
        "universe_sha256": _sha256(
            summary.get("universe_sha256"),
            label="dump diagnostics universe",
        ),
        "geometry_sha256": _sha256(
            summary.get("geometry_sha256"),
            label="dump diagnostics geometry",
        ),
        "candidate_specs_sha256": _sha256(
            summary.get("candidate_specs_sha256"),
            label="dump diagnostics candidate specs",
        ),
        "candidate_rows_sha256": _sha256(
            summary.get("candidate_rows_sha256"),
            label="dump diagnostics candidate rows",
        ),
        "candidate_research_handoff_sha256": _sha256(
            candidate_research_handoff_sha256,
            label="dump diagnostics candidate handoff",
        ),
        "diagnostics_sha256": _sha256(
            diagnostics_sha256,
            label="dump diagnostics rows",
        ),
        "diagnostics_summary_sha256": _sha256(
            diagnostics_summary_sha256,
            label="dump diagnostics summary",
        ),
        "tokens": int(summary["tokens"]),
        "candidates": int(summary["candidates"]),
        "candidate_selected": False,
        "detector_freeze_ready": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }



def materialize_phase2_dump_detector_freeze(
    candidate_rows: Iterable[Mapping[str, object]],
    diagnostics_rows: Iterable[Mapping[str, object]],
    *,
    research_summary: Mapping[str, object],
    diagnostics_summary: Mapping[str, object],
    selected_candidate_id: str,
    output: Path,
) -> tuple[dict, dict]:
    """Freeze one explicitly selected, outcome-blind detector candidate."""

    research = dict(research_summary)
    diagnostics = dict(diagnostics_summary)
    selected = str(selected_candidate_id).strip()
    if not selected:
        raise ValueError("dump detector freeze requires selected candidate id")
    if (
        str(research.get("version") or "")
        != PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
    ):
        raise ValueError("dump detector freeze candidate research version changed")
    if (
        str(diagnostics.get("version") or "")
        != PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION
    ):
        raise ValueError("dump detector freeze diagnostics version changed")
    for payload, label in (
        (research, "candidate research"),
        (diagnostics, "candidate diagnostics"),
    ):
        if payload.get("uses_price_path_only") is not True:
            raise ValueError(
                f"dump detector freeze {label} is not price-path only"
            )
        if payload.get("candidate_selected") is not False:
            raise ValueError(
                f"dump detector freeze {label} already selected a candidate"
            )
        if payload.get("phase2_dump_detector_frozen") is not False:
            raise ValueError(
                f"dump detector freeze {label} already froze a detector"
            )
        if payload.get("outcome_labels_computed") is not False:
            raise ValueError(
                f"dump detector freeze {label} contains outcome labels"
            )
    if diagnostics.get("uses_outcome_labels") is not False:
        raise ValueError(
            "dump detector freeze diagnostics use outcome labels"
        )
    if diagnostics.get("detector_freeze_ready") is not False:
        raise ValueError(
            "dump detector diagnostics cannot self-approve freeze"
        )
    if research.get("point_in_time_confirmation") is not True:
        raise ValueError(
            "dump detector freeze candidate research is not point-in-time"
        )
    if diagnostics.get("point_in_time_confirmation") is not True:
        raise ValueError(
            "dump detector freeze diagnostics are not point-in-time"
        )

    linked_fields = (
        "snapshot_head_block",
        "universe_sha256",
        "geometry_sha256",
        "candidate_specs_sha256",
        "candidate_rows_sha256",
        "tokens",
    )
    for field in linked_fields:
        if str(research.get(field)) != str(diagnostics.get(field)):
            raise ValueError(
                f"dump detector freeze research/diagnostics drift: {field}"
            )

    specs = {
        str(row["candidate_id"]): dict(row)
        for row in (research.get("candidate_specs") or [])
    }
    if selected not in specs:
        raise ValueError(
            f"dump detector freeze selected candidate is unknown: {selected}"
        )
    selected_spec = specs[selected]
    if (
        str(selected_spec.get("family") or "")
        != PEAK_DRAWDOWN_REBOUND_FAMILY
    ):
        raise ValueError(
            "dump detector freeze selected candidate family changed"
        )

    diagnostic_map = {}
    for raw in diagnostics_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_DUMP_CANDIDATE_DIAGNOSTICS_VERSION
        ):
            raise ValueError("dump detector diagnostics row version changed")
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id not in specs:
            raise ValueError(
                f"dump detector diagnostics contain unknown candidate: "
                f"{candidate_id}"
            )
        if candidate_id in diagnostic_map:
            raise ValueError(
                f"dump detector diagnostics repeat candidate: {candidate_id}"
            )
        if row.get("uses_outcome_labels") is not False:
            raise ValueError(
                f"dump detector diagnostics row uses outcomes: {candidate_id}"
            )
        if row.get("candidate_selected") is not False:
            raise ValueError(
                f"dump detector diagnostics row selects candidate: {candidate_id}"
            )
        diagnostic_map[candidate_id] = row
    if set(diagnostic_map) != set(specs):
        raise ValueError(
            "dump detector diagnostics candidate coverage changed"
        )
    selected_diagnostic = diagnostic_map[selected]

    tokens = int(research.get("tokens", -1))
    if tokens <= 0:
        raise ValueError("dump detector freeze token count is invalid")
    all_rows = 0
    selected_rows = []
    seen_selected_tokens = set()
    statuses = Counter()
    for raw in candidate_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_DUMP_CANDIDATE_RESEARCH_VERSION
        ):
            raise ValueError("dump detector candidate row version changed")
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id not in specs:
            raise ValueError(
                f"dump detector freeze contains unknown candidate: "
                f"{candidate_id}"
            )
        token = normalize_address(str(row.get("token") or ""))
        all_rows += 1
        if candidate_id != selected:
            continue
        if token in seen_selected_tokens:
            raise ValueError(
                f"dump detector freeze repeats selected token: {token}"
            )
        seen_selected_tokens.add(token)
        status = str(row.get("candidate_status") or "")
        if status not in {
            "confirmed",
            "drawdown_unconfirmed",
            "no_material_drawdown",
        }:
            raise ValueError(
                f"dump detector freeze selected status is invalid: {status}"
            )
        confirmed = status == "confirmed"
        if bool(row.get("point_in_time_confirmed")) != confirmed:
            raise ValueError(
                "dump detector freeze point-in-time flag drift"
            )
        if row.get("research_candidate_only") is not True:
            raise ValueError(
                "dump detector freeze candidate row is not research-only"
            )
        frozen = {
            key: value
            for key, value in row.items()
            if key not in {
                "version",
                "candidate_id",
                "research_candidate_only",
            }
        }
        frozen.update({
            "version": PHASE2_DUMP_DETECTOR_FREEZE_VERSION,
            "detector_id": selected,
            "detector_family": selected_spec["family"],
            "candidate_status": status,
            "point_in_time_confirmed": confirmed,
            "detector_frozen": True,
        })
        selected_rows.append(frozen)
        statuses[status] += 1

    expected_all = int(research.get("candidate_rows", -1))
    if all_rows != expected_all:
        raise ValueError(
            "dump detector freeze candidate row count changed"
        )
    if len(selected_rows) != tokens:
        raise ValueError(
            "dump detector freeze selected candidate token coverage changed"
        )
    if len(seen_selected_tokens) != tokens:
        raise ValueError(
            "dump detector freeze selected candidate token uniqueness changed"
        )

    selected_rows.sort(key=lambda row: row["token"])
    manifest = write_jsonl_snapshot(
        selected_rows,
        output=output,
        provenance={
            "version": PHASE2_DUMP_DETECTOR_FREEZE_VERSION,
            "selected_candidate_id": selected,
            "candidate_specs_sha256": research["candidate_specs_sha256"],
            "candidate_rows_sha256": research["candidate_rows_sha256"],
            "uses_price_path_only": True,
            "uses_outcome_labels": False,
            "selection_mode": "explicit_candidate_id",
            "candidate_selected": True,
            "dump_threshold_frozen": True,
            "phase2_dump_detector_frozen": True,
            "outcome_labels_computed": False,
        },
    )

    equivalent_candidates = sorted({
        right if left == selected else left
        for pair in diagnostics.get("equivalent_candidate_pairs") or []
        for left, right in [pair]
        if selected in {left, right}
    })
    freeze_summary = {
        "version": PHASE2_DUMP_DETECTOR_FREEZE_VERSION,
        "snapshot_head_block": int(research["snapshot_head_block"]),
        "universe_sha256": str(research["universe_sha256"]),
        "normalized_price_path_sha256": str(
            research["normalized_price_path_sha256"]
        ),
        "geometry_sha256": str(research["geometry_sha256"]),
        "candidate_specs_sha256": str(
            research["candidate_specs_sha256"]
        ),
        "candidate_rows_sha256": str(
            research["candidate_rows_sha256"]
        ),
        "selected_candidate_id": selected,
        "selected_candidate_spec": dict(selected_spec),
        "selected_candidate_diagnostics": dict(selected_diagnostic),
        "equivalent_candidate_ids": equivalent_candidates,
        "tokens": tokens,
        "detector_rows": int(manifest["records"]),
        "detector_rows_sha256": manifest["sha256"],
        "status_counts": dict(sorted(statuses.items())),
        "confirmed_tokens": int(statuses.get("confirmed", 0)),
        "uses_price_path_only": True,
        "uses_outcome_labels": False,
        "selection_mode": "explicit_candidate_id",
        "point_in_time_confirmation": True,
        "candidate_selected": True,
        "detector_freeze_ready": True,
        "dump_threshold_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": False,
    }
    return manifest, freeze_summary


def build_phase2_dump_detector_freeze_handoff(
    freeze_summary: Mapping[str, object],
    *,
    freeze_summary_sha256: str,
    candidate_research_handoff_sha256: str,
    candidate_diagnostics_handoff_sha256: str,
) -> dict:
    """Bind an explicit detector freeze before outcome-label computation."""

    summary = dict(freeze_summary)
    if (
        str(summary.get("version") or "")
        != PHASE2_DUMP_DETECTOR_FREEZE_VERSION
    ):
        raise ValueError("dump detector freeze handoff version changed")
    if summary.get("uses_price_path_only") is not True:
        raise ValueError("dump detector freeze is not price-path only")
    if summary.get("uses_outcome_labels") is not False:
        raise ValueError("dump detector freeze used outcome labels")
    if summary.get("selection_mode") != "explicit_candidate_id":
        raise ValueError("dump detector freeze selection mode changed")
    if summary.get("point_in_time_confirmation") is not True:
        raise ValueError(
            "dump detector freeze is not point-in-time compatible"
        )
    if summary.get("candidate_selected") is not True:
        raise ValueError("dump detector freeze lacks selected candidate")
    if summary.get("detector_freeze_ready") is not True:
        raise ValueError("dump detector freeze is not ready")
    if summary.get("dump_threshold_frozen") is not True:
        raise ValueError("dump detector threshold is not frozen")
    if summary.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("dump detector is not frozen")
    if summary.get("outcome_labels_computed") is not False:
        raise ValueError(
            "dump detector freeze cannot contain outcome labels"
        )

    spec = dict(summary.get("selected_candidate_spec") or {})
    selected = str(summary.get("selected_candidate_id") or "")
    if not selected or str(spec.get("candidate_id") or "") != selected:
        raise ValueError("dump detector freeze selected spec drift")

    return {
        "version": PHASE2_DUMP_DETECTOR_FREEZE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "universe_sha256": _sha256(
            summary.get("universe_sha256"),
            label="dump detector universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="dump detector price path",
        ),
        "geometry_sha256": _sha256(
            summary.get("geometry_sha256"),
            label="dump detector geometry",
        ),
        "candidate_specs_sha256": _sha256(
            summary.get("candidate_specs_sha256"),
            label="dump detector candidate specs",
        ),
        "candidate_rows_sha256": _sha256(
            summary.get("candidate_rows_sha256"),
            label="dump detector candidate rows",
        ),
        "candidate_research_handoff_sha256": _sha256(
            candidate_research_handoff_sha256,
            label="dump detector candidate research handoff",
        ),
        "candidate_diagnostics_handoff_sha256": _sha256(
            candidate_diagnostics_handoff_sha256,
            label="dump detector diagnostics handoff",
        ),
        "detector_rows_sha256": _sha256(
            summary.get("detector_rows_sha256"),
            label="dump detector rows",
        ),
        "freeze_summary_sha256": _sha256(
            freeze_summary_sha256,
            label="dump detector freeze summary",
        ),
        "selected_candidate_id": selected,
        "selected_candidate_spec": spec,
        "tokens": int(summary["tokens"]),
        "detector_rows": int(summary["detector_rows"]),
        "confirmed_tokens": int(summary["confirmed_tokens"]),
        "candidate_selected": True,
        "detector_freeze_ready": True,
        "dump_threshold_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": False,
    }
