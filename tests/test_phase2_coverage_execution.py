from pathlib import Path

import pytest

from hlp.data.phase2_coverage_execution import (
    COVERAGE_NODE_BY_SOURCE,
    PHASE2_COVERAGE_EXECUTION_PLAN_VERSION,
    build_phase2_coverage_execution_nodes,
    build_phase2_coverage_execution_plan,
)
from hlp.data.phase2_sources import build_phase2_source_inventory


SNAPSHOT = 100
COMPLETE = {"pons_v1", "pons_v2"}


def ledger():
    inventory = build_phase2_source_inventory()
    rows = []
    for row in inventory:
        source_id = row["source_id"]
        base = {
            "source_id": source_id,
            "source_readiness": row["readiness"],
            "required_start_block": 0,
            "observed_volume_usd": None,
            "blocking_reason": None,
        }
        if source_id in COMPLETE:
            rows.append({
                **base,
                "coverage_status": "complete",
                "first_block": 0,
                "last_block": SNAPSHOT,
                "continuous": True,
                "missing_ranges": [],
                "tokens_discovered": 1,
                "price_points": 1,
                "priced_points": 1,
                "provenance_sha256": "ab" * 32,
            })
        else:
            rows.append({
                **base,
                "coverage_status": "not_started",
                "first_block": None,
                "last_block": None,
                "continuous": None,
                "missing_ranges": [],
                "tokens_discovered": 0,
                "price_points": 0,
                "priced_points": 0,
                "provenance_sha256": None,
            })
    return {
        "version": "phase2-source-coverage-v1",
        "snapshot_head_block": SNAPSHOT,
        "sources": rows,
    }


def build(completed=()):
    return build_phase2_coverage_execution_plan(
        ledger(),
        build_phase2_source_inventory(),
        completed_node_ids=completed,
    )


def closure(node_id):
    rows = {
        row["node_id"]: row
        for row in build_phase2_coverage_execution_nodes()
    }
    output = set()

    def visit(value):
        if value in output:
            return
        output.add(value)
        for dependency in rows[value]["depends_on"]:
            visit(dependency)

    visit(node_id)
    return output


def test_execution_graph_references_existing_workflows():
    root = Path(".github/workflows")
    for row in build_phase2_coverage_execution_nodes():
        assert row["workflow"]
        assert (root / row["workflow"]).is_file(), row["node_id"]


def test_current_shape_targets_twelve_sources_and_shared_spine():
    report = build()

    assert report["version"] == PHASE2_COVERAGE_EXECUTION_PLAN_VERSION
    assert report["complete_sources"] == 2
    assert report["incomplete_sources"] == 12
    assert report["canonical_complete_source_ids"] == [
        "pons_v1",
        "pons_v2",
    ]
    assert set(report["target_incomplete_source_ids"]) == set(
        COVERAGE_NODE_BY_SOURCE
    )
    ready = set(report["ready_to_dispatch_node_ids"])
    assert ready == {
        "preflight:archive_authenticated",
        "shared:quote_registry",
    }
    assert report[
        "ready_requiring_archive_secret_node_ids"
    ] == ["preflight:archive_authenticated"]
    assert report[
        "ready_without_archive_secret_node_ids"
    ] == ["shared:quote_registry"]
    assert "shared:v3_initialize" not in ready
    assert "coverage:pools_fun" not in ready
    assert report["coverage_acquisition_parallelizable"] is True
    assert report["ledger_promotion_serialized"] is True
    assert report["canonical_ledger_mutation_automatic"] is False
    assert report["workflow_dispatch_performed"] is False


def test_selector_freeze_waits_for_explicit_approval():
    completed = closure("shared:direct_quality_evidence")
    report = build(completed)
    by_id = {row["node_id"]: row for row in report["nodes"]}

    selector = by_id["shared:direct_selector_freeze"]
    assert selector["status"] == "awaiting_explicit_approval"
    assert selector["requires_explicit_approval"] is True
    assert "shared:direct_selector_freeze" in (
        report["awaiting_explicit_approval_node_ids"]
    )


def test_promotions_serialize_only_sources_with_finished_coverage():
    initial = build()
    base_nodes = {
        row["node_id"]
        for row in initial["nodes"]
        if row["kind"] not in {
            "coverage_promotion",
            "manual_ledger_commit",
        }
    }
    report = build(base_nodes)
    by_id = {row["node_id"]: row for row in report["nodes"]}

    assert by_id["promote:pools_fun"]["status"] == "ready_to_dispatch"
    assert by_id["promote:pools_trade_instant"]["status"] == (
        "blocked_by_dependencies"
    )
    assert by_id["promote:pools_trade_instant"][
        "unresolved_dependencies"
    ] == ["ledger_commit:pools_fun"]

    after_promotion = build(base_nodes | {"promote:pools_fun"})
    by_id = {
        row["node_id"]: row
        for row in after_promotion["nodes"]
    }
    assert by_id["ledger_commit:pools_fun"]["status"] == (
        "manual_ledger_commit_required"
    )
    assert by_id["promote:pools_trade_instant"]["status"] == (
        "blocked_by_dependencies"
    )


def test_later_finished_source_can_promote_when_earlier_coverage_is_not_done():
    completed = closure("coverage:hood_fun_current")
    report = build(completed)
    by_id = {row["node_id"]: row for row in report["nodes"]}

    assert by_id["promote:hood_fun_current"]["status"] == (
        "ready_to_dispatch"
    )
    assert by_id["promote:pools_fun"]["status"] == (
        "blocked_by_dependencies"
    )


def test_completed_nodes_must_include_dependency_closure():
    with pytest.raises(ValueError, match="incomplete dependencies"):
        build({"coverage:pools_fun"})


def test_manual_ledger_commit_cannot_be_declared_complete():
    with pytest.raises(ValueError, match="canonical ledger"):
        build({"ledger_commit:pools_fun"})



def test_authenticated_preflight_unlocks_archive_batch():
    report = build({"preflight:archive_authenticated"})
    ready = set(report["ready_to_dispatch_node_ids"])

    assert "shared:quote_registry" in ready
    assert "shared:v3_pool_created" in ready
    assert "shared:v3_initialize" in ready
    assert "shared:v4_initialize" in ready
    assert "shared:v3_swap" in ready
    assert "shared:v4_swap" in ready
    assert "shared:supply_delta" in ready
    assert "registry:pools_fun" in ready
    assert "registry:pools_trade_launcher" in ready
    assert "registry:flap" in ready
    assert "registry:trench" in ready
    assert "coverage:hood_fun_current" in ready
    assert "derive:hood_fun_previous_semantics" in ready
    assert "registry:noxa" in ready



def test_archive_secret_nodes_fail_closed_without_public_chunk_fallback():
    root = Path(".github/workflows")
    for row in build_phase2_coverage_execution_nodes():
        if not row["requires_archive_secret"]:
            continue
        text = (root / row["workflow"]).read_text()
        assert "ROBINHOOD_ARCHIVE_RPC_API_KEY" in text, row["node_id"]
        if row["node_id"] == "preflight:archive_authenticated":
            assert (
                "ROBINHOOD_ARCHIVE_RPC_API_KEY is not configured"
                in text
            )
        else:
            assert (
                "ROBINHOOD_ARCHIVE_RPC_API_KEY is required for "
                "Phase-2 full-history execution"
                in text
            ), row["node_id"]
        assert "CHUNK=200" not in text, row["node_id"]
