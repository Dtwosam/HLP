from pathlib import Path


WORKFLOW = Path(".github/workflows/phase2-coverage-execution-plan.yml")


def test_phase2_execution_plan_workflow_is_read_only():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "completed_node_ids_json:" in text
    assert "contents: read" in text
    assert "contents: write" not in text
    assert "git push" not in text
    assert "gh workflow run" not in text


def test_phase2_execution_plan_uses_canonical_ledger_and_planner():
    text = WORKFLOW.read_text()

    assert ".github/phase2-source-coverage.json" in text
    assert "build_phase2_coverage_execution_plan" in text
    assert "build_phase2_source_inventory" in text
    assert "phase2-coverage-execution-plan.json" in text
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
