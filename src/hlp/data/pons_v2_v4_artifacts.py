"""Resolve canonical Pons V2/V4 shard rows back to Actions artifacts."""

from __future__ import annotations

import re
from typing import Any, Mapping


_SHARD_FILE = re.compile(r"^v4-events-shard-(\d{3})\.jsonl$")
_GAP_FILE = re.compile(r"^v4-events-gap-(\d{3})\.jsonl$")


def resolve_v2_v4_shard_artifact(
    shard: Mapping[str, Any],
    *,
    current_run_id: int,
    partial_run_id: int | None,
) -> dict[str, Any]:
    """Bind one aggregate-manifest shard to its exact source run/artifact."""
    current = int(current_run_id)
    if current <= 0:
        raise ValueError("current V2/V4 run ID must be positive")

    filename = str(shard.get("file") or "")
    source = str(shard.get("source") or "")
    shard_match = _SHARD_FILE.fullmatch(filename)
    gap_match = _GAP_FILE.fullmatch(filename)

    if shard_match is not None:
        if source == "partial":
            partial = int(partial_run_id or 0)
            if partial <= 0:
                raise ValueError(
                    "partial V2/V4 shard lacks a positive partial run ID"
                )
            run_id = partial
        elif source == "":
            # Original, non-recovery canonical manifests predate the explicit
            # source label and all shard artifacts live in the canonical run.
            run_id = current
        else:
            raise ValueError(
                "V2/V4 shard source label changed: "
                f"file={filename} source={source!r}"
            )
        shard_index = int(shard_match.group(1))
        artifact_name = f"phase1-pons-v2-v4-{shard_index}"
        kind = "shard"
    elif gap_match is not None:
        if source in {"", "gaps"}:
            run_id = current
        elif source.isdigit() and int(source) > 0:
            run_id = int(source)
        else:
            raise ValueError(
                "V2/V4 gap source label changed: "
                f"file={filename} source={source!r}"
            )
        gap_id = gap_match.group(1)
        artifact_name = f"phase1-pons-v2-v4-gap-{gap_id}"
        kind = "gap"
    else:
        raise ValueError(
            f"unsupported canonical V2/V4 shard filename: {filename!r}"
        )

    return {
        "run_id": run_id,
        "artifact_name": artifact_name,
        "file": filename,
        "kind": kind,
        "sha256": str(shard.get("sha256") or ""),
        "records": int(shard.get("records", -1)),
        "from_block": int(shard.get("from_block", -1)),
        "to_block": int(shard.get("to_block", -1)),
    }
