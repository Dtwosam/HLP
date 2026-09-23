from pathlib import Path


WORKFLOW = Path(
    ".github/workflows/phase2-direct-selector-approved-freeze.yml"
)


def test_approved_selector_freeze_requires_explicit_human_boolean():
    text = WORKFLOW.read_text()

    assert "workflow_dispatch:" in text
    assert "approve_freeze:" in text
    assert "default: false" in text
    assert "approve_freeze=true" in text
    assert "actions: write" in text
    assert "contents: write" not in text


def test_approved_selector_freeze_requires_exact_read_only_handoff():
    text = WORKFLOW.read_text()

    assert "approval_handoff_run_id:" in text
    assert "expected_handoff_artifact_digest:" in text
    assert "validate_phase2_selector_approval_handoff_receipt" in text
    assert "approval_handoff_control_run_id" in text
    assert "selector approval handoff artifact digest drift" in text


def test_approved_selector_freeze_dispatches_only_selector_workflow():
    text = WORKFLOW.read_text()

    assert "phase2-direct-market-selector-freeze.yml" in text
    assert '"freeze_active_quote_liquidity_causal_v1": True' in text
    assert "validate_direct_selector_freeze" in text
    assert "direct-market-selector-freeze.json" in text


def test_approved_selector_freeze_refreshes_planner_with_prior_receipts():
    text = WORKFLOW.read_text()

    assert "exactly 35 prior" in text
    assert '"shared:direct_selector_freeze"' in text
    assert "completed_node_runs_json" in text
    assert "node_dispatch_run_ids_json" in text
    assert "validate_phase2_selector_freeze_completion" in text


def test_approved_selector_freeze_never_promotes_or_mutates_ledger():
    text = WORKFLOW.read_text()

    assert '"selector_approval_performed": True' in text
    assert '"coverage_promotion_performed": False' in text
    assert '"canonical_coverage_ledger_mutated": False' in text
    assert '"canonical_ledger_write_authorized": False' in text
    assert "phase2-source-coverage-promotion.yml" not in text
