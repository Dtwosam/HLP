from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-execution-node-dispatch.yml"
)


def test_node_dispatch_workflow_is_manual_and_explicit():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "confirm_dispatch:" in text
    assert "default: false" in text
    assert "confirm_dispatch=true" in text
    assert "actions: write" in text
    assert "contents: read" in text
    assert "contents: write" not in text


def test_node_dispatch_workflow_requires_exact_current_planner():
    text = WORKFLOW.read_text()

    assert "planner_run_id:" in text
    assert "expected_planner_artifact_digest:" in text
    assert "phase2-coverage-execution-plan.yml" in text
    assert "planner run was not workflow_dispatch" in text
    assert "planner run is stale; rerun planner at current branch HEAD" in text
    assert "canonical_coverage_ledger_sha256" in text
    assert "planner artifact is stale against canonical coverage ledger" in text
    assert "all_runs_current_or_ledger_only_ancestors" in text


def test_node_dispatch_workflow_reuses_planner_authorization():
    text = WORKFLOW.read_text()

    assert "build_phase2_node_dispatch_request" in text
    assert "manual_inputs_json" in text
    assert "workflow_dispatch_interface_sha256" in text
    assert "default-branch workflow_dispatch interface drift" in text
    assert "canonical_ledger_write_authorized" in text


def test_node_dispatch_workflow_captures_returned_run_id():
    text = WORKFLOW.read_text()

    assert "X-GitHub-Api-Version: 2026-03-10" in text
    assert "workflow_run_id" in text
    assert "dispatched_run_id" in text
    assert "phase2-execution-node-dispatch.json" in text
    assert "workflow_dispatch_performed" in text
