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


def _find_unique(root: Path, name: str) -> Path:
    direct = root / name
    if direct.exists():
        return direct
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one sharded tape file {name!r} under {root}, "
            f"got {len(matches)}"
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

        path = _find_unique(root, name)
        sidecar = _find_unique(root, name + ".manifest.json")
        manifest = json.loads(sidecar.read_text())
        shard_prov = manifest.get("provenance") or {}
        if (
            manifest.get("sha256") != shard["sha256"]
            or int(manifest.get("records", -1)) != int(shard["records"])
            or int(shard_prov.get("from_block", -1)) != lo
            or int(shard_prov.get("to_block", -1)) != hi
        ):
            raise ValueError(f"sharded tape manifest identity changed: {name}")

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
