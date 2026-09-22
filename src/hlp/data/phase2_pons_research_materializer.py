"""Exact Pons research replay over frozen eligible-token membership."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import (
    ROBINHOOD_USDG,
    ROBINHOOD_WETH,
    normalize_address,
)
from hlp.data.phase2_pons_research_replay import (
    materialize_v1_research_points,
    materialize_v2_curve_research_points,
    materialize_v2_post_graduation_research_points,
)
from hlp.data.quote_usd import (
    merge_quote_usd_tapes,
    prepare_quote_usd_inputs,
)
from hlp.data.sharded_tape import (
    iter_sharded_jsonl_matching_field_values,
    iter_validated_jsonl,
    iter_validated_jsonl_matching_field_values,
    validate_jsonl_snapshot,
)
from hlp.data.v2_curve import merge_v2_lifecycle_market_cap_summaries


PHASE2_PONS_RESEARCH_MATERIALIZATION_VERSION = (
    "phase2-pons-research-materialization-v1"
)


def _iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _expected_manifest(
    manifest_path: Path,
    expected: Mapping[str, object],
    *,
    label: str,
) -> dict:
    manifest = json.loads(manifest_path.read_text())
    expected_sha = str(expected.get("sha256") or "").lower()
    expected_records = int(expected.get("records", -1))
    if str(manifest.get("sha256") or "").lower() != expected_sha:
        raise ValueError(f"{label} manifest SHA drift")
    if int(manifest.get("records", -1)) != expected_records:
        raise ValueError(f"{label} manifest record-count drift")
    return manifest


def _validated_state_rows(
    path: Path,
    manifest_path: Path,
    expected: Mapping[str, object],
    *,
    label: str,
) -> list[dict]:
    _expected_manifest(manifest_path, expected, label=label)
    return list(iter_validated_jsonl(path, manifest_path))


def _validate_update_tape(
    path: Path,
    manifest_path: Path,
    expected: Mapping[str, object],
    *,
    label: str,
) -> None:
    _expected_manifest(manifest_path, expected, label=label)
    validate_jsonl_snapshot(path, manifest_path)


def _quote_inputs(
    source_pairs: list[tuple[list[dict], Path]],
):
    states, updates = merge_quote_usd_tapes([
        (state_rows, _iter_jsonl(update_path))
        for state_rows, update_path in source_pairs
    ])
    return prepare_quote_usd_inputs(states, [updates])


def _normalized_tokens(values: Iterable[str]) -> set[str]:
    return {normalize_address(str(value)) for value in values}


def _rows_by_token(rows: Iterable[dict]) -> dict[str, dict]:
    output = {}
    for raw in rows:
        row = dict(raw)
        token = normalize_address(str(row["token"]))
        if token in output:
            raise ValueError(f"duplicate Pons summary token: {token}")
        output[token] = row
    return output


def _require_replay_equivalence(
    rebuilt_rows: Iterable[dict],
    accepted_rows: Iterable[dict],
    *,
    eligible_tokens: set[str],
    label: str,
) -> None:
    rebuilt = _rows_by_token(rebuilt_rows)
    accepted = _rows_by_token(accepted_rows)
    if set(rebuilt) != eligible_tokens:
        raise ValueError(
            f"{label} rebuilt token set changed: "
            f"missing={sorted(eligible_tokens - set(rebuilt))[:10]} "
            f"extra={sorted(set(rebuilt) - eligible_tokens)[:10]}"
        )
    if set(accepted) != eligible_tokens:
        raise ValueError(
            f"{label} accepted token set changed: "
            f"missing={sorted(eligible_tokens - set(accepted))[:10]} "
            f"extra={sorted(set(accepted) - eligible_tokens)[:10]}"
        )
    drift = [
        token
        for token in sorted(eligible_tokens)
        if rebuilt[token] != accepted[token]
    ]
    if drift:
        token = drift[0]
        raise ValueError(
            f"{label} accepted lifecycle replay drift for {token}: "
            f"rebuilt={rebuilt[token]} accepted={accepted[token]}"
        )


def materialize_pons_v1_research(
    *,
    eligible_tokens: Iterable[str],
    accepted_lifecycle_path: Path,
    accepted_lifecycle_manifest_path: Path,
    accepted_lifecycle_expected: Mapping[str, object],
    registry_path: Path,
    registry_manifest_path: Path,
    registry_expected: Mapping[str, object],
    quote_registry_path: Path,
    quote_registry_manifest_path: Path,
    quote_registry_expected: Mapping[str, object],
    market_events_root: Path,
    market_events_manifest_path: Path,
    market_events_expected: Mapping[str, object],
    anchor_events_path: Path,
    anchor_events_manifest_path: Path,
    anchor_expected: Mapping[str, object],
    anchor_initial_path: Path,
    oracle_state_path: Path,
    oracle_state_manifest_path: Path,
    oracle_state_expected: Mapping[str, object],
    oracle_updates_path: Path,
    oracle_updates_manifest_path: Path,
    oracle_updates_expected: Mapping[str, object],
    output: Path,
    provenance: dict,
) -> dict:
    """Rebuild exact eligible Pons V1 points from accepted canonical inputs."""

    eligible = _normalized_tokens(eligible_tokens)
    if not eligible:
        raise ValueError("Pons V1 research eligible-token set is empty")

    _expected_manifest(
        accepted_lifecycle_manifest_path,
        accepted_lifecycle_expected,
        label="Pons V1 accepted lifecycle",
    )
    accepted_rows = list(
        iter_validated_jsonl_matching_field_values(
            accepted_lifecycle_path,
            accepted_lifecycle_manifest_path,
            field="token",
            values=eligible,
        )
    )

    _expected_manifest(
        registry_manifest_path,
        registry_expected,
        label="Pons V1 registry",
    )
    registry = [
        row
        for row in iter_validated_jsonl_matching_field_values(
            registry_path,
            registry_manifest_path,
            field="token",
            values=eligible,
        )
        if row.get("version") == "v1"
    ]
    registry_tokens = _normalized_tokens(
        row["token"] for row in registry
    )
    if registry_tokens != eligible:
        raise ValueError(
            "Pons V1 eligible registry membership changed"
        )
    pools = {str(row["pool"]).lower() for row in registry}

    quote_manifest = _expected_manifest(
        quote_registry_manifest_path,
        quote_registry_expected,
        label="Pons V1 quote registry",
    )
    quote_rows = list(
        iter_validated_jsonl(
            quote_registry_path,
            quote_registry_manifest_path,
        )
    )
    if len(quote_rows) != int(quote_manifest["records"]):
        raise ValueError("Pons V1 quote registry count changed")
    quote_decimals = {
        str(row["quote_token"]).lower(): int(row["quote_decimals"])
        for row in quote_rows
        if row.get("quote_decimals") is not None
    }
    weth_decimals = quote_decimals.get(ROBINHOOD_WETH.lower())
    usdg_decimals = quote_decimals.get(ROBINHOOD_USDG.lower())
    if weth_decimals is None or usdg_decimals is None:
        raise ValueError("Pons V1 quote registry lacks WETH/USDG decimals")

    _expected_manifest(
        market_events_manifest_path,
        market_events_expected,
        label="Pons V1 V3 aggregate",
    )
    _validate_update_tape(
        anchor_events_path,
        anchor_events_manifest_path,
        anchor_expected,
        label="Pons V1 WETH/USDG anchor",
    )
    oracle_state = _validated_state_rows(
        oracle_state_path,
        oracle_state_manifest_path,
        oracle_state_expected,
        label="Pons V1 oracle initial",
    )
    _validate_update_tape(
        oracle_updates_path,
        oracle_updates_manifest_path,
        oracle_updates_expected,
        label="Pons V1 oracle updates",
    )

    anchor_initial = json.loads(anchor_initial_path.read_text())
    initial_weth_usd = Decimal(anchor_initial["weth_usd"])
    initial_quote_usd, quote_updates = _quote_inputs([
        (oracle_state, oracle_updates_path),
    ])
    event_rows = iter_sharded_jsonl_matching_field_values(
        market_events_root,
        market_events_manifest_path,
        field="pool",
        values=pools,
    )
    summary, output_manifest = materialize_v1_research_points(
        registry,
        event_rows,
        _iter_jsonl(anchor_events_path),
        output=output,
        provenance=provenance,
        initial_weth_usd=initial_weth_usd,
        weth_decimals=weth_decimals,
        usdg_decimals=usdg_decimals,
        initial_quote_usd=initial_quote_usd,
        quote_usd_updates=quote_updates,
        quote_decimals_by_token=quote_decimals,
    )
    _require_replay_equivalence(
        summary,
        accepted_rows,
        eligible_tokens=eligible,
        label="Pons V1",
    )
    return {
        "version": PHASE2_PONS_RESEARCH_MATERIALIZATION_VERSION,
        "source_id": "pons_v1",
        "eligible_tokens": len(eligible),
        "materialized_records": int(output_manifest["records"]),
        "materialized_sha256": output_manifest["sha256"],
        "accepted_lifecycle_replay_equivalent": True,
        "full_inputs_validated": True,
        "research_component_ready": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }


def materialize_pons_v2_research(
    *,
    eligible_tokens: Iterable[str],
    accepted_lifecycle_path: Path,
    accepted_lifecycle_manifest_path: Path,
    accepted_lifecycle_expected: Mapping[str, object],
    registry_path: Path,
    registry_manifest_path: Path,
    registry_expected: Mapping[str, object],
    curve_events_path: Path,
    curve_events_manifest_path: Path,
    curve_events_expected: Mapping[str, object],
    graduations_path: Path,
    graduations_manifest_path: Path,
    graduations_expected: Mapping[str, object],
    registrations_path: Path,
    registrations_manifest_path: Path,
    registrations_expected: Mapping[str, object],
    market_events_root: Path,
    market_events_manifest_path: Path,
    market_events_expected: Mapping[str, object],
    anchor_events_path: Path,
    anchor_events_manifest_path: Path,
    anchor_expected: Mapping[str, object],
    anchor_initial_path: Path,
    oracle_state_path: Path,
    oracle_state_manifest_path: Path,
    oracle_state_expected: Mapping[str, object],
    oracle_updates_path: Path,
    oracle_updates_manifest_path: Path,
    oracle_updates_expected: Mapping[str, object],
    fallback_state_path: Path,
    fallback_state_manifest_path: Path,
    fallback_state_expected: Mapping[str, object],
    fallback_updates_path: Path,
    fallback_updates_manifest_path: Path,
    fallback_updates_expected: Mapping[str, object],
    curve_output: Path,
    seed_output: Path,
    v4_output: Path,
    provenance: dict,
) -> dict:
    """Rebuild exact eligible Pons V2 curve -> seed -> V4 research paths."""

    eligible = _normalized_tokens(eligible_tokens)
    if not eligible:
        raise ValueError("Pons V2 research eligible-token set is empty")

    _expected_manifest(
        accepted_lifecycle_manifest_path,
        accepted_lifecycle_expected,
        label="Pons V2 accepted lifecycle",
    )
    accepted_rows = list(
        iter_validated_jsonl_matching_field_values(
            accepted_lifecycle_path,
            accepted_lifecycle_manifest_path,
            field="token",
            values=eligible,
        )
    )

    _expected_manifest(
        registry_manifest_path,
        registry_expected,
        label="Pons V2 registry",
    )
    registry = list(
        iter_validated_jsonl_matching_field_values(
            registry_path,
            registry_manifest_path,
            field="token",
            values=eligible,
        )
    )
    registry_tokens = _normalized_tokens(
        row["token"] for row in registry
    )
    if registry_tokens != eligible:
        raise ValueError(
            "Pons V2 eligible registry membership changed"
        )
    curves = {str(row["curve"]).lower() for row in registry}

    _expected_manifest(
        curve_events_manifest_path,
        curve_events_expected,
        label="Pons V2 curve events",
    )
    curve_events = iter_validated_jsonl_matching_field_values(
        curve_events_path,
        curve_events_manifest_path,
        field="curve",
        values=curves,
    )

    _expected_manifest(
        graduations_manifest_path,
        graduations_expected,
        label="Pons V2 graduations",
    )
    graduations = list(
        iter_validated_jsonl_matching_field_values(
            graduations_path,
            graduations_manifest_path,
            field="token",
            values=eligible,
        )
    )
    _expected_manifest(
        registrations_manifest_path,
        registrations_expected,
        label="Pons V2 registrations",
    )
    registrations = list(
        iter_validated_jsonl_matching_field_values(
            registrations_path,
            registrations_manifest_path,
            field="token",
            values=eligible,
        )
    )
    pool_ids = {
        str(row["pool_id"]).lower()
        for row in registrations
    }

    _expected_manifest(
        market_events_manifest_path,
        market_events_expected,
        label="Pons V2 V4 aggregate",
    )
    _validate_update_tape(
        anchor_events_path,
        anchor_events_manifest_path,
        anchor_expected,
        label="Pons V2 WETH/USDG anchor",
    )
    oracle_state = _validated_state_rows(
        oracle_state_path,
        oracle_state_manifest_path,
        oracle_state_expected,
        label="Pons V2 oracle initial",
    )
    _validate_update_tape(
        oracle_updates_path,
        oracle_updates_manifest_path,
        oracle_updates_expected,
        label="Pons V2 oracle updates",
    )
    fallback_state = _validated_state_rows(
        fallback_state_path,
        fallback_state_manifest_path,
        fallback_state_expected,
        label="Pons V2 fallback initial",
    )
    _validate_update_tape(
        fallback_updates_path,
        fallback_updates_manifest_path,
        fallback_updates_expected,
        label="Pons V2 fallback updates",
    )

    anchor_initial = json.loads(anchor_initial_path.read_text())
    initial_weth_usd = Decimal(anchor_initial["weth_usd"])

    curve_initial, curve_updates = _quote_inputs([
        (oracle_state, oracle_updates_path),
        (fallback_state, fallback_updates_path),
    ])
    curve_summary, curve_manifest = materialize_v2_curve_research_points(
        registry,
        curve_events,
        _iter_jsonl(anchor_events_path),
        output=curve_output,
        provenance=provenance,
        initial_weth_usd=initial_weth_usd,
        initial_quote_usd=curve_initial,
        quote_usd_updates=curve_updates,
    )

    seed_initial, seed_updates = _quote_inputs([
        (oracle_state, oracle_updates_path),
        (fallback_state, fallback_updates_path),
    ])
    v4_initial, v4_updates = _quote_inputs([
        (oracle_state, oracle_updates_path),
        (fallback_state, fallback_updates_path),
    ])
    v4_events = iter_sharded_jsonl_matching_field_values(
        market_events_root,
        market_events_manifest_path,
        field="pool_id",
        values=pool_ids,
    )
    (
        seed_summary,
        v4_summary,
        seed_manifest,
        v4_manifest,
    ) = materialize_v2_post_graduation_research_points(
        registry,
        graduations,
        registrations,
        v4_events,
        seed_anchor_points=_iter_jsonl(anchor_events_path),
        v4_anchor_points=_iter_jsonl(anchor_events_path),
        seed_output=seed_output,
        v4_output=v4_output,
        provenance=provenance,
        initial_weth_usd=initial_weth_usd,
        seed_initial_quote_usd=seed_initial,
        seed_quote_usd_updates=seed_updates,
        v4_initial_quote_usd=v4_initial,
        v4_quote_usd_updates=v4_updates,
    )

    rebuilt = merge_v2_lifecycle_market_cap_summaries(
        registry,
        curve_summary=curve_summary,
        seed_summary=seed_summary,
        v4_summary=v4_summary,
    )
    _require_replay_equivalence(
        rebuilt,
        accepted_rows,
        eligible_tokens=eligible,
        label="Pons V2",
    )
    return {
        "version": PHASE2_PONS_RESEARCH_MATERIALIZATION_VERSION,
        "source_id": "pons_v2",
        "eligible_tokens": len(eligible),
        "segments": {
            "curve": {
                "records": int(curve_manifest["records"]),
                "sha256": curve_manifest["sha256"],
            },
            "graduation_seed": {
                "records": int(seed_manifest["records"]),
                "sha256": seed_manifest["sha256"],
            },
            "v4": {
                "records": int(v4_manifest["records"]),
                "sha256": v4_manifest["sha256"],
            },
        },
        "materialized_records": (
            int(curve_manifest["records"])
            + int(seed_manifest["records"])
            + int(v4_manifest["records"])
        ),
        "accepted_lifecycle_replay_equivalent": True,
        "full_inputs_validated": True,
        "research_component_ready": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }
