"""Resolve exact accepted Phase-1 Pons inputs for Phase-2 research replay."""

from __future__ import annotations

from typing import Mapping


PHASE2_PONS_RESEARCH_INPUTS_VERSION = "phase2-pons-research-inputs-v1"
PONS_RESEARCH_SOURCES = frozenset({"pons_v1", "pons_v2"})


V1_REQUIRED_MANIFESTS = {
    "registry": "pons-full-launch-registry.jsonl.manifest.json",
    "quote_registry": "pons-quote-registry.jsonl.manifest.json",
    "market_events": "pons-v1-v3-full.jsonl.manifest.json",
    "anchor": "pons-weth-usdg-anchor-full.jsonl.manifest.json",
    "oracle_initial": "pons-stock-oracle-initial.jsonl.manifest.json",
    "oracle_updates": "pons-stock-oracle-updates.jsonl.manifest.json",
}

V2_REQUIRED_MANIFESTS = {
    "registry": "pons-v2-full-registry.jsonl.manifest.json",
    "curve_events": "pons-v2-curve-full.jsonl.manifest.json",
    "graduations": "pons-v2-graduations-full.jsonl.manifest.json",
    "registrations": "pons-v2-registrations-full.jsonl.manifest.json",
    "market_events": "pons-v2-v4-full.jsonl.manifest.json",
    "anchor": "pons-weth-usdg-anchor-full.jsonl.manifest.json",
    "oracle_initial": "pons-stock-oracle-initial.jsonl.manifest.json",
    "oracle_updates": "pons-stock-oracle-updates.jsonl.manifest.json",
    "fallback_initial": "pons-quote-fallback-initial.jsonl.manifest.json",
    "fallback_updates": "pons-quote-fallback-updates.jsonl.manifest.json",
}


def _positive_run_id(value: object, *, label: str) -> int:
    run_id = int(value)
    if run_id <= 0:
        raise ValueError(f"{label} run id is invalid")
    return run_id


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _validated_manifest_map(
    validation_report: Mapping[str, object],
    *,
    source_id: str,
    required: Mapping[str, str],
) -> dict[str, dict]:
    rows = validation_report.get("validated_manifests")
    if not isinstance(rows, list):
        raise ValueError(
            f"{source_id} accepted input validation lacks manifest rows"
        )
    by_name = {}
    for raw in rows:
        row = dict(raw)
        path = str(row.get("manifest") or "")
        name = path.rsplit("/", 1)[-1]
        if not name or name in by_name:
            raise ValueError(
                f"{source_id} accepted input manifest identity is invalid: "
                f"{name!r}"
            )
        records = int(row.get("records", -1))
        if records < 0:
            raise ValueError(
                f"{source_id} accepted input record count is invalid: {name}"
            )
        by_name[name] = {
            "manifest_path": path,
            "manifest_filename": name,
            "records": records,
            "sha256": _sha256(
                row.get("sha256"),
                label=f"{source_id} {name}",
            ),
        }

    expected_names = set(required.values())
    if set(by_name) != expected_names:
        raise ValueError(
            f"{source_id} accepted input manifest set changed: "
            f"missing={sorted(expected_names - set(by_name))} "
            f"extra={sorted(set(by_name) - expected_names)}"
        )
    return {
        logical: by_name[filename]
        for logical, filename in required.items()
    }


