"""Deterministic execution DAG for incomplete Phase-2 source coverage."""

from __future__ import annotations

from typing import Iterable, Mapping

from hlp.data.phase2_coverage import validate_phase2_coverage_ledger


PHASE2_COVERAGE_EXECUTION_PLAN_VERSION = (
    "phase2-coverage-execution-plan-v1"
)

COVERAGE_NODE_BY_SOURCE = {
    "pools_fun": "coverage:pools_fun",
    "pools_trade_instant": "coverage:pools_trade_instant",
    "pools_trade_lbp": "coverage:pools_trade_lbp",
    "doppler": "coverage:doppler",
    "flap": "coverage:flap",
    "trench_today": "coverage:trench_today",
    "hood_fun_current": "coverage:hood_fun_current",
    "hood_fun_previous": "coverage:hood_fun_previous",
    "noxa": "coverage:noxa",
    "direct_uniswap_v3": "coverage:direct_uniswap_v3",
    "direct_uniswap_v4": "coverage:direct_uniswap_v4",
    "direct_sushiswap_v3": "coverage:direct_sushiswap_v3",
}


def _node(
    node_id: str,
    workflow: str,
    *,
    kind: str,
    depends_on: tuple[str, ...] = (),
    requires_archive_secret: bool = False,
    requires_explicit_approval: bool = False,
    notes: str,
) -> dict:
    return {
        "node_id": node_id,
        "workflow": workflow,
        "kind": kind,
        "depends_on": list(depends_on),
        "requires_archive_secret": requires_archive_secret,
        "requires_explicit_approval": requires_explicit_approval,
        "manual_action": False,
        "notes": notes,
    }


