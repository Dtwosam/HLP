"""Generate Phase-2 workflow dispatch inputs from verified DAG run receipts."""

from __future__ import annotations

import re
from typing import Mapping

from hlp.data.phase2_coverage_execution import COVERAGE_NODE_BY_SOURCE


PHASE2_DISPATCH_INPUT_PLAN_VERSION = "phase2-dispatch-input-plan-v1"
PHASE2_NODE_DISPATCH_REQUEST_VERSION = "phase2-node-dispatch-request-v1"
PHASE2_NODE_DISPATCH_ATTEMPT_VERSION = (
    "phase2-execution-node-dispatch-attempt-v1"
)
PHASE2_NODE_DISPATCH_RECEIPT_VERSION = "phase2-execution-node-dispatch-v1"

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



def _dispatch_input_value(value: object, *, label: str) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if not value:
            raise ValueError(f"{label} cannot be empty")
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise ValueError(
        f"{label} must be a string, integer, or boolean"
    )


def build_phase2_node_dispatch_request(
    dispatch_input_plan: Mapping[str, object],
    *,
    node_id: str,
    manual_inputs: Mapping[str, object],
) -> dict:
    """Prepare one exact non-approval workflow_dispatch request."""

    plan = dict(dispatch_input_plan)
    if str(plan.get("version") or "") != PHASE2_DISPATCH_INPUT_PLAN_VERSION:
        raise ValueError("Phase-2 dispatch input plan version changed")
    if plan.get("run_id_inputs_generated_from_verified_receipts") is not True:
        raise ValueError("Phase-2 dispatch plan lacks verified run inputs")
    if plan.get("non_run_inputs_left_explicit") is not True:
        raise ValueError("Phase-2 dispatch plan hides non-run inputs")
    if plan.get("workflow_dispatch_performed") is not False:
        raise ValueError("Phase-2 dispatch plan already claims dispatch")

    requested_node = str(node_id or "")
    rows = plan.get("nodes")
    if not isinstance(rows, list):
        raise ValueError("Phase-2 dispatch plan nodes are missing")
    matches = [
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
        and str(row.get("node_id") or "") == requested_node
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Phase-2 dispatch node must match exactly once: {requested_node}"
        )
    row = matches[0]
    if str(row.get("status") or "") != "ready_to_dispatch":
        raise ValueError(
            f"Phase-2 node is not ready_to_dispatch: {requested_node}"
        )
    if row.get("requires_explicit_approval") is not False:
        raise ValueError(
            f"Phase-2 node requires explicit approval: {requested_node}"
        )
    if requested_node.startswith("ledger_commit:"):
        raise ValueError(
            "Phase-2 canonical ledger writes cannot use the node dispatcher"
        )

    workflow = str(row.get("workflow") or "")
    if not workflow.endswith(".yml"):
        raise ValueError("Phase-2 dispatch workflow identity is invalid")

    run_inputs_raw = row.get("run_id_inputs")
    if not isinstance(run_inputs_raw, Mapping):
        raise ValueError("Phase-2 dispatch run_id_inputs are invalid")
    run_inputs = {
        str(name): _dispatch_input_value(
            value,
            label=f"{requested_node} run input {name}",
        )
        for name, value in run_inputs_raw.items()
    }

    remaining_raw = row.get("remaining_manual_inputs")
    all_raw = row.get("all_dispatch_input_names")
    if not isinstance(remaining_raw, list) or not isinstance(all_raw, list):
        raise ValueError("Phase-2 dispatch input-name lists are invalid")
    remaining = [str(value) for value in remaining_raw]
    all_names = [str(value) for value in all_raw]
    if len(remaining) != len(set(remaining)):
        raise ValueError("Phase-2 dispatch plan repeats a manual input name")
    if len(all_names) != len(set(all_names)):
        raise ValueError("Phase-2 dispatch plan repeats an input name")

    supplied = {
        str(name): _dispatch_input_value(
            value,
            label=f"{requested_node} manual input {name}",
        )
        for name, value in dict(manual_inputs).items()
    }
    missing = sorted(set(remaining) - set(supplied))
    extra = sorted(set(supplied) - set(remaining))
    if missing or extra:
        raise ValueError(
            f"Phase-2 dispatch manual input mismatch; "
            f"missing={missing} extra={extra}"
        )

    combined = {**run_inputs, **supplied}
    if set(combined) != set(all_names):
        raise ValueError(
            "Phase-2 dispatch combined inputs do not match workflow schema"
        )

    return {
        "version": PHASE2_NODE_DISPATCH_REQUEST_VERSION,
        "node_id": requested_node,
        "workflow": workflow,
        "inputs": combined,
        "input_names": sorted(combined),
        "requires_archive_secret": bool(
            row.get("requires_archive_secret")
        ),
        "requires_explicit_approval": False,
        "planner_status": "ready_to_dispatch",
        "workflow_dispatch_authorized": True,
        "canonical_ledger_write_authorized": False,
    }



