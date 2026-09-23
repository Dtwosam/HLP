import hashlib
import json

import pytest

from hlp.data.phase2_research_materialization_bundle import (
    PHASE2_RESEARCH_MATERIALIZATION_BUNDLE_VERSION,
    build_phase2_research_materialization_bundle,
    build_phase2_research_materialization_handoff,
)
from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID
from hlp.data.phase2_research_rehydration import (
    PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION,
)


SHA = "ab" * 32
ALT = "cd" * 32


def canonical_sha(payload):
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def fixture():
    launchpads = {
        f"source_{index}": {
            "source_ids": [f"source_{index}"],
            "handoff_run_id": index + 1,
            "handoff_artifact_name": f"handoff-{index}",
            "handoff_artifact_digest": "sha256:" + SHA,
        }
        for index in range(11)
    }
    direct = {
        "component_id": DIRECT_RESEARCH_COMPONENT_ID,
        "source_ids": ["direct_a", "direct_b", "direct_c"],
        "handoff_run_id": 99,
        "handoff_artifact_name": "direct",
        "handoff_artifact_digest": "sha256:" + SHA,
    }
    plan = {
        "version": PHASE2_RESEARCH_REHYDRATION_PLAN_VERSION,
        "chain_id": 4663,
        "snapshot_head_block": 100,
        "eligible_universe_sha256": SHA,
        "universe_provenance_sha256": SHA,
        "coverage_ledger_sha256": ALT,
        "launchpad_bindings": launchpads,
        "direct_binding": direct,
        "component_count": 12,
        "source_count": 14,
    }
    reports = {}
    handoffs = {}
    proofs = {}
    bindings = {**launchpads, DIRECT_RESEARCH_COMPONENT_ID: direct}
    for index, (component_id, binding) in enumerate(sorted(bindings.items())):
        output_sha = hashlib.sha256(component_id.encode()).hexdigest()
        reports[component_id] = {
            "version": "phase2-research-materialization-v1",
            "component_id": component_id,
            "source_ids": binding["source_ids"],
            "source_binding_sha256": canonical_sha(binding),
            "rehydration_plan_sha256": SHA,
            "eligible_universe_sha256": SHA,
            "expected_eligible_tokens": index,
            "observed_eligible_tokens": index,
            "eligible_token_coverage_complete": True,
            "materialized_records": index + 1,
            "materialized_sha256": output_sha,
            "full_input_validated": True,
            "research_component_ready": True,
            "dump_threshold_frozen": False,
            "outcome_labels_computed": False,
        }
        handoffs[component_id] = {
            "run_id": 1000 + index,
            "artifact_name": f"phase2-research-handoff-{component_id}",
            "artifact_digest": "sha256:" + ALT,
            "report_sha256": SHA,
        }
        proofs[component_id] = [{
            "path": f"{component_id}.jsonl",
            "records": index + 1,
            "sha256": output_sha,
            "provenance": {
                "source_binding_sha256": canonical_sha(binding),
                "dump_threshold_frozen": False,
                "outcome_labels_computed": False,
            },
        }]
    return plan, reports, handoffs, proofs


def test_materialization_bundle_freezes_all_12_components_without_dump_labels():
    plan, reports, handoffs, proofs = fixture()
    bundle = build_phase2_research_materialization_bundle(
        plan,
        rehydration_plan_sha256=SHA,
        component_reports=reports,
        component_handoffs=handoffs,
        component_manifest_proofs=proofs,
    )

    assert bundle["version"] == PHASE2_RESEARCH_MATERIALIZATION_BUNDLE_VERSION
    assert bundle["component_count"] == 12
    assert bundle["source_count"] == 14
    assert bundle["all_components_ready"] is True
    assert bundle["research_price_paths_materialized"] is True
    assert bundle["phase2_dump_detector_frozen"] is False
    assert bundle["outcome_labels_computed"] is False

    handoff = build_phase2_research_materialization_handoff(
        bundle,
        bundle_sha256=ALT,
    )
    assert handoff["component_count"] == 12
    assert handoff["research_price_paths_materialized"] is True
    assert handoff["phase2_dump_detector_frozen"] is False


def test_materialization_bundle_rejects_missing_component_or_premature_labels():
    plan, reports, handoffs, proofs = fixture()
    reports.pop("source_0")
    with pytest.raises(ValueError, match="component set changed"):
        build_phase2_research_materialization_bundle(
            plan,
            rehydration_plan_sha256=SHA,
            component_reports=reports,
            component_handoffs=handoffs,
            component_manifest_proofs=proofs,
        )

    plan, reports, handoffs, proofs = fixture()
    reports["source_0"]["outcome_labels_computed"] = True
    with pytest.raises(ValueError, match="prematurely computes"):
        build_phase2_research_materialization_bundle(
            plan,
            rehydration_plan_sha256=SHA,
            component_reports=reports,
            component_handoffs=handoffs,
            component_manifest_proofs=proofs,
        )
