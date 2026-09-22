"""Causal Phase-3 deployment and mint lifecycle-age features."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address
from hlp.data.phase3_feature_entry import (
    PHASE3_FEATURE_ENTRY_HANDOFF_VERSION,
    PHASE3_FEATURE_SNAPSHOT_KIND,
    PHASE3_FEATURE_SUBJECT_FIELDS,
    PHASE3_FEATURE_SUBJECT_VERSION,
)
from hlp.data.phase3_feature_registry import validate_phase3_feature_registry
from hlp.data.phase3_holder_features import (
    PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION,
)
from hlp.data.phase3_transfer_tape import (
    PHASE3_TRANSFER_TOKEN_COVERAGE_VERSION,
)
from hlp.data.snapshot import write_jsonl_snapshot


PHASE3_LIFECYCLE_FEATURE_VERSION = "phase3-lifecycle-age-features-v1"
PHASE3_LIFECYCLE_FEATURE_HANDOFF_VERSION = (
    "phase3-lifecycle-age-features-handoff-v1"
)

LIFECYCLE_FEATURE_IDS = (
    "lifecycle.blocks_deployment_to_cutoff",
    "lifecycle.blocks_initial_mint_to_cutoff",
    "lifecycle.blocks_deployment_to_initial_mint",
    "lifecycle.initial_mint_in_deployment_block",
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


def _subject_cutoff(row: Mapping[str, object]) -> tuple[int, int, int]:
    block = int(row.get("feature_cutoff_block", -1))
    raw_tx = row.get("feature_cutoff_transaction_index")
    tx = -1 if raw_tx is None else int(raw_tx)
    log = int(row.get("feature_cutoff_log_index", -1))
    if block < 0 or tx < -1 or log < 0:
        raise ValueError("Phase-3 lifecycle cutoff is invalid")
    return block, tx, log


def _coverage_sha(rows: Iterable[Mapping[str, object]]) -> tuple[int, str]:
    count = 0
    digest = hashlib.sha256()
    for raw in rows:
        line = (
            json.dumps(
                dict(raw),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode()
        digest.update(line)
        count += 1
    return count, digest.hexdigest()


def materialize_phase3_lifecycle_features(
    subject_rows: Iterable[Mapping[str, object]],
    token_coverage_rows: Iterable[Mapping[str, object]],
    *,
    entry_handoff: Mapping[str, object],
    transfer_handoff: Mapping[str, object],
    feature_registry: Iterable[Mapping[str, object]],
    output: Path,
) -> tuple[dict, dict]:
    """Compute lifecycle age only from verified deployment/mint boundaries."""

    entry = dict(entry_handoff)
    transfer = dict(transfer_handoff)
    registry_rows = [dict(row) for row in feature_registry]
    registry = validate_phase3_feature_registry(registry_rows)

    if (
        str(entry.get("version") or "")
        != PHASE3_FEATURE_ENTRY_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 lifecycle entry version changed")
    if entry.get("phase3_feature_entry_ready") is not True:
        raise ValueError("Phase-3 lifecycle entry is not ready")
    if entry.get("outcome_rows_consumed") is not False:
        raise ValueError("Phase-3 lifecycle entry consumed outcomes")
    if entry.get("outcome_fields_exposed") is not False:
        raise ValueError("Phase-3 lifecycle entry exposes outcomes")
    if entry.get("future_state_allowed") is not False:
        raise ValueError("Phase-3 lifecycle entry allows future state")

    if (
        str(transfer.get("version") or "")
        != PHASE3_CANONICAL_TRANSFER_HANDOFF_VERSION
    ):
        raise ValueError("Phase-3 lifecycle transfer handoff changed")
    for flag in (
        "historical_event_scan_complete",
        "initial_mint_coverage_complete",
        "transfer_coverage_complete",
        "phase3_canonical_transfer_tape_ready",
    ):
        if transfer.get(flag) is not True:
            raise ValueError(
                f"Phase-3 lifecycle transfer handoff lacks {flag}"
            )
    if transfer.get("outcome_rows_consumed") is not False:
        raise ValueError(
            "Phase-3 lifecycle transfer handoff consumed outcomes"
        )
    if transfer.get("future_state_allowed") is not False:
        raise ValueError(
            "Phase-3 lifecycle transfer handoff allows future state"
        )

    snapshot = int(entry.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("Phase-3 lifecycle snapshot is invalid")
    if int(transfer.get("snapshot_head_block", -2)) != snapshot:
        raise ValueError("Phase-3 lifecycle entry/transfer snapshot drift")
    if _sha256(
        transfer.get("eligible_universe_sha256"),
        label="Phase-3 lifecycle transfer universe",
    ) != _sha256(
        entry.get("eligible_universe_sha256"),
        label="Phase-3 lifecycle entry universe",
    ):
        raise ValueError("Phase-3 lifecycle universe drift")

    family_ids = {
        str(row["feature_id"])
        for row in registry_rows
        if str(row.get("family") or "") == "lifecycle_age"
    }
    if family_ids != set(LIFECYCLE_FEATURE_IDS):
        raise ValueError("Phase-3 lifecycle feature registry changed")

    coverage_rows = []
    coverage = {}
    for raw in token_coverage_rows:
        row = dict(raw)
        if (
            str(row.get("version") or "")
            != PHASE3_TRANSFER_TOKEN_COVERAGE_VERSION
        ):
            raise ValueError(
                "Phase-3 lifecycle token-coverage version changed"
            )
        token = normalize_address(str(row.get("token") or ""))
        if token in coverage:
            raise ValueError(
                f"Phase-3 lifecycle token coverage repeats: {token}"
            )
        if int(row.get("snapshot_head_block", -1)) != snapshot:
            raise ValueError(
                f"Phase-3 lifecycle token snapshot drift: {token}"
            )
        first_code = int(row.get("first_code_block", -1))
        mint_block = int(row.get("initial_mint_block", -1))
        raw_mint_tx = row.get("initial_mint_transaction_index")
        mint_tx = -1 if raw_mint_tx is None else int(raw_mint_tx)
        mint_log = int(row.get("initial_mint_log_index", -1))
        if (
            first_code < 0
            or mint_block < first_code
            or mint_block > snapshot
            or mint_tx < -1
            or mint_log < 0
        ):
            raise ValueError(
                f"Phase-3 lifecycle token boundary invalid: {token}"
            )
        for flag in (
            "deployment_boundary_verified",
            "historical_event_scan_complete",
            "initial_mint_coverage_complete",
            "transfer_coverage_complete",
        ):
            if row.get(flag) is not True:
                raise ValueError(
                    f"Phase-3 lifecycle token lacks {flag}: {token}"
                )
        if row.get("outcome_rows_consumed") is not False:
            raise ValueError(
                f"Phase-3 lifecycle token consumed outcomes: {token}"
            )
        if row.get("future_state_allowed") is not False:
            raise ValueError(
                f"Phase-3 lifecycle token allows future state: {token}"
            )
        coverage[token] = {
            "first_code_block": first_code,
            "mint_block": mint_block,
            "mint_event": (mint_block, mint_tx, mint_log),
        }
        coverage_rows.append(row)

    coverage_rows.sort(key=lambda row: normalize_address(str(row["token"])))
    coverage_count, coverage_sha = _coverage_sha(coverage_rows)
    if coverage_count != int(transfer.get("universe_tokens", -1)):
        raise ValueError("Phase-3 lifecycle token coverage count drift")
    if coverage_sha != _sha256(
        transfer.get("token_coverage_sha256"),
        label="Phase-3 lifecycle token coverage",
    ):
        raise ValueError("Phase-3 lifecycle token coverage SHA drift")

    subjects = {}
    for raw in subject_rows:
        row = dict(raw)
        if set(row) != PHASE3_FEATURE_SUBJECT_FIELDS:
            raise ValueError("Phase-3 lifecycle subject fields changed")
        if (
            str(row.get("version") or "")
            != PHASE3_FEATURE_SUBJECT_VERSION
        ):
            raise ValueError("Phase-3 lifecycle subject version changed")
        if row.get("snapshot_kind") != PHASE3_FEATURE_SNAPSHOT_KIND:
            raise ValueError("Phase-3 lifecycle snapshot kind changed")
        if row.get("feature_cutoff_inclusive") is not True:
            raise ValueError("Phase-3 lifecycle cutoff is not inclusive")
        token = normalize_address(str(row.get("token") or ""))
        if token in subjects:
            raise ValueError(
                f"Phase-3 lifecycle repeats subject: {token}"
            )
        cutoff = _subject_cutoff(row)
        if cutoff[0] > snapshot:
            raise ValueError(
                f"Phase-3 lifecycle cutoff after snapshot: {token}"
            )
        evidence = coverage.get(token)
        if evidence is None:
            raise ValueError(
                f"Phase-3 lifecycle lacks token coverage: {token}"
            )
        if evidence["mint_event"] > cutoff:
            raise ValueError(
                f"Phase-3 lifecycle initial mint is after cutoff: {token}"
            )
        if evidence["first_code_block"] > cutoff[0]:
            raise ValueError(
                f"Phase-3 lifecycle deployment is after cutoff: {token}"
            )
        subjects[token] = (row, cutoff, evidence)

    if len(subjects) != int(entry.get("feature_subjects", -1)):
        raise ValueError("Phase-3 lifecycle subject count drift")

    output_rows = []
    for token in sorted(subjects):
        row, cutoff, evidence = subjects[token]
        first_code = int(evidence["first_code_block"])
        mint_block = int(evidence["mint_block"])
        values = {
            "lifecycle.blocks_deployment_to_cutoff": (
                cutoff[0] - first_code
            ),
            "lifecycle.blocks_initial_mint_to_cutoff": (
                cutoff[0] - mint_block
            ),
            "lifecycle.blocks_deployment_to_initial_mint": (
                mint_block - first_code
            ),
            "lifecycle.initial_mint_in_deployment_block": (
                mint_block == first_code
            ),
        }
        output_rows.append({
            "version": PHASE3_LIFECYCLE_FEATURE_VERSION,
            "token": token,
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
                "deployment_boundary_verified": True,
                "initial_mint_boundary_verified": True,
                "complete_transfer_history_verified": True,
                "future_state_used": False,
            },
        })

    manifest = write_jsonl_snapshot(
        output_rows,
        output=output,
        provenance={
            "version": PHASE3_LIFECYCLE_FEATURE_VERSION,
            "feature_family": "lifecycle_age",
            "feature_registry_sha256": registry["registry_sha256"],
            "token_coverage_sha256": coverage_sha,
            "outcome_rows_consumed": False,
            "future_state_allowed": False,
        },
    )
    summary = {
        "version": PHASE3_LIFECYCLE_FEATURE_VERSION,
        "snapshot_head_block": snapshot,
        "feature_family": "lifecycle_age",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": registry["registry_sha256"],
        "feature_ids": list(LIFECYCLE_FEATURE_IDS),
        "features_per_subject": len(LIFECYCLE_FEATURE_IDS),
        "feature_subjects": len(output_rows),
        "feature_rows": int(manifest["records"]),
        "feature_rows_sha256": manifest["sha256"],
        "token_coverage_sha256": coverage_sha,
        "eligible_universe_sha256": str(
            entry["eligible_universe_sha256"]
        ),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_lifecycle_features_ready": True,
    }
    return manifest, summary


def build_phase3_lifecycle_feature_handoff(
    feature_summary: Mapping[str, object],
    *,
    feature_summary_sha256: str,
    feature_entry_handoff_sha256: str,
    canonical_transfer_handoff_sha256: str,
) -> dict:
    summary = dict(feature_summary)
    if (
        str(summary.get("version") or "")
        != PHASE3_LIFECYCLE_FEATURE_VERSION
    ):
        raise ValueError("Phase-3 lifecycle handoff version changed")
    if summary.get("feature_family") != "lifecycle_age":
        raise ValueError("Phase-3 lifecycle feature family changed")
    for flag in (
        "missingness_recorded",
        "data_quality_recorded",
        "phase3_lifecycle_features_ready",
    ):
        if summary.get(flag) is not True:
            raise ValueError(f"Phase-3 lifecycle handoff lacks {flag}")
    for flag in (
        "outcome_rows_consumed",
        "outcome_fields_exposed",
        "future_state_allowed",
    ):
        if summary.get(flag) is not False:
            raise ValueError(
                f"Phase-3 lifecycle handoff violates {flag}"
            )
    return {
        "version": PHASE3_LIFECYCLE_FEATURE_HANDOFF_VERSION,
        "snapshot_head_block": int(summary["snapshot_head_block"]),
        "feature_family": "lifecycle_age",
        "snapshot_kind": PHASE3_FEATURE_SNAPSHOT_KIND,
        "feature_registry_sha256": _sha256(
            summary.get("feature_registry_sha256"),
            label="Phase-3 lifecycle registry",
        ),
        "feature_rows_sha256": _sha256(
            summary.get("feature_rows_sha256"),
            label="Phase-3 lifecycle rows",
        ),
        "feature_summary_sha256": _sha256(
            feature_summary_sha256,
            label="Phase-3 lifecycle summary",
        ),
        "feature_entry_handoff_sha256": _sha256(
            feature_entry_handoff_sha256,
            label="Phase-3 lifecycle entry",
        ),
        "canonical_transfer_handoff_sha256": _sha256(
            canonical_transfer_handoff_sha256,
            label="Phase-3 lifecycle transfer handoff",
        ),
        "token_coverage_sha256": _sha256(
            summary.get("token_coverage_sha256"),
            label="Phase-3 lifecycle token coverage",
        ),
        "eligible_universe_sha256": _sha256(
            summary.get("eligible_universe_sha256"),
            label="Phase-3 lifecycle universe",
        ),
        "feature_subjects": int(summary["feature_subjects"]),
        "features_per_subject": int(summary["features_per_subject"]),
        "outcome_rows_consumed": False,
        "outcome_fields_exposed": False,
        "future_state_allowed": False,
        "missingness_recorded": True,
        "data_quality_recorded": True,
        "phase3_lifecycle_features_ready": True,
    }
