"""Artifact identity helpers for accepted Pons research replay."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Callable, Iterable, Mapping

from hlp.data.github_actions import select_equivalent_artifact_retry


PHASE2_PONS_RESEARCH_ARTIFACTS_VERSION = (
    "phase2-pons-research-artifacts-v1"
)


def discover_artifact_by_manifest(
    artifact_rows: Iterable[Mapping[str, object]],
    artifact_zip: Callable[[Mapping[str, object]], bytes],
    *,
    manifest_filename: str,
    expected_sha256: str,
    expected_records: int,
    label: str,
) -> dict:
    """Find one immutable artifact by exact embedded JSONL-manifest identity."""

    expected_sha = str(expected_sha256).lower()
    if len(expected_sha) != 64:
        raise ValueError(f"{label} expected manifest SHA-256 is invalid")
    try:
        int(expected_sha, 16)
    except ValueError as exc:
        raise ValueError(
            f"{label} expected manifest SHA-256 is invalid"
        ) from exc

    matches = []
    for raw in artifact_rows:
        row = dict(raw)
        if row.get("expired"):
            continue
        blob = artifact_zip(row)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            members = [
                member
                for member in archive.infolist()
                if not member.is_dir()
                and Path(member.filename).name == manifest_filename
            ]
            if len(members) != 1:
                continue
            manifest = json.loads(archive.read(members[0]))
        if (
            str(manifest.get("sha256") or "").lower() == expected_sha
            and int(manifest.get("records", -1)) == int(expected_records)
        ):
            matches.append(row)

    if not matches:
        raise ValueError(
            f"{label} artifact was not found by exact manifest identity"
        )
    return dict(
        select_equivalent_artifact_retry(matches, label=label)
    )


def materialize_bound_shards(
    bindings: Iterable[Mapping[str, object]],
    *,
    artifacts_for_run: Callable[[int], Iterable[Mapping[str, object]]],
    artifact_zip: Callable[[Mapping[str, object]], bytes],
    destination: Path,
    label: str,
) -> dict:
    """Materialize exact manifest-bound shards with retry equivalence checks."""

    rows = [dict(row) for row in bindings]
    if not rows:
        raise ValueError(f"{label} has no shard bindings")

    materialized = []
    by_run: dict[str, int] = {}
    seen_files: set[tuple[int, str]] = set()
    for binding in rows:
        run_id = int(binding.get("run_id", 0))
        artifact_name = str(binding.get("artifact_name") or "")
        filename = str(binding.get("file") or "")
        expected_sha = str(binding.get("sha256") or "").lower()
        expected_records = int(binding.get("records", -1))
        lo = int(binding.get("from_block", -1))
        hi = int(binding.get("to_block", -1))
        if (
            run_id <= 0
            or not artifact_name
            or not filename
            or len(expected_sha) != 64
            or expected_records < 0
            or lo < 0
            or hi < lo
        ):
            raise ValueError(f"{label} shard binding is invalid: {binding}")
        try:
            int(expected_sha, 16)
        except ValueError as exc:
            raise ValueError(
                f"{label} shard SHA-256 is invalid: {filename}"
            ) from exc
        identity = (run_id, filename)
        if identity in seen_files:
            raise ValueError(
                f"{label} repeats bound shard identity: {identity}"
            )
        seen_files.add(identity)

        matches = [
            dict(row)
            for row in artifacts_for_run(run_id)
            if not row.get("expired")
            and str(row.get("name") or "") == artifact_name
        ]
        artifact = select_equivalent_artifact_retry(
            matches,
            label=(
                f"{label} run={run_id} artifact={artifact_name}"
            ),
        )
        blob = artifact_zip(artifact)
        sidecar_name = filename + ".manifest.json"
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            data_members = [
                member
                for member in archive.infolist()
                if not member.is_dir()
                and Path(member.filename).name == filename
            ]
            manifest_members = [
                member
                for member in archive.infolist()
                if not member.is_dir()
                and Path(member.filename).name == sidecar_name
            ]
            if len(data_members) != 1 or len(manifest_members) != 1:
                raise ValueError(
                    f"{label} shard ZIP identity is ambiguous: {filename}"
                )
            data = archive.read(data_members[0])
            manifest_bytes = archive.read(manifest_members[0])

        manifest = json.loads(manifest_bytes)
        provenance = manifest.get("provenance") or {}
        if str(manifest.get("path") or "") != filename:
            raise ValueError(
                f"{label} shard manifest path changed: {filename}"
            )
        if str(manifest.get("sha256") or "").lower() != expected_sha:
            raise ValueError(
                f"{label} shard manifest SHA changed: {filename}"
            )
        if int(manifest.get("records", -1)) != expected_records:
            raise ValueError(
                f"{label} shard manifest records changed: {filename}"
            )
        if (
            int(provenance.get("from_block", -1)),
            int(provenance.get("to_block", -1)),
        ) != (lo, hi):
            raise ValueError(
                f"{label} shard manifest range changed: {filename}"
            )
        if hashlib.sha256(data).hexdigest() != expected_sha:
            raise ValueError(
                f"{label} shard data SHA changed: {filename}"
            )
        records = sum(
            1 for line in data.splitlines() if line.strip()
        )
        if records != expected_records:
            raise ValueError(
                f"{label} shard data records changed: {filename}"
            )

        target = destination / str(run_id)
        target.mkdir(parents=True, exist_ok=True)
        (target / filename).write_bytes(data)
        (target / sidecar_name).write_bytes(manifest_bytes)
        materialized.append({
            "run_id": run_id,
            "artifact_name": artifact_name,
            "artifact_digest": str(
                artifact.get("digest") or ""
            ).lower(),
            "file": filename,
            "records": expected_records,
            "sha256": expected_sha,
            "from_block": lo,
            "to_block": hi,
        })
        key = str(run_id)
        by_run[key] = by_run.get(key, 0) + 1

    return {
        "version": PHASE2_PONS_RESEARCH_ARTIFACTS_VERSION,
        "selected_shards": len(rows),
        "materialized_shards": len(materialized),
        "materialized_shards_by_run": dict(sorted(by_run.items())),
        "shards": materialized,
    }
