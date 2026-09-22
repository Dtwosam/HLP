from pathlib import Path

from hlp.data.phase2_coverage_execution import (
    build_phase2_coverage_execution_plan,
)
from hlp.data.phase2_execution_dispatch import (
    PHASE2_DISPATCH_INPUT_PLAN_VERSION,
    RUN_ID_INPUT_BINDINGS,
    build_phase2_dispatch_input_plan,
    extract_workflow_dispatch_inputs,
)
from hlp.data.phase2_sources import build_phase2_source_inventory


WORKFLOWS = Path(".github/workflows")
SHA = "ab" * 32
SNAPSHOT = 100


def ledger():
    rows = []
    for source in build_phase2_source_inventory():
        complete = source["source_id"] in {"pons_v1", "pons_v2"}
        rows.append({
            "source_id": source["source_id"],
            "source_readiness": source["readiness"],
            "coverage_status": "complete" if complete else "not_started",
            "required_start_block": 0,
            "first_block": 0 if complete else None,
            "last_block": SNAPSHOT if complete else None,
            "continuous": True if complete else None,
            "missing_ranges": [],
            "tokens_discovered": 1 if complete else 0,
            "price_points": 1 if complete else 0,
            "priced_points": 1 if complete else 0,
            "observed_volume_usd": None,
            "provenance_sha256": SHA if complete else None,
            "blocking_reason": None,
        })
    return {
        "version": "phase2-source-coverage-v1",
        "snapshot_head_block": SNAPSHOT,
        "sources": rows,
    }


def receipts(node_ids):
    return {
        "receipts": [
            {
                "node_id": node_id,
                "run_id": index + 100,
            }
            for index, node_id in enumerate(sorted(node_ids))
        ]
    }


def workflow_texts(plan):
    names = {
        row["workflow"]
        for row in plan["nodes"]
        if row.get("workflow")
    }
    return {
        name: (WORKFLOWS / name).read_text()
        for name in names
    }


def test_extract_workflow_dispatch_inputs_handles_no_input_workflow():
    text = (WORKFLOWS / "phase2-direct-quote-registry.yml").read_text()
    assert extract_workflow_dispatch_inputs(text) == []


def test_extract_workflow_dispatch_inputs_reads_declared_inputs():
    text = (
        WORKFLOWS / "phase2-pools-fun-source-coverage.yml"
    ).read_text()
    assert extract_workflow_dispatch_inputs(text) == [
        "registry_run_id",
        "v3_initialize_run_id",
        "v3_swap_run_id",
        "quote_run_id",
    ]


def test_every_run_id_binding_is_a_real_workflow_input_and_dependency():
    base = build_phase2_coverage_execution_plan(
        ledger(),
        build_phase2_source_inventory(),
    )
    nodes = {row["node_id"]: row for row in base["nodes"]}
    for node_id, bindings in RUN_ID_INPUT_BINDINGS.items():
        assert node_id in nodes
        workflow = nodes[node_id]["workflow"]
        input_names = set(
            extract_workflow_dispatch_inputs(
                (WORKFLOWS / workflow).read_text()
            )
        )
        assert set(bindings).issubset(input_names)
        assert set(bindings.values()).issubset(
            set(nodes[node_id]["depends_on"])
        )


def test_initial_dispatch_plan_has_preflight_and_quote_with_no_inputs():
    plan = build_phase2_coverage_execution_plan(
        ledger(),
        build_phase2_source_inventory(),
    )
    dispatch = build_phase2_dispatch_input_plan(
        plan,
        receipts([]),
        workflow_text_by_name=workflow_texts(plan),
    )
    assert dispatch["version"] == PHASE2_DISPATCH_INPUT_PLAN_VERSION
    assert dispatch["dispatchable_nodes"] == 2
    by_id = {row["node_id"]: row for row in dispatch["nodes"]}
    assert set(by_id) == {
        "preflight:archive_authenticated",
        "shared:quote_registry",
    }
    assert by_id["preflight:archive_authenticated"][
        "run_id_inputs"
    ] == {}
    assert by_id["shared:quote_registry"]["remaining_manual_inputs"] == []


def test_verified_dependencies_fill_run_ids_for_ready_coverage():
    completed = {
        "preflight:archive_authenticated",
        "shared:quote_registry",
        "shared:v3_initialize",
        "shared:v3_swap",
        "registry:pools_fun",
    }
    plan = build_phase2_coverage_execution_plan(
        ledger(),
        build_phase2_source_inventory(),
        completed_node_ids=completed,
    )
    dispatch = build_phase2_dispatch_input_plan(
        plan,
        receipts(completed),
        workflow_text_by_name=workflow_texts(plan),
    )
    by_id = {row["node_id"]: row for row in dispatch["nodes"]}
    inputs = by_id["coverage:pools_fun"]["run_id_inputs"]

    run_by_node = {
        row["node_id"]: str(row["run_id"])
        for row in receipts(completed)["receipts"]
    }
    assert inputs == {
        "quote_run_id": run_by_node["shared:quote_registry"],
        "registry_run_id": run_by_node["registry:pools_fun"],
        "v3_initialize_run_id": run_by_node["shared:v3_initialize"],
        "v3_swap_run_id": run_by_node["shared:v3_swap"],
    }
    assert by_id["coverage:pools_fun"][
        "remaining_manual_inputs"
    ] == []