def resolve_accepted_pons_replay_inputs(
    source_id: str,
    lifecycle_manifest: Mapping[str, object],
    validation_report: Mapping[str, object],
    *,
    snapshot_head_block: int,
) -> dict:
    """Resolve upstream run IDs + exact manifest identities from accepted evidence."""

    source_id = str(source_id)
    if source_id not in PONS_RESEARCH_SOURCES:
        raise ValueError(f"unsupported Pons research source: {source_id}")
    snapshot = int(snapshot_head_block)
    if snapshot <= 0:
        raise ValueError("Pons research snapshot is invalid")

    provenance = dict(lifecycle_manifest.get("provenance") or {})
    if int(provenance.get("chain_id", -1)) != 4663:
        raise ValueError(f"{source_id} lifecycle chain changed")
    if int(provenance.get("snapshot_head_block", -1)) != snapshot:
        raise ValueError(f"{source_id} lifecycle snapshot changed")
    if int(validation_report.get("chain_id", -1)) != 4663:
        raise ValueError(f"{source_id} input validation chain changed")
    if int(validation_report.get("snapshot_head_block", -1)) != snapshot:
        raise ValueError(f"{source_id} input validation snapshot changed")

    if source_id == "pons_v1":
        manifests = _validated_manifest_map(
            validation_report,
            source_id=source_id,
            required=V1_REQUIRED_MANIFESTS,
        )
        runs = {
            "registry": _positive_run_id(
                provenance.get("source_registry_run_id"),
                label="Pons V1 registry",
            ),
            "market_events": _positive_run_id(
                provenance.get("v1_v3_run_id"),
                label="Pons V1 V3",
            ),
            "quote_registry": _positive_run_id(
                provenance.get("quote_audit_run_id"),
                label="Pons V1 quote audit",
            ),
            "anchor": _positive_run_id(
                provenance.get("anchor_run_id"),
                label="Pons V1 anchor",
            ),
            "oracle": _positive_run_id(
                provenance.get("oracle_run_id"),
                label="Pons V1 oracle",
            ),
        }
        artifacts = {
            "registry": {
                "run_id": runs["registry"],
                "artifact_name": "phase1-pons-full-registry-recovered",
            },
            "market_events": {
                "run_id": runs["market_events"],
                "artifact_name": "phase1-pons-v1-v3-full",
            },
            "quote_registry": {
                "run_id": runs["quote_registry"],
                "artifact_name": None,
                "discover_by_manifest": manifests["quote_registry"],
            },
            "anchor": {
                "run_id": runs["anchor"],
                "artifact_name": "phase1-pons-weth-usdg-anchor-full",
            },
            "oracle": {
                "run_id": runs["oracle"],
                "artifact_name": "phase1-pons-stock-oracle-full",
            },
        }
    else:
        manifests = _validated_manifest_map(
            validation_report,
            source_id=source_id,
            required=V2_REQUIRED_MANIFESTS,
        )
        runs = {
            "registry": _positive_run_id(
                provenance.get("v2_registry_run_id"),
                label="Pons V2 registry",
            ),
            "curve": _positive_run_id(
                provenance.get("curve_run_id"),
                label="Pons V2 curve",
            ),
            "transition": _positive_run_id(
                provenance.get("transition_run_id"),
                label="Pons V2 transition",
            ),
            "market_events": _positive_run_id(
                provenance.get("v4_run_id"),
                label="Pons V2 V4",
            ),
            "anchor": _positive_run_id(
                provenance.get("anchor_run_id"),
                label="Pons V2 anchor",
            ),
            "oracle": _positive_run_id(
                provenance.get("oracle_run_id"),
                label="Pons V2 oracle",
            ),
            "fallback": _positive_run_id(
                provenance.get("fallback_run_id"),
                label="Pons V2 fallback",
            ),
        }
        artifacts = {
            "registry": {
                "run_id": runs["registry"],
                "artifact_name": "phase1-pons-v2-full-registry",
            },
            "curve": {
                "run_id": runs["curve"],
                "artifact_name": "phase1-pons-v2-curve-full",
            },
            "transition": {
                "run_id": runs["transition"],
                "artifact_name": "phase1-pons-v2-transition-full",
            },
            "market_events": {
                "run_id": runs["market_events"],
                "artifact_name": "phase1-pons-v2-v4-full",
            },
            "anchor": {
                "run_id": runs["anchor"],
                "artifact_name": "phase1-pons-weth-usdg-anchor-full",
            },
            "oracle": {
                "run_id": runs["oracle"],
                "artifact_name": "phase1-pons-stock-oracle-full",
            },
            "fallback": {
                "run_id": runs["fallback"],
                "artifact_name": "phase1-pons-quote-fallback-full",
            },
        }

    return {
        "version": PHASE2_PONS_RESEARCH_INPUTS_VERSION,
        "source_id": source_id,
        "chain_id": 4663,
        "snapshot_head_block": snapshot,
        "runs": dict(sorted(runs.items())),
        "artifacts": dict(sorted(artifacts.items())),
        "validated_manifests": dict(sorted(manifests.items())),
        "accepted_lifecycle_manifest_sha256": _sha256(
            lifecycle_manifest.get("sha256"),
            label=f"{source_id} accepted lifecycle",
        ),
        "canonical_replay_required": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }
