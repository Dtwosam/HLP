"""Continuous Phase-2 post-dump outcome labels.

Outcomes are computed only after the first-major-dump detector is frozen.
Magnitude is measured from the retrospective post-dump trough/base, while
live-compatible timing and adverse excursion are measured from the confirmed
signal event.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_dump_research import (
    PHASE2_DUMP_DETECTOR_FREEZE_VERSION,
)
from hlp.data.phase2_research_paths import (
    PHASE2_RESEARCH_PRICE_PATH_HANDOFF_VERSION,
    PHASE2_RESEARCH_PRICE_PATH_VERSION,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE2_OUTCOME_LABEL_VERSION = "phase2-outcome-label-v1"
PHASE2_OUTCOME_HANDOFF_VERSION = "phase2-outcome-handoff-v1"
DEFAULT_OUTCOME_MILESTONES = (2, 3, 5, 10)


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


def _event_key(
    row: Mapping[str, object],
    *,
    prefix: str = "",
) -> tuple[int, int, int]:
    name = f"{prefix}_" if prefix else ""
    block = int(row.get(f"{name}block_number", row.get(f"{prefix}_block", -1)) if prefix else row.get("block_number", -1))
    if prefix:
        block = int(row.get(f"{prefix}_block", -1))
        raw_transaction = row.get(f"{prefix}_transaction_index")
        log_index = int(row.get(f"{prefix}_log_index", -1))
    else:
        raw_transaction = row.get("transaction_index")
        log_index = int(row.get("log_index", -1))
    transaction = -1 if raw_transaction is None else int(raw_transaction)
    if block < 0 or transaction < -1 or log_index < 0:
        raise ValueError(
            f"outcome event position is invalid: prefix={prefix!r}"
        )
    return block, transaction, log_index


def _normalize_milestones(values: Iterable[int]) -> tuple[int, ...]:
    normalized = sorted({int(value) for value in values})
    if not normalized or any(value <= 1 for value in normalized):
        raise ValueError("outcome milestones must be unique integers above 1")
    if 5 not in normalized:
        raise ValueError("outcome milestones must retain the precommitted 5x boundary")
    return tuple(normalized)


def materialize_phase2_outcome_labels(
    detector_rows: Iterable[Mapping[str, object]],
    price_rows: Iterable[Mapping[str, object]],
    *,
    detector_summary: Mapping[str, object],
    price_path_handoff: Mapping[str, object],
    output: Path,
    milestones: Iterable[int] = DEFAULT_OUTCOME_MILESTONES,
) -> tuple[dict, dict]:
    """Compute continuous outcomes from a frozen detector and canonical path."""

    detector = dict(detector_summary)
    path = dict(price_path_handoff)
    if (
        str(detector.get("version") or "")
        != PHASE2_DUMP_DETECTOR_FREEZE_VERSION
    ):
        raise ValueError("outcome labels require canonical detector freeze")
    if detector.get("candidate_selected") is not True:
        raise ValueError("outcome labels require selected dump detector")
    if detector.get("dump_threshold_frozen") is not True:
        raise ValueError("outcome labels require frozen dump threshold")
    if detector.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("outcome labels require frozen dump detector")
    if detector.get("outcome_labels_computed") is not False:
        raise ValueError("outcome labels cannot consume prior outcome labels")
    if detector.get("uses_outcome_labels") is not False:
        raise ValueError("dump detector freeze was contaminated by outcomes")
    if detector.get("point_in_time_confirmation") is not True:
        raise ValueError("dump detector freeze is not point-in-time compatible")

    if (
        str(path.get("version") or "")
        != PHASE2_RESEARCH_PRICE_PATH_HANDOFF_VERSION
    ):
        raise ValueError("outcome labels require canonical price-path handoff")
    if path.get("research_price_path_ready") is not True:
        raise ValueError("outcome labels require ready research price path")
    if path.get("outcome_labels_computed") is not False:
        raise ValueError("outcome labels cannot consume labeled price path")

    if int(detector.get("snapshot_head_block", -1)) != int(
        path.get("snapshot_head_block", -2)
    ):
        raise ValueError("outcome detector/price-path snapshot drift")
    if _sha256(
        detector.get("universe_sha256"),
        label="outcome detector universe",
    ) != _sha256(
        path.get("universe_sha256"),
        label="outcome price-path universe",
    ):
        raise ValueError("outcome detector/price-path universe drift")
    if _sha256(
        detector.get("normalized_price_path_sha256"),
        label="outcome detector price path",
    ) != _sha256(
        path.get("normalized_price_path_sha256"),
        label="outcome canonical price path",
    ):
        raise ValueError("outcome detector/price-path SHA drift")

    milestone_values = _normalize_milestones(milestones)
    snapshot = int(detector["snapshot_head_block"])
    selected_detector = str(detector.get("selected_candidate_id") or "")
    if not selected_detector:
        raise ValueError("outcome detector id is empty")

    frozen = {}
    confirmed = {}
    statuses = Counter()
    for raw in detector_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_DUMP_DETECTOR_FREEZE_VERSION
        ):
            raise ValueError("outcome detector row version changed")
        if row.get("detector_frozen") is not True:
            raise ValueError("outcome detector row is not frozen")
        if str(row.get("detector_id") or "") != selected_detector:
            raise ValueError("outcome detector row id drift")
        token = normalize_address(str(row.get("token") or ""))
        if token in frozen:
            raise ValueError(f"outcome detector repeats token: {token}")
        row["token"] = token
        status = str(row.get("candidate_status") or "")
        if status not in {
            "confirmed",
            "drawdown_unconfirmed",
            "no_material_drawdown",
        }:
            raise ValueError(f"outcome detector status is invalid: {status}")
        point_confirmed = bool(row.get("point_in_time_confirmed"))
        if point_confirmed != (status == "confirmed"):
            raise ValueError("outcome detector confirmation flag drift")
        frozen[token] = row
        statuses[status] += 1

        if status != "confirmed":
            continue
        trough_event = _event_key(row, prefix="trough")
        confirmation_event = _event_key(row, prefix="confirmation")
        if confirmation_event < trough_event:
            raise ValueError(
                f"outcome detector confirmation precedes trough: {token}"
            )
        trough_value = _decimal(
            row.get("trough_market_cap_proxy_usd"),
            label=f"{token} trough market cap",
            positive=True,
        )
        confirmation_value = _decimal(
            row.get("confirmation_market_cap_proxy_usd"),
            label=f"{token} confirmation market cap",
            positive=True,
        )
        confirmed[token] = {
            "trough_event": trough_event,
            "confirmation_event": confirmation_event,
            "trough_value": trough_value,
            "confirmation_value": confirmation_value,
            "maximum_forward_value": trough_value,
            "maximum_forward_event": trough_event,
            "minimum_post_confirmation_value": confirmation_value,
            "minimum_post_confirmation_event": confirmation_event,
            "historical_milestones": {
                value: None for value in milestone_values
            },
            "live_milestones": {
                value: None for value in milestone_values
            },
        }

    tokens = int(detector.get("tokens", -1))
    if tokens <= 0 or len(frozen) != tokens:
        raise ValueError("outcome detector token coverage changed")
    if tokens != int(path.get("eligible_tokens", -1)):
        raise ValueError("outcome detector/price-path token count drift")

    previous_global = None
    seen_tokens = set()
    total_points = 0
    for raw in price_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_RESEARCH_PRICE_PATH_VERSION
        ):
            raise ValueError("outcome price-path row version changed")
        if row.get("canonical_research_price_path") is not True:
            raise ValueError("outcome price-path row is not canonical")
        token = normalize_address(str(row.get("token") or ""))
        if token not in frozen:
            raise ValueError(
                f"outcome price path contains token outside detector freeze: {token}"
            )
        event = _event_key(row)
        global_key = (*event, token)
        if previous_global is not None and global_key <= previous_global:
            raise ValueError(
                "outcome price path is not strictly globally chronological"
            )
        previous_global = global_key
        value = _decimal(
            row.get("market_cap_proxy_usd"),
            label=f"{token} outcome market cap",
            positive=True,
        )
        total_points += 1
        seen_tokens.add(token)

        state = confirmed.get(token)
        if state is None:
            continue
        trough_event = state["trough_event"]
        confirmation_event = state["confirmation_event"]
        trough_value = state["trough_value"]

        if event > trough_event:
            if value > state["maximum_forward_value"]:
                state["maximum_forward_value"] = value
                state["maximum_forward_event"] = event
            for multiple in milestone_values:
                if state["historical_milestones"][multiple] is None:
                    if value >= trough_value * Decimal(multiple):
                        state["historical_milestones"][multiple] = event

        if event >= confirmation_event:
            if value < state["minimum_post_confirmation_value"]:
                state["minimum_post_confirmation_value"] = value
                state["minimum_post_confirmation_event"] = event
            for multiple in milestone_values:
                if state["live_milestones"][multiple] is None:
                    if value >= trough_value * Decimal(multiple):
                        state["live_milestones"][multiple] = event

    if total_points != int(path.get("price_points", -1)):
        raise ValueError("outcome price-path point count changed")
    if seen_tokens != set(frozen):
        raise ValueError("outcome price-path token coverage changed")

    rows = []
    milestone_reach_counts = Counter()
    comeback_count = 0
    for token in sorted(frozen):
        event = frozen[token]
        status = str(event["candidate_status"])
        if status != "confirmed":
            row = {
                "version": PHASE2_OUTCOME_LABEL_VERSION,
                "token": token,
                "detector_id": selected_detector,
                "dump_status": status,
                "outcome_eligible": False,
                "outcome_status": "no_confirmed_first_major_dump",
                "comeback_5x": None,
                "max_post_dump_multiple": None,
                "maximum_forward_market_cap_proxy_usd": None,
                "maximum_adverse_excursion_from_confirmation_fraction": None,
                "observation_end_block": snapshot,
                "right_censored_at_snapshot": False,
                "death_state_defined": False,
                "eventual_failure_state": None,
            }
            for multiple in milestone_values:
                row[f"reached_{multiple}x"] = None
                row[f"time_to_{multiple}x_from_trough_blocks"] = None
                row[f"time_to_{multiple}x_from_confirmation_blocks"] = None
            rows.append(row)
            continue

        state = confirmed[token]
        trough_value = state["trough_value"]
        confirmation_value = state["confirmation_value"]
        max_value = state["maximum_forward_value"]
        max_event = state["maximum_forward_event"]
        min_live = state["minimum_post_confirmation_value"]
        min_live_event = state["minimum_post_confirmation_event"]
        max_multiple = max_value / trough_value
        adverse = max(
            Decimal("0"),
            (confirmation_value - min_live) / confirmation_value,
        )
        comeback = max_multiple >= Decimal("5")
        if comeback:
            comeback_count += 1

        row = {
            "version": PHASE2_OUTCOME_LABEL_VERSION,
            "token": token,
            "detector_id": selected_detector,
            "dump_status": status,
            "outcome_eligible": True,
            "outcome_status": "observed_through_snapshot",
            "post_dump_base_semantics": "retrospective_trough",
            "live_signal_semantics": "confirmation_event",
            "trough_block": state["trough_event"][0],
            "trough_transaction_index": (
                None
                if state["trough_event"][1] == -1
                else state["trough_event"][1]
            ),
            "trough_log_index": state["trough_event"][2],
            "trough_market_cap_proxy_usd": _decimal_text(trough_value),
            "confirmation_block": state["confirmation_event"][0],
            "confirmation_transaction_index": (
                None
                if state["confirmation_event"][1] == -1
                else state["confirmation_event"][1]
            ),
            "confirmation_log_index": state["confirmation_event"][2],
            "confirmation_market_cap_proxy_usd": _decimal_text(
                confirmation_value
            ),
            "max_post_dump_multiple": _decimal_text(max_multiple),
            "maximum_forward_market_cap_proxy_usd": _decimal_text(
                max_value
            ),
            "maximum_forward_block": max_event[0],
            "maximum_forward_transaction_index": (
                None if max_event[1] == -1 else max_event[1]
            ),
            "maximum_forward_log_index": max_event[2],
            "comeback_5x": comeback,
            "minimum_post_confirmation_market_cap_proxy_usd": (
                _decimal_text(min_live)
            ),
            "minimum_post_confirmation_block": min_live_event[0],
            "minimum_post_confirmation_transaction_index": (
                None if min_live_event[1] == -1 else min_live_event[1]
            ),
            "minimum_post_confirmation_log_index": min_live_event[2],
            "maximum_adverse_excursion_from_confirmation_fraction": (
                _decimal_text(adverse)
            ),
            "observation_end_block": snapshot,
            "right_censored_at_snapshot": True,
            "death_state_defined": False,
            "eventual_failure_state": None,
        }
        for multiple in milestone_values:
            historical = state["historical_milestones"][multiple]
            live = state["live_milestones"][multiple]
            reached = historical is not None
            row[f"reached_{multiple}x"] = reached
            if reached:
                milestone_reach_counts[multiple] += 1
            row[f"time_to_{multiple}x_from_trough_blocks"] = (
                None
                if historical is None
                else historical[0] - state["trough_event"][0]
            )
            row[f"time_to_{multiple}x_from_confirmation_blocks"] = (
                None
                if live is None
                else live[0] - state["confirmation_event"][0]
            )
            row[f"first_{multiple}x_block"] = (
                None if historical is None else historical[0]
            )
            row[f"first_{multiple}x_transaction_index"] = (
                None
                if historical is None or historical[1] == -1
                else historical[1]
            )
            row[f"first_{multiple}x_log_index"] = (
                None if historical is None else historical[2]
            )
        rows.append(row)

    manifest = write_jsonl_snapshot(
        rows,
        output=output,
        provenance={
            "version": PHASE2_OUTCOME_LABEL_VERSION,
            "selected_detector_id": selected_detector,
            "universe_sha256": detector["universe_sha256"],
            "normalized_price_path_sha256": detector[
                "normalized_price_path_sha256"
            ],
            "post_dump_base_semantics": "retrospective_trough",
            "live_signal_semantics": "confirmation_event",
            "milestones": list(milestone_values),
            "phase2_dump_detector_frozen": True,
            "outcome_labels_computed": True,
        },
    )
    summary = {
        "version": PHASE2_OUTCOME_LABEL_VERSION,
        "snapshot_head_block": snapshot,
        "universe_sha256": str(detector["universe_sha256"]),
        "normalized_price_path_sha256": str(
            detector["normalized_price_path_sha256"]
        ),
        "geometry_sha256": str(detector["geometry_sha256"]),
        "selected_detector_id": selected_detector,
        "selected_candidate_spec": dict(
            detector["selected_candidate_spec"]
        ),
        "tokens": tokens,
        "confirmed_dump_tokens": len(confirmed),
        "outcome_eligible_tokens": len(confirmed),
        "comeback_5x_tokens": comeback_count,
        "outcome_rows": int(manifest["records"]),
        "outcome_rows_sha256": manifest["sha256"],
        "milestones": list(milestone_values),
        "milestone_reach_counts": {
            str(value): int(milestone_reach_counts.get(value, 0))
            for value in milestone_values
        },
        "post_dump_base_semantics": "retrospective_trough",
        "live_signal_semantics": "confirmation_event",
        "max_post_dump_multiple_retained": True,
        "right_censoring_recorded": True,
        "death_state_defined": False,
        "candidate_selected": True,
        "dump_threshold_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
    }
    return manifest, summary


def build_phase2_outcome_handoff(
    outcome_summary: Mapping[str, object],
    *,
    outcome_summary_sha256: str,
    detector_freeze_handoff_sha256: str,
    price_path_handoff_sha256: str,
) -> dict:
    """Bind continuous labels to the frozen detector and canonical path."""

    summary = dict(outcome_summary)
    if str(summary.get("version") or "") != PHASE2_OUTCOME_LABEL_VERSION:
        raise ValueError("outcome handoff version changed")
    if summary.get("candidate_selected") is not True:
        raise ValueError("outcome handoff lacks selected detector")
    if summary.get("dump_threshold_frozen") is not True:
        raise ValueError("outcome handoff dump threshold is not frozen")
    if summary.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("outcome handoff detector is not frozen")
    if summary.get("outcome_labels_computed") is not True:
        raise ValueError("outcome handoff labels are not computed")
    if summary.get("max_post_dump_multiple_retained") is not True:
        raise ValueError("outcome handoff lost continuous magnitude")
    if summary.get("post_dump_base_semantics") != "retrospective_trough":
        raise ValueError("outcome handoff base semantics changed")
    if summary.get("live_signal_semantics") != "confirmation_event":
        raise ValueError("outcome handoff live semantics changed")
    if 5 not in [int(value) for value in summary.get("milestones") or []]:
        raise ValueError("outcome handoff lost 5x boundary")

    return {
        "version": PHASE2_OUTCOME_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "universe_sha256": _sha256(
            summary.get("universe_sha256"),
            label="outcome universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="outcome price path",
        ),
        "geometry_sha256": _sha256(
            summary.get("geometry_sha256"),
            label="outcome geometry",
        ),
        "detector_freeze_handoff_sha256": _sha256(
            detector_freeze_handoff_sha256,
            label="outcome detector freeze handoff",
        ),
        "price_path_handoff_sha256": _sha256(
            price_path_handoff_sha256,
            label="outcome price path handoff",
        ),
        "outcome_rows_sha256": _sha256(
            summary.get("outcome_rows_sha256"),
            label="outcome rows",
        ),
        "outcome_summary_sha256": _sha256(
            outcome_summary_sha256,
            label="outcome summary",
        ),
        "selected_detector_id": str(summary["selected_detector_id"]),
        "tokens": int(summary["tokens"]),
        "confirmed_dump_tokens": int(summary["confirmed_dump_tokens"]),
        "comeback_5x_tokens": int(summary["comeback_5x_tokens"]),
        "milestones": [
            int(value) for value in summary["milestones"]
        ],
        "post_dump_base_semantics": "retrospective_trough",
        "live_signal_semantics": "confirmation_event",
        "max_post_dump_multiple_retained": True,
        "candidate_selected": True,
        "dump_threshold_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
    }
