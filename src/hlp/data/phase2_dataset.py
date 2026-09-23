"""Final immutable Phase-2 universe + outcome dataset bundle."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_outcomes import (
    PHASE2_OUTCOME_HANDOFF_VERSION,
    PHASE2_OUTCOME_LABEL_VERSION,
)
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION
from hlp.data.snapshot import write_jsonl_snapshot


PHASE2_DATASET_VERSION = "phase2-universe-outcome-dataset-v1"
PHASE2_DATASET_HANDOFF_VERSION = (
    "phase2-universe-outcome-dataset-handoff-v1"
)
PHASE2_CHECKPOINT_NAME = "hlp-v1-phase2-universe-labels"
PHASE2_UNIVERSE_FREEZE_HANDOFF_VERSION = (
    "phase2-universe-freeze-handoff-v1"
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


def materialize_phase2_dataset(
    universe_rows: Iterable[Mapping[str, object]],
    outcome_rows: Iterable[Mapping[str, object]],
    *,
    universe_summary: Mapping[str, object],
    universe_handoff: Mapping[str, object],
    outcome_handoff: Mapping[str, object],
    output: Path,
) -> tuple[dict, dict]:
    """Join immutable Phase-2 population rows to immutable outcome rows."""

    universe_summary = dict(universe_summary)
    universe_handoff = dict(universe_handoff)
    outcome_handoff = dict(outcome_handoff)

    if (
        str(universe_summary.get("version") or "")
        != PHASE2_UNIVERSE_VERSION
    ):
        raise ValueError("Phase-2 dataset universe version changed")
    if universe_summary.get("coverage_complete") is not True:
        raise ValueError("Phase-2 dataset universe coverage is incomplete")
    if universe_summary.get("phase2_universe_frozen") is not True:
        raise ValueError("Phase-2 dataset universe is not frozen")
    if (
        str(universe_handoff.get("version") or "")
        != PHASE2_UNIVERSE_FREEZE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-2 dataset universe handoff version changed")
    if (
        universe_handoff.get("phase2_universe_coverage_complete")
        is not True
    ):
        raise ValueError("Phase-2 dataset handoff coverage is incomplete")
    if universe_handoff.get("phase2_universe_frozen") is not True:
        raise ValueError("Phase-2 dataset handoff universe is not frozen")

    if (
        str(outcome_handoff.get("version") or "")
        != PHASE2_OUTCOME_HANDOFF_VERSION
    ):
        raise ValueError("Phase-2 dataset outcome handoff version changed")
    if outcome_handoff.get("candidate_selected") is not True:
        raise ValueError("Phase-2 dataset lacks selected dump detector")
    if outcome_handoff.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("Phase-2 dataset dump detector is not frozen")
    if outcome_handoff.get("outcome_labels_computed") is not True:
        raise ValueError("Phase-2 dataset outcomes are not computed")
    if outcome_handoff.get("max_post_dump_multiple_retained") is not True:
        raise ValueError("Phase-2 dataset lost continuous outcome magnitude")

    snapshot = int(universe_summary.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Phase-2 dataset snapshot is invalid")
    if int(universe_handoff.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-2 dataset universe snapshot drift")
    if int(outcome_handoff.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-2 dataset outcome snapshot drift")

    universe_sha = _sha256(
        universe_handoff.get("eligible_universe_sha256"),
        label="Phase-2 eligible universe",
    )
    if universe_sha != _sha256(
        universe_summary.get("eligible_universe_sha256"),
        label="Phase-2 universe summary",
    ):
        raise ValueError("Phase-2 dataset universe SHA drift")
    if universe_sha != _sha256(
        outcome_handoff.get("universe_sha256"),
        label="Phase-2 outcome universe",
    ):
        raise ValueError("Phase-2 dataset outcome/universe SHA drift")

    universe = {}
    for raw in universe_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in universe:
            raise ValueError(
                f"Phase-2 dataset repeats universe token: {token}"
            )
        if row.get("universe_status") != "eligible":
            raise ValueError(
                f"Phase-2 dataset contains non-eligible universe row: {token}"
            )
        row["token"] = token
        universe[token] = row

    expected_tokens = int(universe_summary.get("eligible_tokens", -1))
    if expected_tokens <= 0 or len(universe) != expected_tokens:
        raise ValueError("Phase-2 dataset universe token count changed")
    if int(universe_handoff.get("eligible_tokens", -1)) != expected_tokens:
        raise ValueError("Phase-2 dataset universe handoff count drift")
    if int(outcome_handoff.get("tokens", -1)) != expected_tokens:
        raise ValueError("Phase-2 dataset outcome token count drift")

    outcomes = {}
    for raw in outcome_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_OUTCOME_LABEL_VERSION
        ):
            raise ValueError("Phase-2 dataset outcome row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in outcomes:
            raise ValueError(
                f"Phase-2 dataset repeats outcome token: {token}"
            )
        row["token"] = token
        outcomes[token] = row

    if set(outcomes) != set(universe):
        raise ValueError(
            "Phase-2 dataset universe/outcome token membership changed: "
            f"missing={sorted(set(universe) - set(outcomes))[:20]} "
            f"extra={sorted(set(outcomes) - set(universe))[:20]}"
        )

    confirmed = 0
    outcome_eligible = 0
    comeback_5x = 0
    dataset_rows = []
    for token in sorted(universe):
        outcome = outcomes[token]
        if outcome.get("outcome_eligible") is True:
            outcome_eligible += 1
        if outcome.get("dump_status") == "confirmed":
            confirmed += 1
        if outcome.get("comeback_5x") is True:
            comeback_5x += 1
        dataset_rows.append({
            "version": PHASE2_DATASET_VERSION,
            "token": token,
            "snapshot_head_block": snapshot,
            "universe": universe[token],
            "outcome": outcome,
            "phase2_universe_frozen": True,
            "phase2_dump_detector_frozen": True,
            "outcome_labels_computed": True,
            "phase3_features_attached": False,
        })

    if confirmed != int(outcome_handoff.get("confirmed_dump_tokens", -1)):
        raise ValueError("Phase-2 dataset confirmed-dump count drift")
    if comeback_5x != int(outcome_handoff.get("comeback_5x_tokens", -1)):
        raise ValueError("Phase-2 dataset 5x outcome count drift")
    if outcome_eligible != confirmed:
        raise ValueError(
            "Phase-2 dataset outcome eligibility must equal confirmed dumps"
        )

    manifest = write_jsonl_snapshot(
        dataset_rows,
        output=output,
        provenance={
            "version": PHASE2_DATASET_VERSION,
            "checkpoint_name": PHASE2_CHECKPOINT_NAME,
            "snapshot_head_block": snapshot,
            "eligible_universe_sha256": universe_sha,
            "outcome_rows_sha256": outcome_handoff[
                "outcome_rows_sha256"
            ],
            "phase2_universe_frozen": True,
            "phase2_dump_detector_frozen": True,
            "outcome_labels_computed": True,
            "phase3_features_attached": False,
        },
    )
    summary = {
        "version": PHASE2_DATASET_VERSION,
        "checkpoint_name": PHASE2_CHECKPOINT_NAME,
        "snapshot_head_block": snapshot,
        "eligible_universe_sha256": universe_sha,
        "normalized_price_path_sha256": str(
            outcome_handoff["normalized_price_path_sha256"]
        ),
        "outcome_rows_sha256": str(
            outcome_handoff["outcome_rows_sha256"]
        ),
        "dataset_rows_sha256": manifest["sha256"],
        "tokens": expected_tokens,
        "confirmed_dump_tokens": confirmed,
        "outcome_eligible_tokens": outcome_eligible,
        "comeback_5x_tokens": comeback_5x,
        "max_post_dump_multiple_retained": True,
        "post_dump_base_semantics": str(
            outcome_handoff["post_dump_base_semantics"]
        ),
        "live_signal_semantics": str(
            outcome_handoff["live_signal_semantics"]
        ),
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
        "phase2_dataset_ready": True,
    }
    return manifest, summary


def build_phase2_dataset_handoff(
    dataset_summary: Mapping[str, object],
    *,
    dataset_summary_sha256: str,
    universe_handoff_sha256: str,
    outcome_handoff_sha256: str,
) -> dict:
    """Publish the Phase-2 checkpoint without exposing labels as features."""

    summary = dict(dataset_summary)
    if str(summary.get("version") or "") != PHASE2_DATASET_VERSION:
        raise ValueError("Phase-2 dataset handoff version changed")
    if summary.get("checkpoint_name") != PHASE2_CHECKPOINT_NAME:
        raise ValueError("Phase-2 dataset checkpoint name changed")
    if summary.get("phase2_universe_frozen") is not True:
        raise ValueError("Phase-2 dataset handoff universe is not frozen")
    if summary.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("Phase-2 dataset handoff detector is not frozen")
    if summary.get("outcome_labels_computed") is not True:
        raise ValueError("Phase-2 dataset handoff labels are not computed")
    if summary.get("max_post_dump_multiple_retained") is not True:
        raise ValueError("Phase-2 dataset handoff lost magnitude outcome")
    if summary.get("phase3_features_attached") is not False:
        raise ValueError(
            "Phase-2 dataset handoff must not contain Phase-3 features"
        )
    if summary.get("phase2_dataset_ready") is not True:
        raise ValueError("Phase-2 dataset handoff is not ready")

    return {
        "version": PHASE2_DATASET_HANDOFF_VERSION,
        "checkpoint_name": PHASE2_CHECKPOINT_NAME,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-2 dataset universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="Phase-2 dataset price path",
        ),
        "outcome_rows_sha256": _sha256(
            summary.get("outcome_rows_sha256"),
            label="Phase-2 dataset outcomes",
        ),
        "dataset_rows_sha256": _sha256(
            summary.get("dataset_rows_sha256"),
            label="Phase-2 dataset rows",
        ),
        "dataset_summary_sha256": _sha256(
            dataset_summary_sha256,
            label="Phase-2 dataset summary",
        ),
        "universe_handoff_sha256": _sha256(
            universe_handoff_sha256,
            label="Phase-2 universe handoff",
        ),
        "outcome_handoff_sha256": _sha256(
            outcome_handoff_sha256,
            label="Phase-2 outcome handoff",
        ),
        "tokens": int(summary["tokens"]),
        "confirmed_dump_tokens": int(
            summary["confirmed_dump_tokens"]
        ),
        "comeback_5x_tokens": int(summary["comeback_5x_tokens"]),
        "max_post_dump_multiple_retained": True,
        "phase2_universe_frozen": True,
        "phase2_dump_detector_frozen": True,
        "outcome_labels_computed": True,
        "phase3_features_attached": False,
        "phase2_dataset_ready": True,
    }
