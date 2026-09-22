"""Generate Phase-2 workflow dispatch inputs from verified DAG run receipts."""

from __future__ import annotations

import re
from typing import Mapping

from hlp.data.phase2_coverage_execution import COVERAGE_NODE_BY_SOURCE


PHASE2_DISPATCH_INPUT_PLAN_VERSION = "phase2-dispatch-input-plan-v1"

RUN_ID_INPUT_BINDINGS: dict[str, dict[str, str]] = {
    "shared:direct_market_registry": {
        "quote_run_id": "shared:quote_registry",
        "v3_pool_created_run_id": "shared:v3_pool_created",
        "v3_initialize_run_id": "shared:v3_initialize",
        "v4_initialize_run_id": "shared:v4_initialize",
    },
    "shared:direct_competition_cohort": {
        "registry_run_id": "shared:direct_market_registry",
    },
    "shared:direct_quality_evidence": {
        "quote_run_id": "shared:quote_registry",
        "registry_run_id": "shared:direct_market_registry",
        "cohort_run_id": "shared:direct_competition_cohort",
        "v3_initialize_run_id": "shared:v3_initialize",
        "v3_swap_run_id": "shared:v3_swap",
        "v4_initialize_run_id": "shared:v4_initialize",
        "v4_swap_run_id": "shared:v4_swap",
        "supply_delta_run_id": "shared:supply_delta",
    },
    "shared:direct_selector_freeze": {
        "evidence_run_id": "shared:direct_quality_evidence",
    },
    "shared:direct_origin_attribution": {
        "registry_run_id": "shared:direct_market_registry",
    },
    "shared:direct_launch_population": {
        "attribution_run_id": "shared:direct_origin_attribution",
    },
    "shared:direct_source_population": {
        "direct_launch_run_id": "shared:direct_launch_population",
        "selector_run_id": "shared:direct_selector_freeze",
    },
    "coverage:pools_fun": {
        "registry_run_id": "registry:pools_fun",
        "v3_initialize_run_id": "shared:v3_initialize",
        "v3_swap_run_id": "shared:v3_swap",
        "quote_run_id": "shared:quote_registry",
    },
    "registry:pools_trade_instant": {
        "launcher_run_id": "registry:pools_trade_launcher",
        "v4_initialize_run_id": "shared:v4_initialize",
    },
    "coverage:pools_trade_instant": {
        "registry_run_id": "registry:pools_trade_instant",
        "v4_swap_run_id": "shared:v4_swap",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
    "registry:pools_trade_lbp": {
        "launcher_run_id": "registry:pools_trade_launcher",
    },
    "derive:pools_trade_lbp_cca": {
        "registry_run_id": "registry:pools_trade_lbp",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
    "coverage:pools_trade_lbp": {
        "cca_run_id": "derive:pools_trade_lbp_cca",
        "v4_initialize_run_id": "shared:v4_initialize",
        "v4_swap_run_id": "shared:v4_swap",
    },
    "registry:doppler": {
        "v4_initialize_run_id": "shared:v4_initialize",
        "quote_run_id": "shared:quote_registry",
    },
    "coverage:doppler": {
        "registry_run_id": "registry:doppler",
        "v4_swap_run_id": "shared:v4_swap",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
    "derive:flap_curve": {
        "registry_run_id": "registry:flap",
        "quote_run_id": "shared:quote_registry",
    },
    "coverage:flap": {
        "registry_run_id": "registry:flap",
        "curve_run_id": "derive:flap_curve",
        "direct_registry_run_id": "shared:direct_market_registry",
        "v3_swap_run_id": "shared:v3_swap",
        "quote_run_id": "shared:quote_registry",
    },
    "derive:trench_curve": {
        "registry_run_id": "registry:trench",
        "quote_run_id": "shared:quote_registry",
    },
    "derive:trench_market_evidence": {
        "registry_run_id": "registry:trench",
        "direct_registry_run_id": "shared:direct_market_registry",
    },
    "derive:trench_handoff_freeze": {
        "evidence_run_id": "derive:trench_market_evidence",
    },
    "coverage:trench_today": {
        "registry_run_id": "registry:trench",
        "curve_run_id": "derive:trench_curve",
        "handoff_run_id": "derive:trench_handoff_freeze",
        "direct_registry_run_id": "shared:direct_market_registry",
        "v3_initialize_run_id": "shared:v3_initialize",
        "v4_initialize_run_id": "shared:v4_initialize",
        "v3_swap_run_id": "shared:v3_swap",
        "v4_swap_run_id": "shared:v4_swap",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
    "coverage:hood_fun_previous": {
        "semantics_run_id": "derive:hood_fun_previous_semantics",
    },
    "coverage:noxa": {
        "registry_run_id": "registry:noxa",
        "v3_initialize_run_id": "shared:v3_initialize",
        "v3_swap_run_id": "shared:v3_swap",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
    "coverage:direct_uniswap_v3": {
        "population_run_id": "shared:direct_source_population",
        "initialize_run_id": "shared:v3_initialize",
        "swap_run_id": "shared:v3_swap",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
    "coverage:direct_sushiswap_v3": {
        "population_run_id": "shared:direct_source_population",
        "initialize_run_id": "shared:v3_initialize",
        "swap_run_id": "shared:v3_swap",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
    "coverage:direct_uniswap_v4": {
        "population_run_id": "shared:direct_source_population",
        "initialize_run_id": "shared:v4_initialize",
        "swap_run_id": "shared:v4_swap",
        "supply_delta_run_id": "shared:supply_delta",
        "quote_run_id": "shared:quote_registry",
    },
}

_INPUT_KEY = re.compile(r"^      ([A-Za-z0-9_]+):\s*$")


def _bindings_for_node(node_id: str) -> dict[str, str]:
    bindings = RUN_ID_INPUT_BINDINGS.get(node_id)
    if bindings is not None:
        return dict(bindings)
    if node_id.startswith("promote:"):
        source_id = node_id.split(":", 1)[1]
        if source_id not in COVERAGE_NODE_BY_SOURCE:
            raise ValueError(
                f"unknown Phase-2 promotion source: {source_id}"
            )
        return {
            "coverage_run_id": COVERAGE_NODE_BY_SOURCE[source_id],
        }
    if node_id.startswith("ledger_commit:"):
        source_id = node_id.split(":", 1)[1]
        if source_id not in COVERAGE_NODE_BY_SOURCE:
            raise ValueError(
                f"unknown Phase-2 ledger-commit source: {source_id}"
            )
        return {
            "promotion_run_id": f"promote:{source_id}",
        }
    return {}


def extract_workflow_dispatch_inputs(text: str) -> list[str]:
    """Extract top-level workflow_dispatch input names from workflow YAML."""

    lines = str(text).splitlines()
    in_dispatch = False
    in_inputs = False
    result = []
    for line in lines:
        if line == "  workflow_dispatch:":
            in_dispatch = True
            in_inputs = False
            continue
        if in_dispatch and line == "    inputs:":
            in_inputs = True
            continue
        if not in_dispatch:
            continue

        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if line and indent <= 2 and not line.startswith("  #"):
            break
        if in_inputs and line and indent <= 4 and line != "    inputs:":
            break
        if in_inputs:
            match = _INPUT_KEY.match(line)
            if match:
                result.append(match.group(1))
    return result


def _receipt_run_ids(
    verified_receipts: Mapping[str, object],
) -> dict[str, int]:
    rows = verified_receipts.get("receipts")
    if not isinstance(rows, list):
        raise ValueError("verified execution receipts are missing")
    output = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise ValueError("verified execution receipt row is invalid")
        node_id = str(raw.get("node_id") or "")
        try:
            run_id = int(raw.get("run_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"verified run ID is invalid for {node_id!r}"
            ) from exc
        if not node_id or run_id <= 0:
            raise ValueError("verified execution receipt identity is invalid")
        if node_id in output:
            raise ValueError(
                f"verified execution receipts repeat node: {node_id}"
            )
        output[node_id] = run_id
    return output


def build_phase2_dispatch_input_plan(
    execution_plan: Mapping[str, object],
    verified_receipts: Mapping[str, object],
    *,
    workflow_text_by_name: Mapping[str, str],
) -> dict:
    """Build run-ID inputs and unresolved manual inputs for dispatchable nodes."""

    nodes = execution_plan.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Phase-2 execution plan nodes are missing")
    run_ids = _receipt_run_ids(verified_receipts)

    targets = []
    for raw in nodes:
        if not isinstance(raw, Mapping):
            raise ValueError("Phase-2 execution node row is invalid")
        row = dict(raw)
        status = str(row.get("status") or "")
        if status not in {
            "ready_to_dispatch",
            "awaiting_explicit_approval",
            "ledger_commit_approval_required",
        }:
            continue
        node_id = str(row.get("node_id") or "")
        workflow = row.get("workflow")
        if not isinstance(workflow, str) or not workflow:
            raise ValueError(
                f"dispatchable node has no workflow: {node_id}"
            )
        if workflow not in workflow_text_by_name:
            raise ValueError(
                f"workflow text is missing for dispatchable node: {node_id}"
            )

        dispatch_inputs = extract_workflow_dispatch_inputs(
            workflow_text_by_name[workflow]
        )
        bindings = _bindings_for_node(node_id)
        dependencies = set(
            str(value)
            for value in row.get("depends_on") or []
        )
        invalid_dependencies = sorted(
            set(bindings.values()) - dependencies
        )
        if invalid_dependencies:
            raise ValueError(
                f"{node_id} run-input bindings are not DAG dependencies: "
                f"{invalid_dependencies}"
            )

        run_inputs = {}
        for input_name, dependency in sorted(bindings.items()):
            if input_name not in dispatch_inputs:
                raise ValueError(
                    f"{node_id} workflow lost dispatch input {input_name}"
                )
            if dependency not in run_ids:
                raise ValueError(
                    f"{node_id} lacks verified run receipt for "
                    f"dependency {dependency}"
                )
            run_inputs[input_name] = str(run_ids[dependency])

        manual_inputs = sorted(
            set(dispatch_inputs) - set(run_inputs)
        )
        targets.append({
            "node_id": node_id,
            "workflow": workflow,
            "status": status,
            "run_id_inputs": run_inputs,
            "remaining_manual_inputs": manual_inputs,
            "all_dispatch_input_names": dispatch_inputs,
            "requires_archive_secret": bool(
                row.get("requires_archive_secret")
            ),
            "requires_explicit_approval": bool(
                row.get("requires_explicit_approval")
            ),
        })

    targets.sort(key=lambda row: row["node_id"])
    return {
        "version": PHASE2_DISPATCH_INPUT_PLAN_VERSION,
        "dispatchable_nodes": len(targets),
        "nodes": targets,
        "run_id_inputs_generated_from_verified_receipts": True,
        "non_run_inputs_left_explicit": True,
        "workflow_dispatch_performed": False,
    }