def _sha256_hex(value: object, *, label: str) -> str:
    text = str(value or "").lower().removeprefix("sha256:")
    if len(text) != 64:
        raise ValueError(f"{label} must be 64 hex chars")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def _commit_sha(value: object, *, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 40:
        raise ValueError(f"{label} must be a 40-char commit SHA")
    try:
        int(text, 16)
    except ValueError as exc:
        raise ValueError(f"{label} is not hexadecimal") from exc
    return text


def validate_phase2_node_dispatch_attempt(
    attempt: Mapping[str, object],
) -> dict:
    """Validate evidence that GitHub already created a target workflow run."""

    row = dict(attempt)
    if str(row.get("version") or "") != PHASE2_NODE_DISPATCH_ATTEMPT_VERSION:
        raise ValueError("Phase-2 node-dispatch attempt version changed")

    node_id = str(row.get("node_id") or "")
    if not node_id:
        raise ValueError("Phase-2 node-dispatch attempt node_id is empty")
    if node_id.startswith("ledger_commit:"):
        raise ValueError(
            "Phase-2 node-dispatch attempt cannot authorize ledger commit"
        )

    workflow = str(row.get("target_workflow") or "")
    if not workflow.endswith(".yml"):
        raise ValueError(
            "Phase-2 node-dispatch attempt target workflow is invalid"
        )
    target_ref = str(row.get("target_ref") or "")
    if not target_ref:
        raise ValueError(
            "Phase-2 node-dispatch attempt target ref is empty"
        )
    target_head = _commit_sha(
        row.get("target_head_sha"),
        label="Phase-2 node-dispatch attempt target head",
    )
    control_run_id = int(
        row.get("node_dispatch_control_run_id") or 0
    )
    planner_run_id = int(row.get("planner_run_id") or 0)
    dispatched_run_id = int(row.get("dispatched_run_id") or 0)
    if (
        control_run_id <= 0
        or planner_run_id <= 0
        or dispatched_run_id <= 0
    ):
        raise ValueError(
            "Phase-2 node-dispatch attempt run IDs must be positive"
        )

    artifact_digest = str(
        row.get("planner_artifact_digest") or ""
    ).lower()
    if (
        not artifact_digest.startswith("sha256:")
        or len(artifact_digest) != 71
    ):
        raise ValueError(
            "Phase-2 node-dispatch attempt planner artifact digest is invalid"
        )
    _sha256_hex(
        artifact_digest,
        label="Phase-2 node-dispatch attempt planner artifact digest",
    )
    ledger_sha = _sha256_hex(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 node-dispatch attempt coverage ledger",
    )
    inputs_sha = _sha256_hex(
        row.get("dispatch_inputs_sha256"),
        label="Phase-2 node-dispatch attempt inputs",
    )

    input_names = row.get("dispatch_input_names")
    if not isinstance(input_names, list):
        raise ValueError(
            "Phase-2 node-dispatch attempt input names are invalid"
        )
    normalized_names = [str(value) for value in input_names]
    if len(normalized_names) != len(set(normalized_names)):
        raise ValueError(
            "Phase-2 node-dispatch attempt repeats an input name"
        )

    if row.get("requires_explicit_approval") is not False:
        raise ValueError(
            "Phase-2 node-dispatch attempt unexpectedly required approval"
        )
    if row.get("canonical_ledger_write_authorized") is not False:
        raise ValueError(
            "Phase-2 node-dispatch attempt authorizes ledger write"
        )
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError(
            "Phase-2 node-dispatch attempt does not prove dispatch"
        )
    if row.get("target_run_identity_verified") is not False:
        raise ValueError(
            "Phase-2 node-dispatch attempt must precede target verification"
        )

    return {
        "version": PHASE2_NODE_DISPATCH_ATTEMPT_VERSION,
        "node_id": node_id,
        "target_workflow": workflow,
        "target_ref": target_ref,
        "target_head_sha": target_head,
        "node_dispatch_control_run_id": control_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": artifact_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "dispatch_input_names": sorted(normalized_names),
        "dispatch_inputs_sha256": inputs_sha,
        "dispatched_run_id": dispatched_run_id,
        "requires_explicit_approval": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
        "target_run_identity_verified": False,
    }


def validate_phase2_node_dispatch_receipt(
    receipt: Mapping[str, object],
) -> dict:
    """Validate one immutable node-dispatch receipt before planner reuse."""

    row = dict(receipt)
    if str(row.get("version") or "") != PHASE2_NODE_DISPATCH_RECEIPT_VERSION:
        raise ValueError("Phase-2 node-dispatch receipt version changed")

    node_id = str(row.get("node_id") or "")
    if not node_id:
        raise ValueError("Phase-2 node-dispatch receipt node_id is empty")
    if node_id.startswith("ledger_commit:"):
        raise ValueError(
            "Phase-2 node-dispatch receipt cannot authorize ledger commit"
        )

    workflow = str(row.get("target_workflow") or "")
    if not workflow.endswith(".yml"):
        raise ValueError(
            "Phase-2 node-dispatch receipt target workflow is invalid"
        )
    target_ref = str(row.get("target_ref") or "")
    if not target_ref:
        raise ValueError(
            "Phase-2 node-dispatch receipt target ref is empty"
        )
    target_head = _commit_sha(
        row.get("target_head_sha"),
        label="Phase-2 node-dispatch target head",
    )
    control_run_id = int(
        row.get("node_dispatch_control_run_id") or 0
    )
    planner_run_id = int(row.get("planner_run_id") or 0)
    dispatched_run_id = int(row.get("dispatched_run_id") or 0)
    if (
        control_run_id <= 0
        or planner_run_id <= 0
        or dispatched_run_id <= 0
    ):
        raise ValueError(
            "Phase-2 node-dispatch receipt run IDs must be positive"
        )

    artifact_digest = str(
        row.get("planner_artifact_digest") or ""
    ).lower()
    if (
        not artifact_digest.startswith("sha256:")
        or len(artifact_digest) != 71
    ):
        raise ValueError(
            "Phase-2 node-dispatch planner artifact digest is invalid"
        )
    _sha256_hex(
        artifact_digest,
        label="Phase-2 node-dispatch planner artifact digest",
    )
    ledger_sha = _sha256_hex(
        row.get("canonical_coverage_ledger_sha256"),
        label="Phase-2 node-dispatch coverage ledger",
    )

    input_names = row.get("dispatch_input_names")
    if not isinstance(input_names, list):
        raise ValueError(
            "Phase-2 node-dispatch receipt input names are invalid"
        )
    normalized_names = [str(value) for value in input_names]
    if len(normalized_names) != len(set(normalized_names)):
        raise ValueError(
            "Phase-2 node-dispatch receipt repeats an input name"
        )
    inputs_sha = _sha256_hex(
        row.get("dispatch_inputs_sha256"),
        label="Phase-2 node-dispatch inputs",
    )

    if row.get("requires_explicit_approval") is not False:
        raise ValueError(
            "Phase-2 node-dispatch receipt unexpectedly required approval"
        )
    if row.get("canonical_ledger_write_authorized") is not False:
        raise ValueError(
            "Phase-2 node-dispatch receipt authorizes ledger write"
        )
    if row.get("workflow_dispatch_performed") is not True:
        raise ValueError(
            "Phase-2 node-dispatch receipt does not prove dispatch"
        )

    return {
        "version": PHASE2_NODE_DISPATCH_RECEIPT_VERSION,
        "node_id": node_id,
        "target_workflow": workflow,
        "target_ref": target_ref,
        "target_head_sha": target_head,
        "node_dispatch_control_run_id": control_run_id,
        "planner_run_id": planner_run_id,
        "planner_artifact_digest": artifact_digest,
        "canonical_coverage_ledger_sha256": ledger_sha,
        "dispatch_input_names": sorted(normalized_names),
        "dispatch_inputs_sha256": inputs_sha,
        "dispatched_run_id": dispatched_run_id,
        "requires_explicit_approval": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }
