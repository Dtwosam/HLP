"""Canonical Phase-1 -> Phase-2 Pons eligible-universe handoff."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

from hlp.config import normalize_address


PONS_HANDOFF_VERSION = "phase2-pons-eligible-handoff-v1"
PONS_ELIGIBILITY_THRESHOLD_USD = Decimal("100000")


def validate_pons_handoff_descriptor(
    descriptor: Mapping[str, object],
) -> dict:
    """Validate the immutable accepted-artifact reference."""
    version = str(descriptor.get("version") or "")
    if version != PONS_HANDOFF_VERSION:
        raise ValueError(f"Pons handoff version changed: {version!r}")

    required_positive = (
        "evidence_run_id",
        "artifact_id",
        "accepted_finalizer_run_id",
        "snapshot_head_block",
        "eligible_tokens",
        "eligible_v1",
        "eligible_v2",
        "all_pons_launches",
    )
    normalized = dict(descriptor)
    for field in required_positive:
        value = int(descriptor.get(field, 0))
        if value <= 0:
            raise ValueError(f"Pons handoff {field} must be positive")
        normalized[field] = value

    if normalized["eligible_v1"] + normalized["eligible_v2"] != normalized[
        "eligible_tokens"
    ]:
        raise ValueError("Pons handoff version counts do not sum to total")

    for field in ("artifact_name", "universe_filename", "manifest_filename", "summary_filename"):
        if not str(descriptor.get(field) or ""):
            raise ValueError(f"Pons handoff {field} is empty")

    universe_sha = str(descriptor.get("universe_sha256") or "").lower()
    if len(universe_sha) != 64:
        raise ValueError("Pons handoff universe_sha256 is invalid")
    try:
        int(universe_sha, 16)
    except ValueError as exc:
        raise ValueError("Pons handoff universe_sha256 is invalid") from exc
    normalized["universe_sha256"] = universe_sha

    artifact_digest = str(descriptor.get("artifact_digest") or "").lower()
    if not artifact_digest.startswith("sha256:") or len(artifact_digest) != 71:
        raise ValueError("Pons handoff artifact_digest is invalid")
    try:
        int(artifact_digest.split(":", 1)[1], 16)
    except ValueError as exc:
        raise ValueError("Pons handoff artifact_digest is invalid") from exc
    normalized["artifact_digest"] = artifact_digest

    if int(descriptor.get("unknown_tokens", -1)) != 0:
        raise ValueError("Pons handoff must have zero unknown tokens")
    normalized["unknown_tokens"] = 0
    return normalized


def validate_pons_eligible_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    expected_records: int,
    expected_v1: int,
    expected_v2: int,
) -> dict:
    """Validate every accepted eligible row without weakening Phase-1 semantics."""
    seen: set[str] = set()
    versions = {"v1": 0, "v2": 0}
    records = 0
    total_price_points = 0

    for raw in rows:
        token = normalize_address(str(raw["token"]))
        if token in seen:
            raise ValueError(f"duplicate Pons eligible token: {token}")
        seen.add(token)
        records += 1

        version = str(raw.get("version") or "")
        if version not in versions:
            raise ValueError(
                f"unsupported Pons eligible version for {token}: {version!r}"
            )
        versions[version] += 1

        if raw.get("crossed_100k") is not True:
            raise ValueError(f"Pons eligible token lacks threshold proof: {token}")
        if str(raw.get("eligibility_status") or "") != "eligible":
            raise ValueError(f"Pons eligible status changed: {token}")
        if raw.get("pricing_complete") is not True:
            raise ValueError(f"Pons eligible pricing is incomplete: {token}")

        points = int(raw.get("price_points", -1))
        priced = int(raw.get("priced_points", -1))
        unpriced = int(raw.get("unpriced_points", -1))
        if points <= 0 or priced != points or unpriced != 0:
            raise ValueError(
                f"Pons eligible price-point completeness changed: {token}"
            )
        total_price_points += points

        maximum = Decimal(str(raw["max_market_cap_proxy_usd"]))
        if maximum < PONS_ELIGIBILITY_THRESHOLD_USD:
            raise ValueError(
                f"Pons eligible maximum fell below threshold: {token}"
            )
        max_block = int(raw["max_market_cap_block"])
        launch_block = int(raw["launch_block"])
        if launch_block <= 0 or max_block < launch_block:
            raise ValueError(
                f"Pons eligible max block precedes launch: {token}"
            )

    if records != int(expected_records):
        raise ValueError(
            f"Pons eligible record count changed: {records} != {expected_records}"
        )
    if versions["v1"] != int(expected_v1):
        raise ValueError(
            f"Pons V1 eligible count changed: {versions['v1']} != {expected_v1}"
        )
    if versions["v2"] != int(expected_v2):
        raise ValueError(
            f"Pons V2 eligible count changed: {versions['v2']} != {expected_v2}"
        )

    return {
        "records": records,
        "eligible_v1": versions["v1"],
        "eligible_v2": versions["v2"],
        "unique_tokens": len(seen),
        "total_price_points": total_price_points,
        "all_rows_complete": True,
    }


def validate_pons_handoff_artifact(
    *,
    descriptor: Mapping[str, object],
    manifest: Mapping[str, object],
    summary: Mapping[str, object],
    universe_bytes: bytes,
) -> dict:
    """Validate artifact metadata, raw JSONL bytes and all accepted rows."""
    expected = validate_pons_handoff_descriptor(descriptor)

    digest = hashlib.sha256(universe_bytes).hexdigest()
    if digest != expected["universe_sha256"]:
        raise ValueError(
            f"Pons universe SHA changed: {digest} != {expected['universe_sha256']}"
        )
    if str(manifest.get("sha256") or "").lower() != digest:
        raise ValueError("Pons manifest SHA disagrees with universe bytes")
    if int(manifest.get("records", -1)) != expected["eligible_tokens"]:
        raise ValueError("Pons manifest record count changed")
    if int(manifest.get("schema_version", -1)) != 1:
        raise ValueError("Pons eligible schema version changed")

    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("Pons manifest has no provenance")
    if int(provenance.get("chain_id", -1)) != 4663:
        raise ValueError("Pons handoff chain changed")
    if int(provenance.get("snapshot_head_block", -1)) != expected[
        "snapshot_head_block"
    ]:
        raise ValueError("Pons handoff snapshot changed")
    if str(provenance.get("eligibility_threshold_usd") or "") != "100000":
        raise ValueError("Pons eligibility threshold changed")
    if str(provenance.get("source") or "") != (
        "complete_v1_plus_v2_lifecycle_eligibility"
    ):
        raise ValueError("Pons handoff provenance source changed")

    if int(summary.get("eligible_tokens", -1)) != expected["eligible_tokens"]:
        raise ValueError("Pons summary eligible count changed")
    if int(summary.get("eligible_v1", -1)) != expected["eligible_v1"]:
        raise ValueError("Pons summary V1 count changed")
    if int(summary.get("eligible_v2", -1)) != expected["eligible_v2"]:
        raise ValueError("Pons summary V2 count changed")
    if int(summary.get("unknown_tokens", -1)) != 0:
        raise ValueError("Pons summary unknown population changed")
    if int(summary.get("snapshot_head_block", -1)) != expected[
        "snapshot_head_block"
    ]:
        raise ValueError("Pons summary snapshot changed")
    if str(summary.get("universe_sha256") or "").lower() != digest:
        raise ValueError("Pons summary SHA disagrees with universe bytes")

    rows = []
    for line_number, raw_line in enumerate(
        universe_bytes.decode("utf-8").splitlines(),
        start=1,
    ):
        if not raw_line:
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid Pons universe JSONL at line {line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(
                f"Pons universe row is not an object at line {line_number}"
            )
        rows.append(row)

    row_report = validate_pons_eligible_rows(
        rows,
        expected_records=expected["eligible_tokens"],
        expected_v1=expected["eligible_v1"],
        expected_v2=expected["eligible_v2"],
    )
    return {
        "version": expected["version"],
        "evidence_run_id": expected["evidence_run_id"],
        "artifact_id": expected["artifact_id"],
        "snapshot_head_block": expected["snapshot_head_block"],
        "universe_sha256": digest,
        **row_report,
        "phase2_primary_population_handoff_valid": True,
    }


def validate_pons_handoff_directory(
    directory: str | Path,
    descriptor: Mapping[str, object],
) -> dict:
    """Load a downloaded GitHub artifact directory and validate it."""
    expected = validate_pons_handoff_descriptor(descriptor)
    root = Path(directory)
    manifest = json.loads(
        (root / str(expected["manifest_filename"])).read_text()
    )
    summary = json.loads(
        (root / str(expected["summary_filename"])).read_text()
    )
    universe_bytes = (
        root / str(expected["universe_filename"])
    ).read_bytes()
    return validate_pons_handoff_artifact(
        descriptor=expected,
        manifest=manifest,
        summary=summary,
        universe_bytes=universe_bytes,
    )