def build_phase2_coverage_execution_nodes() -> list[dict]:
    """Return the frozen workflow dependency graph before ledger promotion."""

    rows = [
        _node(
            "preflight:archive_authenticated",
            "phase2-archive-rpc-preflight.yml",
            kind="execution_preflight",
            requires_archive_secret=True,
            notes=(
                "Fail fast unless the authenticated archive route can read "
                "historical state and a filtered-log window wider than the "
                "200-block public cap."
            ),
        ),
        _node(
            "shared:quote_registry",
            "phase2-direct-quote-registry.yml",
            kind="shared_acquisition",
            notes="Freeze canonical quote assets, decimals, and USD feeds.",
        ),
        _node(
            "shared:v3_pool_created",
            "phase2-direct-v3-pool-created-backfill.yml",
            kind="shared_acquisition",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Acquire full-history Uniswap V3 and Sushi V3 PoolCreated "
                "surfaces once for all dependent sources."
            ),
        ),
        _node(
            "shared:v3_initialize",
            "phase2-direct-v3-initialize-backfill.yml",
            kind="shared_acquisition",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Acquire the shared V3 Initialize tape from block 8,930 "
                "through the frozen snapshot."
            ),
        ),
        _node(
            "shared:v4_initialize",
            "phase2-direct-uniswap-v4-initialize-backfill.yml",
            kind="shared_acquisition",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Acquire the shared V4 Initialize tape from block 9,070 "
                "through the frozen snapshot."
            ),
        ),
        _node(
            "shared:v3_swap",
            "phase2-direct-v3-swap-backfill.yml",
            kind="shared_acquisition",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Acquire the shared V3 Swap tape once for launchpad and "
                "direct-source replay."
            ),
        ),
        _node(
            "shared:v4_swap",
            "phase2-direct-v4-swap-backfill.yml",
            kind="shared_acquisition",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Acquire the shared V4 Swap tape once for launchpad and "
                "direct-source replay."
            ),
        ),
        _node(
            "shared:supply_delta",
            "phase2-direct-supply-delta-backfill.yml",
            kind="shared_acquisition",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Acquire the shared ERC-20 mint/burn supply-delta tape "
                "once for all dependent replays."
            ),
        ),
        _node(
            "shared:direct_market_registry",
            "phase2-direct-market-registry-backfill.yml",
            kind="shared_derivation",
            depends_on=(
                "shared:quote_registry",
                "shared:v3_pool_created",
                "shared:v3_initialize",
                "shared:v4_initialize",
            ),
            requires_archive_secret=True,
            notes=(
                "Build exact V3/Sushi/V4 direct-market registries from "
                "shared discovery and Initialize evidence."
            ),
        ),
        _node(
            "shared:direct_competition_cohort",
            "phase2-direct-market-competition-cohort.yml",
            kind="selector_research",
            depends_on=("shared:direct_market_registry",),
            notes=(
                "Freeze the real competing-market cohort used to evaluate "
                "the causal multi-pool selector."
            ),
        ),
        _node(
            "shared:direct_quality_evidence",
            "phase2-direct-market-quality-evidence.yml",
            kind="selector_research",
            depends_on=(
                "shared:quote_registry",
                "shared:direct_market_registry",
                "shared:direct_competition_cohort",
                "shared:v3_initialize",
                "shared:v3_swap",
                "shared:v4_initialize",
                "shared:v4_swap",
                "shared:supply_delta",
            ),
            requires_archive_secret=True,
            notes=(
                "Measure active quote liquidity and causal market quality "
                "on the frozen competition cohort."
            ),
        ),
        _node(
            "shared:direct_selector_freeze",
            "phase2-direct-market-selector-freeze.yml",
            kind="manual_freeze_gate",
            depends_on=("shared:direct_quality_evidence",),
            requires_explicit_approval=True,
            notes=(
                "Requires explicit approval of "
                "active-quote-liquidity-causal-v1 from the exact evidence."
            ),
        ),
        _node(
            "shared:direct_origin_attribution",
            "phase2-direct-origin-pons-attribution.yml",
            kind="shared_derivation",
            depends_on=("shared:direct_market_registry",),
            notes=(
                "Attribute direct-market token origins against the accepted "
                "Pons populations before direct-launch isolation."
            ),
        ),
        _node(
            "shared:direct_launch_population",
            "phase2-direct-launch-population.yml",
            kind="shared_derivation",
            depends_on=("shared:direct_origin_attribution",),
            notes=(
                "Build the direct-launch token population from exact "
                "attribution evidence."
            ),
        ),
        _node(
            "shared:direct_source_population",
            "phase2-direct-source-population-handoff.yml",
            kind="shared_derivation",
            depends_on=(
                "shared:direct_launch_population",
                "shared:direct_selector_freeze",
            ),
            notes=(
                "Combine the direct-launch population with the frozen "
                "multi-pool selector for the three direct DEX sources."
            ),
        ),
        _node(
            "registry:pools_fun",
            "phase2-pools-fun-registry-backfill.yml",
            kind="source_registry",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes="Backfill the complete pools.fun launch registry.",
        ),
        _node(
            "coverage:pools_fun",
            "phase2-pools-fun-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "registry:pools_fun",
                "shared:v3_initialize",
                "shared:v3_swap",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes="Reconstruct and price complete pools.fun history.",
        ),
        _node(
            "registry:pools_trade_launcher",
            "phase2-pools-trade-launcher-backfill.yml",
            kind="source_registry",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Backfill the shared pools.trade launcher surface used by "
                "Instant and LBP strategies."
            ),
        ),
        _node(
            "registry:pools_trade_instant",
            "phase2-pools-trade-instant-registry-backfill.yml",
            kind="source_registry",
            depends_on=(
                "registry:pools_trade_launcher",
                "shared:v4_initialize",
            ),
            requires_archive_secret=True,
            notes="Build the complete pools.trade Instant market registry.",
        ),
        _node(
            "coverage:pools_trade_instant",
            "phase2-pools-trade-instant-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "registry:pools_trade_instant",
                "shared:v4_swap",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Replay and price pools.trade Instant through the snapshot."
            ),
        ),
        _node(
            "registry:pools_trade_lbp",
            "phase2-pools-trade-lbp-registry-backfill.yml",
            kind="source_registry",
            depends_on=("registry:pools_trade_launcher",),
            requires_archive_secret=True,
            notes="Build the complete pools.trade LBP initializer registry.",
        ),
        _node(
            "derive:pools_trade_lbp_cca",
            "phase2-pools-trade-lbp-cca-backfill.yml",
            kind="source_derivation",
            depends_on=(
                "registry:pools_trade_lbp",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Reconstruct finalized CCA bid/exit history and exact "
                "token-fill/refund accounting."
            ),
        ),
        _node(
            "coverage:pools_trade_lbp",
            "phase2-pools-trade-lbp-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "derive:pools_trade_lbp_cca",
                "shared:v4_initialize",
                "shared:v4_swap",
            ),
            requires_archive_secret=True,
            notes=(
                "Combine CCA and migrated-V4 history into complete LBP "
                "coverage."
            ),
        ),
        _node(
            "registry:doppler",
            "phase2-doppler-registry-backfill.yml",
            kind="source_registry",
            depends_on=(
                "shared:v4_initialize",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes="Backfill Doppler launch and market registry evidence.",
        ),
        _node(
            "coverage:doppler",
            "phase2-doppler-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "registry:doppler",
                "shared:v4_swap",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes="Replay and price complete Doppler history.",
        ),
        _node(
            "registry:flap",
            "phase2-flap-registry-backfill.yml",
            kind="source_registry",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes="Backfill the complete Flap lifecycle registry.",
        ),
        _node(
            "derive:flap_curve",
            "phase2-flap-curve-coverage.yml",
            kind="source_derivation",
            depends_on=(
                "registry:flap",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes="Reconstruct and price Flap bonding-curve history.",
        ),
        _node(
            "coverage:flap",
            "phase2-flap-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "registry:flap",
                "derive:flap_curve",
                "shared:direct_market_registry",
                "shared:v3_swap",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Join curve and any post-curve direct V3 lifecycle into "
                "complete Flap coverage."
            ),
        ),
        _node(
            "registry:trench",
            "phase2-trench-registry-backfill.yml",
            kind="source_registry",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Backfill trench.today lifecycle events and exact launch "
                "supply/decimals."
            ),
        ),
        _node(
            "derive:trench_curve",
            "phase2-trench-curve-coverage.yml",
            kind="source_derivation",
            depends_on=(
                "registry:trench",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Reconstruct priced trench curve history through LimitReach."
            ),
        ),
        _node(
            "derive:trench_market_evidence",
            "phase2-trench-limit-market-evidence.yml",
            kind="source_derivation",
            depends_on=(
                "registry:trench",
                "shared:direct_market_registry",
            ),
            notes=(
                "Build exact LimitReach-to-direct-market candidate evidence."
            ),
        ),
        _node(
            "derive:trench_handoff_freeze",
            "phase2-trench-limit-handoff-freeze.yml",
            kind="source_derivation",
            depends_on=("derive:trench_market_evidence",),
            notes=(
                "Freeze the same-transaction-after LimitReach handoff only "
                "when every qualifying token is unambiguous."
            ),
        ),
        _node(
            "coverage:trench_today",
            "phase2-trench-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "registry:trench",
                "derive:trench_curve",
                "derive:trench_handoff_freeze",
                "shared:direct_market_registry",
                "shared:v3_initialize",
                "shared:v4_initialize",
                "shared:v3_swap",
                "shared:v4_swap",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Combine complete curve and selected post-limit direct-market "
                "history for trench.today."
            ),
        ),
        _node(
            "coverage:hood_fun_current",
            "phase2-hoodfun-current-coverage.yml",
            kind="source_coverage",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Backfill and validate complete current-generation hood.fun "
                "coverage."
            ),
        ),
        _node(
            "derive:hood_fun_previous_semantics",
            "phase2-hoodfun-legacy-curve-semantics.yml",
            kind="source_derivation",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes=(
                "Prove previous-generation supply and virtual-reserve curve "
                "semantics before full coverage."
            ),
        ),
        _node(
            "coverage:hood_fun_previous",
            "phase2-hoodfun-previous-coverage.yml",
            kind="source_coverage",
            depends_on=("derive:hood_fun_previous_semantics",),
            requires_archive_secret=True,
            notes=(
                "Backfill previous-generation hood.fun using the exact "
                "semantic-proof identity."
            ),
        ),
        _node(
            "registry:noxa",
            "phase2-noxa-registry-backfill.yml",
            kind="source_registry",
            depends_on=("preflight:archive_authenticated",),
            requires_archive_secret=True,
            notes="Backfill the complete NOXA launch registry.",
        ),
        _node(
            "coverage:noxa",
            "phase2-noxa-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "registry:noxa",
                "shared:v3_initialize",
                "shared:v3_swap",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes="Replay and price complete NOXA V3 history.",
        ),
        _node(
            "coverage:direct_uniswap_v3",
            "phase2-direct-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "shared:direct_source_population",
                "shared:v3_initialize",
                "shared:v3_swap",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Reconstruct the selected direct Uniswap V3 source population."
            ),
        ),
        _node(
            "coverage:direct_uniswap_v4",
            "phase2-direct-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "shared:direct_source_population",
                "shared:v4_initialize",
                "shared:v4_swap",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Reconstruct the selected direct Uniswap V4 source population."
            ),
        ),
        _node(
            "coverage:direct_sushiswap_v3",
            "phase2-direct-source-coverage.yml",
            kind="source_coverage",
            depends_on=(
                "shared:direct_source_population",
                "shared:v3_initialize",
                "shared:v3_swap",
                "shared:supply_delta",
                "shared:quote_registry",
            ),
            requires_archive_secret=True,
            notes=(
                "Reconstruct the selected direct SushiSwap V3 source "
                "population."
            ),
        ),
    ]
    _validate_node_graph(rows)
    return rows


