import hashlib
import json

import pytest

from hlp.data.phase2_eligibility import PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION
from hlp.data.phase2_research_paths import DIRECT_RESEARCH_COMPONENT_ID
from hlp.data.phase2_research_rehydration import (
    PHASE2_RESEARCH_REHYDRATION_SEED_VERSION,
    build_phase2_research_rehydration_plan,
    build_phase2_research_rehydration_seed,
    resolve_direct_rehydration_binding,
    resolve_launchpad_rehydration_binding,
)
from hlp.data.phase2_sources import build_phase2_source_inventory
from hlp.data.phase2_universe import PHASE2_UNIVERSE_VERSION


SHA = "ab" * 32
ALT_SHA = "cd" * 32
UNIVERSE_SHA = "ef" * 32


def canonical_sha(payload):
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def frozen_inputs():
    inventory = build_phase2_source_inventory()
    source_handoffs = {}
    direct_identity = {
        "run_id": 999,
        "artifact_digest": "sha256:" + ALT_SHA,
        "handoff_sha256": SHA,
    }
    for index, row in enumerate(inventory, start=1):
        source_id = row["source_id"]
        if row["source_kind"] == "direct_dex":
            source_handoffs[source_id] = dict(direct_identity)
        else:
            source_handoffs[source_id] = {
                "run_id": index,
                "artifact_digest": "sha256:" + SHA,
                "summary_sha256": ALT_SHA,
            }

    provenance = {
        "version": "phase2-universe-provenance-v1",
        "chain_id": 4663,
        "snapshot_head_block": 100,
        "coverage_ledger_sha256": SHA,
        "source_handoffs": source_handoffs,
        "direct_handoff_sha256": SHA,
        "exclusion_run_id": 55,
        "exclusion_artifact_digest": "sha256:" + SHA,
        "exclusion_summary_sha256": SHA,
        "exclusion_registry_sha256": SHA,
    }
    provenance_sha = canonical_sha(provenance)
    summary = {
        "version": PHASE2_UNIVERSE_VERSION,
        "snapshot_head_block": 100,
        "inventory_sources": 14,
        "eligible_tokens": 2,
        "coverage_complete": True,
        "phase2_universe_frozen": True,
        "coverage_ledger_sha256": SHA,
        "eligibility_provenance_sha256": provenance_sha,
        "eligible_universe_sha256": UNIVERSE_SHA,
    }
    handoff = {
        "version": "phase2-universe-freeze-handoff-v1",
        "snapshot_head_block": 100,
        "eligible_universe_sha256": UNIVERSE_SHA,
        "coverage_ledger_sha256": SHA,
        "eligibility_provenance_sha256": provenance_sha,
        "phase2_universe_coverage_complete": True,
        "phase2_universe_frozen": True,
    }
    return inventory, summary, provenance, handoff


def test_rehydration_seed_collapses_three_direct_sources_exactly_once():
    inventory, summary, provenance, handoff = frozen_inputs()

    seed = build_phase2_research_rehydration_seed(
        summary,
        provenance,
        handoff,
        source_inventory=inventory,
        universe_sha256=UNIVERSE_SHA,
    )

    assert seed["version"] == PHASE2_RESEARCH_REHYDRATION_SEED_VERSION
    assert seed["source_count"] == 14
    assert seed["launchpad_components"] == 11
    assert seed["direct_components"] == 1
    assert seed["component_count"] == 12
    direct = seed["components"][DIRECT_RESEARCH_COMPONENT_ID]
    assert len(direct["source_ids"]) == 3
    assert direct["requires_price_rehydration"] is False
    assert seed["dump_threshold_frozen"] is False
    assert seed["outcome_labels_computed"] is False


def test_rehydration_seed_rejects_direct_handoff_identity_split():
    inventory, summary, provenance, handoff = frozen_inputs()
    provenance["source_handoffs"]["direct_uniswap_v3"]["run_id"] = 1000
    provenance_sha = canonical_sha(provenance)
    summary["eligibility_provenance_sha256"] = provenance_sha
    handoff["eligibility_provenance_sha256"] = provenance_sha

    with pytest.raises(ValueError, match="direct handoff identity split"):
        build_phase2_research_rehydration_seed(
            summary,
            provenance,
            handoff,
            source_inventory=inventory,
            universe_sha256=UNIVERSE_SHA,
        )


