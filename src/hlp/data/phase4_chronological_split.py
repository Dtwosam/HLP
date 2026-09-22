"""Chronological Phase-4 split freeze without outcome/feature assignment."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase4_discovery_entry import (
    PHASE4_DISCOVERY_CHECKPOINT_NAME,
    PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION,
    PHASE4_DISCOVERY_ENTRY_VERSION,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE4_CHRONOLOGICAL_SPLIT_VERSION = "phase4-chronological-split-v1"
PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION = (
    "phase4-chronological-split-handoff-v1"
)
PHASE4_SPLIT_NAMES = ("discovery", "validation", "final_test")


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-4 chronological split cutoff is invalid")
    return block, tx, log


def materialize_phase4_chronological_split(
    discovery_rows: Iterable[Mapping[str, object]],
    *,
    discovery_entry_handoff: Mapping[str, object],
    discovery_end_block: int,
    validation_end_block: int,
    discovery_output: Path,
    validation_output: Path,
    final_test_output: Path,
) -> tuple[dict[str, dict], dict]:
    """Freeze time-only discovery/validation/final-test membership."""

    handoff = dict(discovery_entry_handoff)
    if (
        str(handoff.get("version") or "")
        != PHASE4_DISCOVERY_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-4 split discovery-entry version changed")
    if handoff.get("phase4_checkpoint_name") != (
        PHASE4_DISCOVERY_CHECKPOINT_NAME
    ):
        raise ValueError("Phase-4 split checkpoint name changed")
    if handoff.get("phase4_discovery_entry_ready") is not True:
        raise ValueError("Phase-4 split discovery entry is not ready")
    if handoff.get("labels_joined_after_feature_freeze") is not True:
        raise ValueError("Phase-4 split labels predate feature freeze")
    if handoff.get("feature_values_mutated") is not False:
        raise ValueError("Phase-4 split input mutated frozen features")
    if handoff.get("phase4_discovery_checkpoint_claimed") is not False:
        raise ValueError("Phase-4 split input already claimed discovery")

    discovery_end = int(discovery_end_block)
    validation_end = int(validation_end_block)
    if discovery_end < 0 or validation_end <= discovery_end:
        raise ValueError("Phase-4 split block boundaries are invalid")

    rows = []
    seen = set()
    for raw in discovery_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE4_DISCOVERY_ENTRY_VERSION
        ):
            raise ValueError("Phase-4 split row version changed")
        token = normalize_address(str(row.get("token") or ""))
        if token in seen:
            raise ValueError(f"Phase-4 split repeats token: {token}")
        seen.add(token)
        if row.get("labels_joined_after_feature_freeze") is not True:
            raise ValueError(
                f"Phase-4 split labels joined too early: {token}"
            )
        if row.get("feature_values_mutated") is not False:
            raise ValueError(
                f"Phase-4 split feature row was mutated: {token}"
            )
        if row.get("phase4_discovery_only") is not True:
            raise ValueError(
                f"Phase-4 split row is not discovery-only: {token}"
            )
        cutoff = _cutoff(row)
        rows.append((cutoff, token, row))

    if len(rows) != int(handoff.get("discovery_subjects", -1)):
        raise ValueError("Phase-4 split subject count drift")
    if not rows:
        raise ValueError("Phase-4 split has no subjects")
    rows.sort(key=lambda item: (item[0], item[1]))

    minimum_block = rows[0][0][0]
    maximum_block = rows[-1][0][0]
    if discovery_end < minimum_block:
        raise ValueError(
            "Phase-4 discovery boundary precedes all subjects"
        )
    if validation_end >= maximum_block:
        raise ValueError(
            "Phase-4 validation boundary leaves no final-test subjects"
        )

    split_rows = {name: [] for name in PHASE4_SPLIT_NAMES}
    last_split_index = -1
    for cutoff, _, row in rows:
        block = cutoff[0]
        if block <= discovery_end:
            split = "discovery"
            split_index = 0
        elif block <= validation_end:
            split = "validation"
            split_index = 1
        else:
            split = "final_test"
            split_index = 2
        if split_index < last_split_index:
            raise ValueError(
                "Phase-4 split assignment is not chronological"
            )
        last_split_index = split_index
        split_rows[split].append(row)

    empty = [
        split
        for split in PHASE4_SPLIT_NAMES
        if not split_rows[split]
    ]
    if empty:
        raise ValueError(
            f"Phase-4 chronological split has empty slices: {empty}"
        )

    outputs = {
        "discovery": discovery_output,
        "validation": validation_output,
        "final_test": final_test_output,
    }
    manifests = {}
    for split in PHASE4_SPLIT_NAMES:
        manifests[split] = write_jsonl_snapshot(
            split_rows[split],
            output=outputs[split],
            provenance={
                "version": PHASE4_CHRONOLOGICAL_SPLIT_VERSION,
                "phase4_checkpoint_name": (
                    PHASE4_DISCOVERY_CHECKPOINT_NAME
                ),
                "split": split,
                "discovery_rows_sha256": handoff[
                    "discovery_rows_sha256"
                ],
                "feature_registry_sha256": handoff[
                    "feature_registry_sha256"
                ],
                "discovery_end_block": discovery_end,
                "validation_end_block": validation_end,
                "split_assignment_key": "feature_cutoff_block",
                "split_assignment_uses_feature_values": False,
                "split_assignment_uses_outcome_values": False,
                "random_shuffle_used": False,
                "feature_values_mutated": False,
            },
        )

    split_ranges = {}
    for split in PHASE4_SPLIT_NAMES:
        values = split_rows[split]
        split_ranges[split] = {
            "rows": len(values),
            "minimum_cutoff_block": min(
                int(row["feature_cutoff_block"])
                for row in values
            ),
            "maximum_cutoff_block": max(
                int(row["feature_cutoff_block"])
                for row in values
            ),
            "rows_sha256": manifests[split]["sha256"],
        }

    summary = {
        "version": PHASE4_CHRONOLOGICAL_SPLIT_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            handoff.get("feature_registry_sha256"),
            label="Phase-4 split feature registry",
        ),
        "discovery_rows_sha256": _sha256(
            handoff.get("discovery_rows_sha256"),
            label="Phase-4 split discovery rows",
        ),
        "discovery_subjects": len(rows),
        "discovery_end_block": discovery_end,
        "validation_end_block": validation_end,
        "minimum_cutoff_block": minimum_block,
        "maximum_cutoff_block": maximum_block,
        "split_ranges": split_ranges,
        "split_assignment_key": "feature_cutoff_block",
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "chronological_order_enforced": True,
        "feature_values_mutated": False,
        "final_test_separated": True,
        "phase4_chronological_split_ready": True,
        "phase4_split_frozen": True,
        "phase4_discovery_checkpoint_claimed": False,
    }
    return manifests, summary


def build_phase4_chronological_split_handoff(
    summary: Mapping[str, object],
    *,
    split_summary_sha256: str,
    discovery_entry_handoff_sha256: str,
    feature_registry_file_sha256: str,
) -> dict:
    """Bind explicit block boundaries before feature relationship selection."""

    row = dict(summary)
    if (
        str(row.get("version") or "")
        != PHASE4_CHRONOLOGICAL_SPLIT_VERSION
    ):
        raise ValueError("Phase-4 split handoff version changed")
    if row.get("phase4_checkpoint_name") != PHASE4_DISCOVERY_CHECKPOINT_NAME:
        raise ValueError("Phase-4 split checkpoint changed")
    for flag in (
        "chronological_order_enforced",
        "final_test_separated",
        "phase4_chronological_split_ready",
        "phase4_split_frozen",
    ):
        if row.get(flag) is not True:
            raise ValueError(f"Phase-4 split handoff lacks {flag}")
    for flag in (
        "split_assignment_uses_feature_values",
        "split_assignment_uses_outcome_values",
        "random_shuffle_used",
        "feature_values_mutated",
        "phase4_discovery_checkpoint_claimed",
    ):
        if row.get(flag) is not False:
            raise ValueError(f"Phase-4 split handoff violates {flag}")

    ranges = row.get("split_ranges")
    if not isinstance(ranges, Mapping):
        raise ValueError("Phase-4 split ranges are missing")
    if set(ranges) != set(PHASE4_SPLIT_NAMES):
        raise ValueError("Phase-4 split range names changed")

    return {
        "version": PHASE4_CHRONOLOGICAL_SPLIT_HANDOFF_VERSION,
        "phase4_checkpoint_name": PHASE4_DISCOVERY_CHECKPOINT_NAME,
        "feature_registry_sha256": _sha256(
            row.get("feature_registry_sha256"),
            label="Phase-4 split registry",
        ),
        "feature_registry_file_sha256": _sha256(
            feature_registry_file_sha256,
            label="Phase-4 split registry file",
        ),
        "discovery_rows_sha256": _sha256(
            row.get("discovery_rows_sha256"),
            label="Phase-4 split source rows",
        ),
        "split_summary_sha256": _sha256(
            split_summary_sha256,
            label="Phase-4 split summary",
        ),
        "discovery_entry_handoff_sha256": _sha256(
            discovery_entry_handoff_sha256,
            label="Phase-4 split discovery-entry handoff",
        ),
        "discovery_subjects": int(row["discovery_subjects"]),
        "discovery_end_block": int(row["discovery_end_block"]),
        "validation_end_block": int(row["validation_end_block"]),
        "discovery_split_rows_sha256": _sha256(
            ranges["discovery"]["rows_sha256"],
            label="Phase-4 discovery split rows",
        ),
        "validation_split_rows_sha256": _sha256(
            ranges["validation"]["rows_sha256"],
            label="Phase-4 validation split rows",
        ),
        "final_test_split_rows_sha256": _sha256(
            ranges["final_test"]["rows_sha256"],
            label="Phase-4 final-test split rows",
        ),
        "discovery_split_rows": int(ranges["discovery"]["rows"]),
        "validation_split_rows": int(ranges["validation"]["rows"]),
        "final_test_split_rows": int(ranges["final_test"]["rows"]),
        "split_assignment_key": "feature_cutoff_block",
        "split_assignment_uses_feature_values": False,
        "split_assignment_uses_outcome_values": False,
        "random_shuffle_used": False,
        "chronological_order_enforced": True,
        "feature_values_mutated": False,
        "final_test_separated": True,
        "phase4_chronological_split_ready": True,
        "phase4_split_frozen": True,
        "phase4_discovery_checkpoint_claimed": False,
    }