def _validate_node_graph(rows: list[dict]) -> None:
    by_id = {}
    for row in rows:
        node_id = str(row.get("node_id") or "")
        if not node_id or node_id in by_id:
            raise ValueError(
                f"Phase-2 execution node id is invalid: {node_id!r}"
            )
        by_id[node_id] = row
    for row in rows:
        node_id = row["node_id"]
        dependencies = list(row.get("depends_on") or [])
        if len(dependencies) != len(set(dependencies)):
            raise ValueError(
                f"Phase-2 execution node repeats dependency: {node_id}"
            )
        unknown = sorted(set(dependencies) - set(by_id))
        if unknown:
            raise ValueError(
                f"Phase-2 execution node has unknown dependencies: "
                f"{node_id} -> {unknown}"
            )
        if node_id in dependencies:
            raise ValueError(
                f"Phase-2 execution node depends on itself: {node_id}"
            )

    visiting = set()
    visited = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError(
                f"Phase-2 execution graph has a cycle at {node_id}"
            )
        visiting.add(node_id)
        for dependency in by_id[node_id]["depends_on"]:
            visit(dependency)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in by_id:
        visit(node_id)


def _dependency_closure(
    node_id: str,
    by_id: Mapping[str, Mapping[str, object]],
) -> set[str]:
    output = {node_id}
    for dependency in by_id[node_id]["depends_on"]:
        output.update(_dependency_closure(dependency, by_id))
    return output


