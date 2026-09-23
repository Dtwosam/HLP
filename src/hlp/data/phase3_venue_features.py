"""Causal Phase-3 venue/source mechanics at the frozen signal cutoff."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_research_paths import (
    PHASE2_RESEARCH_PRICE_PATH_HANDOFF_VERSION,
    PHASE2_RESEARCH_PRICE_PATH_VERSION,
)
from hlp.data.phase3_feature_entry import (
    PHASE3_FEATURE_ENTRY_HANDOFF_VERSION,
    PHASE3_FEATURE_SNAPSHOT_KIND,
    PHASE3_FEATURE_SUBJECT_FIELDS,
    PHASE3_FEATURE_SUBJECT_VERSION,
)
from hlp.data.phase3_feature_registry import (
    validate_phase3_feature_registry,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_VENUE_FEATURE_VERSION = "phase3-venue-mechanics-features-v1"
PHASE3_VENUE_FEATURE_HANDOFF_VERSION = (
    "phase3-venue-mechanics-features-handoff-v1"
)

VENUE_FEATURE_IDS = (
    "venue.unique_source_ids_seen_so_far",
    "venue.unique_component_ids_seen_so_far",
    "venue.source_set_switches_so_far",
    "venue.component_set_switches_so_far",
    "venue.current_source_count",
    "venue.current_component_count",
    "venue.multi_source_events_so_far",
    "venue.multi_component_events_so_far",
    "venue.current_event_multi_source",
    "venue.current_event_multi_component",
)


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _event(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 venue event position is invalid")
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 venue cutoff is invalid")
    return block, tx, log


def _identity_list(
    row: Mapping[str, object],
    field: str,
) -> tuple[str, ...]:
    raw = row.get(field)
    if not isinstance(raw, list) or not raw:
        raise ValueError(
            f"Phase-3 venue price row has invalid {field}"
        )
    values = tuple(sorted({str(value) for value in raw if str(value)}))
    if len(values) != len(raw):
        raise ValueError(
            f"Phase-3 venue price row {field} is empty/repeated"
        )
    return values


def materialize_phase3_venue_features(
    subject_rows: Iterable[Mapping[str, object]],
    price_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    price_path_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Measure only source/component mechanics observable by each cutoff."""

    entry = dict(entry_handoff)
    price_handoff = dict(price_path_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 venue entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 venue entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 venue entry consumed outcomes")
    if entry.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 venue entry exposes outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 venue entry allows future state")

    if (
        str(price_handoff.get("version") or "")
        != PHASE2_RESEARCH_PRICE_PATH_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 venue price-path version changed")
    if price_handoff.get("research_price_path_ready") is not True:
        raise ValueError("Phase-3 venue features require ready price path")
    if price_handoff.get("outcome_labels_computed") is not False:
        raise ValueError("Phase-3 venue price path contains outcomes")

    snapshot = int(entry.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Phase-3 venue snapshot is invalid")
    if int(price_handoff.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-3 venue snapshot drift")
    if _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 venue universe",
    ) != _sha256(
        price_handoff.get("universe_sha256"),
        label="Phase-3 venue price-path universe",
    ):
        raise ValueError("Phase-3 venue universe drift")
    if _sha256(
        entry.get("normalized_price_path_sha256"),
        label="Phase-3 venue entry path",
    ) != _sha256(
        price_handoff.get("normalized_price_path_sha256"),
        label="Phase-3 venue canonical path",
    ):
        raise ValueError("Phase-3 venue price-path SHA drift")

    registry_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "venue_mechanics"
    }
    if registry_ids != set(VENUE_FEATURE_IDS):
        raise ValueError("Phase-3 venue feature registry changed")

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 venue subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 venue subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 venue snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 venue cutoff is not inclusive")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 venue subject repeats token: {token}"
            )
        cutoff = _cutoff(row)
        if cutoff[0] > snapshot:
            raise ValueError(
                f"Phase-3 venue cutoff after snapshot: {token}"
            )
        subjects[token] = {
            "cutoff": cutoff,
            "source_ids": set(),
            "component_ids": set(),
            "previous_sources": None,
            "previous_components": None,
            "source_switches": 0,
            "component_switches": 0,
            "multi_source_events": 0,
            "multi_component_events": 0,
            "current_sources": None,
            "current_components": None,
            "exact_cutoff_seen": False,
            "post_cutoff_rows_ignored": 0,
        }
    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 venue subject count drift")

    previous_global = None
    total_rows = 0
    for raw in price_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_RESEARCH_PRICE_PATH_VERSION
        ):
            raise ValueError("Phase-3 venue price row version changed")
        if row.get("canonical_research_price_path") is not True:
            raise ValueError("Phase-3 venue price row is not canonical")
        token = normalize_address(str(row.get("token") or ""))
        event = _event(row)
        if event[0] > snapshot:
            raise ValueError("Phase-3 venue price row after snapshot")
        key = (*event, token)
        if previous_global is not None and key <= previous_global:
            raise ValueError(
                "Phase-3 venue price path is not strictly chronological"
            )
        previous_global = key
        total_rows += 1

        state = subjects.get(token)
        if state is None:
            continue
        if event > state["cutoff"]:
            state["post_cutoff_rows_ignored"] += 1
            continue

        sources = _identity_list(row, "source_ids")
        components = _identity_list(row, "component_ids")
        state["source_ids"].update(sources)
        state["component_ids"].update(components)

        if (
            state["previous_sources"] is not None
            and sources != state["previous_sources"]
        ):
            state["source_switches"] += 1
        if (
            state["previous_components"] is not None
            and components != state["previous_components"]
        ):
            state["component_switches"] += 1
        state["previous_sources"] = sources
        state["previous_components"] = components

        if len(sources) > 1:
            state["multi_source_events"] += 1
        if len(components) > 1:
            state["multi_component_events"] += 1
        state["current_sources"] = sources
        state["current_components"] = components
        if event == state["cutoff"]:
            state["exact_cutoff_seen"] = True

    if total_rows != int(price_handoff.get("price_points", -1)):
        raise ValueError("Phase-3 venue price-point count drift")

    ignored_future = 0
    output_rows = []
    for token in sorted(subjects):
        state = subjects[token]
        if state["exact_cutoff_seen"] is not True:
            raise ValueError(
                f"Phase-3 venue lacks exact cutoff price point: {token}"
            )
        current_sources = state["current_sources"]
        current_components = state["current_components"]
        if not current_sources or not current_components:
            raise ValueError(
                f"Phase-3 venue has no cutoff identity state: {token}"
            )
        values = {
            "venue.unique_source_ids_seen_so_far": len(
                state["source_ids"]
            ),
            "venue.unique_component_ids_seen_so_far": len(
                state["component_ids"]
            ),
            "venue.source_set_switches_so_far": int(
                state["source_switches"]
            ),
            "venue.component_set_switches_so_far": int(
                state["component_switches"]
            ),
            "venue.current_source_count": len(current_sources),
            "venue.current_component_count": len(current_components),
            "venue.multi_source_events_so_far": int(
                state["multi_source_events"]
            ),
            "venue.multi_component_events_so_far": int(
                state["multi_component_events"]
            ),
            "venue.current_event_multi_source": len(current_sources) > 1,
            "venue.current_event_multi_component": (
                len(current_components) > 1
            ),
        }
        if set(values) != set(VENUE_FEATURE_IDS):
            raise ValueError("Phase-3 venue feature output set changed")
        ignored_future += int(state["post_cutoff_rows_ignored"])
        output_rows.append({
            "version": PHASE3_VENUE_FEATURE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": state["cutoff"][0],
            "feature_cutoff_transaction_index": (
                None
                if state["cutoff"][1] == -1
                else state["cutoff"][1]
            ),
            "feature_cutoff_log_index": state["cutoff"][2],
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry["registry_sha256"],
            "feature_values": values,
            "missing_feature_ids": [],
            "data_quality": {
                "exact_cutoff_price_point": True,
                "canonical_source_identity_present": True,
                "canonical_component_identity_present": True,
                "future_price_rows_used": False,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_VENUE_FEATURE_VERSION,
            "feature_family": "venue_mechanics",
            "feature_registry_sha256": registry["registry_sha256"],
            "normalized_price_path_sha256": entry[
                "normalized_price_path_sha256"
            ],
            "outcome_rows_consumed": False,
            "future_price_rows_used": False,
        },
    )
    summary = {
        "version": PHASE3_VENUE_FEATURE_VERSION,
        "snapshot_head_block": snapshot,
        "feature_family": "venue_mechanics",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(VENUE_FEATURE_IDS),
        "features_per_subject": len(VENUE_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_price_points_validated": total_rows,
        "post_cutoff_subject_price_rows_ignored": ignored_future,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "normalized_price_path_sha256": str(
            entry["normalized_price_path_sha256"]
        ),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_venue_features_ready": True,
    }
    return manifest, summary


def build_phase3_venue_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    price_path_handoff_sha256: str,
) -> dict:
    """Bind causal venue mechanics to exact subjects and price-path identity."""

    summary = dict(feature_summary)
    if str(summary.get("version") or "") != PHASE3_VENUE_FEATURE_VERSION:
        raise ValueError("Phase-3 venue feature handoff version changed")
    if summary.get("feature_family") != "venue_mechanics":
        raise ValueError("Phase-3 venue feature family changed")
    for flag in (
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_venue_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 venue feature handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_price_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 venue feature handoff violates {flag}"
            )
    return {
        "version": PHASE3_VENUE_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "venue_mechanics",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 venue feature registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 venue feature rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 venue feature summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 venue feature entry",
        ),
        "price_path_handoff_sha256": _sha256(
            price_path_handoff_sha256,
            label="Phase-3 venue price path",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 venue universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="Phase-3 venue path",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_venue_features_ready": True,
    }
