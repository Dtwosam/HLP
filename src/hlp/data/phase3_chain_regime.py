"""Causal chain-wide regime features at each Phase-3 signal cutoff."""

from __future__ import annotations

from collections import Counter, deque
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
    validate_phase3_feature_registry,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_CHAIN_REGIME_FEATURE_VERSION = "phase3-chain-regime-features-v1"
PHASE3_CHAIN_REGIME_HANDOFF_VERSION = (
    "phase3-chain-regime-features-handoff-v1"
)
REGIME_WINDOW_BLOCKS = 1000

CHAIN_REGIME_FEATURE_IDS = (
    "regime.observed_tokens_so_far",
    "regime.tokens_above_100k_at_cutoff",
    "regime.median_latest_market_cap_proxy_usd",
    "regime.price_points_last_1000_blocks",
    "regime.active_tokens_last_1000_blocks",
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
        raise ValueError("Phase-3 chain-regime event position is invalid")
    return block, tx, log


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    return (
        int(row["feature_cutoff_block"]),
        (
            -1
            if row.get("feature_cutoff_transaction_index") is None
            else int(row["feature_cutoff_transaction_index"])
        ),
        int(row["feature_cutoff_log_index"]),
    )


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


def _median(values: Iterable[Decimal]) -> Decimal:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("Phase-3 chain regime has no observed tokens")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    with localcontext() as context:
        context.prec = 80
        return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def materialize_phase3_chain_regime_features(
    subject_rows: Iterable[Mapping[str, object]],
    price_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    price_path_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Replay the chain-wide canonical price path to every subject cutoff."""

    entry = dict(entry_handoff)
    price_handoff = dict(price_path_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 chain-regime entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 chain-regime entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 chain-regime entry consumed outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 chain-regime entry allows future state")

    if (
        str(price_handoff.get("version") or "")
        != PHASE2_RESEARCH_PRICE_PATH_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 chain-regime price-path version changed")
    if price_handoff.get("research_price_path_ready") is not True:
        raise ValueError("Phase-3 chain regime requires ready price path")
    if price_handoff.get("outcome_labels_computed") is not False:
        raise ValueError("Phase-3 chain-regime price path has outcomes")
    snapshot = int(entry.get("snapshot_head_block", -1))
    if int(price_handoff.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-3 chain-regime snapshot drift")
    if _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 chain-regime universe",
    ) != _sha256(
        price_handoff.get("universe_sha256"),
        label="Phase-3 chain-regime price-path universe",
    ):
        raise ValueError("Phase-3 chain-regime universe drift")
    if _sha256(
        entry.get("normalized_price_path_sha256"),
        label="Phase-3 chain-regime entry path",
    ) != _sha256(
        price_handoff.get("normalized_price_path_sha256"),
        label="Phase-3 chain-regime canonical path",
    ):
        raise ValueError("Phase-3 chain-regime price-path SHA drift")

    regime_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "chain_regime"
    }
    if regime_ids != set(CHAIN_REGIME_FEATURE_IDS):
        raise ValueError("Phase-3 chain-regime registry changed")

    subjects = []
    seen = set()
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 chain-regime subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 chain-regime subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 chain-regime snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 chain-regime cutoff is not inclusive")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(
                f"Phase-3 chain-regime repeats subject: {token}"
            )
        seen.add(token)
        cutoff = _cutoff(row)
        if cutoff[0] > snapshot:
            raise ValueError(
                f"Phase-3 chain-regime cutoff after snapshot: {token}"
            )
        subjects.append((cutoff, token))
    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 chain-regime subject count drift")
    subjects.sort(key=lambda item: (item[0], item[1]))

    latest = {}
    above_100k = 0
    recent = deque()
    recent_counts = Counter()
    threshold = Decimal("100000")
    total_price_rows = 0
    previous_global = None
    price_iter = iter(price_rows)

    def next_validated():
        nonlocal total_price_rows, previous_global
        try:
            raw = next(price_iter)
        except StopIteration:
            return None
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_RESEARCH_PRICE_PATH_VERSION
        ):
            raise ValueError("Phase-3 chain-regime price row version changed")
        if row.get("canonical_research_price_path") is not True:
            raise ValueError("Phase-3 chain-regime price row is not canonical")
        token = normalize_address(str(row.get("token") or ""))
        event = _event(row)
        if event[0] > snapshot:
            raise ValueError(
                "Phase-3 chain-regime price row after snapshot"
            )
        key = (*event, token)
        if previous_global is not None and key <= previous_global:
            raise ValueError(
                "Phase-3 chain-regime price path is not chronological"
            )
        previous_global = key
        total_price_rows += 1
        return {
            "token": token,
            "event": event,
            "market_cap": _decimal(
                row.get("market_cap_proxy_usd"),
                label=f"{token} chain-regime market cap",
            ),
        }

    next_price = next_validated()
    output_rows = []
    price_rows_used_through_last_cutoff = 0
    for cutoff, subject_token in subjects:
        while (
            next_price is not None
            and next_price["event"] <= cutoff
        ):
            token = next_price["token"]
            value = next_price["market_cap"]
            prior = latest.get(token)
            if prior is not None and prior >= threshold:
                above_100k -= 1
            latest[token] = value
            if value >= threshold:
                above_100k += 1
            recent.append(
                (next_price["event"], token)
            )
            recent_counts[token] += 1
            price_rows_used_through_last_cutoff += 1
            next_price = next_validated()

        minimum_block = cutoff[0] - (REGIME_WINDOW_BLOCKS - 1)
        while recent and recent[0][0][0] < minimum_block:
            _, token = recent.popleft()
            recent_counts[token] -= 1
            if recent_counts[token] == 0:
                del recent_counts[token]

        if subject_token not in latest:
            raise ValueError(
                f"Phase-3 chain-regime subject has no price state: "
                f"{subject_token}"
            )
        if not latest:
            raise ValueError("Phase-3 chain-regime state is empty")
        values = {
            "regime.observed_tokens_so_far": len(latest),
            "regime.tokens_above_100k_at_cutoff": above_100k,
            "regime.median_latest_market_cap_proxy_usd": _decimal_text(
                _median(latest.values())
            ),
            "regime.price_points_last_1000_blocks": len(recent),
            "regime.active_tokens_last_1000_blocks": len(recent_counts),
        }
        if set(values) != set(CHAIN_REGIME_FEATURE_IDS):
            raise ValueError("Phase-3 chain-regime feature set changed")
        output_rows.append({
            "version": PHASE3_CHAIN_REGIME_FEATURE_VERSION,
            "token": subject_token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": cutoff[0],
            "feature_cutoff_transaction_index": (
                None if cutoff[1] == -1 else cutoff[1]
            ),
            "feature_cutoff_log_index": cutoff[2],
            "feature_cutoff_inclusive": True,
            "feature_registry_sha256": registry["registry_sha256"],
            "feature_values": values,
            "missing_feature_ids": [],
            "data_quality": {
                "canonical_chain_price_coverage_complete": True,
                "future_price_rows_used": False,
                "regime_window_blocks": REGIME_WINDOW_BLOCKS,
            },
        })

    while next_price is not None:
        next_price = next_validated()

    if total_price_rows != int(price_handoff.get("price_points", -1)):
        raise ValueError("Phase-3 chain-regime price-point count drift")

    output_rows.sort(key=lambda row: row["token"])
    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_CHAIN_REGIME_FEATURE_VERSION,
            "feature_family": "chain_regime",
            "feature_registry_sha256": registry["registry_sha256"],
            "normalized_price_path_sha256": entry[
                "normalized_price_path_sha256"
            ],
            "regime_window_blocks": REGIME_WINDOW_BLOCKS,
            "outcome_rows_consumed": False,
            "future_price_rows_used": False,
        },
    )
    summary = {
        "version": PHASE3_CHAIN_REGIME_FEATURE_VERSION,
        "snapshot_head_block": snapshot,
        "feature_family": "chain_regime",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(CHAIN_REGIME_FEATURE_IDS),
        "features_per_subject": len(CHAIN_REGIME_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "canonical_price_points_validated": total_price_rows,
        "price_rows_used_through_last_cutoff": (
            price_rows_used_through_last_cutoff
        ),
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "normalized_price_path_sha256": str(
            entry["normalized_price_path_sha256"]
        ),
        "regime_window_blocks": REGIME_WINDOW_BLOCKS,
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_chain_regime_features_ready": True,
    }
    return manifest, summary


def build_phase3_chain_regime_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    price_path_handoff_sha256: str,
) -> dict:
    summary = dict(feature_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_CHAIN_REGIME_FEATURE_VERSION
    ):
        raise ValueError("Phase-3 chain-regime handoff version changed")
    if summary.get("feature_family") != "chain_regime":
        raise ValueError("Phase-3 chain-regime family changed")
    for flag in (
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_chain_regime_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(
                f"Phase-3 chain-regime handoff lacks {flag}"
            )
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
        "future_price_rows_used",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 chain-regime handoff violates {flag}"
            )
    return {
        "version": PHASE3_CHAIN_REGIME_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "chain_regime",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 chain-regime registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 chain-regime rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 chain-regime summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 chain-regime entry",
        ),
        "price_path_handoff_sha256": _sha256(
            price_path_handoff_sha256,
            label="Phase-3 chain-regime price path",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 chain-regime universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="Phase-3 chain-regime path",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "regime_window_blocks": int(summary["regime_window_blocks"]),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "future_price_rows_used": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_chain_regime_features_ready": True,
    }