def _depth(
    node_id: str,
    by_id: Mapping[str, Mapping[str, object]],
    memo: dict[str, int],
) -> int:
    if node_id in memo:
        return memo[node_id]
    dependencies = list(by_id[node_id].get("depends_on") or [])
    result = (
        0
        if not dependencies
        else 1 + max(_depth(value, by_id, memo) for value in dependencies)
    )
    memo[node_id] = result
    return result


def _promotion_node(
    source_id: str,
    coverage_node_id: str,
    *,
    previous_commit_node_id: str | None,
) -> dict:
    dependencies = [coverage_node_id]
    if previous_commit_node_id is not None:
        dependencies.append(previous_commit_node_id)
    return {
        "node_id": f"promote:{source_id}",
        "workflow": "phase2-source-coverage-promotion.yml",
        "kind": "coverage_promotion",
        "depends_on": dependencies,
        "requires_archive_secret": False,
        "requires_explicit_approval": False,
        "manual_action": False,
        "notes": (
            "Validate the exact complete coverage artifact and emit a "
            "proposed canonical ledger. This workflow does not mutate the "
            "repository ledger."
        ),
    }


def _manual_commit_node(source_id: str) -> dict:
    return {
        "node_id": f"ledger_commit:{source_id}",
        "workflow": None,
        "kind": "manual_ledger_commit",
        "depends_on": [f"promote:{source_id}"],
        "requires_archive_secret": False,
        "requires_explicit_approval": False,
        "manual_action": True,
        "notes": (
            "Review the proposed ledger and commit it to "
            ".github/phase2-source-coverage.json, then regenerate this plan. "
            "Do not mark this node completed through planner input."
        ),
    }


