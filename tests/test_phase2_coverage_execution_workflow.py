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



def test_phase2_execution_plan_fails_closed_on_compare_file_cap():
    text = WORKFLOW.read_text()

    assert "len(comparison_files) >= 300" in text
    assert "compare file list reached API cap" in text
    assert "rerun the dependency" in text



def test_phase2_execution_plan_publishes_dispatch_artifact_identity():
    text = WORKFLOW.read_text()

    assert "id: upload" in text
    assert "steps.upload.outputs.artifact-digest" in text
    assert "planner_run_id: ${GITHUB_RUN_ID}" in text
    assert "planner_artifact_digest: ${ARTIFACT_DIGEST}" in text
    assert "node-dispatch inputs now require this exact run ID and digest" in text



def test_phase2_execution_plan_resolves_node_dispatch_receipts():
    text = WORKFLOW.read_text()

    assert "node_dispatch_run_ids_json:" in text
    assert "NODE_DISPATCH_RUN_IDS_JSON" in text
    assert "phase2-execution-node-dispatch.yml" in text
    assert "validate_phase2_node_dispatch_receipt" in text
    assert "phase2-execution-node-dispatch.json" in text
    assert "conflicting target run IDs" in text
    assert "node_dispatch_receipts_consumed" in text



def test_phase2_execution_plan_binds_dispatch_receipt_to_control_run():
    text = WORKFLOW.read_text()

    assert '"node_dispatch_control_run_id"' in text
    assert "node-dispatch receipt/control run identity drift" in text
