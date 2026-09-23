from pathlib import Path

import pytest

from hlp.data.phase2_coverage_execution import (
    build_phase2_coverage_execution_plan,
)
from hlp.data.phase2_execution_dispatch import (
    PHASE2_DISPATCH_INPUT_PLAN_VERSION,
    PHASE2_NODE_DISPATCH_ATTEMPT_VERSION,
    PHASE2_NODE_DISPATCH_RECEIPT_VERSION,
    PHASE2_NODE_DISPATCH_REQUEST_VERSION,
    RUN_ID_INPUT_BINDINGS,
    build_phase2_dispatch_input_plan,
    build_phase2_node_dispatch_request,
    validate_phase2_node_dispatch_attempt,
    validate_phase2_node_dispatch_evidence,
    validate_phase2_node_dispatch_receipt,
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



def test_promotion_binding_uses_coverage_run_and_leaves_hashes_explicit():
    completed = {
        "preflight:archive_authenticated",
        "shared:quote_registry",
        "shared:v3_initialize",
        "shared:v3_swap",
        "registry:pools_fun",
        "coverage:pools_fun",
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
    promote = by_id["promote:pools_fun"]
    run_by_node = {
        row["node_id"]: str(row["run_id"])
        for row in receipts(completed)["receipts"]
    }

    assert promote["run_id_inputs"] == {
        "coverage_run_id": run_by_node["coverage:pools_fun"],
    }
    assert {
        "coverage_artifact_name",
        "expected_artifact_digest",
        "coverage_report_path",
        "expected_report_sha256",
        "expected_source_id",
    }.issubset(set(promote["remaining_manual_inputs"]))


def test_ledger_commit_binding_uses_promotion_run():
    completed = {
        "preflight:archive_authenticated",
        "shared:quote_registry",
        "shared:v3_initialize",
        "shared:v3_swap",
        "registry:pools_fun",
        "coverage:pools_fun",
        "promote:pools_fun",
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
    commit = by_id["ledger_commit:pools_fun"]
    run_by_node = {
        row["node_id"]: str(row["run_id"])
        for row in receipts(completed)["receipts"]
    }

    assert commit["run_id_inputs"] == {
        "promotion_run_id": run_by_node["promote:pools_fun"],
    }
    assert "apply_proposed_ledger" in commit[
        "remaining_manual_inputs"
    ]



def test_node_dispatch_request_authorizes_ready_no_input_node():
    plan = build_phase2_coverage_execution_plan(
        ledger(),
        build_phase2_source_inventory(),
    )
    dispatch = build_phase2_dispatch_input_plan(
        plan,
        receipts([]),
        workflow_text_by_name=workflow_texts(plan),
    )
    request = build_phase2_node_dispatch_request(
        dispatch,
        node_id="shared:quote_registry",
        manual_inputs={},
    )

    assert request["version"] == PHASE2_NODE_DISPATCH_REQUEST_VERSION
    assert request["workflow"] == "phase2-direct-quote-registry.yml"
    assert request["inputs"] == {}
    assert request["workflow_dispatch_authorized"] is True
    assert request["canonical_ledger_write_authorized"] is False


def test_node_dispatch_request_requires_all_manual_inputs_exactly():
    completed = {
        "preflight:archive_authenticated",
        "shared:quote_registry",
        "shared:v3_initialize",
        "shared:v3_swap",
        "registry:pools_fun",
        "coverage:pools_fun",
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
    promote = next(
        row
        for row in dispatch["nodes"]
        if row["node_id"] == "promote:pools_fun"
    )

    with pytest.raises(ValueError, match="manual input mismatch"):
        build_phase2_node_dispatch_request(
            dispatch,
            node_id="promote:pools_fun",
            manual_inputs={},
        )

    manual = {
        name: "unit-value"
        for name in promote["remaining_manual_inputs"]
    }
    request = build_phase2_node_dispatch_request(
        dispatch,
        node_id="promote:pools_fun",
        manual_inputs=manual,
    )
    assert request["inputs"]["coverage_run_id"] == str(
        receipts(completed)["receipts"][
            sorted(completed).index("coverage:pools_fun")
        ]["run_id"]
    )
    assert set(request["inputs"]) == set(
        promote["all_dispatch_input_names"]
    )


def test_node_dispatch_request_rejects_approval_gated_nodes():
    dispatch = {
        "version": PHASE2_DISPATCH_INPUT_PLAN_VERSION,
        "run_id_inputs_generated_from_verified_receipts": True,
        "non_run_inputs_left_explicit": True,
        "workflow_dispatch_performed": False,
        "nodes": [
            {
                "node_id": "ledger_commit:pools_fun",
                "workflow": "phase2-source-coverage-ledger-commit.yml",
                "status": "ledger_commit_approval_required",
                "run_id_inputs": {"promotion_run_id": "123"},
                "remaining_manual_inputs": [
                    "apply_proposed_ledger",
                ],
                "all_dispatch_input_names": [
                    "promotion_run_id",
                    "apply_proposed_ledger",
                ],
                "requires_archive_secret": False,
                "requires_explicit_approval": True,
            }
        ],
    }
    with pytest.raises(ValueError, match="not ready_to_dispatch"):
        build_phase2_node_dispatch_request(
            dispatch,
            node_id="ledger_commit:pools_fun",
            manual_inputs={"apply_proposed_ledger": True},
        )



def dispatch_receipt():
    return {
        "version": PHASE2_NODE_DISPATCH_RECEIPT_VERSION,
        "node_id": "shared:quote_registry",
        "target_workflow": "phase2-direct-quote-registry.yml",
        "target_ref": "phase1/data-acquisition-spike",
        "target_head_sha": "ab" * 20,
        "node_dispatch_control_run_id": 99,
        "planner_run_id": 101,
        "planner_artifact_digest": "sha256:" + "cd" * 32,
        "canonical_coverage_ledger_sha256": "ef" * 32,
        "dispatch_input_names": [],
        "dispatch_inputs_sha256": "12" * 32,
        "dispatch_attempt_sha256": "34" * 32,
        "dispatched_run_id": 202,
        "requires_explicit_approval": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
    }


def test_node_dispatch_receipt_validates_immutable_mapping():
    row = validate_phase2_node_dispatch_receipt(dispatch_receipt())

    assert row["node_id"] == "shared:quote_registry"
    assert row["node_dispatch_control_run_id"] == 99
    assert row["dispatched_run_id"] == 202
    assert row["target_workflow"] == "phase2-direct-quote-registry.yml"
    assert row["dispatch_attempt_sha256"] == "34" * 32
    assert row["canonical_ledger_write_authorized"] is False


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("version", "other", "version changed"),
        ("node_id", "ledger_commit:pools_fun", "ledger commit"),
        ("dispatched_run_id", 0, "run IDs must be positive"),
        (
            "canonical_ledger_write_authorized",
            True,
            "authorizes ledger write",
        ),
        (
            "workflow_dispatch_performed",
            False,
            "does not prove dispatch",
        ),
    ],
)
def test_node_dispatch_receipt_rejects_tampering(field, value, match):
    row = dispatch_receipt()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        validate_phase2_node_dispatch_receipt(row)



def dispatch_attempt():
    return {
        "version": PHASE2_NODE_DISPATCH_ATTEMPT_VERSION,
        "node_id": "shared:quote_registry",
        "target_workflow": "phase2-direct-quote-registry.yml",
        "target_ref": "phase1/data-acquisition-spike",
        "target_head_sha": "ab" * 20,
        "node_dispatch_control_run_id": 98,
        "planner_run_id": 101,
        "planner_artifact_digest": "sha256:" + "cd" * 32,
        "canonical_coverage_ledger_sha256": "ef" * 32,
        "dispatch_input_names": [],
        "dispatch_inputs_sha256": "12" * 32,
        "dispatched_run_id": 202,
        "requires_explicit_approval": False,
        "canonical_ledger_write_authorized": False,
        "workflow_dispatch_performed": True,
        "target_run_identity_verified": False,
    }


def test_node_dispatch_attempt_proves_target_creation_before_verification():
    row = validate_phase2_node_dispatch_attempt(dispatch_attempt())

    assert row["node_id"] == "shared:quote_registry"
    assert row["node_dispatch_control_run_id"] == 98
    assert row["dispatched_run_id"] == 202
    assert row["workflow_dispatch_performed"] is True
    assert row["target_run_identity_verified"] is False


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("version", "other", "version changed"),
        ("dispatched_run_id", 0, "run IDs must be positive"),
        (
            "canonical_ledger_write_authorized",
            True,
            "authorizes ledger write",
        ),
        (
            "workflow_dispatch_performed",
            False,
            "does not prove dispatch",
        ),
        (
            "target_run_identity_verified",
            True,
            "must precede target verification",
        ),
    ],
)
def test_node_dispatch_attempt_rejects_tampering(field, value, match):
    row = dispatch_attempt()
    row[field] = value
    with pytest.raises(ValueError, match=match):
        validate_phase2_node_dispatch_attempt(row)



