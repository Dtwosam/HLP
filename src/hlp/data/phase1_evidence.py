from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SNAPSHOT_HEAD_BLOCK = 54_486_035
ALL_PONS_LAUNCHES = 494_639


def _int(value: Any, *, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} is not an integer") from exc


def _sha256(value: Any, *, field: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64:
        raise ValueError(f"{field} is not a SHA256")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{field} is not a SHA256") from exc
    return text


def _provenance(
    manifest: Mapping[str, Any],
    *,
    label: str,
) -> Mapping[str, Any]:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError(f"{label} manifest has no provenance")
    if _int(
        provenance.get("chain_id"),
        field=f"{label}.chain_id",
    ) != 4663:
        raise ValueError(f"{label} chain changed")
    if _int(
        provenance.get("snapshot_head_block"),
        field=f"{label}.snapshot_head_block",
    ) != SNAPSHOT_HEAD_BLOCK:
        raise ValueError(f"{label} snapshot head changed")
    return provenance


def validate_post_eligibility_evidence_bundle(
    *,
    eligible_summary: Mapping[str, Any],
    eligible_manifest: Mapping[str, Any],
    representative_summary: Mapping[str, Any],
    representative_manifest: Mapping[str, Any],
    expected_lifecycle_run_id: int,
    expected_v1_v3_run_id: int,
    expected_v2_v4_run_id: int,
) -> dict[str, Any]:
    lifecycle_run_id = int(expected_lifecycle_run_id)
    v1_v3_run_id = int(expected_v1_v3_run_id)
    v2_v4_run_id = int(expected_v2_v4_run_id)
    if min(lifecycle_run_id, v1_v3_run_id, v2_v4_run_id) <= 0:
        raise ValueError("evidence routing run IDs must be positive")

    if _int(
        eligible_summary.get("snapshot_head_block"),
        field="eligible.snapshot_head_block",
    ) != SNAPSHOT_HEAD_BLOCK:
        raise ValueError("eligible universe snapshot head changed")
    if _int(
        eligible_summary.get("all_pons_launches"),
        field="eligible.all_pons_launches",
    ) != ALL_PONS_LAUNCHES:
        raise ValueError("eligible universe Pons launch count changed")
    if _int(
        eligible_summary.get("unknown_tokens"),
        field="eligible.unknown_tokens",
    ) != 0:
        raise ValueError("eligible universe still contains unknown tokens")

    eligible_tokens = _int(
        eligible_summary.get("eligible_tokens"),
        field="eligible.eligible_tokens",
    )
    eligible_v1 = _int(
        eligible_summary.get("eligible_v1"),
        field="eligible.eligible_v1",
    )
    eligible_v2 = _int(
        eligible_summary.get("eligible_v2"),
        field="eligible.eligible_v2",
    )
    if eligible_tokens <= 0 or eligible_v1 + eligible_v2 != eligible_tokens:
        raise ValueError("eligible universe generation accounting is invalid")

    eligible_provenance = _provenance(
        eligible_manifest,
        label="eligible",
    )
    if str(
        eligible_provenance.get("eligibility_threshold_usd")
    ) != "100000":
        raise ValueError("eligible universe threshold changed")
    universe_sha = _sha256(
        eligible_manifest.get("sha256"),
        field="eligible.manifest.sha256",
    )
    if _sha256(
        eligible_summary.get("universe_sha256"),
        field="eligible.summary.universe_sha256",
    ) != universe_sha:
        raise ValueError("eligible universe summary SHA disagrees with manifest")

    if _int(
        representative_summary.get("snapshot_head_block"),
        field="representative.snapshot_head_block",
    ) != SNAPSHOT_HEAD_BLOCK:
        raise ValueError("representative snapshot head changed")
    if _int(
        representative_summary.get("tokens"),
        field="representative.tokens",
    ) != 10:
        raise ValueError("representative validation must contain 10 tokens")
    if _int(
        representative_summary.get("complete_tokens"),
        field="representative.complete_tokens",
    ) != 10:
        raise ValueError("representative validation is incomplete")
    if dict(representative_summary.get("sample_groups") or {}) != {
        "failure": 5,
        "runner": 5,
    }:
        raise ValueError("representative sample groups changed")

    representative_provenance = _provenance(
        representative_manifest,
        label="representative",
    )
    representative_sha = _sha256(
        representative_manifest.get("sha256"),
        field="representative.manifest.sha256",
    )
    if _sha256(
        representative_summary.get("validation_sha256"),
        field="representative.summary.validation_sha256",
    ) != representative_sha:
        raise ValueError(
            "representative summary SHA disagrees with manifest"
        )

    run_fields = {
        "v1_eligibility_run_id": lifecycle_run_id,
        "v2_eligibility_run_id": lifecycle_run_id,
        "v1_v3_run_id": v1_v3_run_id,
        "v2_v4_run_id": v2_v4_run_id,
    }
    for field, expected in run_fields.items():
        eligible_value = _int(
            eligible_provenance.get(field),
            field=f"eligible.{field}",
        )
        representative_value = _int(
            representative_provenance.get(field),
            field=f"representative.{field}",
        )
        if eligible_value != expected:
            raise ValueError(
                f"eligible {field} does not match evidence routing"
            )
        if representative_value != expected:
            raise ValueError(
                f"representative {field} does not match evidence routing"
            )
        if eligible_value != representative_value:
            raise ValueError(
                f"eligible and representative disagree on {field}"
            )

    if _int(
        eligible_summary.get("validated_v1_v3_run_id"),
        field="eligible.validated_v1_v3_run_id",
    ) != v1_v3_run_id:
        raise ValueError("eligible V1/V3 summary run disagrees")
    if _int(
        eligible_summary.get("validated_v2_v4_run_id"),
        field="eligible.validated_v2_v4_run_id",
    ) != v2_v4_run_id:
        raise ValueError("eligible V2/V4 summary run disagrees")

    lifecycle_hashes: dict[str, str] = {}
    for field, summary_field in (
        ("v1_eligibility_sha256", "validated_v1_input_sha256"),
        ("v2_eligibility_sha256", "validated_v2_input_sha256"),
    ):
        eligible_hash = _sha256(
            eligible_provenance.get(field),
            field=f"eligible.{field}",
        )
        representative_hash = _sha256(
            representative_provenance.get(field),
            field=f"representative.{field}",
        )
        summary_hash = _sha256(
            eligible_summary.get(summary_field),
            field=f"eligible.{summary_field}",
        )
        if eligible_hash != representative_hash:
            raise ValueError(
                f"eligible and representative lifecycle SHA disagree: {field}"
            )
        if summary_hash != eligible_hash:
            raise ValueError(
                f"eligible lifecycle summary SHA disagrees: {field}"
            )
        lifecycle_hashes[field] = eligible_hash

    if _int(
        representative_provenance.get("fallback_run_id"),
        field="representative.fallback_run_id",
    ) != lifecycle_run_id:
        raise ValueError(
            "representative fallback run does not match lifecycle evidence"
        )

    return {
        "status": "ready",
        "snapshot_head_block": SNAPSHOT_HEAD_BLOCK,
        "all_pons_launches": ALL_PONS_LAUNCHES,
        "eligible_tokens": eligible_tokens,
        "representative_tokens": 10,
        "lifecycle_run_id": lifecycle_run_id,
        "v1_v3_run_id": v1_v3_run_id,
        "v2_v4_run_id": v2_v4_run_id,
        "eligible_universe_sha256": universe_sha,
        "representative_validation_sha256": representative_sha,
        **lifecycle_hashes,
    }