def build_phase2_coverage_execution_plan(
    ledger: Mapping[str, object],
    source_inventory: Iterable[Mapping[str, object]],
    *,
    completed_node_ids: Iterable[str] = (),
) -> dict:
    """Build the execution DAG for only the currently incomplete sources."""

    inventory_rows = [dict(row) for row in source_inventory]
    report = validate_phase2_coverage_ledger(ledger, inventory_rows)
    complete = set(report["complete_source_ids"])
    inventory_order = [
        str(row["source_id"])
        for row in inventory_rows
    ]
    incomplete = [
        source_id
        for source_id in inventory_order
        if source_id not in complete
    ]

    unsupported = [
        source_id
        for source_id in incomplete
        if source_id not in COVERAGE_NODE_BY_SOURCE
    ]
    if unsupported:
        raise ValueError(
            "Phase-2 execution planner has no coverage workflow for "
            f"incomplete sources: {unsupported}"
        )

    static_rows = build_phase2_coverage_execution_nodes()
    static_by_id = {
        row["node_id"]: dict(row)
        for row in static_rows
    }
    needed_ids = set()
    required_for: dict[str, set[str]] = {}
    for source_id in incomplete:
        coverage_node = COVERAGE_NODE_BY_SOURCE[source_id]
        closure = _dependency_closure(coverage_node, static_by_id)
        needed_ids.update(closure)
        for node_id in closure:
            required_for.setdefault(node_id, set()).add(source_id)

    declared = [str(value) for value in completed_node_ids]
    if len(declared) != len(set(declared)):
        raise ValueError("Phase-2 execution plan repeats completed node ids")
    declared_set = set(declared)

    possible_dynamic = {
        f"{prefix}:{source_id}"
        for source_id in COVERAGE_NODE_BY_SOURCE
        for prefix in ("promote", "ledger_commit")
    }
    known_ids = set(static_by_id) | possible_dynamic
    unknown_completed = sorted(declared_set - known_ids)
    if unknown_completed:
        raise ValueError(
            "Phase-2 execution plan has unknown completed nodes: "
            f"{unknown_completed}"
        )
    manual_declared = sorted(
        node_id
        for node_id in declared_set
        if node_id.startswith("ledger_commit:")
    )
    if manual_declared:
        raise ValueError(
            "manual ledger commits must be represented by the canonical "
            f"ledger, not completed_node_ids: {manual_declared}"
        )

    promotion_candidates = [
        source_id
        for source_id in incomplete
        if (
            COVERAGE_NODE_BY_SOURCE[source_id] in declared_set
            or f"promote:{source_id}" in declared_set
        )
    ]
    previous_commit = None
    dynamic_rows = []
    for source_id in incomplete:
        promotion = _promotion_node(
            source_id,
            COVERAGE_NODE_BY_SOURCE[source_id],
            previous_commit_node_id=(
                previous_commit
                if source_id in promotion_candidates
                else None
            ),
        )
        commit = _manual_commit_node(source_id)
        dynamic_rows.extend((promotion, commit))
        required_for[promotion["node_id"]] = {source_id}
        required_for[commit["node_id"]] = {source_id}
        needed_ids.update((promotion["node_id"], commit["node_id"]))
        if source_id in promotion_candidates:
            previous_commit = commit["node_id"]

    all_rows = [
        dict(row)
        for row in static_rows
        if row["node_id"] in needed_ids
    ] + dynamic_rows
    by_id = {row["node_id"]: row for row in all_rows}
    _validate_node_graph(all_rows)

    ignored_completed = sorted(
        node_id
        for node_id in declared_set
        if node_id not in needed_ids
    )
    active_completed = declared_set & needed_ids

    for node_id in sorted(active_completed):
        unresolved = [
            dependency
            for dependency in by_id[node_id]["depends_on"]
            if dependency not in active_completed
        ]
        if unresolved:
            raise ValueError(
                "completed Phase-2 execution node has incomplete "
                f"dependencies: {node_id} -> {unresolved}"
            )

    depth_memo: dict[str, int] = {}
    output_rows = []
    for raw in all_rows:
        row = dict(raw)
        node_id = row["node_id"]
        dependencies = list(row["depends_on"])
        unresolved = [
            value
            for value in dependencies
            if value not in active_completed
        ]
        if node_id in active_completed:
            status = "completed"
        elif unresolved:
            status = "blocked_by_dependencies"
        elif row["manual_action"]:
            status = "manual_ledger_commit_required"
        elif row["requires_explicit_approval"]:
            status = "awaiting_explicit_approval"
        else:
            status = "ready_to_dispatch"

        row.update({
            "stage": _depth(node_id, by_id, depth_memo),
            "status": status,
            "unresolved_dependencies": unresolved,
            "required_for_sources": sorted(
                required_for.get(node_id, set())
            ),
        })
        output_rows.append(row)

    output_rows.sort(
        key=lambda row: (
            int(row["stage"]),
            str(row["node_id"]),
        )
    )
    ready = [
        row for row in output_rows
        if row["status"] == "ready_to_dispatch"
    ]
    approval = [
        row["node_id"] for row in output_rows
        if row["status"] == "awaiting_explicit_approval"
    ]
    manual = [
        row["node_id"] for row in output_rows
        if row["status"] == "manual_ledger_commit_required"
    ]
    blocked = [
        row["node_id"] for row in output_rows
        if row["status"] == "blocked_by_dependencies"
    ]
    completed = [
        row["node_id"] for row in output_rows
        if row["status"] == "completed"
    ]

    source_paths = {}
    for source_id in incomplete:
        target = COVERAGE_NODE_BY_SOURCE[source_id]
        base_path = _dependency_closure(target, static_by_id)
        path_ids = set(base_path)
        path_ids.update({
            f"promote:{source_id}",
            f"ledger_commit:{source_id}",
        })
        source_paths[source_id] = [
            row["node_id"]
            for row in output_rows
            if row["node_id"] in path_ids
        ]

    return {
        "version": PHASE2_COVERAGE_EXECUTION_PLAN_VERSION,
        "snapshot_head_block": int(report["snapshot_head_block"]),
        "inventory_sources": int(report["inventory_sources"]),
        "canonical_complete_source_ids": [
            source_id
            for source_id in inventory_order
            if source_id in complete
        ],
        "target_incomplete_source_ids": incomplete,
        "complete_sources": len(complete),
        "incomplete_sources": len(incomplete),
        "phase2_universe_coverage_complete": bool(
            report["phase2_universe_coverage_complete"]
        ),
        "promotion_order_if_ready": promotion_candidates,
        "nodes": output_rows,
        "source_paths": source_paths,
        "operator_declared_completed_node_ids": sorted(active_completed),
        "ignored_completed_node_ids": ignored_completed,
        "ready_to_dispatch_node_ids": [
            row["node_id"] for row in ready
        ],
        "ready_without_archive_secret_node_ids": [
            row["node_id"]
            for row in ready
            if not row["requires_archive_secret"]
        ],
        "ready_requiring_archive_secret_node_ids": [
            row["node_id"]
            for row in ready
            if row["requires_archive_secret"]
        ],
        "awaiting_explicit_approval_node_ids": approval,
        "manual_ledger_commit_node_ids": manual,
        "blocked_node_ids": blocked,
        "completed_node_ids": completed,
        "coverage_acquisition_parallelizable": True,
        "ledger_promotion_serialized": True,
        "canonical_ledger_mutation_automatic": False,
        "canonical_ledger_is_source_of_truth": True,
        "operator_completion_assertions_are_planning_only": True,
        "workflow_dispatch_performed": False,
    }
