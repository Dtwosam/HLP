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



def resolve_v2_v4_canonical_shard_bindings(
    manifest: Mapping[str, Any],
    *,
    current_run_id: int,
    expected_start: int = 26_841_846,
    expected_end: int = 54_486_035,
) -> list[dict[str, Any]]:
    """Validate aggregate shard geometry and return exact artifact bindings."""
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("canonical V2/V4 provenance is missing")
    if provenance.get("storage_mode") != "sharded_artifacts":
        raise ValueError(
            "canonical V2/V4 manifest is not sharded-artifact storage"
        )

    partial_value = provenance.get("partial_run_id")
    try:
        partial_run_id = (
            int(partial_value)
            if partial_value not in {None, "", 0}
            else None
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "canonical V2/V4 partial run ID is invalid"
        ) from exc

    shards = provenance.get("shards")
    if not isinstance(shards, list) or not shards:
        raise ValueError("canonical V2/V4 manifest has no shards")

    try:
        aggregate_records = int(manifest.get("records", -1))
        start = int(expected_start)
        end = int(expected_end)
    except (TypeError, ValueError) as exc:
        raise ValueError("canonical V2/V4 aggregate counts are invalid") from exc
    if aggregate_records < 0:
        raise ValueError("canonical V2/V4 aggregate records are invalid")
    if start <= 0 or end < start:
        raise ValueError("canonical V2/V4 expected range is invalid")

    bindings: list[dict[str, Any]] = []
    seen = set()
    previous_hi = None
    selected_records = 0
    for shard in shards:
        if not isinstance(shard, Mapping):
            raise ValueError("canonical V2/V4 shard row is invalid")
        binding = resolve_v2_v4_shard_artifact(
            shard,
            current_run_id=current_run_id,
            partial_run_id=partial_run_id,
        )
        digest = str(binding["sha256"]).lower()
        records = int(binding["records"])
        lo = int(binding["from_block"])
        hi = int(binding["to_block"])
        if (
            len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ValueError(
                f"canonical V2/V4 shard SHA-256 is invalid: {binding['file']}"
            )
        if records < 0:
            raise ValueError(
                f"canonical V2/V4 shard records are invalid: {binding['file']}"
            )
        if lo <= 0 or hi < lo:
            raise ValueError(
                f"canonical V2/V4 shard range is invalid: {binding['file']}"
            )
        if previous_hi is None:
            if lo != start:
                raise ValueError(
                    "canonical V2/V4 shard coverage start changed: "
                    f"{lo} != {start}"
                )
        elif lo != previous_hi + 1:
            raise ValueError(
                "canonical V2/V4 shard coverage is discontinuous: "
                f"{previous_hi} -> {lo}"
            )
        previous_hi = hi
        selected_records += records

        key = (
            int(binding["run_id"]),
            str(binding["artifact_name"]),
            str(binding["file"]),
        )
        if key in seen:
            raise ValueError(
                f"canonical V2/V4 shard binding is duplicated: {key}"
            )
        seen.add(key)
        binding["sha256"] = digest
        bindings.append(binding)

    if previous_hi != end:
        raise ValueError(
            "canonical V2/V4 shard coverage end changed: "
            f"{previous_hi} != {end}"
        )
    if selected_records != aggregate_records:
        raise ValueError(
            "canonical V2/V4 shard records do not match aggregate: "
            f"{selected_records} != {aggregate_records}"
        )
    return bindings
