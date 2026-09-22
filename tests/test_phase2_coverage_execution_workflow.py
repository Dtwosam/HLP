from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-coverage-execution-plan.yml")


def test_phase2_execution_plan_workflow_is_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "completed_node_runs_json:" in text
    assert "actions: read" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text
    assert "gh workflow run" not in text


def test_phase2_execution_plan_uses_canonical_ledger_and_planner():
    text = WORKFLOW.read_text()

    assert ".github/phase2-source-coverage.json" in text
    assert "build_phase2_coverage_execution_plan" in text
    assert "build_phase2_source_inventory" in text
    assert "validate_phase2_execution_run_receipts" in text
    assert "/actions/runs/{run_id}" in text
    assert "phase2-coverage-execution-plan.json" in text
    assert "phase2-execution-run-receipts.json" in text
    assert "build_phase2_dispatch_input_plan" in text
    assert "phase2-dispatch-input-plan.json" in text
    assert "ledger_promotion_serialized" in text
    assert "canonical_ledger_mutation_automatic" in text
    assert "workflow_dispatch_performed" in text


def test_phase2_execution_plan_reports_secret_and_manual_gates():
    text = WORKFLOW.read_text()

    assert "ready_requiring_archive_secret_node_ids" in text
    assert "ready_without_archive_secret_node_ids" in text
    assert "awaiting_explicit_approval_node_ids" in text
    assert "manual_ledger_commit_node_ids" in text
    assert "ledger_commit_approval_node_ids" in text
    assert "canonical_ledger_commit_workflow_available" in text
    assert "ledger_commit_requires_explicit_approval" in text
    assert "phase2-source-coverage-ledger-commit.yml" in text



def test_phase2_execution_plan_never_trusts_bare_completed_node_names():
    text = WORKFLOW.read_text()

    assert "completed_node_ids_json:" not in text
    assert "COMPLETED_NODE_IDS_JSON" not in text
    assert "completed_node_runs_json:" in text
    assert "verified_completed_runs" in text
    assert "successful workflow_dispatch run IDs" in text



def test_phase2_execution_plan_emits_real_workflow_dispatch_inputs():
    text = WORKFLOW.read_text()

    assert "workflow_text_by_name" in text
    assert "dispatchable_input_plans" in text
    assert "dispatch input plans emitted" in text



def test_phase2_execution_plan_rejects_stale_run_lineage():
    text = WORKFLOW.read_text()

    assert '["git", "rev-parse", "HEAD"]' in text
    assert "/compare/" in text
    assert "changed_paths_since_run" in text
    assert "lineage_status" in text
    assert "current_head_sha=current_head" in text
    assert "all_runs_current_or_ledger_only_ancestors" in text
    assert "canonical-ledger-only ancestor" in text



def test_phase2_execution_plan_binds_exact_canonical_ledger():
    text = WORKFLOW.read_text()

    assert "canonical_coverage_ledger_sha256" in text
    assert "ledger_sha256 = hashlib.sha256" in text
    assert 'plan["planner_head_sha"] = current_head' in text
