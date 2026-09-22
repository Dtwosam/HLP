"""Stream exact source tapes into frozen-universe research subsets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from hlp.config import normalize_address
from hlp.data.sharded_tape import (
    iter_sharded_jsonl_matching_field_values,
    iter_validated_jsonl_matching_field_values,
)
from hlp.data.snapshot import iter_jsonl_snapshot


PHASE2_RESEARCH_MATERIALIZATION_VERSION = (
    "phase2-research-materialization-v1"
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


def _eligible_tokens(values: Iterable[str]) -> list[str]:
    return sorted({
        normalize_address(str(value))
        for value in values
    })


def _exhaust_snapshot(rows, *, output: Path, provenance: dict) -> dict:
    tapped = iter_jsonl_snapshot(
        rows,
        output=output,
        provenance=provenance,
    )
    for _ in tapped:
        pass
    manifest_path = output.with_suffix(
        output.suffix + ".manifest.json"
    )
    if not manifest_path.is_file():
        raise ValueError(
            f"research materialization did not finalize: {output}"
        )
    return json.loads(manifest_path.read_text())


def materialize_single_jsonl_research_subset(
    *,
    component_id: str,
    data_path: Path,
    manifest_path: Path,
    eligible_tokens: Iterable[str],
    expected_logical_sha256: str,
    output: Path,
    source_binding_sha256: str,
) -> dict:
    """Validate one complete JSONL tape and retain only frozen-universe tokens."""

    component_id = str(component_id)
    if not component_id:
        raise ValueError("research materialization component id is empty")
    expected_sha = _sha256(
        expected_logical_sha256,
        label=f"{component_id} logical input",
    )
    binding_sha = _sha256(
        source_binding_sha256,
        label=f"{component_id} source binding",
    )
    manifest = json.loads(manifest_path.read_text())
    input_sha = _sha256(
        manifest.get("sha256"),
        label=f"{component_id} input manifest",
    )
    if input_sha != expected_sha:
        raise ValueError(
            f"{component_id} research logical tape SHA drift"
        )
    input_records = int(manifest.get("records", -1))
    if input_records < 0:
        raise ValueError(
            f"{component_id} research input record count is invalid"
        )

    tokens = _eligible_tokens(eligible_tokens)
    rows = iter_validated_jsonl_matching_field_values(
        data_path,
        manifest_path,
        field="token",
        values=tokens,
    )
    output_manifest = _exhaust_snapshot(
        rows,
        output=output,
        provenance={
            "version": PHASE2_RESEARCH_MATERIALIZATION_VERSION,
            "component_id": component_id,
            "storage_mode": "single_jsonl",
            "source_binding_sha256": binding_sha,
            "logical_input_sha256": input_sha,
            "logical_input_records": input_records,
            "eligible_token_filter_size": len(tokens),
            "full_input_validated": True,
            "dump_threshold_frozen": False,
            "outcome_labels_computed": False,
        },
    )
    return {
        "version": PHASE2_RESEARCH_MATERIALIZATION_VERSION,
        "component_id": component_id,
        "storage_mode": "single_jsonl",
        "source_binding_sha256": binding_sha,
        "logical_input_sha256": input_sha,
        "logical_input_records": input_records,
        "eligible_token_filter_size": len(tokens),
        "materialized_records": int(output_manifest["records"]),
        "materialized_sha256": output_manifest["sha256"],
        "full_input_validated": True,
        "research_price_path_materialized": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }


def materialize_sharded_jsonl_research_subset(
    *,
    component_id: str,
    root: Path,
    aggregate_manifest_path: Path,
    eligible_tokens: Iterable[str],
    expected_logical_sha256: str,
    output: Path,
    source_binding_sha256: str,
) -> dict:
    """Validate every shard byte while decoding only frozen-universe token rows."""

    component_id = str(component_id)
    if not component_id:
        raise ValueError("research materialization component id is empty")
    expected_sha = _sha256(
        expected_logical_sha256,
        label=f"{component_id} logical input",
    )
    binding_sha = _sha256(
        source_binding_sha256,
        label=f"{component_id} source binding",
    )
    aggregate = json.loads(aggregate_manifest_path.read_text())
    input_sha = _sha256(
        aggregate.get("sha256"),
        label=f"{component_id} aggregate manifest",
    )
    if input_sha != expected_sha:
        raise ValueError(
            f"{component_id} research logical tape SHA drift"
        )
    input_records = int(aggregate.get("records", -1))
    if input_records < 0:
        raise ValueError(
            f"{component_id} research input record count is invalid"
        )
    provenance = aggregate.get("provenance") or {}
    if provenance.get("storage_mode") != "sharded_artifacts":
        raise ValueError(
            f"{component_id} research aggregate is not sharded"
        )
    if not list(provenance.get("shards") or []):
        raise ValueError(
            f"{component_id} research aggregate has no shards"
        )

    tokens = _eligible_tokens(eligible_tokens)
    rows = iter_sharded_jsonl_matching_field_values(
        root,
        aggregate_manifest_path,
        field="token",
        values=tokens,
    )
    output_manifest = _exhaust_snapshot(
        rows,
        output=output,
        provenance={
            "version": PHASE2_RESEARCH_MATERIALIZATION_VERSION,
            "component_id": component_id,
            "storage_mode": "sharded_artifacts",
            "source_binding_sha256": binding_sha,
            "logical_input_sha256": input_sha,
            "logical_input_records": input_records,
            "eligible_token_filter_size": len(tokens),
            "full_input_validated": True,
            "dump_threshold_frozen": False,
            "outcome_labels_computed": False,
        },
    )
    return {
        "version": PHASE2_RESEARCH_MATERIALIZATION_VERSION,
        "component_id": component_id,
        "storage_mode": "sharded_artifacts",
        "source_binding_sha256": binding_sha,
        "logical_input_sha256": input_sha,
        "logical_input_records": input_records,
        "eligible_token_filter_size": len(tokens),
        "materialized_records": int(output_manifest["records"]),
        "materialized_sha256": output_manifest["sha256"],
        "full_input_validated": True,
        "research_price_path_materialized": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }
