"""Stream exact source tapes into frozen-universe research subsets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from hlp.config import normalize_address
from hlp.data.sharded_tape import (
    iter_sharded_jsonl_matching_field_values,
    iter_validated_jsonl_matching_field_values,
    validate_shard_block_coverage,
    write_virtual_jsonl_manifest,
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



def normalize_flat_sharded_research_manifest(
    *,
    component_id: str,
    flat_manifest_path: Path,
    output_manifest_path: Path,
    path_name: str,
    expected_logical_sha256: str,
) -> dict:
    """Convert a legacy flat shard manifest into the canonical virtual format."""

    component_id = str(component_id)
    expected_sha = _sha256(
        expected_logical_sha256,
        label=f"{component_id} flat logical input",
    )
    flat = json.loads(flat_manifest_path.read_text())
    actual_sha = _sha256(
        flat.get("sha256"),
        label=f"{component_id} flat manifest",
    )
    if actual_sha != expected_sha:
        raise ValueError(
            f"{component_id} flat research logical tape SHA drift"
        )
    shards = [dict(row) for row in flat.get("shards") or []]
    if not shards:
        raise ValueError(
            f"{component_id} flat research manifest has no shards"
        )
    start = min(int(row["from_block"]) for row in shards)
    end = max(int(row["to_block"]) for row in shards)
    ordered = validate_shard_block_coverage(
        shards,
        start_block=start,
        end_block=end,
    )
    records = sum(int(row["records"]) for row in ordered)
    if records != int(flat.get("records", -1)):
        raise ValueError(
            f"{component_id} flat research record count drift"
        )
    return write_virtual_jsonl_manifest(
        manifest_path=output_manifest_path,
        path_name=path_name,
        records=records,
        sha256=actual_sha,
        provenance={
            "storage_mode": "sharded_artifacts",
            "source": "normalized_flat_research_manifest",
            "component_id": component_id,
            "from_block": start,
            "to_block": end,
            "shards": ordered,
        },
    )


def rebuild_report_sharded_research_manifest(
    *,
    component_id: str,
    root: Path,
    point_pattern: str,
    report_template: str,
    report_records_field: str,
    expected_logical_sha256: str,
    output_manifest_path: Path,
    path_name: str,
) -> dict:
    """Rebuild a virtual tape from exact point sidecars plus shard reports."""

    component_id = str(component_id)
    expected_sha = _sha256(
        expected_logical_sha256,
        label=f"{component_id} rebuilt logical input",
    )
    point_files = sorted(
        path
        for path in root.rglob(point_pattern)
        if path.is_file()
    )
    if not point_files:
        raise ValueError(
            f"{component_id} research shard rebuild found no point files"
        )

    aggregate = hashlib.sha256()
    shards = []
    seen_names: set[str] = set()
    for path in point_files:
        if path.name in seen_names:
            raise ValueError(
                f"{component_id} research shard filename repeats: "
                f"{path.name}"
            )
        seen_names.add(path.name)
        suffix = path.stem.rsplit("-", 1)[-1]
        report_path = path.parent / report_template.format(
            suffix=suffix
        )
        sidecar_path = path.with_suffix(
            path.suffix + ".manifest.json"
        )
        if not report_path.is_file() or not sidecar_path.is_file():
            raise ValueError(
                f"{component_id} research shard evidence is incomplete: "
                f"{path.name}"
            )
        report = json.loads(report_path.read_text())
        sidecar = json.loads(sidecar_path.read_text())
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != _sha256(
            sidecar.get("sha256"),
            label=f"{component_id} shard {path.name}",
        ):
            raise ValueError(
                f"{component_id} research shard SHA drift: {path.name}"
            )
        if digest != _sha256(
            report.get("points_sha256"),
            label=f"{component_id} report {path.name}",
        ):
            raise ValueError(
                f"{component_id} research report point SHA drift: "
                f"{path.name}"
            )
        records = int(sidecar.get("records", -1))
        if records < 0 or records != int(
            report.get(report_records_field, -2)
        ):
            raise ValueError(
                f"{component_id} research shard record count drift: "
                f"{path.name}"
            )
        if int(report.get("priced_points", -1)) != records:
            raise ValueError(
                f"{component_id} research shard contains unpriced points: "
                f"{path.name}"
            )
        lo = int(report.get("from_block", -1))
        hi = int(report.get("to_block", -1))
        if lo < 0 or hi < lo:
            raise ValueError(
                f"{component_id} research shard range is invalid: "
                f"{path.name}"
            )
        aggregate.update(raw)
        shards.append({
            "file": path.name,
            "records": records,
            "sha256": digest,
            "from_block": lo,
            "to_block": hi,
        })

    start = min(int(row["from_block"]) for row in shards)
    end = max(int(row["to_block"]) for row in shards)
    ordered = validate_shard_block_coverage(
        shards,
        start_block=start,
        end_block=end,
    )
    actual_sha = aggregate.hexdigest()
    if actual_sha != expected_sha:
        raise ValueError(
            f"{component_id} rebuilt research logical tape SHA drift"
        )
    return write_virtual_jsonl_manifest(
        manifest_path=output_manifest_path,
        path_name=path_name,
        records=sum(int(row["records"]) for row in ordered),
        sha256=actual_sha,
        provenance={
            "storage_mode": "sharded_artifacts",
            "source": "rebuilt_report_sharded_research_manifest",
            "component_id": component_id,
            "from_block": start,
            "to_block": end,
            "shards": ordered,
        },
    )
