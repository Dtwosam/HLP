"""Immutable JSONL snapshot helpers for Phase 1 acquisition evidence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Any


def _jsonable(row: Any) -> dict:
    if is_dataclass(row):
        return asdict(row)
    if isinstance(row, dict):
        return row
    raise TypeError(f"unsupported snapshot row: {type(row)!r}")


def write_jsonl_snapshot(
    rows: Iterable[Any],
    *,
    output: Path,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Write rows atomically and emit a sidecar manifest with SHA-256."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    count = 0
    digest = hashlib.sha256()
    with temp.open("wb") as handle:
        for row in rows:
            line = (
                json.dumps(_jsonable(row), sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode()
            handle.write(line)
            digest.update(line)
            count += 1
    temp.replace(output)

    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "path": output.name,
        "records": count,
        "sha256": digest.hexdigest(),
        "provenance": provenance,
    }
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    manifest_temp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    manifest_temp.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_temp.replace(manifest_path)
    return manifest