def test_launchpad_binding_resolves_exact_coverage_and_raw_eligibility_inputs():
    inventory, summary, provenance, handoff = frozen_inputs()
    seed = build_phase2_research_rehydration_seed(
        summary,
        provenance,
        handoff,
        source_inventory=inventory,
        universe_sha256=UNIVERSE_SHA,
    )
    source_id = "pools_fun"
    eligibility_provenance = {
        "version": "phase2-launchpad-eligibility-provenance-v1",
        "chain_id": 4663,
        "source_id": source_id,
        "coverage_run_id": 321,
        "coverage_artifact_name": "coverage",
        "coverage_artifact_digest": "sha256:" + SHA,
        "coverage_report_path": "coverage.json",
        "coverage_report_sha256": SHA,
        "coverage_provenance_sha256": ALT_SHA,
        "eligibility_run_id": 654,
        "eligibility_artifact_name": "eligibility",
        "eligibility_artifact_digest": "sha256:" + ALT_SHA,
        "eligibility_summary_path": "summary.jsonl",
        "eligibility_summary_sha256": SHA,
    }
    eligibility_summary = {
        "version": PHASE2_LAUNCHPAD_ELIGIBILITY_VERSION,
        "source_id": source_id,
        "coverage_provenance_sha256": ALT_SHA,
        "eligibility_provenance_sha256": canonical_sha(
            eligibility_provenance
        ),
        "phase2_universe_source_ready": True,
        "phase2_universe_frozen": False,
    }

    binding = resolve_launchpad_rehydration_binding(
        seed,
        source_id,
        eligibility_summary,
        eligibility_provenance,
    )

    assert binding["coverage_run_id"] == 321
    assert binding["eligibility_run_id"] == 654
    assert binding["coverage_provenance_sha256"] == ALT_SHA
    assert binding["requires_price_rehydration"] is True


def test_direct_binding_keeps_all_three_coverage_tapes_under_one_component():
    inventory, summary, provenance, handoff = frozen_inputs()
    seed = build_phase2_research_rehydration_seed(
        summary,
        provenance,
        handoff,
        source_inventory=inventory,
        universe_sha256=UNIVERSE_SHA,
    )
    direct_sources = seed["components"][DIRECT_RESEARCH_COMPONENT_ID][
        "source_ids"
    ]
    direct_handoff = {
        "coverage_bindings": {
            source_id: {
                "run_id": index + 1,
                "artifact_digest": "sha256:" + SHA,
                "coverage_report_sha256": SHA,
                "market_points_sha256": ALT_SHA,
                "coverage_provenance_sha256": SHA,
            }
            for index, source_id in enumerate(direct_sources)
        }
    }

    binding = resolve_direct_rehydration_binding(
        seed,
        direct_handoff,
    )

    assert binding["component_id"] == DIRECT_RESEARCH_COMPONENT_ID
    assert set(binding["coverage_bindings"]) == set(direct_sources)
    assert binding["requires_price_rehydration"] is False



def test_rehydration_plan_refuses_identity_substitution_and_stays_unmaterialized():
    inventory, summary, provenance, handoff = frozen_inputs()
    seed = build_phase2_research_rehydration_seed(
        summary,
        provenance,
        handoff,
        source_inventory=inventory,
        universe_sha256=UNIVERSE_SHA,
    )

    launchpad_bindings = {}
    for source_id, component in seed["components"].items():
        if component["source_kind"] != "launchpad":
            continue
        launchpad_bindings[source_id] = {
            "version": "phase2-research-launchpad-binding-v1",
            "component_id": source_id,
            "source_ids": [source_id],
            "handoff_run_id": component["handoff_run_id"],
            "handoff_artifact_name": component["handoff_artifact_name"],
            "handoff_artifact_digest": component[
                "handoff_artifact_digest"
            ],
            "coverage_run_id": 100,
            "coverage_artifact_name": "coverage",
            "coverage_artifact_digest": "sha256:" + SHA,
            "coverage_report_path": "coverage.json",
            "coverage_report_sha256": SHA,
            "coverage_provenance_sha256": SHA,
            "eligibility_run_id": 200,
            "eligibility_artifact_name": "eligibility",
            "eligibility_artifact_digest": "sha256:" + SHA,
            "eligibility_summary_path": "summary.jsonl",
            "eligibility_summary_sha256": SHA,
            "requires_price_rehydration": True,
            "dump_threshold_frozen": False,
            "outcome_labels_computed": False,
        }

    direct_component = seed["components"][DIRECT_RESEARCH_COMPONENT_ID]
    direct_binding = {
        "version": "phase2-research-direct-binding-v1",
        "component_id": DIRECT_RESEARCH_COMPONENT_ID,
        "source_ids": direct_component["source_ids"],
        "handoff_run_id": direct_component["handoff_run_id"],
        "handoff_artifact_name": direct_component[
            "handoff_artifact_name"
        ],
        "handoff_artifact_digest": direct_component[
            "handoff_artifact_digest"
        ],
        "canonical_points_path": direct_component[
            "canonical_points_path"
        ],
        "coverage_bindings": {},
        "requires_price_rehydration": False,
        "dump_threshold_frozen": False,
        "outcome_labels_computed": False,
    }

    plan = build_phase2_research_rehydration_plan(
        seed,
        launchpad_bindings,
        direct_binding,
    )
    assert plan["component_count"] == 12
    assert plan["research_price_paths_materialized"] is False
    assert plan["dump_threshold_frozen"] is False
    assert plan["outcome_labels_computed"] is False

    launchpad_bindings["pools_fun"]["handoff_run_id"] += 1
    with pytest.raises(ValueError, match="handoff run drift"):
        build_phase2_research_rehydration_plan(
            seed,
            launchpad_bindings,
            direct_binding,
        )
