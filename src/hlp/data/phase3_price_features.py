"""Causal Phase-3 price/drawdown features at the frozen signal cutoff."""

from __future__ import annotations

from decimal import Decimal, localcontext
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
    PHASE3_FEATURE_REGISTRY_VERSION,
    validate_phase3_feature_registry,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_PRICE_FEATURE_VERSION = "phase3-price-features-v1"
PHASE3_PRICE_FEATURE_HANDOFF_VERSION = (
    "phase3-price-features-handoff-v1"
)

PRICE_FEATURE_IDS = (
    "price.market_cap_proxy_usd_at_cutoff",
    "price.trailing_peak_market_cap_proxy_usd",
    "price.drawdown_fraction_from_trailing_peak",
    "price.max_drawdown_fraction_so_far",
    "price.minimum_market_cap_proxy_usd_so_far",
    "price.expansion_multiple_from_first_observation",
    "price.recovery_multiple_from_minimum_so_far",
    "price.price_points_so_far",
    "price.blocks_since_first_observation",
    "price.blocks_since_trailing_peak",
    "price.events_since_trailing_peak",
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


def _decimal(value: object, *, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{label} is not numeric") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= 0:
        raise ValueError("Phase-3 price feature denominator is non-positive")
    with localcontext() as context:
        context.prec = 80
        return numerator / denominator


def _event_key(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("block_number", -1))
    raw_tx = row.get("transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 price feature event position is invalid")
    return block, tx, log


def _subject_cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 feature subject cutoff is invalid")
    return block, tx, log


def materialize_phase3_price_features(
    subject_rows: Iterable[Mapping[str, object]],
    price_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    price_path_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Compute causal price features using no rows after each subject cutoff."""

    entry = dict(entry_handoff)
    price_handoff = dict(price_path_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 price features entry handoff version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 price features entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 price features entry consumed outcomes")
    if entry.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 price features entry exposes outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 price features entry allows future state")
    if entry.get("phase3_feature_values_computed") is not False:
        raise ValueError("Phase-3 price features entry already has features")
    if entry.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
        raise ValueError("Phase-3 price feature snapshot semantics changed")
    if entry.get("feature_cutoff_inclusive") is not True:
        raise ValueError("Phase-3 price feature cutoff semantics changed")

    if (
        str(price_handoff.get("version") or "")
        != PHASE2_RESEARCH_PRICE_PATH_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 price path handoff version changed")
    if price_handoff.get("research_price_path_ready") is not True:
        raise ValueError("Phase-3 price features require ready price path")
    if price_handoff.get("outcome_labels_computed") is not False:
        raise ValueError("Phase-3 price path contains outcome labels")

    snapshot = int(entry.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Phase-3 price feature snapshot is invalid")
    if int(price_handoff.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-3 entry/price-path snapshot drift")
    if _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 price feature universe",
    ) != _sha256(
        price_handoff.get("universe_sha256"),
        label="Phase-3 canonical price-path universe",
    ):
        raise ValueError("Phase-3 entry/price-path universe drift")
    if _sha256(
        entry.get("normalized_price_path_sha256"),
        label="Phase-3 entry price path",
    ) != _sha256(
        price_handoff.get("normalized_price_path_sha256"),
        label="Phase-3 canonical price path",
    ):
        raise ValueError("Phase-3 entry/price-path SHA drift")

    price_registry_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "price_drawdown"
    }
    expected_registry_ids = set(PRICE_FEATURE_IDS)
    if price_registry_ids != expected_registry_ids:
        raise ValueError(
            "Phase-3 price feature registry changed: "
            f"missing={sorted(expected_registry_ids - price_registry_ids)} "
            f"extra={sorted(price_registry_ids - expected_registry_ids)}"
        )
    if registry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 feature registry allows future state")
    if registry.get("outcome_dependency_allowed") is not False:
        raise ValueError("Phase-3 feature registry depends on outcomes")

    subjects = {}
    selected_detector = str(entry.get("selected_detector_id") or "")
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 price feature subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 price feature subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 price subject snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 price subject cutoff is not inclusive")
        if str(row.get("selected_detector_id") or "") != selected_detector:
            raise ValueError("Phase-3 price subject detector id drift")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 price feature subject repeats token: {token}"
            )
        cutoff = _subject_cutoff(row)
        if cutoff[0] > snapshot:
            raise ValueError(
                f"Phase-3 price feature cutoff is after snapshot: {token}"
            )
        subjects[token] = {
            "row": row,
            "cutoff": cutoff,
            "state": None,
            "exact_cutoff_matches": 0,
            "post_cutoff_rows_ignored": 0,
        }

    expected_subjects = int(entry.get("feature_subjects", -1))
    if expected_subjects <= 0 or len(subjects) != expected_subjects:
        raise ValueError("Phase-3 price feature subject count changed")

    previous_global = None
    total_price_points = 0
    for raw in price_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_RESEARCH_PRICE_PATH_VERSION
        ):
            raise ValueError("Phase-3 price row version changed")
        if row.get("canonical_research_price_path") is not True:
            raise ValueError("Phase-3 price row is not canonical")
        token = normalize_address(str(row.get("token") or ""))
        event = _event_key(row)
        if event[0] > snapshot:
            raise ValueError("Phase-3 price row is after frozen snapshot")
        global_key = (*event, token)
        if previous_global is not None and global_key <= previous_global:
            raise ValueError(
                "Phase-3 canonical price path is not strictly chronological"
            )
        previous_global = global_key
        value = _decimal(
            row.get("market_cap_proxy_usd"),
            label=f"{token} Phase-3 market-cap proxy",
        )
        total_price_points += 1

        subject = subjects.get(token)
        if subject is None:
            continue
        cutoff = subject["cutoff"]
        if event > cutoff:
            subject["post_cutoff_rows_ignored"] += 1
            continue

        state = subject["state"]
        if state is None:
            state = {
                "first_event": event,
                "first_value": value,
                "current_event": event,
                "current_value": value,
                "peak_event": event,
                "peak_value": value,
                "peak_point_index": 1,
                "minimum_event": event,
                "minimum_value": value,
                "max_drawdown": Decimal("0"),
                "points": 1,
            }
            subject["state"] = state
        else:
            state["points"] += 1
            if value > state["peak_value"]:
                state["peak_value"] = value
                state["peak_event"] = event
                state["peak_point_index"] = state["points"]
            if value < state["minimum_value"]:
                state["minimum_value"] = value
                state["minimum_event"] = event
            state["current_event"] = event
            state["current_value"] = value

        with localcontext() as context:
            context.prec = 80
            drawdown = (
                state["peak_value"] - value
            ) / state["peak_value"]
        if drawdown > state["max_drawdown"]:
            state["max_drawdown"] = drawdown
        if event == cutoff:
            subject["exact_cutoff_matches"] += 1

    if total_price_points != int(price_handoff.get("price_points", -1)):
        raise ValueError("Phase-3 canonical price-path point count changed")

    output_rows = []
    ignored_future_rows = 0
    for token in sorted(subjects):
        subject = subjects[token]
        state = subject["state"]
        if state is None:
            raise ValueError(
                f"Phase-3 price feature subject has no pre-cutoff path: {token}"
            )
        if subject["exact_cutoff_matches"] != 1:
            raise ValueError(
                f"Phase-3 price feature cutoff lacks exact canonical point: "
                f"{token}"
            )
        if state["current_event"] != subject["cutoff"]:
            raise ValueError(
                f"Phase-3 price feature state did not stop at cutoff: {token}"
            )

        current = state["current_value"]
        peak = state["peak_value"]
        minimum = state["minimum_value"]
        with localcontext() as context:
            context.prec = 80
            current_drawdown = (peak - current) / peak
        values = {
            "price.market_cap_proxy_usd_at_cutoff": _decimal_text(current),
            "price.trailing_peak_market_cap_proxy_usd": _decimal_text(peak),
            "price.drawdown_fraction_from_trailing_peak": _decimal_text(
                current_drawdown
            ),
            "price.max_drawdown_fraction_so_far": _decimal_text(
                state["max_drawdown"]
            ),
            "price.minimum_market_cap_proxy_usd_so_far": _decimal_text(
                minimum
            ),
            "price.expansion_multiple_from_first_observation": _decimal_text(
                _ratio(current, state["first_value"])
            ),
            "price.recovery_multiple_from_minimum_so_far": _decimal_text(
                _ratio(current, minimum)
            ),
            "price.price_points_so_far": int(state["points"]),
            "price.blocks_since_first_observation": (
                subject["cutoff"][0] - state["first_event"][0]
            ),
            "price.blocks_since_trailing_peak": (
                subject["cutoff"][0] - state["peak_event"][0]
            ),
            "price.events_since_trailing_peak": (
                int(state["points"]) - int(state["peak_point_index"])
            ),
        }
        if set(values) != expected_registry_ids:
            raise ValueError("Phase-3 price feature output set changed")
        if any(
            value < 0
            for key, value in values.items()
            if key in {
                "price.price_points_so_far",
                "price.blocks_since_first_observation",
                "price.blocks_since_trailing_peak",
                "price.events_since_trailing_peak",
            }
        ):
            raise ValueError(
                f"Phase-3 price feature causal duration is negative: {token}"
            )

        ignored_future_rows += int(subject["post_cutoff_rows_ignored"])
        output_rows.append({
            "version": PHASE3_PRICE_FEATURE_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": subject["cutoff"][0],
            "feature_cutoff_transaction_index": (
                None
                if subject["cutoff"][1] == -1
                else subject["cutoff"][1]
            ),
            "feature_cutoff_log_index": subject["cutoff"][2],
            "feature_cutoff_inclusive": True,
            "feature_registry_version": PHASE3_FEATURE_REGISTRY_VERSION,
            "feature_registry_sha256": registry["registry_sha256"],
            "feature_values": values,
            "missing_feature_ids": [],
            "data_quality": {
                "exact_cutoff_price_point": True,
                "future_price_rows_used": False,
                "all_registered_price_features_present": True,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_PRICE_FEATURE_VERSION,
            "feature_registry_sha256": registry["registry_sha256"],
            "feature_family": "price_drawdown",
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_inclusive": True,
            "normalized_price_path_sha256": entry[
                "normalized_price_path_sha256"
            ],
            "outcome_rows_consumed": False,
            "future_price_rows_used": False,
        },
    )
    summary = {
        "version": PHASE3_PRICE_FEATURE_VERSION,
        "snapshot_head_block": snapshot,
        "feature_family": "price_drawdown",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_cutoff_inclusive": True,
        "feature_registry_version": PHASE3_FEATURE_REGISTRY_VERSION,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(PRICE_FEATURE_IDS),
        "features_per_subject": len(PRICE_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_price_points_validated": total_price_points,
        "post_cutoff_subject_price_rows_ignored": ignored_future_rows,
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
        "phase3_price_features_ready": True,
    }
    return manifest, summary


def build_phase3_price_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    price_path_handoff_sha256: str,
) -> dict:
    """Bind causal price features to exact entry and price-path identities."""

    summary = dict(feature_summary)
    if str(summary.get("version") or "") != PHASE3_PRICE_FEATURE_VERSION:
        raise ValueError("Phase-3 price feature handoff version changed")
    if summary.get("feature_family") != "price_drawdown":
        raise ValueError("Phase-3 price feature family changed")
    if summary.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
        raise ValueError("Phase-3 price feature snapshot kind changed")
    if summary.get("feature_cutoff_inclusive") is not True:
        raise ValueError("Phase-3 price feature cutoff semantics changed")
    if summary.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 price feature handoff consumed outcomes")
    if summary.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 price feature handoff exposes outcomes")
    if summary.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 price feature handoff allows future state")
    if summary.get("future_price_rows_used") is not False:
        raise ValueError("Phase-3 price feature handoff used future rows")
    if summary.get("missingness_recorded") is not True:
        raise ValueError("Phase-3 price feature missingness is not recorded")
    if summary.get("data_quality_recorded") is not True:
        raise ValueError("Phase-3 price feature data quality is not recorded")
    if summary.get("phase3_price_features_ready") is not True:
        raise ValueError("Phase-3 price features are not ready")

    return {
        "version": PHASE3_PRICE_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "price_drawdown",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_cutoff_inclusive": True,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 price feature registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 price feature rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 price feature summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 feature entry handoff",
        ),
        "price_path_handoff_sha256": _sha256(
            price_path_handoff_sha256,
            label="Phase-3 price-path handoff",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 price feature universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="Phase-3 price feature path",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_price_features_ready": True,
    }
