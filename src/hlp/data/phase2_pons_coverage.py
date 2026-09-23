"""Validate accepted Phase-1 Pons lifecycle coverage for Phase 2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping


PONS_SOURCE_COVERAGE_VERSION = "phase2-pons-source-coverage-v1"


def validate_pons_source_coverage_descriptor(
    descriptor: Mapping[str, object],
) -> dict:
    version = str(descriptor.get("version") or "")
    if version != PONS_SOURCE_COVERAGE_VERSION:
        raise ValueError(
            f"Pons source coverage version changed: {version!r}"
        )
    snapshot = int(descriptor.get("snapshot_head_block", 0))
    if snapshot <= 0:
        raise ValueError("Pons source coverage snapshot must be positive")

    raw_sources = descriptor.get("sources")
    if not isinstance(raw_sources, list) or len(raw_sources) != 2:
        raise ValueError("Pons source coverage must contain V1 and V2")

    output = []
    seen: set[str] = set()
    for raw in raw_sources:
        if not isinstance(raw, Mapping):
            raise ValueError("Pons source coverage contains non-object row")
        source_id = str(raw.get("source_id") or "")
        if source_id not in {"pons_v1", "pons_v2"}:
            raise ValueError(
                f"unexpected Pons source coverage id: {source_id!r}"
            )
        if source_id in seen:
            raise ValueError(
                f"duplicate Pons source coverage id: {source_id}"
            )
        seen.add(source_id)

        item = dict(raw)
        positive = (
            "artifact_id",
            "artifact_run_id",
            "records",
            "eligible_tokens",
            "required_start_block",
            "price_points",
        )
        for field in positive:
            value = int(item.get(field, 0))
            if value <= 0:
                raise ValueError(
                    f"{source_id} {field} must be positive"
                )
            item[field] = value

        if item["required_start_block"] >= snapshot:
            raise ValueError(
                f"{source_id} required start is not before snapshot"
            )
        if item["eligible_tokens"] > item["records"]:
            raise ValueError(
                f"{source_id} eligible count exceeds records"
            )

        for field in (
            "artifact_name",
            "lifecycle_filename",
            "manifest_filename",
        ):
            if not str(item.get(field) or ""):
                raise ValueError(f"{source_id} {field} is empty")

        sha = str(item.get("lifecycle_sha256") or "").lower()
        if len(sha) != 64:
            raise ValueError(
                f"{source_id} lifecycle_sha256 is invalid"
            )
        try:
            int(sha, 16)
        except ValueError as exc:
            raise ValueError(
                f"{source_id} lifecycle_sha256 is invalid"
            ) from exc
        item["lifecycle_sha256"] = sha

        digest = str(item.get("artifact_digest") or "").lower()
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ValueError(
                f"{source_id} artifact_digest is invalid"
            )
        try:
            int(digest.split(":", 1)[1], 16)
        except ValueError as exc:
            raise ValueError(
                f"{source_id} artifact_digest is invalid"
            ) from exc
        item["artifact_digest"] = digest
        output.append(item)

    if seen != {"pons_v1", "pons_v2"}:
        raise ValueError("Pons source coverage source set changed")

    return {
        "version": version,
        "snapshot_head_block": snapshot,
        "sources": sorted(output, key=lambda row: row["source_id"]),
    }


def validate_pons_lifecycle_artifact(
    *,
    source: Mapping[str, object],
    snapshot_head_block: int,
    directory: str | Path,
) -> dict:
    source_id = str(source["source_id"])
    root = Path(directory)
    lifecycle_path = root / str(source["lifecycle_filename"])
    manifest_path = root / str(source["manifest_filename"])

    lifecycle_bytes = lifecycle_path.read_bytes()
    digest = hashlib.sha256(lifecycle_bytes).hexdigest()
    expected_sha = str(source["lifecycle_sha256"])
    if digest != expected_sha:
        raise ValueError(
            f"{source_id} lifecycle SHA changed: "
            f"{digest} != {expected_sha}"
        )

    manifest = json.loads(manifest_path.read_text())
    if int(manifest.get("schema_version", -1)) != 1:
        raise ValueError(f"{source_id} lifecycle schema changed")
    if int(manifest.get("records", -1)) != int(source["records"]):
        raise ValueError(f"{source_id} lifecycle record count changed")
    if str(manifest.get("sha256") or "").lower() != digest:
        raise ValueError(
            f"{source_id} manifest SHA disagrees with lifecycle bytes"
        )

    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"{source_id} lifecycle provenance missing")
    if int(provenance.get("chain_id", -1)) != 4663:
        raise ValueError(f"{source_id} chain changed")
    if int(provenance.get("snapshot_head_block", -1)) != int(
        snapshot_head_block
    ):
        raise ValueError(f"{source_id} snapshot changed")
    if str(provenance.get("eligibility_threshold_usd") or "") != "100000":
        raise ValueError(f"{source_id} eligibility threshold changed")

    records = 0
    eligible = 0
    unknown = 0
    incomplete = 0
    total_points = 0
    priced_points = 0
    unpriced_points = 0
    min_launch: int | None = None
    max_launch: int | None = None
    max_last_priced: int | None = None
    seen_tokens: set[str] = set()

    for line_number, raw_line in enumerate(
        lifecycle_bytes.decode("utf-8").splitlines(),
        start=1,
    ):
        if not raw_line:
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{source_id} invalid lifecycle JSONL line {line_number}"
            ) from exc

        token = str(row.get("token") or "").lower()
        if not token:
            raise ValueError(
                f"{source_id} lifecycle row lacks token at line {line_number}"
            )
        if token in seen_tokens:
            raise ValueError(
                f"{source_id} lifecycle repeats token: {token}"
            )
        seen_tokens.add(token)
        records += 1

        status = str(row.get("eligibility_status") or "")
        if status == "eligible":
            eligible += 1
        elif status == "unknown":
            unknown += 1
        elif status != "ineligible":
            raise ValueError(
                f"{source_id} invalid eligibility status: {status!r}"
            )

        if row.get("pricing_complete") is not True:
            incomplete += 1

        points = int(row.get("price_points", -1))
        priced = int(row.get("priced_points", -1))
        unpriced = int(row.get("unpriced_points", -1))
        if points < 0 or priced < 0 or unpriced < 0:
            raise ValueError(
                f"{source_id} negative price-point accounting: {token}"
            )
        if priced + unpriced != points:
            raise ValueError(
                f"{source_id} price-point accounting mismatch: {token}"
            )
        total_points += points
        priced_points += priced
        unpriced_points += unpriced

        launch = int(row["launch_block"])
        if launch <= 0 or launch > int(snapshot_head_block):
            raise ValueError(
                f"{source_id} invalid launch block: {token}"
            )
        min_launch = launch if min_launch is None else min(min_launch, launch)
        max_launch = launch if max_launch is None else max(max_launch, launch)

        last_priced = row.get("last_priced_block")
        if last_priced is not None:
            value = int(last_priced)
            if value < launch or value > int(snapshot_head_block):
                raise ValueError(
                    f"{source_id} invalid last priced block: {token}"
                )
            max_last_priced = (
                value
                if max_last_priced is None
                else max(max_last_priced, value)
            )

    if records != int(source["records"]):
        raise ValueError(
            f"{source_id} records changed: {records} != {source['records']}"
        )
    if eligible != int(source["eligible_tokens"]):
        raise ValueError(
            f"{source_id} eligible count changed: "
            f"{eligible} != {source['eligible_tokens']}"
        )
    if min_launch != int(source["required_start_block"]):
        raise ValueError(
            f"{source_id} first launch changed: "
            f"{min_launch} != {source['required_start_block']}"
        )
    if total_points != int(source["price_points"]):
        raise ValueError(
            f"{source_id} price-point count changed: "
            f"{total_points} != {source['price_points']}"
        )
    if unknown or incomplete or unpriced_points:
        raise ValueError(
            f"{source_id} lifecycle is not fully priced: "
            f"unknown={unknown} incomplete={incomplete} "
            f"unpriced_points={unpriced_points}"
        )
    if priced_points != total_points:
        raise ValueError(
            f"{source_id} priced points do not equal total points"
        )

    return {
        "source_id": source_id,
        "records": records,
        "eligible_tokens": eligible,
        "unknown_tokens": unknown,
        "required_start_block": min_launch,
        "max_launch_block": max_launch,
        "max_last_priced_block": max_last_priced,
        "price_points": total_points,
        "priced_points": priced_points,
        "unpriced_points": unpriced_points,
        "pricing_incomplete_tokens": incomplete,
        "provenance_sha256": digest,
        "coverage_status": "complete",
        "continuous": True,
        "missing_ranges": [],
        "snapshot_head_block": int(snapshot_head_block),
    }


def validate_pons_source_coverage_bundle(
    descriptor: Mapping[str, object],
    *,
    v1_directory: str | Path,
    v2_directory: str | Path,
) -> dict:
    expected = validate_pons_source_coverage_descriptor(descriptor)
    directories = {
        "pons_v1": v1_directory,
        "pons_v2": v2_directory,
    }
    reports = []
    for source in expected["sources"]:
        reports.append(
            validate_pons_lifecycle_artifact(
                source=source,
                snapshot_head_block=expected["snapshot_head_block"],
                directory=directories[str(source["source_id"])],
            )
        )
    return {
        "version": expected["version"],
        "snapshot_head_block": expected["snapshot_head_block"],
        "sources": reports,
        "total_launches": sum(row["records"] for row in reports),
        "total_eligible_tokens": sum(
            row["eligible_tokens"] for row in reports
        ),
        "total_price_points": sum(
            row["price_points"] for row in reports
        ),
        "all_pons_source_coverage_complete": True,
    }
