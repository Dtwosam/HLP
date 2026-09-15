"""Helpers for canonical JSONL tapes stored as ordered shard artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def canonical_jsonl_bytes(row: dict) -> bytes:
    """Return the canonical JSONL encoding used by snapshot writers."""
    return (
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def write_virtual_jsonl_manifest(
    *,
    manifest_path: Path,
    path_name: str,
    records: int,
    sha256: str,
    provenance: dict,
) -> dict:
    """Write a manifest for a logical JSONL tape whose bytes remain sharded."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "path": path_name,
        "records": int(records),
        "sha256": sha256,
        "provenance": provenance,
    }
    temp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    temp.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(manifest_path)
    return manifest


def _find_shard(
    root: Path,
    shard: dict,
) -> tuple[Path, dict]:
    """Resolve a shard by manifest identity, not filename alone.

    Gap-recovery generations intentionally reuse compact names such as
    events-gap-000.jsonl. Consumers may therefore download different shards
    with the same basename into separate source-run directories.
    """
    name = str(shard["file"])
    lo = int(shard["from_block"])
    hi = int(shard["to_block"])
    expected_sha = str(shard["sha256"])
    expected_records = int(shard["records"])

    candidates = sorted(path for path in root.rglob(name) if path.is_file())
    if not candidates:
        raise ValueError(
            f"sharded tape file {name!r} is missing under {root}"
        )

    matches: list[tuple[Path, dict]] = []
    for path in candidates:
        sidecar = path.with_suffix(path.suffix + ".manifest.json")
        if not sidecar.exists():
            continue
        manifest = json.loads(sidecar.read_text())
        shard_prov = manifest.get("provenance") or {}
        if (
            manifest.get("sha256") == expected_sha
            and int(manifest.get("records", -1)) == expected_records
            and int(shard_prov.get("from_block", -1)) == lo
            and int(shard_prov.get("to_block", -1)) == hi
        ):
            matches.append((path, manifest))

    if not matches:
        raise ValueError(
            f"sharded tape manifest identity changed: {name}; "
            f"checked {len(candidates)} candidate file(s)"
        )
    return matches[0]


def iter_sharded_jsonl(
    root: Path,
    aggregate_manifest_path: Path,
) -> Iterator[dict]:
    """Stream and validate a logical JSONL tape from its ordered shard list."""
    aggregate = json.loads(aggregate_manifest_path.read_text())
    provenance = aggregate.get("provenance") or {}
    if provenance.get("storage_mode") != "sharded_artifacts":
        raise ValueError("aggregate manifest is not a sharded-artifact tape")
    shards = provenance.get("shards") or []
    if not shards:
        raise ValueError("aggregate sharded tape manifest contains no shards")

    total_records = 0
    aggregate_digest = hashlib.sha256()
    previous_hi = None
    for shard in shards:
        name = str(shard["file"])
        lo = int(shard["from_block"])
        hi = int(shard["to_block"])
        if previous_hi is not None and lo != previous_hi + 1:
            raise ValueError(
                "sharded tape block coverage is discontinuous: "
                f"{previous_hi} -> {lo}"
            )
        previous_hi = hi

        path, manifest = _find_shard(root, shard)

        local_records = 0
        local_digest = hashlib.sha256()
        with path.open("rb") as handle:
            for raw in handle:
                local_digest.update(raw)
                aggregate_digest.update(raw)
                if not raw.strip():
                    continue
                local_records += 1
                total_records += 1
                yield json.loads(raw)

        if local_records != int(shard["records"]):
            raise ValueError(
                f"sharded tape record count changed for {name}: "
                f"{local_records} != {shard['records']}"
            )
        if local_digest.hexdigest() != shard["sha256"]:
            raise ValueError(f"sharded tape SHA changed for {name}")

    if total_records != int(aggregate.get("records", -1)):
        raise ValueError(
            "aggregate sharded tape record count changed: "
            f"{total_records} != {aggregate.get('records')}"
        )
    if aggregate_digest.hexdigest() != aggregate.get("sha256"):
        raise ValueError("aggregate sharded tape SHA changed")
