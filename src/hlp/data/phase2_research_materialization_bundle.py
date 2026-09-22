"""Freeze complete Phase-2 research price-path materialization evidence."""

from __future__ import annotations

import json
from collections import Counter
from typing import Iterable, Mapping

from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID
from hlp.data.phase2_research_rehydration import (
    PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION,
)


PHASE2_RESEARCH_MATERIALIZATION_BUNDLE_VERSION = (
    "phase2-research-materialization-bundle-v1"
)
PHASE2_RESEARCH_MATERIALIZATION_HANDOFF_VERSION = (
    "phase2-research-materialization-handoff-v1"
)
_ALLOWED_REPORT_VERSIONS = frozenset({
    "phase2-research-materialization-v1",
    "phase2-research-composite-materialization-v1",
    "phase2-pons-research-materialization-v1",
})


def _sha256(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} SHA-256 is invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} SHA-256 is invalid") from exc
    return text


def _artifact_digest(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if not text.startswith("sha256:"):
        raise ValueError(f"{label} artifact digest is invalid")
    _sha256(text, label=label)
    return text


def _canonical_sha(payload: Mapping[str, object]) -> str:
    raw = (
        json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def _expected_output_proofs(report: Mapping[str, object]) -> Counter:
    value = dict(report)
    if isinstance(value.get("segment_reports"), Mapping):
        rows = [
            dict(row)
            for row in value["segment_reports"].values()
        ]
        return Counter(
            (
                _sha256(
                    row.get("materialized_sha256"),
                    label="component segment materialized output",
                ),
                int(row.get("materialized_records", -1)),
            )
            for row in rows
        )
    if isinstance(value.get("segments"), Mapping):
        rows = [
            dict(row)
            for row in value["segments"].values()
        ]
        return Counter(
            (
                _sha256(
                    row.get("sha256"),
                    label="Pons segment materialized output",
                ),
                int(row.get("records", -1)),
            )
            for row in rows
        )
    return Counter({
        (
            _sha256(
                value.get("materialized_sha256"),
                label="component materialized output",
            ),
            int(value.get("materialized_records", -1)),
        ): 1
    })


def _validate_manifest_proofs(
    component_id: str,
    report: Mapping[str, object],
    proofs: Iterable[Mapping[str, object]],
    *,
    source_binding_sha256: str,
) -> list[dict]:
    normalized = []
    observed = Counter()
    for raw in proofs:
        proof = dict(raw)
        records = int(proof.get("records", -1))
        if records < 0:
            raise ValueError(
                f"{component_id} output manifest record count is invalid"
            )
        sha = _sha256(
            proof.get("sha256"),
            label=f"{component_id} output manifest",
        )
        provenance = dict(proof.get("provenance") or {})
        if provenance.get("dump_threshold_frozen") is not False:
            raise ValueError(
                f"{component_id} output manifest freezes dump threshold"
            )
        if provenance.get("outcome_labels_computed") is not False:
            raise ValueError(
                f"{component_id} output manifest contains outcome labels"
            )
        if _sha256(
            provenance.get("source_binding_sha256"),
            label=f"{component_id} output source binding",
        ) != source_binding_sha256:
            raise ValueError(
                f"{component_id} output manifest source-binding drift"
            )
        observed[(sha, records)] += 1
        normalized.append({
            "path": str(proof.get("path") or ""),
            "records": records,
            "sha256": sha,
        })

    expected = _expected_output_proofs(report)
    if any(records < 0 for _, records in expected):
        raise ValueError(
            f"{component_id} report has invalid materialized record count"
        )
    if observed != expected:
        raise ValueError(
            f"{component_id} output manifest proof set changed: "
            f"expected={dict(expected)} observed={dict(observed)}"
        )
    return sorted(
        normalized,
        key=lambda row: (row["path"], row["sha256"]),
    )


def _eligible_count(report: Mapping[str, object]) -> int:
    if "expected_eligible_tokens" in report:
        expected = int(report.get("expected_eligible_tokens", -1))
        observed = int(report.get("observed_eligible_tokens", -2))
        if expected < 0 or observed != expected:
            raise ValueError(
                "research component eligible-token coverage count changed"
            )
        return expected
    value = int(report.get("eligible_tokens", -1))
    if value < 0:
        raise ValueError(
            "research component eligible-token count is invalid"
        )
    return value


def _full_inputs_validated(report: Mapping[str, object]) -> bool:
    if report.get("full_input_validated") is True:
        return True
    if report.get("full_inputs_validated") is True:
        return True
    segments = report.get("segment_reports")
    if isinstance(segments, Mapping) and segments:
        return all(
            dict(row).get("full_input_validated") is True
            for row in segments.values()
        )
    return False


def build_phase2_research_materialization_bundle(
    plan: Mapping[str, object],
    *,
    rehydration_plan_sha256: str,
    component_reports: Mapping[str, Mapping[str, object]],
    component_handoffs: Mapping[str, Mapping[str, object]],
    component_manifest_proofs: Mapping[
        str,
        Iterable[Mapping[str, object]],
    ],
) -> dict:
    """Freeze exact research materialization evidence before dump research."""

    plan = dict(plan)
    if (
        str(plan.get("version") or "")
        != PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION
    ):
        raise ValueError("research materialization plan version changed")
    plan_sha = _sha256(
        rehydration_plan_sha256,
        label="research rehydration plan",
    )
    universe_sha = _sha256(
        plan.get("eligible_universe_sha256"),
        label="research materialization universe",
    )

    launchpads = plan.get("launchpad_bindings")
    direct = plan.get("direct_binding")
    if not isinstance(launchpads, Mapping) or not isinstance(direct, Mapping):
        raise ValueError(
            "research materialization plan bindings are incomplete"
        )
    expected_components = set(str(value) for value in launchpads)
    expected_components.add(DIRECT_RESEARCH_COMPONENT_ID)
    if len(expected_components) != int(plan.get("component_count", -1)):
        raise ValueError(
            "research materialization component count changed"
        )

    supplied_sets = [
        set(str(value) for value in component_reports),
        set(str(value) for value in component_handoffs),
        set(str(value) for value in component_manifest_proofs),
    ]
    for supplied in supplied_sets:
        if supplied != expected_components:
            raise ValueError(
                "research materialization component set changed: "
                f"missing={sorted(expected_components - supplied)} "
                f"extra={sorted(supplied - expected_components)}"
            )

    components = {}
    total_eligible = 0
    total_records = 0
    for component_id in sorted(expected_components):
        binding = dict(
            direct
            if component_id == DIRECT_RESEARCH_COMPONENT_ID
            else launchpads[component_id]
        )
        binding_sha = _canonical_sha(binding)
        report = dict(component_reports[component_id])
        report_version = str(report.get("version") or "")
        if report_version not in _ALLOWED_REPORT_VERSIONS:
            raise ValueError(
                f"{component_id} research report version changed"
            )
        if str(
            report.get("component_id")
            or report.get("source_id")
            or ""
        ) != component_id:
            raise ValueError(
                f"{component_id} research report component drift"
            )
        if sorted(report.get("source_ids") or []) != sorted(
            binding.get("source_ids") or []
        ):
            raise ValueError(
                f"{component_id} research report source set changed"
            )
        if _sha256(
            report.get("source_binding_sha256"),
            label=f"{component_id} report source binding",
        ) != binding_sha:
            raise ValueError(
                f"{component_id} research source-binding SHA drift"
            )
        if _sha256(
            report.get("rehydration_plan_sha256"),
            label=f"{component_id} report plan",
        ) != plan_sha:
            raise ValueError(
                f"{component_id} research plan SHA drift"
            )
        if _sha256(
            report.get("eligible_universe_sha256"),
            label=f"{component_id} report universe",
        ) != universe_sha:
            raise ValueError(
                f"{component_id} research universe SHA drift"
            )
        if report.get("eligible_token_coverage_complete") is not True:
            raise ValueError(
                f"{component_id} eligible-token coverage is incomplete"
            )
        if report.get("research_component_ready") is not True:
            raise ValueError(
                f"{component_id} research component is not ready"
            )
        if report.get("dump_threshold_frozen") is not False:
            raise ValueError(
                f"{component_id} prematurely freezes dump threshold"
            )
        if report.get("outcome_labels_computed") is not False:
            raise ValueError(
                f"{component_id} prematurely computes outcome labels"
            )
        if not _full_inputs_validated(report):
            raise ValueError(
                f"{component_id} full input validation is not proven"
            )

        handoff = dict(component_handoffs[component_id])
        run_id = int(handoff.get("run_id", 0))
        if run_id <= 0:
            raise ValueError(
                f"{component_id} handoff run id is invalid"
            )
        expected_name = f"phase2-research-handoff-{component_id}"
        if str(handoff.get("artifact_name") or "") != expected_name:
            raise ValueError(
                f"{component_id} handoff artifact name changed"
            )
        artifact_digest = _artifact_digest(
            handoff.get("artifact_digest"),
            label=f"{component_id} handoff",
        )
        report_sha = _sha256(
            handoff.get("report_sha256"),
            label=f"{component_id} handoff report",
        )

        manifest_proofs = _validate_manifest_proofs(
            component_id,
            report,
            component_manifest_proofs[component_id],
            source_binding_sha256=binding_sha,
        )
        eligible = _eligible_count(report)
        records = sum(
            int(row["records"])
            for row in manifest_proofs
        )
        total_eligible += eligible
        total_records += records
        components[component_id] = {
            "run_id": run_id,
            "artifact_name": expected_name,
            "artifact_digest": artifact_digest,
            "report_sha256": report_sha,
            "report_version": report_version,
            "source_ids": sorted(binding.get("source_ids") or []),
            "source_binding_sha256": binding_sha,
            "eligible_tokens": eligible,
            "materialized_records": records,
            "output_manifests": manifest_proofs,
            "research_component_ready": True,
        }

    return {
        "version": PHASE2_RESEARCH_MATERIALIZATION_BUNDLE_VERSION,
        "chain_id": int(plan.get("chain_id", 0)),
        "snapshot_head_block": int(plan["snapshot_head_block"]),
        "rehydration_plan_sha256": plan_sha,
        "eligible_universe_sha256": universe_sha,
        "coverage_ledger_sha256": _sha256(
            plan.get("coverage_ledger_sha256"),
            label="research materialization coverage ledger",
        ),
        "components": components,
        "component_count": len(components),
        "source_count": int(plan["source_count"]),
        "eligible_source_memberships": total_eligible,
        "materialized_records": total_records,
        "all_components_ready": True,
        "research_price_paths_materialized": True,
        "phase2_dump_detector_frozen": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }


def build_phase2_research_materialization_handoff(
    bundle: Mapping[str, object],
    *,
    bundle_sha256: str,
) -> dict:
    bundle = dict(bundle)
    if (
        str(bundle.get("version") or "")
        != PHASE2_RESEARCH_MATERIALIZATION_BUNDLE_VERSION
    ):
        raise ValueError("research materialization bundle version changed")
    if bundle.get("all_components_ready") is not True:
        raise ValueError("research materialization bundle is not ready")
    if bundle.get("research_price_paths_materialized") is not True:
        raise ValueError("research price paths are not fully materialized")
    if bundle.get("phase2_dump_detector_frozen") is not False:
        raise ValueError("materialization handoff cannot freeze dump detector")
    if bundle.get("outcome_labels_computed") is not False:
        raise ValueError("materialization handoff cannot contain labels")
    return {
        "version": PHASE2_RESEARCH_MATERIALIZATION_HANDOFF_VERSION,
        "chain_id": int(bundle["chain_id"]),
        "snapshot_head_block": int(bundle["snapshot_head_block"]),
        "bundle_sha256": _sha256(
            bundle_sha256,
            label="research materialization bundle",
        ),
        "rehydration_plan_sha256": bundle["rehydration_plan_sha256"],
        "eligible_universe_sha256": bundle["eligible_universe_sha256"],
        "component_count": int(bundle["component_count"]),
        "source_count": int(bundle["source_count"]),
        "all_components_ready": True,
        "research_price_paths_materialized": True,
        "phase2_dump_detector_frozen": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }
