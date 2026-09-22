"""Resolve exact Phase-2 research rehydration inputs from frozen provenance."""

from __future__ import annotations

import hashlib
import json
from typing import Iterable, Mapping

from hlp.data.phase2_eligibility import PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION
from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION


PHASE2_RESEARCH_REHYDRATION_SEED_VERSION = (
    "phase2-research-rehydration-seed-v1"
)
PHASE2_RESEARCH_LAUNCHPAD_BINDING_VERSION = (
    "phase2-research-launchpad-binding-v1"
)
PHASE2_RESEARCH_DIRECT_BINDING_VERSION = (
    "phase2-research-direct-binding-v1"
)
PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION = (
    "phase2-research-rehydration-plan-v1"
)
PHASE2_UNIVERSE_PROVENANCE_VERSION = "phase2-universe-provenance-v1"
PHASE2_UNIVERSE_FREEZE_HANDOFF_VERSION = "phase2-universe-freeze-handoff-v1"
LAUNCHPAD_ELIGIBILITY_PROVENANCE_VERSION = (
    "phase2-launchpad-eligibility-provenance-v1"
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
    return hashlib.sha256(raw).hexdigest()


def _positive_run_id(value: object, *, label: str) -> int:
    run_id = int(value)
    if run_id <= 0:
        raise ValueError(f"{label} run id is invalid")
    return run_id


def build_phase2_research_rehydration_seed(
    universe_summary: Mapping[str, object],
    universe_provenance: Mapping[str, object],
    universe_freeze_handoff: Mapping[str, object],
    *,
    source_inventory: Iterable[Mapping[str, object]],
    universe_sha256: str,
) -> dict:
    """Bind the research root to the exact frozen-universe source handoffs."""

    summary = dict(universe_summary)
    provenance = dict(universe_provenance)
    handoff = dict(universe_freeze_handoff)
    inventory = [dict(row) for row in source_inventory]

    if str(summary.get("version") or "") != PHASE2_UNIVERSE_VERSION:
        raise ValueError("research rehydration requires canonical universe summary")
    if summary.get("phase2_universe_frozen") is not True:
        raise ValueError("research rehydration requires a frozen universe")
    if summary.get("coverage_complete") is not True:
        raise ValueError("research rehydration requires complete source coverage")
    if str(provenance.get("version") or "") != PHASE2_UNIVERSE_PROVENANCE_VERSION:
        raise ValueError("research rehydration universe provenance version changed")
    if str(handoff.get("version") or "") != PHASE2_UNIVERSE_FREEZE_HANDOFF_VERSION:
        raise ValueError("research rehydration universe handoff version changed")
    if handoff.get("phase2_universe_frozen") is not True:
        raise ValueError("research rehydration handoff is not frozen")
    if handoff.get("phase2_universe_coverage_complete") is not True:
        raise ValueError("research rehydration handoff coverage is incomplete")

    universe_sha = _sha256(universe_sha256, label="eligible universe")
    if universe_sha != _sha256(
        summary.get("eligible_universe_sha256"),
        label="universe summary eligible universe",
    ):
        raise ValueError("research rehydration eligible-universe SHA drift")
    if universe_sha != _sha256(
        handoff.get("eligible_universe_sha256"),
        label="universe handoff eligible universe",
    ):
        raise ValueError("research rehydration handoff universe SHA drift")

    provenance_sha = _canonical_sha(provenance)
    if provenance_sha != _sha256(
        summary.get("eligibility_provenance_sha256"),
        label="universe summary provenance",
    ):
        raise ValueError("research rehydration universe provenance SHA drift")
    if provenance_sha != _sha256(
        handoff.get("eligibility_provenance_sha256"),
        label="universe handoff provenance",
    ):
        raise ValueError("research rehydration handoff provenance SHA drift")

    coverage_ledger_sha = _sha256(
        provenance.get("coverage_ledger_sha256"),
        label="universe provenance coverage ledger",
    )
    if coverage_ledger_sha != _sha256(
        summary.get("coverage_ledger_sha256"),
        label="universe summary coverage ledger",
    ):
        raise ValueError("research rehydration coverage-ledger SHA drift")
    if coverage_ledger_sha != _sha256(
        handoff.get("coverage_ledger_sha256"),
        label="universe handoff coverage ledger",
    ):
        raise ValueError("research rehydration handoff coverage-ledger SHA drift")

    snapshot = int(summary.get("snapshot_head_block", -1))
    if snapshot <= 0:
        raise ValueError("research rehydration snapshot is invalid")
    if int(provenance.get("snapshot_head_block", -1)) != snapshot:
        raise ValueError("research rehydration provenance snapshot drift")
    if int(handoff.get("snapshot_head_block", -1)) != snapshot:
        raise ValueError("research rehydration handoff snapshot drift")

    inventory_by_id = {
        str(row["source_id"]): row
        for row in inventory
    }
    if len(inventory_by_id) != 14:
        raise ValueError("research rehydration requires the 14-source inventory")
    launchpads = {
        source_id
        for source_id, row in inventory_by_id.items()
        if row.get("source_kind") == "launchpad"
    }
    directs = {
        source_id
        for source_id, row in inventory_by_id.items()
        if row.get("source_kind") == "direct_dex"
    }
    if len(launchpads) != 11 or len(directs) != 3:
        raise ValueError("research rehydration source-kind split changed")

    source_handoffs = provenance.get("source_handoffs")
    if not isinstance(source_handoffs, Mapping):
        raise ValueError("research rehydration source handoffs are missing")
    if {str(value) for value in source_handoffs} != set(inventory_by_id):
        raise ValueError("research rehydration source handoff set changed")

    components = {}
    for source_id in sorted(launchpads):
        raw = dict(source_handoffs[source_id])
        components[source_id] = {
            "component_id": source_id,
            "source_ids": [source_id],
            "source_kind": "launchpad",
            "handoff_run_id": _positive_run_id(
                raw.get("run_id"),
                label=source_id,
            ),
            "handoff_artifact_name": (
                f"phase2-launchpad-eligibility-{source_id}"
            ),
            "handoff_artifact_digest": _artifact_digest(
                raw.get("artifact_digest"),
                label=f"{source_id} handoff",
            ),
            "handoff_summary_sha256": _sha256(
                raw.get("summary_sha256"),
                label=f"{source_id} handoff summary",
            ),
            "requires_price_rehydration": True,
        }

    direct_rows = [dict(source_handoffs[source_id]) for source_id in sorted(directs)]
    direct_identity = {
        (
            _positive_run_id(row.get("run_id"), label="direct handoff"),
            _artifact_digest(
                row.get("artifact_digest"),
                label="direct handoff",
            ),
            _sha256(
                row.get("handoff_sha256"),
                label="direct handoff file",
            ),
        )
        for row in direct_rows
    }
    if len(direct_identity) != 1:
        raise ValueError("research rehydration direct handoff identity split")
    direct_run, direct_digest, direct_handoff_sha = next(iter(direct_identity))
    components[DIRECT_RESEARCH_COMPONENT_ID] = {
        "component_id": DIRECT_RESEARCH_COMPONENT_ID,
        "source_ids": sorted(directs),
        "source_kind": "direct_dex",
        "handoff_run_id": direct_run,
        "handoff_artifact_name": "phase2-direct-eligibility-handoff",
        "handoff_artifact_digest": direct_digest,
        "handoff_sha256": direct_handoff_sha,
        "requires_price_rehydration": False,
        "canonical_points_path": "direct-canonical-market-cap-points.jsonl",
    }

    return {
        "version": PHASE2_RESEARCH_REHYDRATION_SEED_VERSION,
        "chain_id": int(provenance.get("chain_id", 0)),
        "snapshot_head_block": snapshot,
        "eligible_universe_sha256": universe_sha,
        "universe_provenance_sha256": provenance_sha,
        "coverage_ledger_sha256": coverage_ledger_sha,
        "components": dict(sorted(components.items())),
        "component_count": len(components),
        "launchpad_components": len(launchpads),
        "direct_components": 1,
        "source_count": len(inventory_by_id),
        "source_handoffs_exact": True,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }


def resolve_launchpad_rehydration_binding(
    seed: Mapping[str, object],
    source_id: str,
    eligibility_summary: Mapping[str, object],
    eligibility_provenance: Mapping[str, object],
) -> dict:
    """Resolve one launchpad handoff to its accepted coverage/raw eligibility inputs."""

    source_id = str(source_id)
    components = seed.get("components")
    if not isinstance(components, Mapping) or source_id not in components:
        raise ValueError(f"launchpad rehydration component is missing: {source_id}")
    component = dict(components[source_id])
    if component.get("source_kind") != "launchpad":
        raise ValueError(f"rehydration component is not a launchpad: {source_id}")

    summary = dict(eligibility_summary)
    provenance = dict(eligibility_provenance)
    if (
        str(summary.get("version") or "")
        != PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION
    ):
        raise ValueError(f"{source_id} eligibility summary version changed")
    if str(summary.get("source_id") or "") != source_id:
        raise ValueError(f"{source_id} eligibility summary source drift")
    if summary.get("phase2_universe_source_ready") is not True:
        raise ValueError(f"{source_id} eligibility source is not ready")
    if summary.get("phase2_universe_frozen") is not False:
        raise ValueError(f"{source_id} eligibility prematurely freezes universe")

    if (
        str(provenance.get("version") or "")
        != LAUNCHPAD_ELIGIBILITY_PROVENANCE_VERSION
    ):
        raise ValueError(f"{source_id} eligibility provenance version changed")
    if str(provenance.get("source_id") or "") != source_id:
        raise ValueError(f"{source_id} eligibility provenance source drift")
    provenance_sha = _canonical_sha(provenance)
    if provenance_sha != _sha256(
        summary.get("eligibility_provenance_sha256"),
        label=f"{source_id} eligibility provenance",
    ):
        raise ValueError(f"{source_id} eligibility provenance SHA drift")
    if _sha256(
        provenance.get("coverage_provenance_sha256"),
        label=f"{source_id} coverage provenance",
    ) != _sha256(
        summary.get("coverage_provenance_sha256"),
        label=f"{source_id} eligibility coverage provenance",
    ):
        raise ValueError(f"{source_id} coverage provenance drift")

    return {
        "version": PHASE2_RESEARCH_LAUNCHPAD_BINDING_VERSION,
        "component_id": source_id,
        "source_ids": [source_id],
        "handoff_run_id": int(component["handoff_run_id"]),
        "handoff_artifact_name": component["handoff_artifact_name"],
        "handoff_artifact_digest": component["handoff_artifact_digest"],
        "coverage_run_id": _positive_run_id(
            provenance.get("coverage_run_id"),
            label=f"{source_id} coverage",
        ),
        "coverage_artifact_name": str(
            provenance.get("coverage_artifact_name") or ""
        ),
        "coverage_artifact_digest": _artifact_digest(
            provenance.get("coverage_artifact_digest"),
            label=f"{source_id} coverage",
        ),
        "coverage_report_path": str(
            provenance.get("coverage_report_path") or ""
        ),
        "coverage_report_sha256": _sha256(
            provenance.get("coverage_report_sha256"),
            label=f"{source_id} coverage report",
        ),
        "coverage_provenance_sha256": _sha256(
            provenance.get("coverage_provenance_sha256"),
            label=f"{source_id} coverage provenance",
        ),
        "eligibility_run_id": _positive_run_id(
            provenance.get("eligibility_run_id"),
            label=f"{source_id} raw eligibility",
        ),
        "eligibility_artifact_name": str(
            provenance.get("eligibility_artifact_name") or ""
        ),
        "eligibility_artifact_digest": _artifact_digest(
            provenance.get("eligibility_artifact_digest"),
            label=f"{source_id} raw eligibility",
        ),
        "eligibility_summary_path": str(
            provenance.get("eligibility_summary_path") or ""
        ),
        "eligibility_summary_sha256": _sha256(
            provenance.get("eligibility_summary_sha256"),
            label=f"{source_id} raw eligibility summary",
        ),
        "requires_price_rehydration": True,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }


def resolve_direct_rehydration_binding(
    seed: Mapping[str, object],
    direct_handoff: Mapping[str, object],
) -> dict:
    """Bind the direct research component to all three accepted coverage tapes."""

    components = seed.get("components")
    if not isinstance(components, Mapping):
        raise ValueError("direct rehydration seed components are missing")
    component = dict(components.get(DIRECT_RESEARCH_COMPONENT_ID) or {})
    if component.get("source_kind") != "direct_dex":
        raise ValueError("direct rehydration component is missing")

    handoff = dict(direct_handoff)
    coverage = handoff.get("coverage_bindings")
    if not isinstance(coverage, Mapping):
        raise ValueError("direct rehydration coverage bindings are missing")
    expected = set(component["source_ids"])
    if {str(value) for value in coverage} != expected:
        raise ValueError("direct rehydration coverage source set changed")

    normalized = {}
    for source_id in sorted(expected):
        row = dict(coverage[source_id])
        normalized[source_id] = {
            "run_id": _positive_run_id(
                row.get("run_id"),
                label=source_id,
            ),
            "artifact_digest": _artifact_digest(
                row.get("artifact_digest"),
                label=source_id,
            ),
            "coverage_report_sha256": _sha256(
                row.get("coverage_report_sha256"),
                label=f"{source_id} coverage report",
            ),
            "market_points_sha256": _sha256(
                row.get("market_points_sha256"),
                label=f"{source_id} market points",
            ),
            "coverage_provenance_sha256": _sha256(
                row.get("coverage_provenance_sha256"),
                label=f"{source_id} coverage provenance",
            ),
        }

    return {
        "version": PHASE2_RESEARCH_DIRECT_BINDING_VERSION,
        "component_id": DIRECT_RESEARCH_COMPONENT_ID,
        "source_ids": sorted(expected),
        "handoff_run_id": int(component["handoff_run_id"]),
        "handoff_artifact_name": component["handoff_artifact_name"],
        "handoff_artifact_digest": component["handoff_artifact_digest"],
        "canonical_points_path": component["canonical_points_path"],
        "coverage_bindings": normalized,
        "requires_price_rehydration": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }



def build_phase2_research_rehydration_plan(
    seed: Mapping[str, object],
    launchpad_bindings: Mapping[str, Mapping[str, object]],
    direct_binding: Mapping[str, object],
) -> dict:
    """Assemble a compact immutable identity plan before shard downloads."""

    if (
        str(seed.get("version") or "")
        != PHASE2_RESEARCH_REHYDRATION_SEED_VERSION
    ):
        raise ValueError("research rehydration seed version changed")
    components = seed.get("components")
    if not isinstance(components, Mapping):
        raise ValueError("research rehydration seed components are missing")

    expected_launchpads = {
        str(component_id)
        for component_id, raw in components.items()
        if dict(raw).get("source_kind") == "launchpad"
    }
    if {str(value) for value in launchpad_bindings} != expected_launchpads:
        raise ValueError("research rehydration launchpad binding set changed")

    normalized_launchpads = {}
    for source_id in sorted(expected_launchpads):
        binding = dict(launchpad_bindings[source_id])
        component = dict(components[source_id])
        if (
            str(binding.get("version") or "")
            != PHASE2_RESEARCH_LAUNCHPAD_BINDING_VERSION
        ):
            raise ValueError(
                f"{source_id} research launchpad binding version changed"
            )
        if str(binding.get("component_id") or "") != source_id:
            raise ValueError(
                f"{source_id} research launchpad component drift"
            )
        if int(binding.get("handoff_run_id", -1)) != int(
            component["handoff_run_id"]
        ):
            raise ValueError(
                f"{source_id} research launchpad handoff run drift"
            )
        if str(binding.get("handoff_artifact_name") or "") != str(
            component["handoff_artifact_name"]
        ):
            raise ValueError(
                f"{source_id} research launchpad artifact name drift"
            )
        if _artifact_digest(
            binding.get("handoff_artifact_digest"),
            label=f"{source_id} research handoff",
        ) != component["handoff_artifact_digest"]:
            raise ValueError(
                f"{source_id} research launchpad artifact digest drift"
            )
        if binding.get("requires_price_rehydration") is not True:
            raise ValueError(
                f"{source_id} research launchpad unexpectedly skips rehydration"
            )
        if binding.get("dump_threshold_frozen") is not False:
            raise ValueError(
                f"{source_id} research launchpad freezes dump threshold"
            )
        if binding.get("outcome_labels_computed") is not False:
            raise ValueError(
                f"{source_id} research launchpad contains outcome labels"
            )
        normalized_launchpads[source_id] = binding

    direct_component = dict(
        components.get(DIRECT_RESEARCH_COMPONENT_ID) or {}
    )
    direct = dict(direct_binding)
    if (
        str(direct.get("version") or "")
        != PHASE2_RESEARCH_DIRECT_BINDING_VERSION
    ):
        raise ValueError("research direct binding version changed")
    if (
        str(direct.get("component_id") or "")
        != DIRECT_RESEARCH_COMPONENT_ID
    ):
        raise ValueError("research direct component id changed")
    if sorted(direct.get("source_ids") or []) != sorted(
        direct_component.get("source_ids") or []
    ):
        raise ValueError("research direct source set changed")
    if int(direct.get("handoff_run_id", -1)) != int(
        direct_component.get("handoff_run_id", -2)
    ):
        raise ValueError("research direct handoff run drift")
    if str(direct.get("handoff_artifact_name") or "") != str(
        direct_component.get("handoff_artifact_name") or ""
    ):
        raise ValueError("research direct handoff artifact name drift")
    if _artifact_digest(
        direct.get("handoff_artifact_digest"),
        label="research direct handoff",
    ) != direct_component.get("handoff_artifact_digest"):
        raise ValueError("research direct handoff artifact digest drift")
    if direct.get("requires_price_rehydration") is not False:
        raise ValueError("research direct canonical tape should already exist")
    if direct.get("dump_threshold_frozen") is not False:
        raise ValueError("research direct binding freezes dump threshold")
    if direct.get("outcome_labels_computed") is not False:
        raise ValueError("research direct binding contains outcome labels")

    return {
        "version": PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION,
        "chain_id": int(seed.get("chain_id", 0)),
        "snapshot_head_block": int(seed["snapshot_head_block"]),
        "eligible_universe_sha256": _sha256(
            seed.get("eligible_universe_sha256"),
            label="research plan universe",
        ),
        "universe_provenance_sha256": _sha256(
            seed.get("universe_provenance_sha256"),
            label="research plan universe provenance",
        ),
        "coverage_ledger_sha256": _sha256(
            seed.get("coverage_ledger_sha256"),
            label="research plan coverage ledger",
        ),
        "launchpad_bindings": normalized_launchpads,
        "direct_binding": direct,
        "component_count": int(seed["component_count"]),
        "source_count": int(seed["source_count"]),
        "source_handoffs_exact": True,
        "research_price_paths_materialized": False,
        "dump_threshold_frozen": False,
        "phase2_dump_detector_frozen": False,
        "outcome_labels_computed": False,
    }
