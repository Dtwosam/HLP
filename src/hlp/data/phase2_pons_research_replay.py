"""Streaming Pons research-point replay from accepted canonical inputs."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from hlp.data.snapshot import iter_jsonl_snapshot
from hlp.data.universe import (
    build_v1_market_cap_points,
    summarize_v1_market_caps,
)
from hlp.data.v2_curve import (
    build_v2_curve_market_cap_points,
    summarize_v2_curve_market_caps,
)
from hlp.data.v4 import (
    build_v2_graduation_seed_points,
    build_v2_v4_market_cap_points,
)


PONS_RESEARCH_REPLAY_VERSION = "phase2-pons-research-replay-v1"


def _manifest(output: Path) -> dict:
    path = output.with_suffix(output.suffix + ".manifest.json")
    if not path.is_file():
        raise ValueError(
            f"Pons research replay did not finalize snapshot: {output}"
        )
    return json.loads(path.read_text())


def _provenance(
    supplied: dict,
    *,
    phase: str,
) -> dict:
    value = dict(supplied)
    value.update({
        "version": PONS_RESEARCH_REPLAY_VERSION,
        "phase": phase,
        "canonical_replay": True,
        "research_only": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    })
    return value


def materialize_v1_research_points(
    registry_rows: Iterable[dict],
    swap_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    output: Path,
    provenance: dict,
    initial_weth_usd: Decimal,
    weth_decimals: int,
    usdg_decimals: int,
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
    quote_decimals_by_token: dict[str, int] | None = None,
) -> tuple[list[dict], dict]:
    """Replay V1 once, streaming the canonical point tape into research storage."""

    points = build_v1_market_cap_points(
        registry_rows,
        swap_rows,
        weth_usd_anchor_points,
        initial_weth_usd=initial_weth_usd,
        weth_decimals=weth_decimals,
        usdg_decimals=usdg_decimals,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_usd_updates,
        quote_decimals_by_token=quote_decimals_by_token,
    )
    tapped = iter_jsonl_snapshot(
        points,
        output=output,
        provenance=_provenance(provenance, phase="pons_v1_v3"),
    )
    summary = summarize_v1_market_caps(tapped)
    return summary, _manifest(output)


def materialize_v2_curve_research_points(
    registry_rows: Iterable[dict],
    curve_event_rows: Iterable[dict],
    weth_usd_anchor_points: Iterable[dict],
    *,
    output: Path,
    provenance: dict,
    initial_weth_usd: Decimal,
    initial_quote_usd: dict[str, Decimal] | None = None,
    quote_usd_updates: Iterable[dict] = (),
) -> tuple[list[dict], dict]:
    """Replay the V2 curve once while preserving every canonical price point."""

    points = build_v2_curve_market_cap_points(
        registry_rows,
        curve_event_rows,
        weth_usd_anchor_points,
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_usd_updates,
    )
    tapped = iter_jsonl_snapshot(
        points,
        output=output,
        provenance=_provenance(provenance, phase="pons_v2_curve"),
    )
    summary = summarize_v2_curve_market_caps(tapped)
    return summary, _manifest(output)


def materialize_v2_post_graduation_research_points(
    registry_rows: Iterable[dict],
    graduation_rows: Iterable[dict],
    registration_rows: Iterable[dict],
    v4_event_rows: Iterable[dict],
    *,
    seed_anchor_points: Iterable[dict],
    v4_anchor_points: Iterable[dict],
    seed_output: Path,
    v4_output: Path,
    provenance: dict,
    initial_weth_usd: Decimal,
    seed_initial_quote_usd: dict[str, Decimal] | None = None,
    seed_quote_usd_updates: Iterable[dict] = (),
    v4_initial_quote_usd: dict[str, Decimal] | None = None,
    v4_quote_usd_updates: Iterable[dict] = (),
) -> tuple[list[dict], list[dict], dict, dict]:
    """Materialize V2 graduation-seed and V4 point tapes without buffering them."""

    registry = [dict(row) for row in registry_rows]
    graduations = [dict(row) for row in graduation_rows]
    registrations = [dict(row) for row in registration_rows]

    seed_points = build_v2_graduation_seed_points(
        registry,
        graduations,
        seed_anchor_points,
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=seed_initial_quote_usd,
        quote_usd_updates=seed_quote_usd_updates,
    )
    seed_tapped = iter_jsonl_snapshot(
        seed_points,
        output=seed_output,
        provenance=_provenance(provenance, phase="pons_v2_graduation_seed"),
    )
    seed_summary = summarize_v2_curve_market_caps(seed_tapped)

    v4_points = build_v2_v4_market_cap_points(
        registry,
        registrations,
        v4_event_rows,
        v4_anchor_points,
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=v4_initial_quote_usd,
        quote_usd_updates=v4_quote_usd_updates,
    )
    v4_tapped = iter_jsonl_snapshot(
        v4_points,
        output=v4_output,
        provenance=_provenance(provenance, phase="pons_v2_v4"),
    )
    v4_summary = summarize_v2_curve_market_caps(v4_tapped)

    return (
        seed_summary,
        v4_summary,
        _manifest(seed_output),
        _manifest(v4_output),
    )