def matching_dispatch_evidence():
    attempt = dispatch_attempt()
    receipt = dispatch_receipt()
    attempt["node_dispatch_control_run_id"] = 99
    attempt_sha = receipt["dispatch_attempt_sha256"]
    return attempt, receipt, attempt_sha


def test_node_dispatch_evidence_reconciles_attempt_and_final_receipt():
    attempt, receipt, attempt_sha = matching_dispatch_evidence()
    evidence = validate_phase2_node_dispatch_evidence(
        attempt,
        receipt,
        attempt_file_sha256=attempt_sha,
    )

    assert evidence["node_id"] == "shared:quote_registry"
    assert evidence["dispatch_attempt_sha256"] == attempt_sha
    assert evidence["attempt_target_run_identity_verified"] is False
    assert evidence["final_target_run_identity_verified"] is True
    assert evidence["canonical_ledger_write_authorized"] is False


def test_node_dispatch_evidence_rejects_attempt_file_sha_drift():
    attempt, receipt, _ = matching_dispatch_evidence()
    with pytest.raises(ValueError, match="exact attempt file bytes"):
        validate_phase2_node_dispatch_evidence(
            attempt,
            receipt,
            attempt_file_sha256="56" * 32,
        )


def test_node_dispatch_evidence_rejects_attempt_receipt_identity_drift():
    attempt, receipt, attempt_sha = matching_dispatch_evidence()
    attempt["dispatched_run_id"] = 999
    with pytest.raises(ValueError, match="identity drift"):
        validate_phase2_node_dispatch_evidence(
            attempt,
            receipt,
            attempt_file_sha256=attempt_sha,
        )
