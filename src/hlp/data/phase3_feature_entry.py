"""Leakage-safe Phase-3 feature-subject entry contract."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase2_dataset import (
    PHASE2_CHECKPOINT_NAME,
    PHASE2_DATASET_HANDOFF_VERSION,
)
from hlp.data.phase2_dump_research import (
    PHASE2_DUMP_DETECTOR_FREEZE_HANDOFF_VERSION,
    PHASE2_DUMP_DETECTOR_FREEZE_VERSION,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_FEATURE_SUBJECT_VERSION = "phase3-feature-subject-v1"
PHASE3_FEATURE_ENTRY_HANDOFF_VERSION = (
    "phase3-feature-entry-handoff-v1"
)
PHASE3_FEATURE_SNAPSHOT_KIND = "first_major_dump_confirmation"

PHASE3_FEATURE_SUBJECT_FIELDS = frozenset({
    "version",
    "token",
    "snapshot_kind",
    "feature_cutoff_block",
    "feature_cutoff_transaction_index",
    "feature_cutoff_log_index",
    "feature_cutoff_inclusive",
    "selected_detector_id",
    "detector_family",
})


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def materialize_phase3_feature_subjects(
    universe_rows: Iterable[Mapping[str, object]],
    detector_rows: Iterable[Mapping[str, object]],
    *,
    phase2_dataset_handoff: Mapping[str, object],
    detector_handoff: Mapping[str, object],
    output: Path,
) -> tuple[dict, dict]:
    """Freeze Phase-3 subject cutoffs without exposing future-derived labels."""

    checkpoint = dict(phase2_dataset_handoff)
    detector = dict(detector_handoff)

    if (
        str(checkpoint.get("version") or "")
        != PHASE2_DATASET_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 entry Phase-2 checkpoint version changed")
    if checkpoint.get("checkpoint_name") != PHASE2_CHECKPOINT_NAME:
        raise ValueError("Phase-3 entry Phase-2 checkpoint name changed")
    if checkpoint.get("phase2_dataset_ready") is not True:
        raise ValueError("Phase-3 entry requires ready Phase-2 dataset")
    if checkpoint.get("phase2_universe_frozen") is not True:
        raise ValueError("Phase-3 entry universe is not frozen")
    if checkpoint.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("Phase-3 entry detector is not frozen")
    if checkpoint.get("outcome_labels_computed") is not True:
        raise ValueError("Phase-3 entry requires completed Phase-2 labels")
    if checkpoint.get("phase3_features_attached") is not False:
        raise ValueError("Phase-3 entry checkpoint already contains features")

    if (
        str(detector.get("version") or "")
        != PHASE2_DUMP_DETECTOR_FREEZE_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 entry detector handoff version changed")
    if detector.get("candidate_selected") is not True:
        raise ValueError("Phase-3 entry detector has no selected candidate")
    if detector.get("detector_freeze_ready") is not True:
        raise ValueError("Phase-3 entry detector is not freeze-ready")
    if detector.get("phase2_dump_detector_frozen") is not True:
        raise ValueError("Phase-3 entry detector is not frozen")
    if detector.get("outcome_labels_computed") is not False:
        raise ValueError(
            "Phase-3 entry detector handoff contains outcome labels"
        )

    snapshot = int(checkpoint.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Phase-3 entry snapshot is invalid")
    if int(detector.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-3 entry checkpoint/detector snapshot drift")
    if _sha256(
        checkpoint.get("eligible_universe_sha256"),
        label="Phase-3 entry checkpoint universe",
    ) != _sha256(
        detector.get("universe_sha256"),
        label="Phase-3 entry detector universe",
    ):
        raise ValueError("Phase-3 entry checkpoint/detector universe drift")
    if _sha256(
        checkpoint.get("normalized_price_path_sha256"),
        label="Phase-3 entry checkpoint price path",
    ) != _sha256(
        detector.get("normalized_price_path_sha256"),
        label="Phase-3 entry detector price path",
    ):
        raise ValueError("Phase-3 entry checkpoint/detector price-path drift")
    if int(checkpoint.get("tokens", -1)) != int(
        detector.get("tokens", -2)
    ):
        raise ValueError("Phase-3 entry checkpoint/detector token-count drift")

    universe = set()
    for raw in universe_rows:
        row = dict(raw)
        token = normalize_address(str(row.get("token") or ""))
        if token in universe:
            raise ValueError(
                f"Phase-3 entry universe repeats token: {token}"
            )
        if row.get("universe_status") != "eligible":
            raise ValueError(
                f"Phase-3 entry universe contains non-eligible token: {token}"
            )
        universe.add(token)

    expected_tokens = int(checkpoint["tokens"])
    if len(universe) != expected_tokens:
        raise ValueError("Phase-3 entry universe token count changed")

    selected_detector = str(detector.get("selected_candidate_id") or "")
    selected_spec = dict(detector.get("selected_candidate_spec") or {})
    detector_family = str(selected_spec.get("family") or "")
    if not selected_detector:
        raise ValueError("Phase-3 entry selected detector id is empty")
    if str(selected_spec.get("candidate_id") or "") != selected_detector:
        raise ValueError("Phase-3 entry selected detector spec drift")
    if not detector_family:
        raise ValueError("Phase-3 entry detector family is empty")

    seen = set()
    subjects = []
    status_counts = {}
    for raw in detector_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE2_DUMP_DETECTOR_FREEZE_VERSION
        ):
            raise ValueError("Phase-3 entry detector row version changed")
        if row.get("detector_frozen") is not True:
            raise ValueError("Phase-3 entry detector row is not frozen")
        if str(row.get("detector_id") or "") != selected_detector:
            raise ValueError("Phase-3 entry detector row id drift")
        token = normalize_address(str(row.get("token") or ""))
        if token not in universe:
            raise ValueError(
                f"Phase-3 entry detector token is outside universe: {token}"
            )
        if token in seen:
            raise ValueError(
                f"Phase-3 entry detector repeats token: {token}"
            )
        seen.add(token)
        status = str(row.get("candidate_status") or "")
        if status not in {
            "confirmed",
            "drawdown_unconfirmed",
            "no_material_drawdown",
        }:
            raise ValueError(
                f"Phase-3 entry detector status is invalid: {status}"
            )
        status_counts[status] = status_counts.get(status, 0) + 1

        if status != "confirmed":
            if row.get("point_in_time_confirmed") is not False:
                raise ValueError(
                    "Phase-3 entry non-confirmed detector flag drift"
                )
            continue
        if row.get("point_in_time_confirmed") is not True:
            raise ValueError(
                "Phase-3 entry confirmed detector flag drift"
            )
        block = int(row.get("confirmation_block", -1))
        raw_tx = row.get("confirmation_transaction_index")
        tx = None if raw_tx is None else int(raw_tx)
        log = int(row.get("confirmation_log_index", -1))
        if block < 0 or (tx is not None and tx < 0) or log < 0:
            raise ValueError(
                f"Phase-3 entry confirmation position is invalid: {token}"
            )
        if block > snapshot:
            raise ValueError(
                f"Phase-3 entry confirmation is after snapshot: {token}"
            )

        subject = {
            "version": PHASE3_FEATURE_SUBJECT_VERSION,
            "token": token,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_block": block,
            "feature_cutoff_transaction_index": tx,
            "feature_cutoff_log_index": log,
            "feature_cutoff_inclusive": True,
            "selected_detector_id": selected_detector,
            "detector_family": detector_family,
        }
        if set(subject) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 feature subject field contract changed")
        subjects.append(subject)

    if seen != universe:
        raise ValueError(
            "Phase-3 entry detector/universe token membership changed"
        )
    confirmed = int(status_counts.get("confirmed", 0))
    if confirmed != int(detector.get("confirmed_tokens", -1)):
        raise ValueError("Phase-3 entry detector confirmed-token count drift")
    if confirmed != int(checkpoint.get("confirmed_dump_tokens", -1)):
        raise ValueError(
            "Phase-3 entry checkpoint confirmed-token count drift"
        )
    if len(subjects) != confirmed:
        raise ValueError("Phase-3 feature-subject count drift")
    if not subjects:
        raise ValueError("Phase-3 entry has no confirmed feature subjects")

    subjects.sort(key=lambda row: row["token"])
    manifest = write_jsonl_snapshot(
        subjects,
        output=output,
        provenance={
            "version": PHASE3_FEATURE_SUBJECT_VERSION,
            "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
            "feature_cutoff_inclusive": True,
            "phase2_checkpoint_name": PHASE2_CHECKPOINT_NAME,
            "eligible_universe_sha256": checkpoint[
                "eligible_universe_sha256"
            ],
            "normalized_price_path_sha256": checkpoint[
                "normalized_price_path_sha256"
            ],
            "selected_detector_id": selected_detector,
            "outcome_rows_consumed": False,
            "outcome_fields_exposed": False,
            "phase3_feature_values_computed": False,
        },
    )
    summary = {
        "version": PHASE3_FEATURE_SUBJECT_VERSION,
        "snapshot_head_block": snapshot,
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_cutoff_inclusive": True,
        "phase2_checkpoint_name": PHASE2_CHECKPOINT_NAME,
        "eligible_universe_sha256": str(
            checkpoint["eligible_universe_sha256"]
        ),
        "normalized_price_path_sha256": str(
            checkpoint["normalized_price_path_sha256"]
        ),
        "selected_detector_id": selected_detector,
        "detector_family": detector_family,
        "universe_tokens": expected_tokens,
        "feature_subjects": len(subjects),
        "detector_status_counts": dict(sorted(status_counts.items())),
        "feature_subjects_sha256": manifest["sha256"],
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": True,
    }
    return manifest, summary


def build_phase3_feature_entry_handoff(
    entry_summary: Mapping[str, object],
    *,
    entry_summary_sha256: str,
    phase2_dataset_handoff_sha256: str,
    detector_freeze_handoff_sha256: str,
) -> dict:
    """Bind the leakage-safe Phase-3 subject population and cutoff semantics."""

    summary = dict(entry_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_FEATURE_SUBJECT_VERSION
    ):
        raise ValueError("Phase-3 feature entry handoff version changed")
    if summary.get("phase2_checkpoint_name") != PHASE2_CHECKPOINT_NAME:
        raise ValueError("Phase-3 feature entry checkpoint drift")
    if summary.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
        raise ValueError("Phase-3 feature entry snapshot semantics changed")
    if summary.get("feature_cutoff_inclusive") is not True:
        raise ValueError("Phase-3 feature entry cutoff semantics changed")
    if summary.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 feature entry consumed outcome rows")
    if summary.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 feature entry exposes outcome fields")
    if summary.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 feature entry allows future state")
    if summary.get("phase3_feature_values_computed") is not False:
        raise ValueError("Phase-3 entry unexpectedly computed features")
    if summary.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 feature entry is not ready")

    return {
        "version": PHASE3_FEATURE_ENTRY_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_cutoff_inclusive": True,
        "phase2_checkpoint_name": PHASE2_CHECKPOINT_NAME,
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 feature-entry universe",
        ),
        "normalized_price_path_sha256": _sha256(
            summary.get("normalized_price_path_sha256"),
            label="Phase-3 feature-entry price path",
        ),
        "phase2_dataset_handoff_sha256": _sha256(
            phase2_dataset_handoff_sha256,
            label="Phase-3 Phase-2 dataset handoff",
        ),
        "detector_freeze_handoff_sha256": _sha256(
            detector_freeze_handoff_sha256,
            label="Phase-3 detector freeze handoff",
        ),
        "feature_subjects_sha256": _sha256(
            summary.get("feature_subjects_sha256"),
            label="Phase-3 feature subjects",
        ),
        "selected_detector_id": str(summary["selected_detector_id"]),
        "universe_tokens": int(summary["universe_tokens"]),
        "feature_subjects": int(summary["feature_subjects"]),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "phase3_feature_values_computed": False,
        "phase3_feature_entry_ready": True,
    }
